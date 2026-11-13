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
from systems.interface.popups import constants as popup_const
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


def _swap_pair():
    """(mover, held, origin, target): two augments that both fit two
    sockets, and the two sockets. None when no two augments share two."""
    for mover in augments_in_order():
        for held in augments_in_order():
            shared = [key for key in mover.sockets if key in held.sockets]

            if held is not mover and len(shared) > 1:
                return mover, held, shared[0], shared[1]

    return None


def _one_way_pair():
    """(mover, held, origin, target): the mover fits the origin and the
    target, and the held augment fits the target only. None for no pair."""
    for mover in augments_in_order():
        for held in augments_in_order():
            for target in mover.sockets:
                origins = [key for key in mover.sockets
                           if key != target and key not in held.sockets]

                if held is not mover and target in held.sockets and origins:
                    return mover, held, origins[0], target

    return None


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

    def test_swap_trades_two_augments_that_fit_both_sockets(self):
        pair = _swap_pair()

        if pair is None:
            self.skipTest("no two augments share two sockets")

        mover, held, origin, target = pair
        sockets.place(self.char1, mover, origin)
        sockets.place(self.char1, held, target)

        done, message = sockets.place(self.char1, mover, target, swap=True)

        self.assertTrue(done, message)
        self.assertEqual({target: mover.key, origin: held.key}, sockets.assignments(self.char1))
        self.assertIn("moves", message.lower())

    def test_swap_puts_out_a_held_augment_that_cannot_move(self):
        pair = _one_way_pair()

        if pair is None:
            self.skipTest("no held augment misses the socket of the mover")

        mover, held, origin, target = pair
        sockets.place(self.char1, mover, origin)
        sockets.place(self.char1, held, target)
        ensure_augment_handler(self.char1).light(held, aug_const.AUG_POWER_LEVEL_DEFAULT)

        done, message = sockets.place(self.char1, mover, target, swap=True)

        self.assertTrue(done, message)
        self.assertEqual({target: mover.key}, sockets.assignments(self.char1))
        self.assertIn("leaves", message.lower())
        self.assertIsNone(get_augment_handler_for(self.char1))

    def test_swap_from_the_catalogue_takes_the_held_augment_out(self):
        pair = _swap_pair()

        if pair is None:
            self.skipTest("no two augments share a socket")

        mover, held, _origin, target = pair
        sockets.place(self.char1, held, target)

        done, message = sockets.place(self.char1, mover, target, swap=True)

        self.assertTrue(done, message)
        self.assertEqual({target: mover.key}, sockets.assignments(self.char1))

    def test_swap_into_an_empty_socket_is_a_plain_place(self):
        done, message = sockets.place(self.char1, self.augment, self.socket_key, swap=True)

        self.assertTrue(done, message)
        self.assertEqual({self.socket_key: self.augment.key}, sockets.assignments(self.char1))

    def test_swap_still_refuses_a_socket_the_augment_does_not_fit(self):
        wrong = [key for key in aug_const.SOCKETS if key not in self.augment.sockets]

        if not wrong:
            self.skipTest("the augment fits every socket")

        done, _message = sockets.place(self.char1, self.augment, wrong[0], swap=True)

        self.assertFalse(done)
        self.assertEqual({}, sockets.assignments(self.char1))

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
        ensure_augment_handler(self.char1).light(self.augment, aug_const.AUG_POWER_LEVEL_DEFAULT)

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

    def test_the_swap_switch_reaches_the_command_through_the_parser(self):
        pair = _swap_pair()

        if pair is None:
            self.skipTest("no two augments share a socket")

        mover, held, _origin, target = pair
        sockets.place(self.char1, held, target)

        self.char1.execute_cmd(
            aug_const.SOCKET_SWAP_TEMPLATE.format(name=mover.name, socket=target))

        self.assertEqual(mover.key, sockets.assignments(self.char1)[target])

    def test_an_unknown_switch_gives_the_usage_and_changes_nothing(self):
        response = self.call(CmdSocket(), f"/moon {self.augment.name} {self.socket_key}",
                             caller=self.char1)

        self.assertIn("usage", response.lower())
        self.assertEqual({}, sockets.assignments(self.char1))

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

    def test_the_sockets_grid_names_the_rig_layout(self):
        grids = self._grids()

        self.assertEqual(
            popup_const.POPUP_LAYOUT_RIG,
            grids[SOCKETS_GRID_KEY].get(popup_const.GRID_LAYOUT_FIELD))
        self.assertNotIn(popup_const.GRID_LAYOUT_FIELD, grids[AUGMENTS_GRID_KEY])

    def test_each_socket_cell_names_its_socket_as_its_place(self):
        cells = self._grids()[SOCKETS_GRID_KEY]["items"]

        for slot, socket_key in enumerate(aug_const.SOCKETS):
            with self.subTest(socket=socket_key):
                self.assertEqual(socket_key, cells[slot][popup_const.ROW_PLACE_FIELD])

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

    def test_a_locked_augment_names_its_level_in_the_short_form(self):
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, aug_const.NO_UNLOCK_LEVEL)
        cells = {cell["name"]: cell for cell in self._grids()[AUGMENTS_GRID_KEY]["items"]}
        locked = [augment for augment in augments_in_order()
                  if augment.unlock_level > aug_const.NO_UNLOCK_LEVEL]

        if not locked:
            self.skipTest("every augment is open at level 0")

        for augment in locked:
            with self.subTest(augment=augment.key):
                expected = aug_const.RIG_LOCKED_DETAIL.format(level=augment.unlock_level)
                self.assertEqual(expected, cells[augment.name]["detail"])

    def test_the_status_counts_the_open_sockets(self):
        status = RigPopup().status(self.char1, self.char1)

        self.assertIn(str(len(sockets.open_sockets(self.char1))), status)

    def test_the_rows_of_the_rail_are_the_socketed_augments(self):
        sockets.place(self.char1, self.augment, self.socket_key)

        keys = [row["key"] for row in detail.ability_rows(self.char1)
                if row["kind"] != aug_const.AUG_SET_ROW_KEY]

        self.assertEqual([self.augment.key, aug_const.AUG_SET_ROW_KEY], keys)


class TestRigDrag(_Rig, EvenniaCommandTest):
    """The drag of the rig pop-up (11/09/2026). Each drop runs through the
    real parser, as the client sends it. A drop that the parser refuses is
    a drag that does nothing."""

    def _grids(self) -> dict:
        grids = RigPopup().grids(self.char1, self.char1, None)

        return {entry["key"]: entry for entry in grids}

    def _socket_cell(self, socket_key: str) -> dict:
        cells = self._grids()[SOCKETS_GRID_KEY]["items"]

        return cells[aug_const.SOCKETS.index(socket_key)]

    def _augment_cell(self, augment) -> dict:
        cells = self._grids()[AUGMENTS_GRID_KEY]["items"]

        return cells[augments_in_order().index(augment)]

    def _drop(self, source: dict, target: dict) -> None:
        """Drop one cell on another, as the client does: look up the drag
        key of the source in the drop table of the target, and send."""
        drag_key = source[popup_const.ROW_DRAG_KEY_FIELD]

        self.char1.execute_cmd(target[popup_const.ROW_DROPS_FIELD][drag_key])

    def test_a_socket_takes_the_drop_of_each_augment_that_fits_it(self):
        for socket_key in aug_const.SOCKETS:
            drops = self._socket_cell(socket_key)[popup_const.ROW_DROPS_FIELD]

            for augment in augments_in_order():
                with self.subTest(socket=socket_key, augment=augment.key):
                    drag_key = self._augment_cell(augment)[popup_const.ROW_DRAG_KEY_FIELD]
                    self.assertEqual(socket_key in augment.sockets, drag_key in drops)

    def test_a_drop_of_an_augment_on_a_socket_puts_it_there(self):
        self._drop(self._augment_cell(self.augment), self._socket_cell(self.socket_key))

        self.assertEqual(self.socket_key, sockets.socket_of(self.char1, self.augment.key))

    def test_a_drop_of_a_socket_on_a_full_socket_swaps_the_two(self):
        pair = _swap_pair()

        if pair is None:
            self.skipTest("no two augments share two sockets")

        mover, held, origin, target = pair
        sockets.place(self.char1, mover, origin)
        sockets.place(self.char1, held, target)

        self._drop(self._socket_cell(origin), self._socket_cell(target))

        self.assertEqual({target: mover.key, origin: held.key}, sockets.assignments(self.char1))

    def test_a_filled_socket_drops_out_on_any_augment_cell(self):
        sockets.place(self.char1, self.augment, self.socket_key)
        source = self._socket_cell(self.socket_key)
        drag_key = source[popup_const.ROW_DRAG_KEY_FIELD]

        for augment in augments_in_order():
            with self.subTest(augment=augment.key):
                drops = self._augment_cell(augment)[popup_const.ROW_DROPS_FIELD]
                self.assertIn(drag_key, drops)

        self._drop(source, self._augment_cell(augments_in_order()[-1]))

        self.assertEqual({}, sockets.assignments(self.char1))

    def test_an_augment_cell_takes_no_drop_from_another_augment_cell(self):
        cells = self._grids()[AUGMENTS_GRID_KEY]["items"]
        drag_keys = {cell[popup_const.ROW_DRAG_KEY_FIELD] for cell in cells}

        for cell in cells:
            with self.subTest(augment=cell["name"]):
                self.assertFalse(drag_keys & set(cell[popup_const.ROW_DROPS_FIELD]))

    def test_a_socket_takes_no_drop_of_the_augment_it_holds(self):
        sockets.place(self.char1, self.augment, self.socket_key)
        target = self._socket_cell(self.socket_key)
        drops = target[popup_const.ROW_DROPS_FIELD]

        self.assertNotIn(target[popup_const.ROW_DRAG_KEY_FIELD], drops)
        self.assertNotIn(self._augment_cell(self.augment)[popup_const.ROW_DRAG_KEY_FIELD], drops)

    def test_a_closed_socket_takes_no_drop_and_an_empty_one_does_not_drag(self):
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, aug_const.NO_UNLOCK_LEVEL)
        closed = _a_locked_socket_for(self.char1)

        if not closed:
            self.skipTest("every socket is open at level 0")

        empty = sockets.open_sockets(self.char1)[0]

        self.assertNotIn(popup_const.ROW_DROPS_FIELD, self._socket_cell(closed))
        self.assertIn(popup_const.ROW_DROPS_FIELD, self._socket_cell(empty))
        self.assertNotIn(popup_const.ROW_DRAG_KEY_FIELD, self._socket_cell(empty))

    def test_every_drag_key_names_one_cell(self):
        sockets.place(self.char1, self.augment, self.socket_key)
        grids = self._grids()
        cells = grids[SOCKETS_GRID_KEY]["items"] + grids[AUGMENTS_GRID_KEY]["items"]
        drag_keys = [cell[popup_const.ROW_DRAG_KEY_FIELD] for cell in cells
                     if popup_const.ROW_DRAG_KEY_FIELD in cell]

        self.assertEqual(len(drag_keys), len(set(drag_keys)))
        self.assertEqual(len(augments_in_order()) + 1, len(drag_keys))
