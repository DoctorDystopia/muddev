"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: Tests for subscription filtering, rate capping, and the emit path.

             These use hand-built stand-ins rather than live Evennia objects on
             purpose. What is under test is the routing logic -- who gets a
             message and who does not -- and a stand-in lets a test assert on
             the exact kwargs handed to msg() without a Portal, an AMP
             connection, or a socket anywhere in the picture.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.statefeed
"""

import unittest
from types import SimpleNamespace

from systems.statefeed import constants as const
from systems.statefeed import subscriptions
from systems.statefeed.emit import emit, emit_to_room
from systems.statefeed.payloads import CharVitalsPayload, RoomInfoPayload


# ─── Private helper routines ─────────────────────────────────────────────────

def _make_session():
    """Return a stand-in Session with the ndb holder emit and subscriptions use."""
    return SimpleNamespace(ndb=SimpleNamespace())


class _FakeSessionHandler:
    """The minimum of Evennia's session handler that emit touches."""

    def __init__(self, sessions):
        self._sessions = sessions

    def all(self):
        return list(self._sessions)


class _FakeObserver:
    """An object with sessions that records what msg() was called with.

    `db_sessid` is derived from the sessions rather than hardcoded, because
    emit_to_room pre-filters occupants on that raw column before it will call
    emit() at all -- see emit._could_listen. A double that carried sessions but
    left the column empty would be a shape no real object has, and it would
    make a room broadcast test pass or fail for the wrong reason.
    """

    def __init__(self, sessions=(), obj_id=1):
        self.id = obj_id
        self.key = "Fake"
        self.sessions = _FakeSessionHandler(sessions)
        self.db_sessid = ",".join(str(index)
                                  for index, _ in enumerate(sessions, start=1))
        self.sent = []

    def msg(self, session=None, **kwargs):
        self.sent.append((session, kwargs))


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestSubscriptions(unittest.TestCase):
    """The opt-in that keeps the feed free for telnet players."""

    def setUp(self):
        self.session = _make_session()

    def test_a_fresh_session_is_subscribed_to_nothing(self):
        self.assertEqual(subscriptions.subscribed_channels(self.session), set())

    def test_subscribing_records_the_channel(self):
        subscriptions.subscribe(self.session, [const.CHANNEL_ROOM_INFO])

        self.assertTrue(
            subscriptions.is_subscribed(self.session, const.CHANNEL_ROOM_INFO)
        )

    def test_unknown_channel_names_are_rejected_not_stored(self):
        accepted = subscriptions.subscribe(self.session, ["room_inf0", "nonsense"])

        self.assertEqual(accepted, set())

    def test_a_typo_does_not_take_valid_channels_down_with_it(self):
        accepted = subscriptions.subscribe(
            self.session, [const.CHANNEL_ROOM_INFO, "room_inf0"]
        )

        self.assertEqual(accepted, {const.CHANNEL_ROOM_INFO})

    def test_subscribe_all_takes_every_known_channel(self):
        accepted = subscriptions.subscribe(self.session, const.SUBSCRIBE_ALL)

        self.assertEqual(accepted, set(const.SUBSCRIBABLE_CHANNELS))

    def test_a_bare_string_is_one_channel_not_a_pile_of_letters(self):
        accepted = subscriptions.subscribe(self.session, const.CHANNEL_COMBAT)

        self.assertEqual(accepted, {const.CHANNEL_COMBAT})

    def test_subscribing_is_additive(self):
        subscriptions.subscribe(self.session, [const.CHANNEL_ROOM_INFO])
        accepted = subscriptions.subscribe(self.session, [const.CHANNEL_COMBAT])

        self.assertEqual(accepted, {const.CHANNEL_ROOM_INFO, const.CHANNEL_COMBAT})

    def test_unsubscribe_all_clears_everything(self):
        subscriptions.subscribe(self.session, const.SUBSCRIBE_ALL)
        remaining = subscriptions.unsubscribe(self.session, const.SUBSCRIBE_ALL)

        self.assertEqual(remaining, set())

    def test_unsubscribing_an_unknown_name_is_harmless(self):
        subscriptions.subscribe(self.session, [const.CHANNEL_COMBAT])
        remaining = subscriptions.unsubscribe(self.session, ["never_existed"])

        self.assertEqual(remaining, {const.CHANNEL_COMBAT})

    def test_the_returned_set_is_a_copy_not_the_live_one(self):
        subscriptions.subscribe(self.session, [const.CHANNEL_COMBAT])
        borrowed = subscriptions.subscribed_channels(self.session)
        borrowed.add(const.CHANNEL_ROOM_INFO)

        self.assertFalse(
            subscriptions.is_subscribed(self.session, const.CHANNEL_ROOM_INFO)
        )


class TestEmitRouting(unittest.TestCase):
    """Who receives a payload, and who is not made to pay for it."""

    def setUp(self):
        self.session = _make_session()
        self.observer = _FakeObserver(sessions=[self.session])
        self.payload = RoomInfoPayload(num=7, name="Bank")

    def test_an_unsubscribed_session_receives_nothing(self):
        sent = emit(self.observer, self.payload)

        self.assertEqual(sent, 0)
        self.assertEqual(self.observer.sent, [])

    def test_a_subscribed_session_receives_the_payload(self):
        subscriptions.subscribe(self.session, [const.CHANNEL_ROOM_INFO])
        sent = emit(self.observer, self.payload)

        self.assertEqual(sent, 1)

    def test_the_payload_arrives_under_its_channel_name(self):
        subscriptions.subscribe(self.session, [const.CHANNEL_ROOM_INFO])
        emit(self.observer, self.payload)
        _session, kwargs = self.observer.sent[0]

        self.assertIn(const.CHANNEL_ROOM_INFO, kwargs)

    def test_the_body_carries_the_payload_fields(self):
        subscriptions.subscribe(self.session, [const.CHANNEL_ROOM_INFO])
        emit(self.observer, self.payload)
        _session, kwargs = self.observer.sent[0]
        body = kwargs[const.CHANNEL_ROOM_INFO]

        self.assertEqual(body["num"], 7)
        self.assertEqual(body["name"], "Bank")

    def test_the_body_does_not_repeat_the_channel_name(self):
        subscriptions.subscribe(self.session, [const.CHANNEL_ROOM_INFO])
        emit(self.observer, self.payload)
        _session, kwargs = self.observer.sent[0]
        body = kwargs[const.CHANNEL_ROOM_INFO]

        self.assertNotIn("channel", body)

    def test_only_the_subscribed_session_is_targeted(self):
        quiet_session = _make_session()
        self.observer.sessions = _FakeSessionHandler([self.session, quiet_session])
        subscriptions.subscribe(self.session, [const.CHANNEL_ROOM_INFO])
        emit(self.observer, self.payload)
        targeted, _kwargs = self.observer.sent[0]

        self.assertEqual(targeted, [self.session])

    def test_subscribing_to_one_channel_does_not_open_another(self):
        subscriptions.subscribe(self.session, [const.CHANNEL_COMBAT])
        sent = emit(self.observer, self.payload)

        self.assertEqual(sent, 0)

    def test_an_object_with_no_sessions_is_not_an_error(self):
        npc = SimpleNamespace(id=2, key="Mutant")
        sent = emit(npc, self.payload)

        self.assertEqual(sent, 0)

    def test_a_failing_msg_is_swallowed_not_raised(self):
        subscriptions.subscribe(self.session, [const.CHANNEL_ROOM_INFO])

        def _explode(session=None, **kwargs):
            raise RuntimeError("portal is on fire")

        self.observer.msg = _explode

        # The contract that matters: a cosmetic feed can never break the
        # gameplay path it is called from.
        sent = emit(self.observer, self.payload)

        self.assertEqual(sent, 0)


class TestRateCapping(unittest.TestCase):
    """Noisy channels are capped; combat deliberately is not."""

    def setUp(self):
        self.session = _make_session()
        self.observer = _FakeObserver(sessions=[self.session])
        subscriptions.subscribe(self.session, const.SUBSCRIBE_ALL)

    def test_a_capped_channel_drops_an_immediate_second_send(self):
        payload = CharVitalsPayload(hp=10, max_hp=10)
        first = emit(self.observer, payload)
        second = emit(self.observer, payload)

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)

    def test_combat_is_uncapped_because_a_dropped_swing_desyncs_the_client(self):
        from systems.statefeed.payloads import CombatPayload

        payload = CombatPayload(damage=3)
        first = emit(self.observer, payload)
        second = emit(self.observer, payload)

        self.assertEqual(first, 1)
        self.assertEqual(second, 1)

    def test_force_bypasses_the_cap_for_a_resync(self):
        payload = CharVitalsPayload(hp=10, max_hp=10)
        emit(self.observer, payload)
        forced = emit(self.observer, payload, force=True)

        self.assertEqual(forced, 1)

    def test_a_forced_send_does_not_starve_the_next_ordinary_one(self):
        payload = CharVitalsPayload(hp=10, max_hp=10)
        emit(self.observer, payload, force=True)
        ordinary = emit(self.observer, payload)

        self.assertEqual(ordinary, 1)

    def test_room_contents_are_never_capped(self):
        # Regression. This channel WAS capped at 1.0s, and it meant walking two
        # rooms inside a second published the second room_info with no matching
        # contents -- leaving the client rendering the previous room's
        # occupants indefinitely. A state transition must never be dropped.
        from systems.statefeed.payloads import RoomPlayersPayload

        payload = RoomPlayersPayload(entities=[])
        first = emit(self.observer, payload)
        second = emit(self.observer, payload)

        self.assertEqual(first, 1)
        self.assertEqual(second, 1)

    def test_only_continuous_value_channels_are_capped(self):
        # The rule the cap table encodes: a capped message must be superseded
        # by the next one. Transitions do not supersede, so they must not
        # appear here.
        transition_channels = {
            const.CHANNEL_ROOM_INFO,
            const.CHANNEL_ROOM_PLAYERS,
            const.CHANNEL_ROOM_PLAYER_ADD,
            const.CHANNEL_ROOM_PLAYER_REMOVE,
            const.CHANNEL_COMBAT,
            const.CHANNEL_AURA,
            const.CHANNEL_MAP,
        }
        capped = set(const.CHANNEL_MIN_INTERVAL_SECONDS)

        self.assertEqual(capped & transition_channels, set())

    def test_one_session_being_capped_does_not_cap_another(self):
        other_session = _make_session()
        subscriptions.subscribe(other_session, const.SUBSCRIBE_ALL)
        payload = CharVitalsPayload(hp=10, max_hp=10)

        emit(self.observer, payload)
        self.observer.sessions = _FakeSessionHandler([self.session, other_session])
        sent = emit(self.observer, payload)

        self.assertEqual(sent, 1)


class TestReservedChannelGuard(unittest.TestCase):
    """Evennia silently drops an outputfunc named "options"."""

    def test_the_reserved_name_is_refused_rather_than_sent_into_the_void(self):
        session = _make_session()
        observer = _FakeObserver(sessions=[session])
        subscriptions.subscribe(session, const.SUBSCRIBE_ALL)

        payload = RoomInfoPayload()
        payload.channel = const.RESERVED_CHANNEL_NAME

        sent = emit(observer, payload)

        self.assertEqual(sent, 0)
        self.assertEqual(observer.sent, [])

    def test_no_subscribable_channel_uses_the_reserved_name(self):
        self.assertNotIn(const.RESERVED_CHANNEL_NAME, const.SUBSCRIBABLE_CHANNELS)


class TestEmitToRoom(unittest.TestCase):
    """A room broadcast must reach exactly who the text reaches."""

    def setUp(self):
        self.watcher_session = _make_session()
        self.watcher = _FakeObserver(sessions=[self.watcher_session], obj_id=1)
        self.actor = _FakeObserver(sessions=[_make_session()], obj_id=2)
        subscriptions.subscribe(self.watcher_session, const.SUBSCRIBE_ALL)
        self.room = SimpleNamespace(contents=[self.watcher, self.actor])

    def test_occupants_receive_the_broadcast(self):
        sent = emit_to_room(self.room, RoomInfoPayload(num=1))

        self.assertEqual(sent, 1)

    def test_excluded_occupants_are_skipped(self):
        sent = emit_to_room(
            self.room, RoomInfoPayload(num=1), exclude=(self.watcher,)
        )

        self.assertEqual(sent, 0)

    def test_a_none_room_is_a_no_op(self):
        sent = emit_to_room(None, RoomInfoPayload(num=1))

        self.assertEqual(sent, 0)

    def test_scenery_is_not_asked_whether_it_is_listening(self):
        """
        A room's contents are mostly rocks. PERF-0002 measured 1,242 emit()
        calls for two moves, nearly all of them on objects that cannot hold a
        session, and this is the filter that stops them.
        """
        rock = _FakeObserver(sessions=[], obj_id=3)
        self.room.contents = [self.watcher, rock]

        sent = emit_to_room(self.room, RoomInfoPayload(num=1))

        self.assertEqual(sent, 1)
        self.assertEqual(rock.sent, [])

    def test_the_filter_narrows_how_not_who(self):
        """
        The invariant to preserve if this loop is touched again: an occupant
        that COULD listen still faces the real subscription check, and is still
        sent nothing when it is not subscribed.
        """
        unsubscribed = _FakeObserver(sessions=[_make_session()], obj_id=4)
        self.room.contents = [unsubscribed]

        sent = emit_to_room(self.room, RoomInfoPayload(num=1))

        self.assertEqual(sent, 0)
        self.assertEqual(unsubscribed.sent, [])

    def test_every_observer_receives_the_same_body_object(self):
        """
        The body is rendered once per broadcast rather than once per observer.
        Asserting identity, not equality: equality would pass just as well if
        to_dict were still being called per observer, which is the cost this
        removed.
        """
        second_session = _make_session()
        second = _FakeObserver(sessions=[second_session], obj_id=5)
        subscriptions.subscribe(second_session, const.SUBSCRIBE_ALL)
        self.room.contents = [self.watcher, second]

        emit_to_room(self.room, RoomInfoPayload(num=1))

        first_body = self.watcher.sent[0][1][const.CHANNEL_ROOM_INFO]
        second_body = second.sent[0][1][const.CHANNEL_ROOM_INFO]

        self.assertIs(first_body, second_body)
