"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: Tests for TickScheduler — deferred work keyed on absolute tick
             number — and for the engine running it once per tick.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.tick
"""

import unittest
from unittest import mock

from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.tick import constants as const
from systems.tick.engine import get_tick_engine
from systems.tick.scheduler import NO_HANDLE, TickScheduler, seconds_to_ticks


# Public constant definitions

START_TICK = 100
SHORT_DELAY = 3


class TestSecondsToTicks(unittest.TestCase):
    """Callers keep expressing intent in seconds; the engine works in ticks."""

    def test_one_tick_of_seconds_is_one_tick(self):
        self.assertEqual(seconds_to_ticks(const.TICK_SECONDS), 1)

    def test_a_minute_is_a_hundred_ticks(self):
        # The vault states regen as "1 HP per minute"; at 0.6s that is 100.
        self.assertEqual(seconds_to_ticks(60), 100)

    def test_a_fractional_interval_rounds_rather_than_truncates(self):
        # 2s / 0.6s = 3.33 -> 3, not truncated toward a different answer by
        # accident.
        self.assertEqual(seconds_to_ticks(2), 3)

    def test_zero_still_produces_a_future_tick(self):
        """Scheduling "now" would file into a bucket already popped."""
        self.assertGreaterEqual(seconds_to_ticks(0), 1)


class TestSchedulerBasics(unittest.TestCase):
    """Pure logic -- no database needed."""

    def setUp(self):
        self.scheduler = TickScheduler()
        self.fired = []

    def _record(self, label):
        return lambda: self.fired.append(label)

    def test_a_callback_fires_on_its_due_tick(self):
        self.scheduler.schedule_at(START_TICK, self._record("a"))

        self.scheduler.run_due(START_TICK)

        self.assertEqual(self.fired, ["a"])

    def test_a_callback_does_not_fire_early(self):
        self.scheduler.schedule_at(START_TICK, self._record("a"))

        self.scheduler.run_due(START_TICK - 1)

        self.assertEqual(self.fired, [])

    def test_a_callback_fires_exactly_once(self):
        self.scheduler.schedule_at(START_TICK, self._record("a"))

        self.scheduler.run_due(START_TICK)
        self.scheduler.run_due(START_TICK)

        self.assertEqual(self.fired, ["a"])

    def test_schedule_in_lands_the_requested_distance_out(self):
        self.scheduler.schedule_in(SHORT_DELAY, self._record("a"), now=START_TICK)

        self.scheduler.run_due(START_TICK + SHORT_DELAY - 1)
        self.assertEqual(self.fired, [])

        self.scheduler.run_due(START_TICK + SHORT_DELAY)
        self.assertEqual(self.fired, ["a"])

    def test_a_zero_delay_is_pushed_to_the_next_tick(self):
        """A callback running during tick N cannot schedule INTO tick N --
        that bucket has already been popped."""
        self.scheduler.schedule_in(0, self._record("a"), now=START_TICK)

        self.scheduler.run_due(START_TICK)
        self.assertEqual(self.fired, [])

        self.scheduler.run_due(START_TICK + 1)
        self.assertEqual(self.fired, ["a"])

    def test_callbacks_due_together_fire_in_scheduling_order(self):
        self.scheduler.schedule_at(START_TICK, self._record("first"))
        self.scheduler.schedule_at(START_TICK, self._record("second"))

        self.scheduler.run_due(START_TICK)

        self.assertEqual(self.fired, ["first", "second"])

    def test_scheduling_nothing_yields_no_handle(self):
        handle = self.scheduler.schedule_at(START_TICK, None)

        self.assertEqual(handle, NO_HANDLE)


class TestCancellation(unittest.TestCase):
    def setUp(self):
        self.scheduler = TickScheduler()
        self.fired = []

    def test_a_cancelled_callback_never_fires(self):
        handle = self.scheduler.schedule_at(
            START_TICK, lambda: self.fired.append("a")
        )

        cancelled = self.scheduler.cancel(handle)
        self.scheduler.run_due(START_TICK)

        self.assertTrue(cancelled)
        self.assertEqual(self.fired, [])

    def test_cancelling_leaves_its_neighbours_alone(self):
        doomed = self.scheduler.schedule_at(
            START_TICK, lambda: self.fired.append("doomed")
        )
        self.scheduler.schedule_at(START_TICK, lambda: self.fired.append("kept"))

        self.scheduler.cancel(doomed)
        self.scheduler.run_due(START_TICK)

        self.assertEqual(self.fired, ["kept"])

    def test_cancelling_an_unknown_handle_is_harmless(self):
        self.assertFalse(self.scheduler.cancel(NO_HANDLE))
        self.assertFalse(self.scheduler.cancel(9999))

    def test_cancelling_after_firing_reports_nothing_cancelled(self):
        handle = self.scheduler.schedule_at(START_TICK, lambda: None)

        self.scheduler.run_due(START_TICK)

        self.assertFalse(self.scheduler.cancel(handle))


class TestIsolation(unittest.TestCase):
    """A callback must never take the tick down with it."""

    def setUp(self):
        self.scheduler = TickScheduler()
        self.fired = []

    def test_a_raising_callback_does_not_escape(self):
        self.scheduler.schedule_at(START_TICK, lambda: 1 / 0)

        # Must not raise. An exception here would errback the LoopingCall and
        # stop the tick for the whole server.
        self.scheduler.run_due(START_TICK)

    def test_a_raising_callback_does_not_stop_the_others(self):
        self.scheduler.schedule_at(START_TICK, lambda: 1 / 0)
        self.scheduler.schedule_at(START_TICK, lambda: self.fired.append("ok"))

        self.scheduler.run_due(START_TICK)

        self.assertEqual(self.fired, ["ok"])


class TestIntrospection(unittest.TestCase):
    def setUp(self):
        self.scheduler = TickScheduler()

    def test_pending_count_tracks_scheduling_and_firing(self):
        self.scheduler.schedule_at(START_TICK, lambda: None)
        self.scheduler.schedule_at(START_TICK + 1, lambda: None)

        self.assertEqual(self.scheduler.pending_count(), 2)

        self.scheduler.run_due(START_TICK)

        self.assertEqual(self.scheduler.pending_count(), 1)

    def test_next_due_tick_finds_the_earliest_live_entry(self):
        self.scheduler.schedule_at(START_TICK + 10, lambda: None)
        self.scheduler.schedule_at(START_TICK, lambda: None)

        self.assertEqual(self.scheduler.next_due_tick(), START_TICK)

    def test_next_due_tick_ignores_cancelled_entries(self):
        handle = self.scheduler.schedule_at(START_TICK, lambda: None)
        self.scheduler.schedule_at(START_TICK + 10, lambda: None)

        self.scheduler.cancel(handle)

        self.assertEqual(self.scheduler.next_due_tick(), START_TICK + 10)

    def test_an_idle_scheduler_has_nothing_due(self):
        self.assertIsNone(self.scheduler.next_due_tick())


class TestEngineIntegration(EvenniaTestCase):
    """The engine advances the scheduler once per tick."""

    def setUp(self):
        super().setUp()
        self.engine = get_tick_engine()
        self.engine.ndb._handler_ids = {}
        self.engine.ndb._scheduler = None

    def test_a_scheduled_callback_fires_on_a_later_tick(self):
        fired = []

        self.engine.schedule_in(SHORT_DELAY, lambda: fired.append("a"))

        for _ in range(SHORT_DELAY):
            self.engine._tick()

        self.assertEqual(fired, ["a"])

    def test_it_does_not_fire_before_its_delay_elapses(self):
        fired = []

        self.engine.schedule_in(SHORT_DELAY, lambda: fired.append("a"))

        for _ in range(SHORT_DELAY - 1):
            self.engine._tick()

        self.assertEqual(fired, [])

    def test_the_engine_can_cancel_scheduled_work(self):
        fired = []

        handle = self.engine.schedule_in(SHORT_DELAY, lambda: fired.append("a"))
        self.engine.cancel_scheduled(handle)

        for _ in range(SHORT_DELAY + 1):
            self.engine._tick()

        self.assertEqual(fired, [])

    def test_current_tick_advances_with_the_engine(self):
        self.engine.ndb.tick_number = None

        before = self.engine.current_tick()
        self.engine._tick()
        after = self.engine.current_tick()

        self.assertEqual(after, before + 1)

    def test_a_callback_may_schedule_more_work(self):
        """The re-arm pattern a repeating job needs. The new entry must land
        in a FUTURE bucket, never the one being drained."""
        fired = []

        def again():
            fired.append(len(fired))
            if len(fired) < 3:
                self.engine.schedule_in(1, again)

        self.engine.schedule_in(1, again)

        for _ in range(5):
            self.engine._tick()

        self.assertEqual(fired, [0, 1, 2])

    def test_a_raising_callback_does_not_stop_the_tick(self):
        self.engine.ndb.tick_number = None
        self.engine.schedule_in(1, lambda: 1 / 0)

        for _ in range(3):
            self.engine._tick()

        self.assertEqual(self.engine.current_tick(), 3)

    def test_handlers_run_before_deferred_work(self):
        """A callback due this tick must see what the handlers just did, not
        state they are halfway through changing."""
        order = []
        handler = mock.MagicMock()
        handler.tick = mock.MagicMock(side_effect=lambda: order.append("handler"))
        handler.pk = 1
        handler.id = 1

        self.engine.schedule_in(1, lambda: order.append("scheduled"))

        with mock.patch.object(
            self.engine, "_advance_one", side_effect=lambda _id: order.append("handler")
        ):
            self.engine.ndb._handler_ids = {1: None}
            self.engine._tick()

        self.assertEqual(order, ["handler", "scheduled"])
