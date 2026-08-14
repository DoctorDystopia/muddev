"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: Tests that the feed is actually reachable from the outside —
             the subscription handshake a client performs, and the movement
             hooks that publish rooms.

             Separate from test_integration.py because these exercise the
             SEAMS rather than the payload contents: that the inputfunc a
             client calls exists and does what it claims, and that walking
             through a door reaches the feed at all.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.statefeed
"""

from types import SimpleNamespace
from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from server.conf import inputfuncs
from server.conf.serversession import ServerSession as BlackoutServerSession
from systems.statefeed import constants as const
from systems.statefeed import subscriptions
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.rooms import GridTile


# ─── Private helper routines ─────────────────────────────────────────────────

class _FakeSession:
    """A stand-in Session that records what was sent back to the client."""

    def __init__(self, puppet=None):
        self.ndb = SimpleNamespace()
        self.puppet = puppet
        self.sent = []

    def msg(self, **kwargs):
        self.sent.append(kwargs)


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestSubscribeInputfunc(EvenniaTest):
    """The handshake a graphical client performs on connect."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.fake_session = _FakeSession()

    def test_subscribing_to_all_records_every_channel(self):
        inputfuncs.blackout_subscribe(self.fake_session, channels="all")

        subscribed = subscriptions.subscribed_channels(self.fake_session)
        self.assertEqual(subscribed, set(const.SUBSCRIBABLE_CHANNELS))

    def test_the_client_is_told_what_it_got(self):
        inputfuncs.blackout_subscribe(self.fake_session, channels="all")

        acknowledgements = []

        for message in self.fake_session.sent:
            if "blackout_subscribed" in message:
                acknowledgements.append(message["blackout_subscribed"])

        self.assertTrue(acknowledgements)
        self.assertIn(const.CHANNEL_COMBAT, acknowledgements[0]["channels"])

    def test_a_channel_list_is_honoured(self):
        inputfuncs.blackout_subscribe(
            self.fake_session, channels=[const.CHANNEL_COMBAT])

        subscribed = subscriptions.subscribed_channels(self.fake_session)
        self.assertEqual(subscribed, {const.CHANNEL_COMBAT})

    def test_channels_may_arrive_positionally(self):
        inputfuncs.blackout_subscribe(self.fake_session, [const.CHANNEL_COMBAT])

        subscribed = subscriptions.subscribed_channels(self.fake_session)
        self.assertEqual(subscribed, {const.CHANNEL_COMBAT})

    def test_omitting_channels_subscribes_to_everything(self):
        inputfuncs.blackout_subscribe(self.fake_session)

        subscribed = subscriptions.subscribed_channels(self.fake_session)
        self.assertEqual(subscribed, set(const.SUBSCRIBABLE_CHANNELS))

    def test_a_typo_is_reported_back_as_an_empty_set(self):
        inputfuncs.blackout_subscribe(self.fake_session, channels=["rooom_info"])

        acknowledged = self.fake_session.sent[0]["blackout_subscribed"]
        self.assertEqual(acknowledged["channels"], [])

    def test_unsubscribing_reports_what_remains(self):
        inputfuncs.blackout_subscribe(self.fake_session, channels="all")
        self.fake_session.sent = []
        inputfuncs.blackout_unsubscribe(self.fake_session, channels="all")

        acknowledged = self.fake_session.sent[0]["blackout_subscribed"]
        self.assertEqual(acknowledged["channels"], [])

    def test_subscribing_without_a_puppet_is_not_an_error(self):
        # The normal case for a client that subscribes before puppeting.
        self.fake_session.puppet = None

        inputfuncs.blackout_subscribe(self.fake_session, channels="all")

        subscribed = subscriptions.subscribed_channels(self.fake_session)
        self.assertEqual(subscribed, set(const.SUBSCRIBABLE_CHANNELS))

    def test_resync_without_a_puppet_is_not_an_error(self):
        self.fake_session.puppet = None

        inputfuncs.blackout_resync(self.fake_session)

        # Reaching here without raising is the assertion.
        self.assertTrue(True)


class TestAnnounce(EvenniaTest):
    """The message that lets a client recover a lost subscription.

    Both ways a subscription goes missing are silent from the client's side:
    a reload wipes the ndb it lives on without dropping the socket, and a
    subscribe sent before the Server finished syncing is discarded without a
    reply. The announcement at at_sync is the only thing that tells a client
    either happened.
    """

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.fake_session = _FakeSession()

    def test_a_forgotten_session_is_told_it_has_nothing(self):
        subscriptions.announce(self.fake_session)

        sent = self.fake_session.sent[-1]
        self.assertEqual(sent[const.CHANNEL_SUBSCRIBED_ACK], {"channels": []})

    def test_a_subscribed_session_is_told_the_whole_set(self):
        subscriptions.subscribe(self.fake_session, const.SUBSCRIBE_ALL)
        self.fake_session.sent.clear()

        subscriptions.announce(self.fake_session)

        sent = self.fake_session.sent[-1]
        expected = sorted(const.SUBSCRIBABLE_CHANNELS)
        self.assertEqual(sent[const.CHANNEL_SUBSCRIBED_ACK], {"channels": expected})

    def test_the_ack_channel_is_not_itself_subscribable(self):
        # A client cannot turn this off, and must never have to ask for it.
        self.assertNotIn(const.CHANNEL_SUBSCRIBED_ACK, const.SUBSCRIBABLE_CHANNELS)

    def test_session_sync_announces(self):
        # The seam itself, not just the function it calls. EvenniaTest builds a
        # stock ServerSession rather than Blackout's, so this constructs one --
        # without it, deleting the call from at_sync breaks every graphical
        # client and passes every other test.
        session = BlackoutServerSession()
        session.protocol_flags = {}

        with mock.patch("server.conf.serversession.BaseServerSession.at_sync"):
            with mock.patch("server.conf.serversession.resync"):
                with mock.patch("server.conf.serversession.subscriptions") as mocked:
                    session.at_sync()

        mocked.announce.assert_called_once_with(session)


class TestPuppetHook(EvenniaTest):
    """Taking control of a character has to hand a client the world.

    This is the seam that makes subscribing-before-login work, which is what
    every graphical client does: the socket opens and subscribes long before
    anyone has typed a password, and by then ServerSession.at_sync has already
    run against a session with no puppet.
    """

    character_typeclass = BlackoutCharacter

    def test_puppeting_pushes_the_full_snapshot(self):
        with mock.patch("typeclasses.characters.resync") as mocked:
            self.char1.at_post_puppet()

        mocked.send_full_state.assert_called_once_with(self.char1)

    def test_a_failing_feed_does_not_block_the_login(self):
        # send_full_state swallows its own failures, which is why
        # at_post_puppet calls it unguarded. This is the test that keeps that
        # true: break the feed for real and the player still gets in.
        with mock.patch("systems.statefeed.resync._send_map",
                        side_effect=RuntimeError("feed is down")):
            self.char1.at_post_puppet()

        # Reaching here without raising is the assertion.
        self.assertTrue(True)


class TestMovementHooks(EvenniaTest):
    """Walking through a door has to reach the feed."""

    character_typeclass = BlackoutCharacter
    room_typeclass = GridTile

    def setUp(self):
        super().setUp()
        self.destination = create_object(GridTile, key="Destination", nohome=True)

    def test_arriving_publishes_the_new_room_to_the_mover(self):
        with mock.patch("typeclasses.rooms.subscriptions.has_subscribers",
                        return_value=True):
            with mock.patch("typeclasses.rooms.feed") as mocked:
                self.char1.move_to(self.destination, quiet=True)

        self.assertTrue(mocked.emit_room_info.called)

    def test_arriving_publishes_the_room_contents_to_the_mover(self):
        with mock.patch("typeclasses.rooms.subscriptions.has_subscribers",
                        return_value=True):
            with mock.patch("typeclasses.rooms.feed") as mocked:
                self.char1.move_to(self.destination, quiet=True)

        self.assertTrue(mocked.emit_room_contents.called)

    def test_arriving_announces_the_mover_to_everyone_already_there(self):
        with mock.patch("typeclasses.rooms.feed") as mocked:
            self.char1.move_to(self.destination, quiet=True)

        self.assertTrue(mocked.emit_entity_arrived.called)

    def test_leaving_announces_the_departure_to_the_old_room(self):
        with mock.patch("typeclasses.rooms.feed") as mocked:
            self.char1.move_to(self.destination, quiet=True)

        self.assertTrue(mocked.emit_entity_left.called)

    def test_the_departure_carries_the_id_not_the_object(self):
        # The object may already be deleted by the time a client reads this --
        # this hook also fires for an NPC that just died.
        with mock.patch("typeclasses.rooms.feed") as mocked:
            expected_id = self.char1.id
            self.char1.move_to(self.destination, quiet=True)

        args, _kwargs = mocked.emit_entity_left.call_args
        self.assertEqual(args[1], expected_id)

    def test_an_unsubscribed_mover_costs_no_room_snapshot(self):
        # The gate that keeps every dropped rock from walking the room's
        # contents to build a payload nobody will receive.
        with mock.patch("typeclasses.rooms.feed") as mocked:
            self.char1.move_to(self.destination, quiet=True)

        self.assertFalse(mocked.emit_room_info.called)

    def test_a_failing_feed_does_not_strand_the_mover(self):
        with mock.patch("typeclasses.rooms.feed") as mocked:
            mocked.emit_entity_arrived.side_effect = RuntimeError("feed is down")

            moved = self.char1.move_to(self.destination, quiet=True)

        self.assertTrue(moved)
        self.assertEqual(self.char1.location, self.destination)
