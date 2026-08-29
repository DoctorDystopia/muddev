"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Cases for the char_status channel.

             Two halves, and they fail differently -- the same split
             test_quest_feed.py draws, for the same reason.

             THE SHAPE. `_read_levels` decides which skills a graphical client
             is told about. A mistake here is visible: a missing skill, a
             float where a level should be.

             THE TRIGGER. `logic._publish_level_change` fires from the two
             places a level actually moves. A mistake THERE is invisible, and
             it is the defect this module was written for: char_status was
             assembled in exactly one place, `resync._send_self`, so a client
             received its level table at login and NEVER AGAIN. Levelling
             Fortitude moved the cap, the dossier and the telnet screen while
             the graphical client kept drawing the levels it had when it
             connected, for as long as it stayed connected.

             The trigger cases patch `events.emit` -- the sink -- but leave the
             SUBSCRIPTION gate real, so a level-up that stops reaching the feed
             fails here whether the break is in the gate or in the caller.
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.combat import constants as combat_constants
from systems.progression.skills.constants import (
    COMBAT_SKILL_KEYS,
    FORTITUDE_SKILL_KEY,
)
from systems.progression.skills import logic
from systems.statefeed import constants as const
from systems.statefeed import events
from systems.statefeed import resync
from systems.statefeed import subscriptions
from typeclasses.characters import Character as BlackoutCharacter


# ─── Private constant definitions ────────────────────────────────────────────

# A skill that is deliberately NOT on this channel. Named from the gathering
# tree rather than invented, so the exclusion is asserted against a skill that
# really exists and really is left out.
_NON_COMBAT_SKILL: str = "cutting"


# ─── Test cases ──────────────────────────────────────────────────────────────

class _SubscribedCharacterTest(EvenniaTest):
    """A character whose session subscribes to everything, with a tapped feed.

    The tap replaces emit() rather than reading the session's outbox: the
    assertions below are about which payloads the feed is HANDED and what is in
    them, and routing them to a socket is emit.py's contract and test_emit.py's
    job.
    """

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

    def _record(self, obj, payload, force=False):
        """Stand in for emit(), keeping the channel, the body and the cap."""
        self.published.append((payload.channel, payload.to_dict(), force))

        return 0

    def _bodies(self, channel: str) -> list:
        return [body for sent, body, _ in self.published if sent == channel]

    def _levels_published(self) -> list:
        return [body["levels"] for body in self._bodies(const.CHANNEL_CHAR_STATUS)]


class TestStatusShape(_SubscribedCharacterTest):
    """What a status message contains."""

    def test_every_combat_skill_is_reported(self):
        levels = events._read_levels(self.char1.skills)

        for skill_key in COMBAT_SKILL_KEYS:
            with self.subTest(skill=skill_key):
                self.assertIn(skill_key, levels)

    def test_no_skill_outside_the_combat_set_is_reported(self):
        """The narrowing is deliberate. A skills tab reads char_summary."""
        levels = events._read_levels(self.char1.skills)

        self.assertNotIn(_NON_COMBAT_SKILL, levels)
        self.assertEqual(sorted(levels), sorted(COMBAT_SKILL_KEYS))

    def test_every_level_is_an_int(self):
        """The client keys on these. A float would arrive as 10.0 and miss."""
        levels = events._read_levels(self.char1.skills)

        for skill_key, level in levels.items():
            with self.subTest(skill=skill_key):
                self.assertIsInstance(level, int)

    def test_an_entity_with_no_skills_reports_an_empty_table(self):
        self.assertEqual(events._read_levels(None), {})

    def test_the_reported_level_is_the_stored_one(self):
        self.char1.skills.set_level(FORTITUDE_SKILL_KEY, 42)

        levels = events._read_levels(self.char1.skills)

        self.assertEqual(levels[FORTITUDE_SKILL_KEY], 42)


class TestStatusTrigger(_SubscribedCharacterTest):
    """When a status message is sent. The half that fails silently."""

    def test_levelling_a_skill_publishes_the_new_level(self):
        """The regression: this channel had no live emitter at all."""
        before = self.char1.skills.get_level("strike")
        needed = logic.calculate_xp_needed(before)

        self.char1.skills.add_xp("strike", needed * 2)

        after = self.char1.skills.get_level("strike")
        self.assertGreater(after, before)
        self.assertIn(after, [levels["strike"] for levels in self._levels_published()])

    def test_xp_that_does_not_level_publishes_nothing(self):
        """Combat awards XP on every hit; only a LEVEL is worth a send."""
        needed = logic.calculate_xp_needed(self.char1.skills.get_level("strike"))
        self.published.clear()

        self.char1.skills.add_xp("strike", max(needed - 1, 0))

        self.assertEqual(self._bodies(const.CHANNEL_CHAR_STATUS), [])

    def test_setting_a_level_publishes_it(self):
        """set_level is the other write path -- a drain, a builder, the egg."""
        self.published.clear()

        self.char1.skills.set_level(FORTITUDE_SKILL_KEY, 42)

        published = [levels[FORTITUDE_SKILL_KEY] for levels in self._levels_published()]
        self.assertIn(42, published)

    def test_setting_the_same_level_publishes_nothing(self):
        self.char1.skills.set_level(FORTITUDE_SKILL_KEY, 42)
        self.published.clear()

        self.char1.skills.set_level(FORTITUDE_SKILL_KEY, 42)

        self.assertEqual(self._bodies(const.CHANNEL_CHAR_STATUS), [])

    def test_a_drained_level_is_published_too(self):
        """A decrease moves the table exactly as much as an increase does."""
        self.char1.skills.set_level(FORTITUDE_SKILL_KEY, 42)
        self.published.clear()

        self.char1.skills.set_level(FORTITUDE_SKILL_KEY, 20)

        published = [levels[FORTITUDE_SKILL_KEY] for levels in self._levels_published()]
        self.assertIn(20, published)

    def test_the_published_table_agrees_with_the_handler(self):
        """The bug's signature was the two disagreeing. Assert they cannot."""
        self.char1.skills.set_level("brawn", 33)

        last = self._levels_published()[-1]
        for skill_key, level in last.items():
            with self.subTest(skill=skill_key):
                self.assertEqual(level, self.char1.skills.get_level(skill_key))

    def test_levelling_also_publishes_the_dossier(self):
        """The channel a skills tab draws from, refreshed on the same event."""
        self.published.clear()

        self.char1.skills.set_level("brawn", 33)

        self.assertTrue(self._bodies(const.CHANNEL_CHAR_SUMMARY))


class TestFortitudeOrdering(_SubscribedCharacterTest):
    """The published dossier must not describe a cap that has been replaced.

    Fortitude's level-up side effect moves max_hp. If the publish ran first,
    one payload would announce the new Fortitude level beside the old HP cap --
    a client drawing both would show a character whose own two numbers
    disagree.
    """

    def setUp(self):
        super().setUp()
        self.caps_at_publish = []

        patcher = mock.patch.object(
            events, "emit_summary", side_effect=self._record_cap
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _record_cap(self, observer, force=False):
        self.caps_at_publish.append(observer.max_hp)

        return 0

    def test_the_cap_is_already_updated_when_the_dossier_is_built(self):
        self.char1.skills.set_level(FORTITUDE_SKILL_KEY, 42)

        expected = 42 * combat_constants.HP_PER_FORTITUDE_LEVEL
        self.assertEqual(self.caps_at_publish[-1], expected)


class TestStatusCosts(EvenniaTest):
    """What the channel costs a server with no graphical client attached."""

    character_typeclass = BlackoutCharacter

    def test_an_unsubscribed_observer_is_sent_nothing(self):
        sent = events.emit_status(self.char1)

        self.assertEqual(sent, 0)

    def test_an_unsubscribed_observer_costs_no_payload(self):
        """The gate is checked BEFORE the levels are read, not after."""
        with mock.patch.object(events, "_read_levels") as reader:
            events.emit_status(self.char1)

        reader.assert_not_called()


class TestResyncDelegates(EvenniaTest):
    """Login must send the same message the live path does.

    Asserted because resync is where this payload used to be BUILT. A resync
    that assembles its own copy is a second definition of what a status message
    contains, and it agrees with the first only until somebody edits one.
    """

    character_typeclass = BlackoutCharacter

    def test_resync_sends_status_through_the_emitter(self):
        with mock.patch.object(events, "emit_status", return_value=0) as emitter:
            resync._send_self(self.char1)

        emitter.assert_called_once_with(self.char1, force=True)

    def test_resync_sends_vitals_through_the_emitter(self):
        with mock.patch.object(events, "emit_vitals", return_value=0) as emitter:
            resync._send_self(self.char1)

        emitter.assert_called_once_with(self.char1, force=True)
