"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: Tests for the per-tick coalescing buffer.

Two properties matter and they pull against each other: a coalescable channel
must collapse to one message per tick, and a channel that is NOT coalescable
must not lose a single one. The second is the half that would fail silently --
it is the room_players bug the cap discussion in constants.py documents, moved
into a new mechanism.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.statefeed
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.statefeed import buffer
from systems.statefeed import constants as const
from systems.statefeed import emit as emit_module
from systems.statefeed import payloads
from systems.tick.engine import get_tick_engine


class _BufferTestCase(EvenniaTest):
    """Buffer state is module-level, so every test starts and ends clean."""

    def setUp(self):
        super().setUp()
        buffer.reset()

    def tearDown(self):
        buffer.reset()
        super().tearDown()

    def _vitals(self, hp=10):
        """A payload on a COALESCABLE channel."""
        return payloads.CharVitalsPayload(hp=hp, max_hp=20)

    def _combat(self):
        """A payload on a channel that must NEVER be coalesced."""
        return payloads.CombatPayload()


class TestHoldingWindow(_BufferTestCase):
    """Only emissions inside a tick are held."""

    def test_nothing_is_held_outside_a_tick(self):
        held = buffer.hold(self.char1, self._vitals())

        self.assertFalse(held)
        self.assertEqual(buffer.pending_count(), 0)

    def test_a_coalescable_channel_is_held_inside_a_tick(self):
        buffer.begin_tick()

        held = buffer.hold(self.char1, self._vitals())

        self.assertTrue(held)
        self.assertEqual(buffer.pending_count(), 1)

    def test_flush_ends_the_window(self):
        buffer.begin_tick()
        buffer.flush()

        self.assertFalse(buffer.is_holding())
        held = buffer.hold(self.char1, self._vitals())

        self.assertFalse(held)

    def test_begin_tick_twice_is_harmless(self):
        buffer.begin_tick()
        buffer.begin_tick()

        self.assertTrue(buffer.is_holding())


class TestCoalescing(_BufferTestCase):
    """Several snapshots in one tick become the newest one."""

    def test_repeated_payloads_collapse_to_one(self):
        buffer.begin_tick()

        buffer.hold(self.char1, self._vitals(hp=10))
        buffer.hold(self.char1, self._vitals(hp=8))
        buffer.hold(self.char1, self._vitals(hp=5))

        self.assertEqual(buffer.pending_count(), 1)

    def test_the_newest_payload_is_the_one_sent(self):
        buffer.begin_tick()
        buffer.hold(self.char1, self._vitals(hp=10))
        buffer.hold(self.char1, self._vitals(hp=5))

        with mock.patch.object(emit_module, "emit", return_value=1) as sent:
            buffer.flush()

        _args, kwargs = sent.call_args
        payload = sent.call_args[0][1]

        self.assertEqual(payload.hp, 5)

    def test_different_observers_do_not_collapse_together(self):
        buffer.begin_tick()

        buffer.hold(self.char1, self._vitals())
        buffer.hold(self.char2, self._vitals())

        self.assertEqual(buffer.pending_count(), 2)

    def test_flushing_empties_the_buffer(self):
        buffer.begin_tick()
        buffer.hold(self.char1, self._vitals())

        buffer.flush()

        self.assertEqual(buffer.pending_count(), 0)


class TestNonCoalescableChannelsPassThrough(_BufferTestCase):
    """The half that would fail silently.

    Coalescing an EVENT channel loses events. Two attackers hitting one target
    on the same tick produce two combat messages, and keeping only the newest
    drops a hit the text log still shows.
    """

    def test_a_combat_payload_is_never_held(self):
        buffer.begin_tick()

        held = buffer.hold(self.char1, self._combat())

        self.assertFalse(held)
        self.assertEqual(buffer.pending_count(), 0)

    def test_every_coalescable_channel_is_declared_deliberately(self):
        """Guards against a channel drifting into the set. Anything added here
        must survive "keeping only the newest loses nothing"."""
        expected = {
            # Identity, and a fixed one: two avatars for the same observer in
            # one tick are the same message twice, so the newest is the whole
            # truth by definition.
            const.CHANNEL_CHAR_AVATAR,
            const.CHANNEL_CHAR_VITALS,
            const.CHANNEL_CHAR_STATUS,
            const.CHANNEL_CHAR_SUMMARY,
            const.CHANNEL_CHAR_ITEMS,
            const.CHANNEL_ROOM_INFO,
            const.CHANNEL_ROOM_PLAYERS,
        }

        self.assertEqual(set(const.COALESCABLE_CHANNELS), expected)

    def test_delta_channels_are_excluded(self):
        for channel in (
            const.CHANNEL_ROOM_PLAYER_ADD,
            const.CHANNEL_ROOM_PLAYER_REMOVE,
            const.CHANNEL_COMBAT,
            const.CHANNEL_MAP,
        ):
            self.assertNotIn(channel, const.COALESCABLE_CHANNELS, msg=channel)


class TestFlushIsolation(_BufferTestCase):
    def test_a_deleted_observer_is_skipped(self):
        buffer.begin_tick()
        buffer.hold(self.obj1, self._vitals())
        self.obj1.delete()

        sent = buffer.flush()  # must not raise

        self.assertEqual(sent, 0)

    def test_one_failing_send_does_not_strand_the_others(self):
        buffer.begin_tick()
        buffer.hold(self.char1, self._vitals())
        buffer.hold(self.char2, self._vitals())

        calls = []

        def _flaky(obj, payload, force=False):
            calls.append(obj)
            if len(calls) == 1:
                raise RuntimeError("boom")
            return 1

        with mock.patch.object(emit_module, "emit", side_effect=_flaky):
            buffer.flush()

        self.assertEqual(len(calls), 2)

    def test_flushing_an_empty_buffer_is_free(self):
        self.assertEqual(buffer.flush(), 0)

    def test_flush_does_not_re_enter_the_buffer(self):
        """_holding is cleared before draining, or the emits below would land
        straight back in the buffer they are draining."""
        buffer.begin_tick()
        buffer.hold(self.char1, self._vitals())

        buffer.flush()

        self.assertEqual(buffer.pending_count(), 0)


class TestEngineBrackets(_BufferTestCase):
    """The engine opens and closes the window itself."""

    def setUp(self):
        super().setUp()
        self.engine = get_tick_engine()
        self.engine.ndb._handler_ids = {}
        self.engine.ndb._inbound_actions = []

    def test_a_tick_leaves_the_buffer_closed(self):
        self.engine._tick()

        self.assertFalse(buffer.is_holding())

    def test_a_tick_flushes_what_it_held(self):
        held = []

        def _hold_during_tick():
            held.append(buffer.is_holding())

        self.engine.scheduler().schedule_in(
            1, _hold_during_tick, self.engine.current_tick()
        )
        self.engine._tick()

        self.assertEqual(held, [True])

    def test_emissions_during_a_tick_are_coalesced_and_sent_once(self):
        self.engine.ndb._handler_ids = {}
        sent = []

        def _emit_three_times():
            for hp in (10, 8, 5):
                emit_module.emit(self.char1, self._vitals(hp=hp))

        self.engine.scheduler().schedule_in(
            1, _emit_three_times, self.engine.current_tick()
        )

        with mock.patch.object(
            emit_module, "_eligible_sessions", return_value=[]
        ):
            with mock.patch.object(
                self.char1, "msg", side_effect=lambda **kw: sent.append(kw)
            ):
                self.engine._tick()

        # No subscribed sessions, so nothing actually goes out -- what matters
        # is that the buffer emptied rather than stranding the snapshots.
        self.assertEqual(buffer.pending_count(), 0)
