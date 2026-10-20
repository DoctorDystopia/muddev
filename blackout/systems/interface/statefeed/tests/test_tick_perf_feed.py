"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/16/2026
Description: Cases for the blackout_tick_perf channel: one reading of the
             server tick for each session that asked for it.

             The load-bearing cases are the opt-in rule (SUBSCRIBE_ALL
             leaves the channel out) and the wiring (a real `_tick` sends
             one reading, from PHASE_END, after the engine recorded the
             duration). The engine's `_tick` is driven directly, as
             test_engine.py drives it, so no case waits on a clock.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.statefeed.tests.test_tick_perf_feed
"""

from dataclasses import fields
from types import SimpleNamespace
from unittest import mock

from evennia import SESSION_HANDLER
from evennia.utils.test_resources import EvenniaTestCase

from systems.core.tick import constants as tick_const
from systems.core.tick import debug as tick_debug
from systems.core.tick import engine as tick_engine
from systems.interface.statefeed import constants as const
from systems.interface.statefeed import performance, subscriptions
from systems.interface.statefeed.payloads import TickPerfPayload


# ─── Private helper routines ─────────────────────────────────────────────────

class _FakeSession:
    """A stand-in session that records what the feed sent it."""

    def __init__(self):
        self.ndb = SimpleNamespace()
        self.sent = []

    def msg(self, **kwargs):
        self.sent.append(kwargs)


class _RaisingSession(_FakeSession):
    """A session whose socket is gone."""

    def msg(self, **kwargs):
        raise RuntimeError("socket closed")


def _readings(session) -> list:
    """The body of each tick reading that a fake session got."""
    return [
        kwargs[const.CHANNEL_TICK_PERF]
        for kwargs in session.sent
        if const.CHANNEL_TICK_PERF in kwargs
    ]


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestChannel(EvenniaTestCase):
    """The declaration of the channel, which decides who gets it."""

    def test_a_client_may_subscribe_to_it(self):
        self.assertIn(const.CHANNEL_TICK_PERF, const.SUBSCRIBABLE_CHANNELS)

    def test_it_is_opt_in(self):
        self.assertIn(const.CHANNEL_TICK_PERF, const.OPT_IN_CHANNELS)
        self.assertNotIn(const.CHANNEL_TICK_PERF, const.DEFAULT_CHANNELS)

    def test_every_opt_in_channel_is_subscribable(self):
        for channel in const.OPT_IN_CHANNELS:
            with self.subTest(channel=channel):
                self.assertIn(channel, const.SUBSCRIBABLE_CHANNELS)

    def test_the_default_set_is_the_rest(self):
        expected = const.SUBSCRIBABLE_CHANNELS - const.OPT_IN_CHANNELS

        self.assertEqual(const.DEFAULT_CHANNELS, expected)

    def test_subscribe_all_leaves_it_out(self):
        # 100 messages a minute, to a client that may never draw them.
        session = _FakeSession()

        accepted = subscriptions.subscribe(session, const.SUBSCRIBE_ALL)

        self.assertNotIn(const.CHANNEL_TICK_PERF, accepted)

    def test_a_client_takes_it_by_name(self):
        session = _FakeSession()
        subscriptions.subscribe(session, const.SUBSCRIBE_ALL)

        accepted = subscriptions.subscribe(session, const.CHANNEL_TICK_PERF)

        self.assertIn(const.CHANNEL_TICK_PERF, accepted)
        self.assertTrue(const.DEFAULT_CHANNELS <= accepted)

    def test_channel_is_never_coalesced(self):
        # An event: each message is one tick, and a graph with a gap lies.
        self.assertNotIn(const.CHANNEL_TICK_PERF, const.COALESCABLE_CHANNELS)

    def test_channel_is_not_rate_capped(self):
        self.assertNotIn(const.CHANNEL_TICK_PERF, const.CHANNEL_MIN_INTERVAL_SECONDS)


class _FeedTest(EvenniaTestCase):
    """Shared fixture: an engine with an empty rotation, and fake sessions in
    place of the session handler's."""

    def setUp(self):
        super().setUp()
        self.engine = tick_engine.get_tick_engine()
        self.engine.ndb._handler_ids = {}
        self.engine.ndb._handler_strikes = {}
        self.sessions = []

        patcher = mock.patch.object(
            SESSION_HANDLER, "get_sessions", side_effect=lambda: list(self.sessions))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _subscribed(self, session=None):
        """Add a fake session that subscribes to the channel."""
        if session is None:
            session = _FakeSession()

        subscriptions.subscribe(session, const.CHANNEL_TICK_PERF)
        self.sessions.append(session)

        return session

    def _bystander(self):
        """Add a fake session that subscribes to everything else."""
        session = _FakeSession()
        subscriptions.subscribe(session, const.SUBSCRIBE_ALL)
        self.sessions.append(session)

        return session


class TestPayload(_FeedTest):
    """What one reading says."""

    def test_the_reading_is_the_timing_the_engine_recorded(self):
        self.engine._tick()

        payload = performance.build_payload(self.engine)

        self.assertEqual(payload.tick, self.engine.ndb.tick_number)
        self.assertEqual(payload.interval, self.engine.ndb.tick_interval)
        self.assertEqual(payload.duration, self.engine.ndb.tick_duration)
        self.assertEqual(payload.handlers, self.engine.registered_count())
        self.assertEqual(payload.failing, self.engine.failing_count())

    def test_a_nominal_interval_is_not_late(self):
        self.engine.ndb.tick_interval = tick_const.TICK_SECONDS

        payload = performance.build_payload(self.engine)

        self.assertFalse(payload.late)

    def test_the_late_rule_is_the_tickdebug_rule(self):
        # One owner for "what counts as late".
        self.engine.ndb.tick_interval = tick_debug.late_threshold() * 2

        payload = performance.build_payload(self.engine)

        self.assertTrue(payload.late)

    def test_a_reading_before_the_first_tick_is_valid(self):
        self.engine.ndb.tick_number = None
        self.engine.ndb.tick_interval = None
        self.engine.ndb.tick_duration = None

        payload = performance.build_payload(self.engine)

        self.assertEqual(payload.tick, 0)
        self.assertFalse(payload.late)

    def test_every_field_is_json_safe(self):
        self.engine._tick()
        body = performance.build_payload(self.engine).to_dict()

        for entry in fields(TickPerfPayload):
            with self.subTest(field=entry.name):
                self.assertIsInstance(body[entry.name], (int, float, bool))


class TestEmit(_FeedTest):
    """Who gets a reading, and who pays for one."""

    def test_no_subscriber_builds_nothing(self):
        self._bystander()

        with mock.patch.object(performance, "build_payload") as built:
            sent = performance.emit_tick_perf(self.engine)

        self.assertEqual(sent, 0)
        built.assert_not_called()

    def test_a_subscribed_session_gets_the_reading(self):
        session = self._subscribed()
        self.engine._tick()
        session.sent.clear()

        sent = performance.emit_tick_perf(self.engine)

        self.assertEqual(sent, 1)
        self.assertEqual(len(_readings(session)), 1)
        self.assertEqual(_readings(session)[0]["tick"], self.engine.ndb.tick_number)

    def test_a_bystander_beside_a_subscriber_gets_nothing(self):
        subscriber = self._subscribed()
        bystander = self._bystander()

        performance.emit_tick_perf(self.engine)

        self.assertEqual(len(_readings(subscriber)), 1)
        self.assertEqual(_readings(bystander), [])

    def test_a_dead_socket_does_not_raise(self):
        self._subscribed(_RaisingSession())

        with mock.patch.object(performance.logger, "log_trace") as logged:
            sent = performance.emit_tick_perf(self.engine)

        self.assertEqual(sent, 0)
        self.assertTrue(logged.called)


class TestWiring(_FeedTest):
    """The hook on the engine, and where in the tick it fires."""

    def test_the_hook_is_on_the_end_phase(self):
        self.assertIn(performance.on_tick_end, tick_engine._PHASE_HOOKS[tick_engine.PHASE_END])

    def test_attach_registers_one_hook_for_each_process(self):
        before = list(tick_engine._PHASE_HOOKS[tick_engine.PHASE_END])

        performance.attach()

        self.assertEqual(tick_engine._PHASE_HOOKS[tick_engine.PHASE_END], before)

    def test_a_tick_sends_one_reading(self):
        session = self._subscribed()

        self.engine._tick()

        self.assertEqual(len(_readings(session)), 1)
        self.assertEqual(_readings(session)[0]["tick"], self.engine.ndb.tick_number)

    def test_the_end_phase_fires_after_the_duration_is_recorded(self):
        # The send is outside the number that it reports.
        self.engine.ndb.tick_duration = None
        seen = []

        def probe():
            seen.append(self.engine.ndb.tick_duration)

        tick_engine.register_phase_hook(tick_engine.PHASE_END, probe)
        self.addCleanup(tick_engine._PHASE_HOOKS[tick_engine.PHASE_END].remove, probe)

        self.engine._tick()

        self.assertEqual(len(seen), 1)
        self.assertIsNotNone(seen[0])

    def test_the_end_phase_fires_after_the_feed_phase(self):
        order = []

        def feed_probe():
            order.append(tick_engine.PHASE_FEED)

        def end_probe():
            order.append(tick_engine.PHASE_END)

        tick_engine.register_phase_hook(tick_engine.PHASE_FEED, feed_probe)
        tick_engine.register_phase_hook(tick_engine.PHASE_END, end_probe)
        self.addCleanup(tick_engine._PHASE_HOOKS[tick_engine.PHASE_FEED].remove, feed_probe)
        self.addCleanup(tick_engine._PHASE_HOOKS[tick_engine.PHASE_END].remove, end_probe)

        self.engine._tick()

        self.assertEqual(order, [tick_engine.PHASE_FEED, tick_engine.PHASE_END])
