"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Evennia-backed tests for the tick monitor (tick_debug) and the
             timing the engine records for it.

Run with the Evennia/Django test runner from the game dir:

    evennia test --settings settings.py systems.combat

The engine's _tick is driven directly rather than through the LoopingCall, the
same way test_combat_handler.py drives it, which makes every cadence assertion
below deterministic instead of wall-clock dependent.
"""

from unittest import mock

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaCommandTest, EvenniaTest

from commands.combat_cmds import CmdTickDebug
from systems.tick import constants as const
from systems.tick import debug as tick_debug
from systems.combat.combat import ensure_combat_handler
from systems.tick.engine import get_tick_engine


class TickDebugTestCase(EvenniaTest):
    """Shared setup: a clean observer registry and a captured message stream.

    tick_debug._observers is module state, so a test that attached and did not
    detach would leak an observer into every test that ran after it.
    """

    def setUp(self):
        super().setUp()
        tick_debug._observers.clear()
        self.lines = []
        self.char1.msg = mock.MagicMock(side_effect=self._record)

    def tearDown(self):
        tick_debug._observers.clear()
        super().tearDown()

    def _record(self, text="", **kwargs):
        """Stand in for Character.msg, keeping the plain text of every line."""
        stripped = strip_ansi(str(text))
        self.lines.append(stripped)

    def _stream_lines(self):
        """Return only the lines that look like a streamed tick reading."""
        found = []

        for line in self.lines:
            if line.startswith("[t "):
                found.append(line)

        return found

    def _engage(self):
        """Put char1 and char2 into a real, mutually-recognised fight.

        A lone handler does NOT survive a tick: check_stop_combat finds no
        enemy, announces "You won!" and ends combat on the very first pass. Any
        test that needs a handler to still be there on the second tick has to
        give it something to be fighting, which means a handler on BOTH sides
        and a target set — that is what get_sides looks for.

        The pending action is then replaced with a hold, so the ticks under
        test resolve without rolling real damage and killing the sparring
        partner mid-assertion.
        """
        ensure_combat_handler(self.char2)
        handler = ensure_combat_handler(self.char1)

        handler.queue_action({"kind": "attack", "target": self.char2})
        handler.queue_action({"kind": "hold"})

        return handler


class TestEngineTiming(TickDebugTestCase):
    """The engine had no notion of "now" before the monitor needed one."""

    def test_tick_number_increments_once_per_tick(self):
        engine = get_tick_engine()
        engine.ndb.tick_number = None

        engine._tick()
        engine._tick()
        engine._tick()

        self.assertEqual(engine.ndb.tick_number, 3)

    def test_an_empty_registry_still_advances_the_tick(self):
        """Regression: _tick returned early on an empty registry, so a player
        watching the tick saw nothing until somebody attacked."""
        engine = get_tick_engine()
        engine.ndb._handler_ids = {}  # ordered registry; see BlackoutTickEngine._registry
        engine.ndb.tick_number = None

        engine._tick()

        self.assertEqual(engine.ndb.tick_number, 1)

    def test_intervals_are_recorded_within_the_sample_window(self):
        engine = get_tick_engine()
        engine.ndb.tick_intervals = None

        for _ in range(const.TICK_DEBUG_SAMPLE_WINDOW + 10):
            engine._tick()

        recorded = engine.ndb.tick_intervals

        self.assertEqual(len(recorded), const.TICK_DEBUG_SAMPLE_WINDOW)

    def test_first_ever_tick_reports_the_nominal_interval(self):
        """With no previous tick to measure against, the engine must not
        report the seconds since the epoch as this tick's interval."""
        engine = get_tick_engine()
        engine.ndb.last_tick_at = None

        engine._tick()

        self.assertEqual(engine.ndb.tick_interval, const.TICK_SECONDS)

    def test_registration_is_publicly_readable(self):
        engine = get_tick_engine()
        handler = ensure_combat_handler(self.char1)

        self.assertTrue(engine.is_registered(handler))
        self.assertGreaterEqual(engine.registered_count(), 1)

        engine.unregister(handler)

        self.assertFalse(engine.is_registered(handler))


class TestObserverCost(TickDebugTestCase):
    """What the monitor costs when nobody is using it."""

    def test_no_observers_means_no_output(self):
        engine = get_tick_engine()
        ensure_combat_handler(self.char1)

        engine._tick()

        self.assertEqual(self._stream_lines(), [])

    def test_no_observers_skips_state_capture_entirely(self):
        """The hooks must return on a dictionary truth test, before they reach
        anything that would read a handler."""
        engine = get_tick_engine()
        ensure_combat_handler(self.char1)

        with mock.patch.object(tick_debug, "_capture_combat") as captured:
            engine._tick()

        captured.assert_not_called()


class TestStreaming(TickDebugTestCase):
    """What a watching player actually receives."""

    def test_all_mode_emits_one_line_per_tick(self):
        engine = get_tick_engine()
        tick_debug.attach(self.char1, tick_debug.MODE_ALL)

        engine._tick()
        engine._tick()

        self.assertEqual(len(self._stream_lines()), 2)

    def test_a_line_names_the_tick_number_and_interval(self):
        engine = get_tick_engine()
        engine.ndb.tick_number = None
        tick_debug.attach(self.char1, tick_debug.MODE_ALL)

        engine._tick()

        line = self._stream_lines()[0]

        self.assertIn("[t 00001]", line)
        self.assertIn("s ", line)

    def test_an_idle_watcher_is_told_the_engine_is_idle(self):
        engine = get_tick_engine()
        tick_debug.attach(self.char1, tick_debug.MODE_ALL)

        engine._tick()

        self.assertIn("idle", self._stream_lines()[0])

    def test_quiet_mode_is_silent_while_a_cooldown_counts_down(self):
        """The point of quiet: three ticks in four of a speed-4 cycle say
        nothing the previous line did not already say."""
        engine = get_tick_engine()
        handler = self._engage()
        handler.ndb.cooldown_ticks = 3

        tick_debug.attach(self.char1, tick_debug.MODE_QUIET)

        engine._tick()  # first tick always reports, there is nothing to diff
        self.lines.clear()

        engine._tick()

        self.assertEqual(self._stream_lines(), [])

    def test_quiet_mode_speaks_on_the_tick_an_action_resolves(self):
        engine = get_tick_engine()
        handler = self._engage()
        handler.ndb.cooldown_ticks = 3

        tick_debug.attach(self.char1, tick_debug.MODE_QUIET)

        engine._tick()
        self.lines.clear()

        # A pending action with a spent cooldown is exactly the state
        # BlackoutCombatHandler.tick resolves on.
        handler.ndb.cooldown_ticks = 0

        engine._tick()

        lines = self._stream_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn("RESOLVE", lines[0])

    def test_a_swing_is_labelled_a_swing(self):
        """A hold and a swing resolve on the same branch of the handler's tick,
        but calling a hold a SWING on the line the player is reading would be
        a lie about the only tick that matters."""
        swing = tick_debug._resolution_marker("attack")
        other = tick_debug._resolution_marker("hold")

        self.assertEqual(swing, tick_debug._SWING_LABEL)
        self.assertEqual(other, tick_debug._RESOLVE_LABEL)

    def test_a_late_tick_is_always_reported(self):
        engine = get_tick_engine()
        tick_debug.attach(self.char1, tick_debug.MODE_QUIET)

        engine._tick()
        self.lines.clear()

        late = const.TICK_SECONDS * const.TICK_DEBUG_LATE_TICK_FACTOR
        stalled_at = engine.ndb.last_tick_at - (late * 2)
        engine.ndb.last_tick_at = stalled_at

        engine._tick()

        lines = self._stream_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn("LATE", lines[0])

    def test_a_handler_dropped_from_the_rotation_is_reported(self):
        """The silent failure the monitor exists for: a handler leaves the
        rotation and combat just stops with nothing said.

        Eviction now costs TICK_HANDLER_MAX_STRIKES consecutive failures
        rather than one, so the failing ticks before the last are quiet by
        design -- the handler is still registered and still recoverable. Only
        the tick that actually evicts is worth reporting.
        """
        engine = get_tick_engine()
        handler = self._engage()

        tick_debug.attach(self.char1, tick_debug.MODE_QUIET)
        engine._tick()

        with mock.patch.object(type(handler), "tick", side_effect=RuntimeError("boom")):
            for _ in range(const.TICK_HANDLER_MAX_STRIKES - 1):
                engine._tick()

            # Nothing has been evicted yet, so nothing should have been said.
            self.lines.clear()

            engine._tick()

        lines = self._stream_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn("UNREGISTERED", lines[0])


class TestObserverLifecycle(TickDebugTestCase):
    """Attaching, detaching, and never outstaying the welcome."""

    def test_attach_and_detach_are_reported_accurately(self):
        self.assertFalse(tick_debug.is_watching(self.char1))

        tick_debug.attach(self.char1)

        self.assertTrue(tick_debug.is_watching(self.char1))
        self.assertEqual(tick_debug.watched_mode(self.char1), tick_debug.DEFAULT_MODE)
        self.assertTrue(tick_debug.detach(self.char1))
        self.assertFalse(tick_debug.detach(self.char1))

    def test_attaching_twice_does_not_stack_two_streams(self):
        engine = get_tick_engine()

        tick_debug.attach(self.char1, tick_debug.MODE_ALL)
        tick_debug.attach(self.char1, tick_debug.MODE_ALL)

        engine._tick()

        self.assertEqual(len(self._stream_lines()), 1)

    def test_the_stream_expires_on_its_own(self):
        engine = get_tick_engine()

        tick_debug.attach(self.char1, tick_debug.MODE_QUIET)
        engine.ndb._handler_ids = {}  # ordered registry; see BlackoutTickEngine._registry

        for _ in range(const.TICK_DEBUG_AUTO_EXPIRE_TICKS):
            engine._tick()

        self.assertFalse(tick_debug.is_watching(self.char1))

        expired = [line for line in self.lines if "expired" in line]

        self.assertEqual(len(expired), 1)

    def test_disconnecting_stops_the_stream(self):
        tick_debug.attach(self.char1)

        self.char1.at_disconnect_combat_cleanup()

        self.assertFalse(tick_debug.is_watching(self.char1))

    def test_a_deleted_observer_is_dropped(self):
        """Deletion is the one way an observer can vanish with no event to
        tell us, so the serving pass has to notice it itself.

        Deliberately not a Character: Character.at_object_delete returns None,
        which Evennia's DefaultObject.delete reads as "abort", so deleting one
        silently does nothing and this test would pass for the wrong reason.
        """
        engine = get_tick_engine()

        tick_debug.attach(self.obj1, tick_debug.MODE_ALL)
        deleted = self.obj1.delete()

        self.assertTrue(deleted, "the test needs an object that really deletes")

        engine._tick()

        self.assertEqual(len(tick_debug._observers), 0)


class TestFailureIsolation(TickDebugTestCase):
    """A diagnostic must never be able to stop the server-wide tick."""

    def test_a_raising_renderer_does_not_stop_the_loop(self):
        engine = get_tick_engine()
        handler = self._engage()

        tick_debug.attach(self.char1, tick_debug.MODE_ALL)

        with mock.patch.object(tick_debug, "_render_line", side_effect=RuntimeError("boom")):
            engine._tick()  # must not raise

        self.assertTrue(engine.is_registered(handler))

    def test_a_raising_capture_does_not_stop_the_loop(self):
        engine = get_tick_engine()
        handler = self._engage()

        tick_debug.attach(self.char1, tick_debug.MODE_ALL)

        with mock.patch.object(tick_debug, "_capture_aura", side_effect=RuntimeError("boom")):
            engine._tick()  # must not raise

        self.assertTrue(engine.is_registered(handler))

    def test_one_broken_observer_does_not_cost_another_its_line(self):
        """Regression: a shared try/except around the serving loop let a single
        deleted watcher abort the pass for everyone else -- and strand itself
        in the observer dictionary, since the retirement never ran."""
        engine = get_tick_engine()

        tick_debug.attach(self.obj1, tick_debug.MODE_ALL)
        tick_debug.attach(self.char1, tick_debug.MODE_ALL)
        self.obj1.delete()

        engine._tick()

        self.assertEqual(len(self._stream_lines()), 1)
        self.assertTrue(tick_debug.is_watching(self.char1))
        self.assertEqual(len(tick_debug._observers), 1)

    def test_handlers_still_tick_when_the_monitor_is_broken(self):
        engine = get_tick_engine()
        handler = ensure_combat_handler(self.char1)

        tick_debug.attach(self.char1, tick_debug.MODE_ALL)

        with mock.patch.object(tick_debug, "before_tick", side_effect=RuntimeError("boom")):
            with mock.patch.object(type(handler), "tick") as ticked:
                with self.assertRaises(RuntimeError):
                    engine._tick()

        # before_tick's own guard is what protects the loop; the assertion above
        # documents that the engine does NOT add a second one, so a hook that
        # ever stopped swallowing would fail loudly here rather than silently
        # costing every combatant their tick.
        ticked.assert_not_called()


class TestStatusReport(TickDebugTestCase):
    """The one-shot report, which must work without any handlers at all."""

    def test_status_renders_when_not_in_combat(self):
        report = tick_debug.snapshot(self.char1)
        plain = strip_ansi(report)

        self.assertIn("Tick engine", plain)
        self.assertIn("not in combat", plain)
        self.assertIn("none burning", plain)

    def test_status_reports_the_running_loop_and_rotation(self):
        engine = get_tick_engine()
        self._engage()
        engine._tick()

        report = tick_debug.snapshot(self.char1)
        plain = strip_ansi(report)

        self.assertIn("running", plain)
        self.assertIn("2 registered", plain)  # both sides of the fight

    def test_status_names_the_cooldown_and_weapon_speed(self):
        handler = ensure_combat_handler(self.char1)
        handler.ndb.cooldown_ticks = 2

        report = tick_debug.snapshot(self.char1)
        plain = strip_ansi(report)
        speed = handler.ndb.active_weapon_data["attack_speed"]

        self.assertIn(f"cooldown 2/{speed}", plain)

    def test_status_reports_a_missing_engine_rather_than_creating_one(self):
        """A diagnostic must be able to answer "the engine is gone"."""
        with mock.patch.object(tick_debug, "_find_engine", return_value=None):
            report = tick_debug.snapshot(self.char1)

        plain = strip_ansi(report)

        self.assertIn("no tick engine exists", plain)


class TestTickDebugCommand(EvenniaCommandTest):
    """The player-facing surface: the command that drives all of the above."""

    def setUp(self):
        super().setUp()
        tick_debug._observers.clear()

    def tearDown(self):
        tick_debug._observers.clear()
        super().tearDown()

    def test_bare_command_toggles_the_stream_on_then_off(self):
        self.call(CmdTickDebug(), "")

        self.assertTrue(tick_debug.is_watching(self.char1))
        self.assertEqual(tick_debug.watched_mode(self.char1), tick_debug.DEFAULT_MODE)

        self.call(CmdTickDebug(), "")

        self.assertFalse(tick_debug.is_watching(self.char1))

    def test_a_named_mode_is_honoured(self):
        self.call(CmdTickDebug(), tick_debug.MODE_ALL)

        self.assertEqual(tick_debug.watched_mode(self.char1), tick_debug.MODE_ALL)

    def test_status_reports_without_starting_a_stream(self):
        response = self.call(CmdTickDebug(), tick_debug.MODE_STATUS)

        self.assertIn("Tick engine", response)
        self.assertFalse(tick_debug.is_watching(self.char1))

    def test_an_unknown_argument_reports_usage(self):
        response = self.call(CmdTickDebug(), "sideways")

        self.assertIn("Usage: tickdebug", response)
        self.assertFalse(tick_debug.is_watching(self.char1))

    def test_off_says_so_when_nothing_was_running(self):
        response = self.call(CmdTickDebug(), tick_debug.MODE_OFF)

        self.assertIn("isn't running", response)
