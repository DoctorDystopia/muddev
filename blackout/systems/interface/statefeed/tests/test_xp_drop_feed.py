"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/13/2026
Description: Cases for the blackout_xp channel -- one XP award, as the player
             earned it, published from xp_awards.grant_xp.

             The load-bearing case is
             `test_the_drop_names_what_the_log_line_prints`: the drop and the
             text readout are two views of one award, and it is the test that
             fails if they ever describe it differently.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.statefeed.tests.test_xp_drop_feed
"""

from unittest import mock

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills import xp_awards
from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from systems.interface.statefeed import buffer
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed
from systems.interface.statefeed import subscriptions
from typeclasses.characters import Character as BlackoutCharacter


# Private constant definitions

# A butcher's award: the primary skill and the secondary it also teaches.
_PRIMARY = skill_constants.BUTCHERY_SKILL_KEY
_SECONDARY = skill_constants.CUTTING_SKILL_KEY
_AWARDS = [(_PRIMARY, 25), (_SECONDARY, 5)]
_KIND = feed_const.MESSAGE_TYPE_GATHERING


class _XpDropTest(EvenniaTest):
    """Shared fixture: a Blackout character, and a way to see what it was sent."""

    character_typeclass = BlackoutCharacter

    def tearDown(self):
        buffer.reset()
        super().tearDown()

    def _subscribe(self) -> None:
        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_XP_DROP)

    def _grant(self, awards) -> list:
        """Grant through the real seam and return every drop body sent."""
        with mock.patch.object(type(self.char1), "msg") as mocked_msg:
            xp_awards.grant_xp(self.char1, awards, _KIND)

        return [
            call.kwargs[feed_const.CHANNEL_XP_DROP]
            for call in mocked_msg.call_args_list
            if feed_const.CHANNEL_XP_DROP in call.kwargs
        ]


class TestChannel(_XpDropTest):
    """The channel's declaration, which decides whether it can be reached."""

    def test_a_client_may_subscribe_to_it(self):
        self.assertIn(
            feed_const.CHANNEL_XP_DROP, feed_const.SUBSCRIBABLE_CHANNELS)

    def test_channel_is_not_rate_capped(self):
        # A dropped award is a drop the player never sees, with nothing
        # scheduled behind it.
        self.assertNotIn(
            feed_const.CHANNEL_XP_DROP, feed_const.CHANNEL_MIN_INTERVAL_SECONDS)

    def test_channel_is_never_coalesced(self):
        # An event: two awards on one tick are two drops, and keeping only
        # the newest would lose one the text log still prints.
        self.assertNotIn(
            feed_const.CHANNEL_XP_DROP, feed_const.COALESCABLE_CHANNELS)

    def test_emit_is_a_no_op_without_a_subscriber(self):
        self.assertEqual(0, feed.emit_xp_drop(self.char1, _AWARDS, _KIND))

    def test_an_object_with_no_sessions_is_a_no_op(self):
        self.assertEqual(0, feed.emit_xp_drop(object(), _AWARDS, _KIND))

    def test_a_telnet_player_is_sent_nothing(self):
        self.assertEqual([], self._grant(_AWARDS))


class TestGrantPublishes(_XpDropTest):
    """What reaches a subscribed client when grant_xp pays an award."""

    def setUp(self):
        super().setUp()
        self._subscribe()

    def test_one_action_is_one_drop_naming_every_skill(self):
        drops = self._grant(_AWARDS)

        self.assertEqual(1, len(drops))
        self.assertEqual(
            [key for key, _amount in _AWARDS],
            [row["skill_key"] for row in drops[0]["awards"]])
        self.assertEqual(
            [amount for _key, amount in _AWARDS],
            [row["amount"] for row in drops[0]["awards"]])

    def test_the_drop_carries_the_kind_of_its_line(self):
        drops = self._grant(_AWARDS)

        self.assertEqual(_KIND, drops[0]["kind"])

    def test_every_row_is_named_by_the_registry(self):
        for row in self._grant(_AWARDS)[0]["awards"]:
            with self.subTest(skill=row["skill_key"]):
                skill_class = SKILL_REGISTRY[row["skill_key"]]
                self.assertEqual(skill_class.name, row["name"])
                self.assertEqual(skill_class.category, row["category"])

    def test_progress_is_read_after_the_award(self):
        """A client fills a bar from these, so they must include the award."""
        for row in self._grant(_AWARDS)[0]["awards"]:
            with self.subTest(skill=row["skill_key"]):
                current, needed, _rest = self.char1.skills.get_xp_level(
                    row["skill_key"])
                self.assertEqual(current, row["current_xp"])
                self.assertEqual(needed, row["needed_xp"])
                self.assertEqual(
                    self.char1.skills.get_level(row["skill_key"]), row["level"])

    def test_the_drop_names_what_the_log_line_prints(self):
        readout = strip_ansi(xp_awards.format_xp_readout(_AWARDS))

        for row in self._grant(_AWARDS)[0]["awards"]:
            with self.subTest(skill=row["skill_key"]):
                self.assertIn(f"+{row['amount']} {row['name']}", readout)

    def test_nothing_granted_publishes_nothing(self):
        self.assertEqual([], self._grant([(_PRIMARY, 0)]))

    def test_a_zero_entry_is_left_out_of_the_drop(self):
        drops = self._grant([(_PRIMARY, 25), (_SECONDARY, 0)])

        self.assertEqual(
            [_PRIMARY], [row["skill_key"] for row in drops[0]["awards"]])

    def test_a_drop_inside_a_tick_is_sent_at_once(self):
        """Not held for the flush: this channel is not coalescable."""
        buffer.begin_tick()

        self.assertEqual(1, len(self._grant(_AWARDS)))
