"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The augment rows of the ability rail and the set row
             (DESIGN-0015, Phase 3). Also the glow on the figure, and the
             rail that follows its facts. The shape of
             statefeed/tests/test_abilities_feed.py, one system over.
Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.augmentation
"""

import json
from unittest import mock

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaCommandTest, EvenniaTest

from commands.augment_cmds import CmdAug
from systems.gameplay import abilities as composer
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
from systems.gameplay.combat.auras.registry import AURA_REGISTRY
from systems.gameplay.progression.skills.constants import SKILL_KEY_AUGMENTATION
from systems.interface.statefeed import abilities as abilities_feed
from systems.interface.statefeed import buffer
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed
from systems.interface.statefeed import serializers
from systems.interface.statefeed import subscriptions
from typeclasses.characters import Character as BlackoutCharacter


_LEVEL_PAST_EVERY_UNLOCK: int = max(
    [augment.unlock_level for augment in AUGMENT_REGISTRY.values()]
    + [aug_const.NO_UNLOCK_LEVEL]
) + 1

_STATES: frozenset = frozenset((
    feed_const.ABILITY_STATE_READY,
    feed_const.ABILITY_STATE_ACTIVE,
    feed_const.ABILITY_STATE_LOCKED,
))


def _first_augment():
    return augments_in_order()[0]


class _Fixture:

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, _LEVEL_PAST_EVERY_UNLOCK)
        pool.restore(self.char1)
        # The rail shows the socketed augments only (Phase 5). The first
        # augment of the order always finds a socket: the head is open at
        # level 0, and the test fixture depends on that row.
        self.rig = support.socket_fitting(self.char1, augments_in_order())
        self.assertIn(_first_augment(), self.rig)

    def tearDown(self):
        handler = get_augment_handler_for(self.char1)

        if handler is not None:
            handler.stop_handler()

        super().tearDown()

    def _rows(self) -> list:
        return detail.ability_rows(self.char1)

    def _row(self, key: str) -> dict:
        for row in self._rows():
            if row["key"] == key:
                return row

        self.fail("no row for %s" % key)

    def _set_row(self) -> dict:
        return self._row(aug_const.AUG_SET_ROW_KEY)

    def _light(self, augment, power_level: int = aug_const.AUG_POWER_LEVEL_DEFAULT) -> None:
        ensure_augment_handler(self.char1).light(augment, power_level)


class TestRows(_Fixture, EvenniaTest):
    """The rows, measured against the registry."""

    def test_one_row_for_each_socketed_augment_then_the_set_row(self):
        keys = [row["key"] for row in self._rows()]
        expected = [augment.key for augment in sockets.socketed_augments(self.char1)]
        expected.append(aug_const.AUG_SET_ROW_KEY)

        self.assertEqual(expected, keys)
        self.assertTrue(len(expected) > 1, "the fixture socketed nothing")

    def test_an_augment_outside_the_rig_has_no_row(self):
        outside = [augment for augment in augments_in_order()
                   if augment not in self.rig]

        if not outside:
            self.skipTest("every augment found a socket")

        keys = [row["key"] for row in self._rows()]

        self.assertNotIn(outside[0].key, keys)

    def test_every_augment_row_has_its_fields(self):
        for row in self._rows():
            if row["kind"] != feed_const.ABILITY_KIND_TOGGLE:
                continue

            with self.subTest(ability=row["key"]):
                augment = AUGMENT_REGISTRY[row["key"]]
                self.assertEqual(augment.name, row["name"])
                self.assertIn(row["state"], _STATES)
                self.assertEqual(aug_const.AUG_POWER_LEVELS,
                                 row[feed_const.ABILITY_POWER_LEVELS_KEY])
                tip = row[feed_const.TIP_KEY]
                self.assertEqual(augment.name, tip[feed_const.TIP_TITLE_KEY])
                self.assertIn(augment.description, tip[feed_const.TIP_LINES_KEY])

    def test_the_rows_survive_json(self):
        json.dumps(self._rows())

    def test_a_ready_row_names_the_light_and_no_power_level(self):
        for row in self._rows():
            if row["kind"] != feed_const.ABILITY_KIND_TOGGLE:
                continue

            with self.subTest(ability=row["key"]):
                augment = AUGMENT_REGISTRY[row["key"]]
                self.assertEqual(feed_const.ABILITY_STATE_READY, row["state"])
                self.assertEqual(
                    aug_const.AUG_IGNITE_TEMPLATE.format(name=augment.name), row["command"])
                self.assertEqual(0, row[feed_const.ABILITY_POWER_LEVEL_KEY])
                self.assertEqual("", row[feed_const.ABILITY_POWER_LEVEL_COMMAND_KEY])

    def test_a_lit_row_carries_its_power_level_and_the_next_power_level(self):
        augment = _first_augment()
        self._light(augment, aug_const.AUG_POWER_LEVEL_MIN)

        row = self._row(augment.key)

        self.assertEqual(feed_const.ABILITY_STATE_ACTIVE, row["state"])
        self.assertEqual(
            aug_const.AUG_EXTINGUISH_TEMPLATE.format(name=augment.name), row["command"])
        self.assertEqual(aug_const.AUG_POWER_LEVEL_MIN, row[feed_const.ABILITY_POWER_LEVEL_KEY])
        self.assertEqual(
            aug_const.AUG_IGNITE_POWER_LEVEL_TEMPLATE.format(
                name=augment.name, power_level=aug_const.AUG_POWER_LEVEL_MIN + 1),
            row[feed_const.ABILITY_POWER_LEVEL_COMMAND_KEY])

    def test_a_ready_row_names_a_line_for_each_power_level(self):
        augment = _first_augment()
        expected = [
            aug_const.AUG_IGNITE_POWER_LEVEL_TEMPLATE.format(
                name=augment.name, power_level=power_level)
            for power_level in range(aug_const.AUG_POWER_LEVEL_MIN,
                                     aug_const.AUG_POWER_LEVELS + 1)
        ]

        row = self._row(augment.key)

        self.assertEqual(expected, row[feed_const.ABILITY_POWER_LEVEL_COMMANDS_KEY])

    def test_a_lit_row_names_no_line_for_its_own_power_level(self):
        augment = _first_augment()
        self._light(augment, aug_const.AUG_POWER_LEVEL_MIN)

        lines = self._row(augment.key)[feed_const.ABILITY_POWER_LEVEL_COMMANDS_KEY]

        self.assertEqual(aug_const.AUG_POWER_LEVELS, len(lines))
        self.assertEqual("", lines[0])
        self.assertTrue(all(lines[1:]), lines)

    def test_the_top_power_level_wraps_to_the_first(self):
        augment = _first_augment()
        self._light(augment, aug_const.AUG_POWER_LEVELS)

        row = self._row(augment.key)

        self.assertEqual(
            aug_const.AUG_IGNITE_POWER_LEVEL_TEMPLATE.format(
                name=augment.name, power_level=aug_const.AUG_POWER_LEVEL_MIN),
            row[feed_const.ABILITY_POWER_LEVEL_COMMAND_KEY])

    def test_a_level_under_the_unlock_locks_the_row(self):
        # The row needs a socket that stays open under the unlock level, or
        # the level cut hides the row with the lock.
        gated = [augment for augment in augments_in_order()
                 if augment.unlock_level > aug_const.NO_UNLOCK_LEVEL
                 and any(sockets.unlock_level(key) < augment.unlock_level
                         for key in augment.sockets)]

        if not gated:
            self.skipTest("no gated augment fits a socket under its unlock")

        augment = gated[0]
        socket_key = [key for key in augment.sockets
                      if sockets.unlock_level(key) < augment.unlock_level][0]
        sockets.remove(self.char1, socket_key)
        sockets.remove(self.char1, sockets.socket_of(self.char1, augment.key) or socket_key)
        placed, message = sockets.place(self.char1, augment, socket_key)
        self.assertTrue(placed, message)
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, augment.unlock_level - 1)

        row = self._row(augment.key)

        self.assertEqual(feed_const.ABILITY_STATE_LOCKED, row["state"])
        self.assertEqual("", row["command"])
        self.assertIn(str(augment.unlock_level), row["reason"])
        self.assertEqual([""] * aug_const.AUG_POWER_LEVELS,
                         row[feed_const.ABILITY_POWER_LEVEL_COMMANDS_KEY])

    def test_the_set_row_lights_the_set_when_nothing_burns(self):
        row = self._set_row()

        self.assertEqual(feed_const.ABILITY_KIND_SET, row["kind"])
        self.assertEqual(feed_const.ABILITY_STATE_READY, row["state"])
        self.assertEqual(aug_const.AUG_SET_COMMAND, row["command"])
        self.assertNotIn(feed_const.ABILITY_POWER_LEVEL_KEY, row)

    def test_the_set_row_puts_all_out_when_anything_burns(self):
        self._light(_first_augment())

        row = self._set_row()

        self.assertEqual(feed_const.ABILITY_STATE_ACTIVE, row["state"])
        self.assertEqual(aug_const.AUG_EXTINGUISH_ALL_COMMAND, row["command"])


class TestComposer(_Fixture, EvenniaTest):
    """The rail holds the aura rows first, then the augment rows."""

    def test_the_aura_rows_come_first_and_the_augment_rows_after(self):
        rows = composer.ability_rows(self.char1)
        keys = [row["key"] for row in rows]
        aura_count = len(AURA_REGISTRY)

        self.assertEqual(list(AURA_REGISTRY), keys[:aura_count])
        self.assertEqual([row["key"] for row in self._rows()], keys[aura_count:])

    def test_the_feed_reads_the_composer(self):
        fed = abilities_feed.build_payload(self.char1).to_dict()["abilities"]
        composed = composer.ability_rows(self.char1)

        self.assertEqual([row["key"] for row in composed], [row["key"] for row in fed])


class TestCommand(_Fixture, EvenniaCommandTest):
    """The rail and the command are halves of one promise."""

    def _send(self, command: str) -> str:
        argument = command[len(CmdAug.key):].strip()

        return self.call(CmdAug(), argument)

    def test_every_ready_command_lights_its_augment(self):
        for row in self._rows():
            if row["kind"] != feed_const.ABILITY_KIND_TOGGLE:
                continue

            with self.subTest(ability=row["key"]):
                self._send(row["command"])

                self.assertTrue(get_augment_handler_for(self.char1).is_lit(row["key"]))

    def test_the_active_command_puts_its_augment_out(self):
        augment = _first_augment()
        self._light(augment)

        self._send(self._row(augment.key)["command"])

        handler = get_augment_handler_for(self.char1)
        self.assertTrue(handler is None or not handler.is_lit(augment.key))

    def test_the_power_level_command_moves_the_power_level(self):
        augment = _first_augment()
        self._light(augment, aug_const.AUG_POWER_LEVEL_MIN)

        self._send(self._row(augment.key)[feed_const.ABILITY_POWER_LEVEL_COMMAND_KEY])

        self.assertEqual(
            aug_const.AUG_POWER_LEVEL_MIN + 1,
            get_augment_handler_for(self.char1).power_level_of(augment.key))

    def test_each_power_level_line_reaches_its_power_level(self):
        """The power level buttons of the client send these lines. An out
        augment lights at the power level, and a lit one moves to it."""
        augment = _first_augment()

        for power_level in range(aug_const.AUG_POWER_LEVEL_MIN,
                                 aug_const.AUG_POWER_LEVELS + 1):
            with self.subTest(power_level=power_level):
                lines = self._row(augment.key)[feed_const.ABILITY_POWER_LEVEL_COMMANDS_KEY]

                self._send(lines[power_level - aug_const.AUG_POWER_LEVEL_MIN])

                self.assertEqual(
                    power_level,
                    get_augment_handler_for(self.char1).power_level_of(augment.key))

    def test_the_set_command_lights_the_rig_and_then_puts_all_out(self):
        self._send(self._set_row()["command"])

        handler = get_augment_handler_for(self.char1)
        self.assertEqual(len(sockets.socketed_augments(self.char1)),
                         len(handler.lit_augments()))

        self._send(self._set_row()["command"])

        self.assertIsNone(get_augment_handler_for(self.char1))

    def test_the_listing_and_the_rail_agree(self):
        augment = _first_augment()
        self._light(augment)

        listing = strip_ansi(self.call(CmdAug(), ""))

        for row in self._rows():
            if row["kind"] == feed_const.ABILITY_KIND_TOGGLE:
                self.assertIn(row["name"], listing)

        self.assertIn("online", listing)


class TestTheRailFollowsItsFacts(_Fixture, EvenniaTest):
    """A light, a put-out, a power shift, and a level reach the rail with
    no call beside the write."""

    def setUp(self):
        super().setUp()

        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_CHAR_ABILITIES)
            subscriptions.subscribe(session, feed_const.CHANNEL_CHAR_AVATAR)

        self.published = []
        patcher = mock.patch.object(feed, "emit", side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)
        buffer.reset()
        self.addCleanup(buffer.reset)

    def _record(self, obj, payload, force=False):
        self.published.append((payload.channel, payload.to_dict()))

        return 0

    def _drained_rows(self) -> dict:
        buffer.drain_stale()
        bodies = [body for sent, body in self.published
                  if sent == feed_const.CHANNEL_CHAR_ABILITIES]
        self.assertTrue(bodies, "nothing reached the rail")

        return {row["key"]: row for row in bodies[-1]["abilities"]}

    def _last_avatar(self) -> dict:
        bodies = [body for sent, body in self.published
                  if sent == feed_const.CHANNEL_CHAR_AVATAR]
        self.assertTrue(bodies, "no avatar reached the owner")

        return bodies[-1]

    def test_a_light_reaches_the_rail(self):
        augment = _first_augment()

        self._light(augment)

        rows = self._drained_rows()
        self.assertEqual(feed_const.ABILITY_STATE_ACTIVE, rows[augment.key]["state"])
        self.assertEqual(feed_const.ABILITY_STATE_ACTIVE,
                         rows[aug_const.AUG_SET_ROW_KEY]["state"])

    def test_a_power_shift_reaches_the_rail(self):
        augment = _first_augment()
        self._light(augment, aug_const.AUG_POWER_LEVEL_MIN)
        buffer.drain_stale()
        self.published.clear()

        self._light(augment, aug_const.AUG_POWER_LEVELS)

        rows = self._drained_rows()
        self.assertEqual(aug_const.AUG_POWER_LEVELS,
                         rows[augment.key][feed_const.ABILITY_POWER_LEVEL_KEY])

    def test_a_put_out_reaches_the_rail_after_the_handler_is_gone(self):
        augment = _first_augment()
        self._light(augment)
        buffer.drain_stale()
        self.published.clear()

        handler = get_augment_handler_for(self.char1)
        handler.put_out_all()
        handler.stop_handler()

        rows = self._drained_rows()
        self.assertEqual(feed_const.ABILITY_STATE_READY, rows[augment.key]["state"])
        self.assertEqual(feed_const.ABILITY_STATE_READY,
                         rows[aug_const.AUG_SET_ROW_KEY]["state"])

    def test_a_light_reaches_the_own_figure(self):
        augment = _first_augment()

        self._light(augment)

        self.assertEqual([augment.key], self._last_avatar()["augments"])

    def test_a_put_out_clears_the_own_figure(self):
        augment = _first_augment()
        self._light(augment)
        self.published.clear()

        get_augment_handler_for(self.char1).put_out(augment.key)

        self.assertEqual([], self._last_avatar()["augments"])


class TestTheEntityRowCarriesTheGlow(_Fixture, EvenniaTest):
    """Every observer draws the glow from the entity row."""

    def test_a_row_with_nothing_lit_has_no_augments_key(self):
        body = serializers.serialize_entity(self.char1)

        self.assertNotIn(feed_const.ENTITY_AUGMENTS_KEY, body)

    def test_a_row_names_the_lit_augments_in_rail_order(self):
        wanted = support.one_of_each_group(augments_in_order())

        for augment in reversed(wanted):
            self._light(augment)

        body = serializers.serialize_entity(self.char1)

        self.assertEqual([augment.key for augment in wanted],
                         body[feed_const.ENTITY_AUGMENTS_KEY])
