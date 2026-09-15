"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/12/2026
Description: Cases for keeping what a graphical client draws current.

             The defect this module was written for: the Character tab showed
             whatever was true the last time the player opened `score`. The
             dossier repeats HP, combat state, location, credits, quests and
             the active style, and it was built on resync, on the score menu
             and on four hand-picked events -- never on a hit, a step, a
             purchase or a quest taken. The skill roster had the same defect
             one channel over, for XP, and the status channel for in_combat.

             Each case drives a real write and asserts on what reaches the feed
             AFTER buffer.drain_stale, which is where a deferred rebuild lands
             outside a tick. The tap replaces events.emit -- the sink -- and
             leaves every subscription gate real, the arrangement
             test_status_feed.py uses for the reason it gives.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.statefeed.tests.test_freshness
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.core.stat_tracker import constants as stat_constants
from systems.gameplay.combat.combat import ensure_combat_handler
from systems.gameplay.progression.skills import constants as skill_constants
from systems.interface.statefeed import buffer
from systems.interface.statefeed import constants as const
from systems.interface.statefeed import events
from systems.interface.statefeed import subscriptions
from typeclasses.characters import Character as BlackoutCharacter


# ─── Private constant definitions ────────────────────────────────────────────

# The dossier band repeating HP, total XP and combat state. A summary panel
# key, named once so a rename under panel_defs/ fails here in one place.
_VITALS_PANEL: str = "vitals"

# The dossier band repeating the stat tracker's tallies, and a hostile to tally.
_RECORDS_PANEL: str = "records"
_HOSTILE: str = "mutant_raider"

# A skill outside combat, so an award to it cannot move combat level and drag
# the combat channels into an assertion. From the gathering tree, not invented.
_GATHERING_SKILL: str = skill_constants.SKILL_KEY_CUTTING


# ─── Test cases ──────────────────────────────────────────────────────────────

class _FreshnessTest(EvenniaTest):
    """A character subscribed to everything, a tapped feed, a clean buffer."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()

        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, const.SUBSCRIBE_ALL)

        self.char1.skills.seed_fortitude_on_creation()
        self.published = []

        patcher = mock.patch.object(events, "emit", side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)

        # Seeding above marked snapshots stale on the way; start from nothing.
        buffer.reset()
        self.addCleanup(buffer.reset)

    def _record(self, obj, payload, force=False):
        """Stand in for emit(), keeping the channel and the body."""
        self.published.append((payload.channel, payload.to_dict()))

        return 0

    def _bodies(self, channel: str) -> list:
        return [body for sent, body in self.published if sent == channel]

    def _drain(self, channel: str) -> list:
        """Build whatever is stale, then return every body sent on channel."""
        buffer.drain_stale()

        return self._bodies(channel)


class TestDossierFollowsItsFacts(_FreshnessTest):
    """The Character tab, which only ever refreshed on `score`."""

    def test_losing_hp_reaches_the_dossier(self):
        self.char1.hp = self.char1.max_hp - 1

        bodies = self._drain(const.CHANNEL_CHAR_SUMMARY)

        self.assertTrue(bodies)
        vitals = bodies[-1]["panels"][_VITALS_PANEL]
        self.assertEqual(vitals["hp"], self.char1.hp)

    def test_nothing_is_built_until_the_changes_stop(self):
        """Three hits, one dossier -- the one true after all three."""
        for lost in (1, 2, 3):
            self.char1.hp = self.char1.max_hp - lost

        self.assertEqual(self._bodies(const.CHANNEL_CHAR_SUMMARY), [])

        bodies = self._drain(const.CHANNEL_CHAR_SUMMARY)

        self.assertEqual(len(bodies), 1)
        vitals = bodies[0]["panels"][_VITALS_PANEL]
        self.assertEqual(vitals["hp"], self.char1.hp)

    def test_every_channel_repeating_a_dossier_fact_marks_it_stale(self):
        """The dossier follows a fact because that fact's own emitter calls
        refresh_summary, not because of a call beside each write -- so each
        of those emitters, on its own, must leave the dossier marked."""
        emitters = (
            events.emit_vitals,
            events.emit_status,
            events.emit_inventory,
            events.emit_quests,
            events.emit_room_info,
            events.emit_combat_options,
        )

        for emitter in emitters:
            with self.subTest(emitter=emitter.__name__):
                buffer.reset()

                emitter(self.char1)

                self.assertEqual(buffer.stale_count(), 1)

    def test_an_aura_lighting_marks_it_and_a_pulse_does_not(self):
        events.emit_aura(self.char1, events.AURA_EVENT_ACTIVATE, "test", 1)
        self.assertEqual(buffer.stale_count(), 1)

        buffer.reset()
        events.emit_aura(self.char1, events.AURA_EVENT_PULSE, "test", 1)
        self.assertEqual(buffer.stale_count(), 0)

    def test_a_character_nobody_is_watching_marks_nothing(self):
        """A telnet player's cost: a session lookup, and no scheduled build."""
        events.emit_vitals(self.char2)

        self.assertEqual(buffer.stale_count(), 0)

    def test_asking_just_after_a_change_builds_once(self):
        """`score` straight after a hit must not buy a second build later."""
        self.char1.hp = self.char1.max_hp - 1

        events.emit_summary(self.char1)

        self.assertEqual(buffer.stale_count(), 0)

    def test_a_recorded_stat_reaches_the_dossier(self):
        """A kill writes only the stat tracker -- no emitter of its own."""
        self.char1.stats.increment(stat_constants.KILLS_PER_HOSTILE_STAT_KEY, _HOSTILE)

        bodies = self._drain(const.CHANNEL_CHAR_SUMMARY)

        self.assertTrue(bodies)
        records = bodies[-1]["panels"][_RECORDS_PANEL]
        self.assertEqual(records[stat_constants.KILLS_PER_HOSTILE_STAT_KEY], {_HOSTILE: 1})


class TestRosterFollowsXp(_FreshnessTest):
    """The Skills tab, whose bars moved only when a level did."""

    def test_xp_that_does_not_level_reaches_the_roster(self):
        before = self.char1.skills.get_level(_GATHERING_SKILL)

        self.char1.skills.add_xp(_GATHERING_SKILL, 1)

        self.assertEqual(self.char1.skills.get_level(_GATHERING_SKILL), before)
        bodies = self._drain(const.CHANNEL_CHAR_SKILLS)
        self.assertTrue(bodies)

        rows = [row for row in bodies[-1]["skills"]
                if row["key"] == _GATHERING_SKILL]
        current, _needed, _remaining = self.char1.skills.get_xp_level(
            _GATHERING_SKILL)
        self.assertEqual(rows[0]["current_xp"], current)

    def test_xp_reaches_the_dossier_total(self):
        self.char1.skills.add_xp(_GATHERING_SKILL, 1)

        bodies = self._drain(const.CHANNEL_CHAR_SUMMARY)

        vitals = bodies[-1]["panels"][_VITALS_PANEL]
        self.assertEqual(vitals["total_xp"], self.char1.skills.combined_xp())

    def test_an_award_of_nothing_marks_nothing(self):
        self.char1.skills.add_xp(_GATHERING_SKILL, 0)

        self.assertEqual(buffer.stale_count(), 0)


class TestStatusFollowsCombat(_FreshnessTest):
    """in_combat, which the status channel carried only at login."""

    def test_a_fight_starting_is_published(self):
        ensure_combat_handler(self.char1)

        bodies = self._drain(const.CHANNEL_CHAR_STATUS)

        self.assertTrue(bodies)
        self.assertTrue(bodies[-1]["in_combat"])

    def test_a_fight_ending_is_published(self):
        handler = ensure_combat_handler(self.char1)
        buffer.drain_stale()
        self.published.clear()

        handler.end_combat()

        bodies = self._drain(const.CHANNEL_CHAR_STATUS)
        self.assertTrue(bodies)
        self.assertFalse(bodies[-1]["in_combat"])

    def test_the_dossier_follows_the_fight_too(self):
        """Two passes: the status build marks the dossier, which repeats it."""
        ensure_combat_handler(self.char1)

        bodies = self._drain(const.CHANNEL_CHAR_SUMMARY)

        self.assertTrue(bodies)
        self.assertTrue(bodies[-1]["panels"][_VITALS_PANEL]["in_combat"])
