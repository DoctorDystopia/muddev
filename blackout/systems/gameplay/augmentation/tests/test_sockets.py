"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The rig (DESIGN-0015, Phase 5): the sockets, the `socket`,
             `unsocket`, and `rig` commands, and the rig pop-up. The rail
             shows the socketed augments only, and an unsocket puts a lit
             augment out.
Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.augmentation
"""

import json
import unittest
from unittest import mock

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaCommandTest

from commands.augment_cmds import CmdAug, CmdRig, CmdSocket, CmdUnsocket
from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import detail
from systems.gameplay.augmentation import pool
from systems.gameplay.augmentation import sockets
from systems.gameplay.augmentation.handler import (
    ensure_augment_handler,
    get_augment_handler_for,
)
from systems.gameplay.augmentation.registry import AUGMENT_REGISTRY, augments_in_order
from systems.gameplay.augmentation.tests import support
from systems.gameplay.progression.skills.constants import SKILL_KEY_AUGMENTATION
from systems.interface.popups.popup_defs.rig import (
    AUGMENTS_GRID_KEY,
    RIG_POPUP_KEY,
    SOCKETS_GRID_KEY,
    RigPopup,
)
from systems.interface.popups.registry import get_popup
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.mixins import CombatEntity


def _first_augment():
    return augments_in_order()[0]


def _a_locked_socket_for(character) -> str:
    """A socket that the level of the character keeps closed, or ""."""
    opened = set(sockets.open_sockets(character))

    for key in aug_const.SOCKETS:
        if key not in opened:
            return key

    return ""


class TestSocketTable(unittest.TestCase):
    """The socket table and the augments agree. No DB."""

    def test_every_socket_has_a_label_and_an_unlock_level(self):
        for key in aug_const.SOCKETS:
            with self.subTest(socket=key):
                self.assertIn(key, aug_const.SOCKET_NAMES)
                self.assertIn(key, aug_const.SOCKET_UNLOCK_LEVELS)

    def test_the_unlock_table_names_sockets_only(self):
        self.assertEqual(set(aug_const.SOCKET_UNLOCK_LEVELS), set(aug_const.SOCKETS))

    def test_a_socket_is_open_at_level_zero(self):
        opened = [key for key, level in aug_const.SOCKET_UNLOCK_LEVELS.items()
                  if level <= aug_const.NO_UNLOCK_LEVEL]

        self.assertTrue(opened, "no socket opens at level 0")

    def test_every_augment_fits_a_real_socket(self):
        for augment in AUGMENT_REGISTRY.values():
            with self.subTest(augment=augment.key):
                self.assertTrue(augment.sockets, "an augment with no socket never reaches the rail")

                for key in augment.sockets:
                    self.assertIn(key, aug_const.SOCKETS)

    def test_find_socket_reads_the_key_the_label_and_a_prefix(self):
        key = aug_const.SOCKETS[0]
        label = aug_const.SOCKET_NAMES[key]

        self.assertEqual(key, sockets.find_socket(key))
        self.assertEqual(key, sockets.find_socket(label.lower()))
        self.assertEqual(key, sockets.find_socket(label[:3]))
        self.assertEqual("", sockets.find_socket("no such socket"))


class _Rig:

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        support.open_every_socket(self.char1)
        pool.restore(self.char1)
        self.augment = _first_augment()
        self.socket_key = self.augment.sockets[0]

    def tearDown(self):
        handler = get_augment_handler_for(self.char1)

        if handler is not None:
            handler.stop_handler()

        super().tearDown()


class TestSockets(_Rig, EvenniaCommandTest):
    """sockets.place and sockets.remove, the one writer of the rig."""

    def test_the_level_opens_the_sockets(self):
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, aug_const.NO_UNLOCK_LEVEL)
        at_zero = sockets.open_sockets(self.char1)
        expected = [key for key in aug_const.SOCKETS
                    if aug_const.SOCKET_UNLOCK_LEVELS[key] <= aug_const.NO_UNLOCK_LEVEL]

        self.assertEqual(expected, at_zero)

        support.open_every_socket(self.char1)

        self.assertEqual(list(aug_const.SOCKETS), sockets.open_sockets(self.char1))

    def test_place_puts_the_augment_in_the_socket(self):
        done, message = sockets.place(self.char1, self.augment, self.socket_key)

        self.assertTrue(done, message)
        self.assertEqual(self.socket_key, sockets.socket_of(self.char1, self.augment.key))
        self.assertTrue(sockets.is_socketed(self.char1, self.augment.key))
        self.assertEqual([self.augment], sockets.socketed_augments(self.char1))

    def test_place_refuses_a_socket_the_augment_does_not_fit(self):
        wrong = [key for key in aug_const.SOCKETS if key not in self.augment.sockets]

        if not wrong:
            self.skipTest("the augment fits every socket")

        done, message = sockets.place(self.char1, self.augment, wrong[0])

        self.assertFalse(done)
        self.assertIn("fit", message.lower())
        self.assertEqual({}, sockets.assignments(self.char1))

    def test_place_refuses_a_closed_socket(self):
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, aug_const.NO_UNLOCK_LEVEL)
        closed = _a_locked_socket_for(self.char1)

        if not closed:
            self.skipTest("every socket is open at level 0")

        fitting = [augment for augment in AUGMENT_REGISTRY.values()
                   if closed in augment.sockets]

        if not fitting:
            self.skipTest("nothing fits the closed socket")

        done, message = sockets.place(self.char1, fitting[0], closed)

        self.assertFalse(done)
        self.assertIn("opens at", message.lower())

    def test_place_refuses_a_socket_another_augment_holds(self):
        others = [augment for augment in augments_in_order()
                  if augment is not self.augment and self.socket_key in augment.sockets]

        if not others:
            self.skipTest("no second augment fits the socket")

        sockets.place(self.char1, self.augment, self.socket_key)

        done, message = sockets.place(self.char1, others[0], self.socket_key)

        self.assertFalse(done)
        self.assertIn("holds", message.lower())
        self.assertEqual(self.augment.key, sockets.assignments(self.char1)[self.socket_key])

    def test_place_moves_an_augment_between_sockets(self):
        if len(self.augment.sockets) < 2:
            self.skipTest("the augment fits one socket")

        first, second = self.augment.sockets[0], self.augment.sockets[1]
        sockets.place(self.char1, self.augment, first)

        done, _message = sockets.place(self.char1, self.augment, second)

        self.assertTrue(done)
        self.assertEqual({second: self.augment.key}, sockets.assignments(self.char1))

    def test_place_says_so_when_the_augment_already_sits_there(self):
        sockets.place(self.char1, self.augment, self.socket_key)

        done, message = sockets.place(self.char1, self.augment, self.socket_key)

        self.assertFalse(done)
        self.assertIn("already", message.lower())

    def test_place_and_remove_refuse_a_fight(self):
        with mock.patch.object(CombatEntity, "in_combat", new_callable=mock.PropertyMock,
                               return_value=True):
            done, message = sockets.place(self.char1, self.augment, self.socket_key)
            self.assertFalse(done)
            self.assertIn("fight", message.lower())

            removed, message = sockets.remove(self.char1, self.socket_key)
            self.assertFalse(removed)
            self.assertIn("fight", message.lower())

    def test_remove_empties_the_socket(self):
        sockets.place(self.char1, self.augment, self.socket_key)

        done, message = sockets.remove(self.char1, self.socket_key)

        self.assertTrue(done, message)
        self.assertEqual({}, sockets.assignments(self.char1))

    def test_remove_says_so_for_an_empty_socket(self):
        done, message = sockets.remove(self.char1, self.socket_key)

        self.assertFalse(done)
        self.assertIn("nothing", message.lower())

    def test_remove_puts_a_lit_augment_out(self):
        sockets.place(self.char1, self.augment, self.socket_key)
        ensure_augment_handler(self.char1).light(self.augment, aug_const.AUG_STEP_DEFAULT)

        sockets.remove(self.char1, self.socket_key)

        self.assertIsNone(get_augment_handler_for(self.char1))

    def test_a_write_marks_the_rail_stale(self):
        with mock.patch("systems.interface.statefeed.events.refresh_abilities") as marked:
            sockets.place(self.char1, self.augment, self.socket_key)

        marked.assert_called_with(self.char1)

    def test_a_closed_socket_hides_its_augment_and_keeps_it(self):
        sockets.place(self.char1, self.augment, self.socket_key)
        needed = aug_const.SOCKET_UNLOCK_LEVELS[self.socket_key]

        if needed <= aug_const.NO_UNLOCK_LEVEL:
            self.skipTest("the socket is open at every level")

        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, needed - 1)

        self.assertFalse(sockets.is_socketed(self.char1, self.augment.key))

        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, needed)

        self.assertTrue(sockets.is_socketed(self.char1, self.augment.key))


class TestSocketCommands(_Rig, EvenniaCommandTest):

    def test_socket_places_by_name_and_label(self):
        label = aug_const.SOCKET_NAMES[self.socket_key]

        response = self.call(CmdSocket(), f" {self.augment.name} {label}", caller=self.char1)

        self.assertIn("sits in", response.lower())
        self.assertEqual(self.socket_key, sockets.socket_of(self.char1, self.augment.key))

    def test_socket_with_no_argument_gives_the_usage(self):
        response = self.call(CmdSocket(), "", caller=self.char1)

        self.assertIn("usage", response.lower())

    def test_socket_with_an_unknown_augment_is_refused(self):
        label = aug_const.SOCKET_NAMES[self.socket_key]

        response = self.call(CmdSocket(), f" no such thing {label}", caller=self.char1)

        self.assertIn("know no augment", response.lower())

    def test_unsocket_empties_the_socket(self):
        sockets.place(self.char1, self.augment, self.socket_key)
        label = aug_const.SOCKET_NAMES[self.socket_key]

        response = self.call(CmdUnsocket(), f" {label}", caller=self.char1)

        self.assertIn("take", response.lower())
        self.assertEqual({}, sockets.assignments(self.char1))

    def test_unsocket_with_an_unknown_socket_is_refused(self):
        response = self.call(CmdUnsocket(), " elbow", caller=self.char1)

        self.assertIn("no socket", response.lower())

    def test_aug_lights_a_socketed_augment_and_refuses_the_rest(self):
        response = self.call(CmdAug(), f" {self.augment.name}", caller=self.char1)
        self.assertIn("rig", response.lower())

        sockets.place(self.char1, self.augment, self.socket_key)

        response = self.call(CmdAug(), f" {self.augment.name}", caller=self.char1)
        self.assertIn("online", response.lower())

    def test_rig_prints_every_socket_and_every_augment(self):
        sockets.place(self.char1, self.augment, self.socket_key)

        response = strip_ansi(self.call(CmdRig(), "", caller=self.char1))

        for key in aug_const.SOCKETS:
            with self.subTest(socket=key):
                self.assertIn(aug_const.SOCKET_NAMES[key], response)

        for augment in augments_in_order():
            with self.subTest(augment=augment.key):
                self.assertIn(augment.name, response)


class TestRigPopup(_Rig, EvenniaCommandTest):
    """The pop-up describes the rig, and each cell carries a whole command."""

    def _grids(self) -> dict:
        grids = RigPopup().grids(self.char1, self.char1, None)

        return {entry["key"]: entry for entry in grids}

    def test_the_registry_finds_the_rig_popup(self):
        self.assertIsInstance(get_popup(RIG_POPUP_KEY), RigPopup)

    def test_the_anchor_is_the_character(self):
        popup = RigPopup()

        self.assertTrue(popup.anchor_is_usable(self.char1, self.char1))
        self.assertFalse(popup.anchor_is_usable(self.char1, self.char2))
        self.assertFalse(popup.room_bound)

    def test_one_cell_for_each_socket_and_each_augment(self):
        grids = self._grids()

        self.assertEqual(len(aug_const.SOCKETS), len(grids[SOCKETS_GRID_KEY]["items"]))
        self.assertEqual(len(augments_in_order()), len(grids[AUGMENTS_GRID_KEY]["items"]))
        json.dumps(grids)

    def test_a_filled_socket_carries_the_unsocket_line(self):
        sockets.place(self.char1, self.augment, self.socket_key)
        slot = aug_const.SOCKETS.index(self.socket_key)

        cell = self._grids()[SOCKETS_GRID_KEY]["items"][slot]

        self.assertEqual(self.augment.name, cell["name"])
        self.assertEqual(
            [aug_const.UNSOCKET_TEMPLATE.format(socket=self.socket_key)],
            [action["command"] for action in cell["actions"]])

    def test_an_augment_cell_offers_each_open_empty_socket_it_fits(self):
        cells = {cell["name"]: cell for cell in self._grids()[AUGMENTS_GRID_KEY]["items"]}
        cell = cells[self.augment.name]
        expected = [aug_const.SOCKET_TEMPLATE.format(name=self.augment.name, socket=key)
                    for key in self.augment.sockets]

        self.assertEqual(expected, [action["command"] for action in cell["actions"]])

    def test_a_closed_socket_is_dim(self):
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, aug_const.NO_UNLOCK_LEVEL)
        closed = _a_locked_socket_for(self.char1)

        if not closed:
            self.skipTest("every socket is open at level 0")

        cell = self._grids()[SOCKETS_GRID_KEY]["items"][aug_const.SOCKETS.index(closed)]

        self.assertFalse(cell["enabled"])
        self.assertEqual([], cell["actions"])

    def test_the_status_counts_the_open_sockets(self):
        status = RigPopup().status(self.char1, self.char1)

        self.assertIn(str(len(sockets.open_sockets(self.char1))), status)

    def test_the_rows_of_the_rail_are_the_socketed_augments(self):
        sockets.place(self.char1, self.augment, self.socket_key)

        keys = [row["key"] for row in detail.ability_rows(self.char1)
                if row["kind"] != aug_const.AUG_SET_ROW_KEY]

        self.assertEqual([self.augment.key, aug_const.AUG_SET_ROW_KEY], keys)
