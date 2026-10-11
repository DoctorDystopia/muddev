"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/08/2026
Description: Cases for the blackout_moment channel: one game moment that a
             client can mark with a sound.

             The load-bearing case is
             `test_the_last_task_kill_sends_the_task_complete_moment`. It runs
             a whole Exterminator task through the real handler, and it fails
             if the completion stops sending its moment.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.statefeed.tests.test_moment_feed
"""

import random
from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.exterminator.preceptors import PRECEPTOR_ATTICUS_QUIN
from systems.interface.statefeed import buffer
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed
from systems.interface.statefeed import subscriptions
from typeclasses.characters import Character as BlackoutCharacter


# Private constant definitions

_SEED: int = 1234

# A name that is not in MOMENTS.
_UNKNOWN_MOMENT: str = "not_a_moment"


class _MomentTest(EvenniaTest):
    """Shared fixture: a Blackout character, and a way to see what it was sent."""

    character_typeclass = BlackoutCharacter

    def tearDown(self):
        buffer.reset()
        super().tearDown()

    def _subscribe(self) -> None:
        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_MOMENT)

    def _sent(self, action) -> list:
        """Run action, and return the body of each moment that it sent."""
        with mock.patch.object(type(self.char1), "msg") as mocked_msg:
            action()

        return [
            call.kwargs[feed_const.CHANNEL_MOMENT]
            for call in mocked_msg.call_args_list
            if feed_const.CHANNEL_MOMENT in call.kwargs
        ]


class TestChannel(_MomentTest):
    """The declaration of the channel, which decides if a client gets it."""

    def test_a_client_may_subscribe_to_it(self):
        self.assertIn(feed_const.CHANNEL_MOMENT, feed_const.SUBSCRIBABLE_CHANNELS)

    def test_channel_is_never_coalesced(self):
        # An event: two moments in one tick are two sounds.
        self.assertNotIn(feed_const.CHANNEL_MOMENT, feed_const.COALESCABLE_CHANNELS)

    def test_channel_is_not_rate_capped(self):
        self.assertNotIn(
            feed_const.CHANNEL_MOMENT, feed_const.CHANNEL_MIN_INTERVAL_SECONDS)

    def test_emit_is_a_no_op_without_a_subscriber(self):
        self.assertEqual(
            0, feed.emit_moment(self.char1, feed_const.MOMENT_TASK_COMPLETE))

    def test_an_object_with_no_sessions_is_a_no_op(self):
        self.assertEqual(
            0, feed.emit_moment(object(), feed_const.MOMENT_TASK_COMPLETE))


class TestEmit(_MomentTest):
    """What reaches a subscribed client."""

    def setUp(self):
        super().setUp()
        self._subscribe()

    def test_each_moment_reaches_the_client_by_name(self):
        for moment in feed_const.MOMENTS:
            with self.subTest(moment=moment):
                sent = self._sent(lambda: feed.emit_moment(self.char1, moment))

                self.assertEqual(1, len(sent))
                self.assertEqual(moment, sent[0]["moment"])

    def test_an_unknown_name_is_refused(self):
        with mock.patch.object(feed.logger, "log_err") as logged:
            sent = self._sent(lambda: feed.emit_moment(self.char1, _UNKNOWN_MOMENT))

        self.assertEqual([], sent)
        self.assertTrue(logged.called)

    def test_the_last_task_kill_sends_the_task_complete_moment(self):
        handler = self.char1.exterminator
        assigned, _message = handler.assign(
            PRECEPTOR_ATTICUS_QUIN, rng=random.Random(_SEED))
        self.assertTrue(assigned)

        types = (handler.creature_type(),)
        kills_before_last = handler.total() - 1

        before_last = self._sent(
            lambda: [handler.record_kill(types, 0) for _kill in range(kills_before_last)])
        last = self._sent(lambda: handler.record_kill(types, 0))

        self.assertEqual([], before_last)
        self.assertEqual(
            [feed_const.MOMENT_TASK_COMPLETE], [body["moment"] for body in last])
