"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/20/2026
Description: Cases for the char_abilities channel, the detail behind it, the
             `aura` command that its rows name, and the rail that follows
             its facts.

             The load-bearing case is
             `test_every_ready_command_the_rail_is_sent_lights_its_aura`.
             It runs the command of each row through the real command and
             checks that the aura lit.

             NOTHING HERE ASSERTS A CENSUS of the auras. Expectations come
             from AURA_REGISTRY, so a new aura re-derives the test.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.statefeed.tests.test_abilities_feed
"""

import json
from unittest import mock

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaCommandTest, EvenniaTest

from commands.combat_cmds import CmdAura
from systems.gameplay.combat import constants as combat_const
from systems.gameplay.combat.auras import detail
from systems.gameplay.combat.auras.aura_defs.base_aura import NO_UNLOCK_REQUIREMENT
from systems.gameplay.combat.auras.aura_handler import (
    ensure_aura_handler,
    get_aura_handler_for,
)
from systems.gameplay.combat.auras.registry import AURA_REGISTRY
from systems.gameplay.progression.skills import logic as skill_logic
from systems.interface.statefeed import abilities as abilities_feed
from systems.interface.statefeed import buffer
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed
from systems.interface.statefeed import subscriptions
from typeclasses.characters import Character as BlackoutCharacter


# ─── Private constant definitions ────────────────────────────────────────────

# A level past every unlock in the registry, so every aura is ready.
_LEVEL_PAST_EVERY_UNLOCK: int = max(
    [aura.unlock_level for aura in AURA_REGISTRY.values()] + [NO_UNLOCK_REQUIREMENT]
) + 1

# The states a row may carry.
_STATES: frozenset = frozenset((
    feed_const.ABILITY_STATE_READY,
    feed_const.ABILITY_STATE_ACTIVE,
    feed_const.ABILITY_STATE_LOCKED,
))

# A cost line, to prove that the tip carries one when an aura declares it.
_COST_TEXT: str = "Burns one hit point each pulse."


# ─── Private helper routines ─────────────────────────────────────────────────

def _gated_aura():
    """The first aura with an unlock level, or None when none has one."""
    for aura in AURA_REGISTRY.values():
        if aura.unlock_level > NO_UNLOCK_REQUIREMENT:
            return aura

    return None


class _Fixture:
    """Level and read helpers shared by the feed and command cases."""

    character_typeclass = BlackoutCharacter

    def _set_every_scaling_skill(self, level: int) -> None:
        for aura in AURA_REGISTRY.values():
            if aura.scaling_skill:
                self.char1.db.skills[aura.scaling_skill] = {"level": level, "xp": 0}

    def _rows(self) -> list:
        return abilities_feed.build_payload(self.char1).to_dict()["abilities"]

    def _row(self, key: str) -> dict:
        for row in self._rows():
            if row["key"] == key:
                return row

        self.fail("no row for %s" % key)

    def _subscribe(self) -> None:
        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_CHAR_ABILITIES)

    def _light(self, aura) -> None:
        ensure_aura_handler(self.char1).activate(aura)

    def _put_out(self) -> None:
        handler = get_aura_handler_for(self.char1)

        if handler is not None:
            handler.stop_aura()


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestChannel(_Fixture, EvenniaTest):
    """The declaration of the channel, which decides whether it can be reached."""

    def test_a_client_may_subscribe_to_it(self):
        self.assertIn(
            feed_const.CHANNEL_CHAR_ABILITIES, feed_const.SUBSCRIBABLE_CHANNELS)

    def test_channel_is_not_rate_capped(self):
        # A dropped snapshot leaves a lit aura unlit with nothing scheduled
        # to correct it.
        self.assertNotIn(
            feed_const.CHANNEL_CHAR_ABILITIES,
            feed_const.CHANNEL_MIN_INTERVAL_SECONDS)

    def test_channel_may_be_coalesced(self):
        self.assertIn(
            feed_const.CHANNEL_CHAR_ABILITIES, feed_const.COALESCABLE_CHANNELS)

    def test_emit_is_a_no_op_without_a_subscriber(self):
        self.assertEqual(0, feed.emit_abilities(self.char1))

    def test_emit_reaches_a_subscribed_session(self):
        self._subscribe()

        self.assertGreater(feed.emit_abilities(self.char1), 0)

    def test_the_payload_survives_json(self):
        body = abilities_feed.build_payload(self.char1).to_dict()

        json.dumps(body)


class TestRows(_Fixture, EvenniaTest):
    """The rows, measured against the registry."""

    def setUp(self):
        super().setUp()
        self._set_every_scaling_skill(_LEVEL_PAST_EVERY_UNLOCK)

    def tearDown(self):
        self._put_out()
        super().tearDown()

    def test_one_row_for_each_aura_in_the_order_of_the_registry(self):
        keys = [row["key"] for row in self._rows()]

        self.assertEqual(list(AURA_REGISTRY), keys)

    def test_every_row_is_well_formed(self):
        for row in self._rows():
            with self.subTest(ability=row["key"]):
                aura = AURA_REGISTRY[row["key"]]

                self.assertEqual(aura.name, row["name"])
                self.assertEqual(feed_const.ABILITY_KIND_TOGGLE, row["kind"])
                self.assertIn(row["state"], _STATES)

                tip = row[feed_const.TIP_KEY]
                self.assertEqual(aura.name, tip[feed_const.TIP_TITLE_KEY])
                self.assertTrue(tip[feed_const.TIP_LINES_KEY])
                self.assertIn(aura.description, tip[feed_const.TIP_LINES_KEY])

    def test_a_ready_row_names_the_command_a_player_would_type(self):
        for row in self._rows():
            with self.subTest(ability=row["key"]):
                aura = AURA_REGISTRY[row["key"]]

                self.assertEqual(feed_const.ABILITY_STATE_READY, row["state"])
                self.assertEqual("", row["reason"])
                self.assertEqual(
                    combat_const.AURA_IGNITE_TEMPLATE.format(name=aura.name),
                    row["command"])

    def test_the_lit_aura_is_the_one_active_row_and_its_command_puts_it_out(self):
        aura = next(iter(AURA_REGISTRY.values()))
        self._light(aura)

        active = [row for row in self._rows()
                  if row["state"] == feed_const.ABILITY_STATE_ACTIVE]

        self.assertEqual([aura.key], [row["key"] for row in active])
        self.assertEqual(combat_const.AURA_EXTINGUISH_COMMAND, active[0]["command"])

    def test_a_level_under_the_unlock_locks_the_row_with_its_reason(self):
        aura = _gated_aura()

        if aura is None:
            self.skipTest("no aura declares an unlock level")

        self.char1.db.skills[aura.scaling_skill] = {
            "level": aura.unlock_level - 1, "xp": 0,
        }

        row = self._row(aura.key)

        self.assertEqual(feed_const.ABILITY_STATE_LOCKED, row["state"])
        self.assertEqual("", row["command"])
        self.assertIn(str(aura.unlock_level), row["reason"])

    def test_the_tip_names_the_unlock_of_a_gated_aura(self):
        aura = _gated_aura()

        if aura is None:
            self.skipTest("no aura declares an unlock level")

        lines = " ".join(self._row(aura.key)[feed_const.TIP_KEY][feed_const.TIP_LINES_KEY])

        self.assertIn(str(aura.unlock_level), lines)

    def test_the_tip_carries_the_cost_when_the_aura_declares_one(self):
        aura = next(iter(AURA_REGISTRY.values()))

        with mock.patch.object(type(aura), "cost", _COST_TEXT):
            lines = self._row(aura.key)[feed_const.TIP_KEY][feed_const.TIP_LINES_KEY]

        self.assertIn(_COST_TEXT, lines)

    def test_a_caster_with_no_skills_gets_every_gated_aura_locked(self):
        rows = detail.ability_rows(self.obj1)

        for row in rows:
            with self.subTest(ability=row["key"]):
                aura = AURA_REGISTRY[row["key"]]

                if aura.unlock_level > NO_UNLOCK_REQUIREMENT:
                    self.assertEqual(feed_const.ABILITY_STATE_LOCKED, row["state"])


class TestCommand(_Fixture, EvenniaCommandTest):
    """The rail and the command are halves of one promise."""

    def setUp(self):
        super().setUp()
        self._set_every_scaling_skill(_LEVEL_PAST_EVERY_UNLOCK)

    def tearDown(self):
        self._put_out()
        super().tearDown()

    def _send(self, command: str) -> str:
        """Run one whole line, as the rail sends it, through the real command."""
        argument = command[len(CmdAura.key):].strip()

        return self.call(CmdAura(), argument)

    def test_every_ready_command_the_rail_is_sent_lights_its_aura(self):
        for row in self._rows():
            with self.subTest(ability=row["key"]):
                self._put_out()

                self._send(row["command"])

                handler = get_aura_handler_for(self.char1)
                self.assertIsNotNone(handler)
                self.assertEqual(row["key"], handler.get_aura().key)

    def test_the_active_command_puts_the_aura_out(self):
        aura = next(iter(AURA_REGISTRY.values()))
        self._light(aura)

        self._send(self._row(aura.key)["command"])

        self.assertIsNone(get_aura_handler_for(self.char1))

    def test_the_listing_and_the_rail_agree_on_the_lit_aura(self):
        aura = next(iter(AURA_REGISTRY.values()))
        self._light(aura)

        listing = strip_ansi(self.call(CmdAura(), ""))

        for row in self._rows():
            with self.subTest(ability=row["key"]):
                self.assertIn(row["name"], listing)

        self.assertIn("burning", listing)


class TestTheRailFollowsItsFacts(_Fixture, EvenniaTest):
    """A light, a put-out and a level reach the rail without a call beside
    the write. The arrangement of test_freshness.py, for one channel."""

    def setUp(self):
        super().setUp()
        self._subscribe()
        self.published = []

        patcher = mock.patch.object(feed, "emit", side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)

        buffer.reset()
        self.addCleanup(buffer.reset)

    def tearDown(self):
        self._put_out()
        super().tearDown()

    def _record(self, obj, payload, force=False):
        self.published.append((payload.channel, payload.to_dict()))

        return 0

    def _drained_states(self) -> dict:
        """Build what is stale, then read {key: state} from the LAST send."""
        buffer.drain_stale()

        bodies = [body for sent, body in self.published
                  if sent == feed_const.CHANNEL_CHAR_ABILITIES]

        self.assertTrue(bodies, "nothing reached the rail")

        return {row["key"]: row["state"] for row in bodies[-1]["abilities"]}

    def test_a_light_reaches_the_rail(self):
        self._set_every_scaling_skill(_LEVEL_PAST_EVERY_UNLOCK)
        aura = next(iter(AURA_REGISTRY.values()))

        self._light(aura)

        self.assertEqual(
            feed_const.ABILITY_STATE_ACTIVE, self._drained_states()[aura.key])

    def test_a_put_out_reaches_the_rail_after_the_handler_is_gone(self):
        self._set_every_scaling_skill(_LEVEL_PAST_EVERY_UNLOCK)
        aura = next(iter(AURA_REGISTRY.values()))
        self._light(aura)
        buffer.drain_stale()
        self.published.clear()

        self._put_out()

        self.assertEqual(
            feed_const.ABILITY_STATE_READY, self._drained_states()[aura.key])

    def test_a_level_that_unlocks_an_aura_reaches_the_rail(self):
        aura = _gated_aura()

        if aura is None:
            self.skipTest("no aura declares an unlock level")

        self.char1.db.skills[aura.scaling_skill] = {
            "level": aura.unlock_level - 1, "xp": 0,
        }
        self.assertEqual(
            feed_const.ABILITY_STATE_LOCKED, self._row(aura.key)["state"])

        skill_logic.set_level(self.char1, aura.scaling_skill, aura.unlock_level)

        self.assertEqual(
            feed_const.ABILITY_STATE_READY, self._drained_states()[aura.key])
