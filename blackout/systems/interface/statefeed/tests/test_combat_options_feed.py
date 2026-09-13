"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/12/2026
Description: Cases for the char_combat channel, the description behind it, and
             the `combatoptions <style>` command its rows name.

             The three belong in one file because they are halves of one
             promise: the Combat tab offers exactly the styles the command
             accepts. `test_every_command_the_tab_is_sent_is_accepted` is the
             load-bearing case -- it runs each row's command through the real
             command and checks the style moved.

             NOTHING HERE ASSERTS A CENSUS of a weapon's styles. Expectations
             are derived from the ItemDef, so re-balancing the shortsword
             re-derives the test rather than breaking it.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.statefeed.tests.test_combat_options_feed
"""

import json
from unittest import mock

from evennia.utils.test_resources import EvenniaCommandTest, EvenniaTest

from commands.combat_cmds import CmdCombatOptions
from systems.core.tick import constants as tick_const
from systems.gameplay.combat import constants as combat_const
from systems.gameplay.combat import style_options
from systems.gameplay.combat.combat import (
    active_combat_style_key,
    combat_profile,
    set_combat_style,
)
from systems.gameplay.combat.combat_level.logic import get_combat_level
from systems.interface.menus import combat_options_menu
from systems.interface.statefeed import combat_options as combat_feed
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed
from systems.interface.statefeed import resync, subscriptions
from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB


# ─── Private constant definitions ────────────────────────────────────────────

# A weapon with four styles, the shape the tab is modelled on.
_WEAPON_KEY = "rusty_scrap_shortsword"


# ─── Private helper routines ─────────────────────────────────────────────────

class _Fixture:
    """Equip and read helpers shared by the feed and command cases."""

    character_typeclass = BlackoutCharacter

    def _equip(self):
        item = ITEM_DB[_WEAPON_KEY].create(location=self.char1)
        self.char1.equipment.equip(item)

        return item

    def _payload(self) -> dict:
        return combat_feed.build_payload(self.char1).to_dict()

    def _item_styles(self) -> dict:
        return ITEM_DB[_WEAPON_KEY].combat_styles

    def _subscribe(self) -> None:
        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_CHAR_COMBAT)


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestChannel(_Fixture, EvenniaTest):
    """The channel's declaration, which decides whether it can be reached."""

    def test_a_client_may_subscribe_to_it(self):
        self.assertIn(
            feed_const.CHANNEL_CHAR_COMBAT, feed_const.SUBSCRIBABLE_CHANNELS)

    def test_channel_is_not_rate_capped(self):
        # A dropped snapshot leaves the clicked style unlit with nothing
        # scheduled to correct it.
        self.assertNotIn(
            feed_const.CHANNEL_CHAR_COMBAT,
            feed_const.CHANNEL_MIN_INTERVAL_SECONDS)

    def test_channel_may_be_coalesced(self):
        self.assertIn(
            feed_const.CHANNEL_CHAR_COMBAT, feed_const.COALESCABLE_CHANNELS)

    def test_emit_is_a_no_op_without_a_subscriber(self):
        self.assertEqual(0, feed.emit_combat_options(self.char1))

    def test_emit_reaches_a_subscribed_session(self):
        self._subscribe()

        self.assertGreater(feed.emit_combat_options(self.char1), 0)

    def test_an_observer_with_no_equipment_is_an_empty_payload(self):
        payload = combat_feed.build_payload(self.obj1).to_dict()

        self.assertEqual([], payload["styles"])


class TestArmedPayload(_Fixture, EvenniaTest):
    """A wielded weapon's snapshot, measured against its ItemDef."""

    def setUp(self):
        super().setUp()
        self.weapon = self._equip()

    def test_styles_are_the_itemdefs_in_its_order(self):
        # Order ships so a client places the buttons where the ItemDef did.
        keys = [row["key"] for row in self._payload()["styles"]]

        self.assertEqual(list(self._item_styles()), keys)

    def test_exactly_one_style_is_active_and_it_is_the_weapons(self):
        active = [row["key"] for row in self._payload()["styles"] if row["active"]]

        self.assertEqual([active_combat_style_key(self.weapon)], active)

    def test_every_row_names_the_command_a_player_would_type(self):
        for row in self._payload()["styles"]:
            with self.subTest(style=row["key"]):
                self.assertEqual(
                    "%s %s" % (CmdCombatOptions.key, row["key"]), row["command"])

    def test_boosts_and_xp_skills_come_from_the_style_definition(self):
        definitions = self._item_styles()

        for row in self._payload()["styles"]:
            style = definitions[row["key"]]
            boosts = {entry["skill_key"]: entry["amount"] for entry in row["boosts"]}
            xp_keys = [entry["skill_key"] for entry in row["xp_skills"]]
            expected_xp = style_options._skill_keys(style["weapon_style_xp_skill"])

            with self.subTest(style=row["key"]):
                self.assertEqual(dict(style["weapon_style_level_boost"]), boosts)
                self.assertEqual(list(expected_xp), xp_keys)
                self.assertEqual(style["attack_type"], row["attack_type"])
                self.assertEqual(style["weapon_style"], row["weapon_style"])

    def test_the_header_describes_the_wielded_weapon(self):
        payload = self._payload()
        ticks = combat_profile(self.char1)["attack_speed"]

        self.assertEqual(self.weapon.key, payload["weapon_name"])
        self.assertTrue(payload["armed"])
        self.assertEqual(ticks, payload["attack_speed_ticks"])
        self.assertAlmostEqual(
            ticks * tick_const.TICK_SECONDS, payload["attack_speed_seconds"])
        self.assertEqual(get_combat_level(self.char1), payload["combat_level"])

    def test_a_switch_moves_the_active_row(self):
        target = [key for key in self._item_styles()
                  if key != active_combat_style_key(self.weapon)][0]

        set_combat_style(self.weapon, target, combatant=self.char1)

        active = [row["key"] for row in self._payload()["styles"] if row["active"]]
        self.assertEqual([target], active)

    def test_the_whole_payload_survives_json(self):
        json.dumps(self._payload())


class TestUnarmedPayload(_Fixture, EvenniaTest):
    """Bare hands fight with one style, and it cannot be changed."""

    def test_bare_hands_report_the_unarmed_name(self):
        payload = self._payload()

        self.assertEqual(combat_const.UNARMED_WEAPON_NAME, payload["weapon_name"])
        self.assertFalse(payload["armed"])

    def test_the_only_row_is_the_style_combat_resolves_and_it_sends_nothing(self):
        rows = self._payload()["styles"]

        self.assertEqual(1, len(rows))
        self.assertEqual(combat_const.UNARMED_DEFAULT_COMBAT_STYLE, rows[0]["key"])
        self.assertTrue(rows[0]["active"])
        self.assertEqual("", rows[0]["command"])


class TestRepublish(_Fixture, EvenniaTest):
    """Every way the tab's facts change has to reach the feed."""

    def test_switching_style_republishes(self):
        weapon = self._equip()

        with mock.patch("systems.gameplay.combat.combat.feed") as mocked:
            set_combat_style(weapon, "guard", combatant=self.char1)

        mocked.emit_combat_options.assert_called_with(self.char1)

    def test_equipping_republishes(self):
        with mock.patch.object(feed, "emit_combat_options") as mocked:
            self._equip()

        mocked.assert_called_with(self.char1)

    def test_resync_sends_it(self):
        with mock.patch.object(feed, "emit_combat_options",
                               return_value=0) as mocked:
            resync.send_full_state(self.char1)

        mocked.assert_called_once_with(self.char1, force=True)


class TestMenu(_Fixture, EvenniaTest):
    """The EvMenu renders the same description the tab is sent."""

    def test_one_option_per_style_with_the_active_one_marked_once(self):
        self._equip()

        text, options = combat_options_menu.start(self.char1)

        self.assertEqual(len(self._item_styles()), len(options))
        self.assertEqual(1, text.count(combat_options_menu.ACTIVE_MARKER))

        for row in self._payload()["styles"]:
            with self.subTest(style=row["key"]):
                self.assertIn(row["name"], text)

    def test_bare_hands_end_the_menu(self):
        _text, options = combat_options_menu.start(self.char1)

        self.assertIsNone(options)


class TestCommand(_Fixture, EvenniaCommandTest):
    """`combatoptions <style>` -- the line the tab sends."""

    def setUp(self):
        super().setUp()
        self.weapon = self._equip()

    def test_every_command_the_tab_is_sent_is_accepted(self):
        """The reason the tab and the command live in one test file."""
        for row in self._payload()["styles"]:
            if row["active"]:
                continue

            command_key, _, argument = row["command"].partition(" ")

            with self.subTest(style=row["key"]):
                self.assertEqual(CmdCombatOptions.key, command_key)
                self.call(CmdCombatOptions(), argument)
                self.assertEqual(row["key"], active_combat_style_key(self.weapon))

    def test_a_style_is_matched_whatever_its_case(self):
        self.call(CmdCombatOptions(), "GUARD")

        self.assertEqual("guard", active_combat_style_key(self.weapon))

    def test_an_unknown_style_is_refused_and_the_real_ones_named(self):
        before = active_combat_style_key(self.weapon)

        response = self.call(CmdCombatOptions(), "moonwalk")

        self.assertIn("no style called", response.lower())
        self.assertIn("guard", response.lower())
        self.assertEqual(before, active_combat_style_key(self.weapon))

    def test_the_active_style_is_reported_rather_than_reapplied(self):
        active = active_combat_style_key(self.weapon)

        with mock.patch("commands.combat_cmds.set_combat_style") as mocked:
            response = self.call(CmdCombatOptions(), active)

        self.assertIn("already", response.lower())
        mocked.assert_not_called()

    def test_bare_hands_are_refused(self):
        self.char1.equipment.unequip(self.weapon)

        response = self.call(CmdCombatOptions(), "guard")

        self.assertIn("no weapon", response.lower())

    def test_the_bare_command_republishes_the_tab(self):
        with mock.patch("commands.combat_cmds.feed") as mocked:
            with mock.patch(
                    "systems.interface.menus.base_menu.start_blackout_menu"):
                self.call(CmdCombatOptions(), "")

        mocked.emit_combat_options.assert_called_once_with(self.char1)
