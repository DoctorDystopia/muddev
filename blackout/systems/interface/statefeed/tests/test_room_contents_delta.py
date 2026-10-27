"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/08/2026
Description: Guard the list-or-delta decision in events.emit_room_contents.

What is actually at risk here
-----------------------------
Every other optimisation in PERF-0002 was invisible to a client: the same
messages, produced more cheaply. This one changes WHAT IS SENT, and the failure
mode is not a slow game but a wrong one — a client rendering an entity that is
no longer there, or missing one that is, with nothing scheduled that would
correct it until the player resyncs.

So the tests below are mostly about the four ways the delta path must decline
to take a shortcut:

  * `force` (a resync) must always send the whole list, because the whole point
    of a resync is that the client's state is not to be trusted.
  * A client that does not subscribe to the delta channel must never be sent
    one, or an old build silently stops updating.
  * No recorded snapshot means no basis for a diff.
  * A send that reached nobody must not leave a snapshot behind claiming it did.

The fifth test is the payoff: on a map smaller than the radius, walking does
not change what is visible, and the right number of messages is zero.
"""

import unittest
from types import SimpleNamespace

from evennia.utils.test_resources import EvenniaTest

from systems.interface.statefeed import constants as const
from systems.interface.statefeed import events, subscriptions


# ─── Private constant definitions ────────────────────────────────────────────

_TEST_MAP = "delta_test_map"

# Wide enough that the observer can take a step without leaving the grid, and
# small enough to build per test method. The production radius is 10, so any
# grid this size is entirely inside one neighbourhood -- which is the live-map
# situation the delta path exists for.
_GRID = 3

# Scenery objects spread across the grid. Twelve makes a one-entity change 8%
# of the list, comfortably inside ROOM_PLAYERS_DELTA_MAX_FRACTION, so the
# delta path is reached for the reason under test rather than by luck.
_SCENERY_COUNT = 12


# ─── Private helper routines ─────────────────────────────────────────────────

def _make_session(sessid: int = 1):
    """A session stand-in carrying the ndb holder subscriptions writes to."""
    return SimpleNamespace(ndb=SimpleNamespace(), sessid=sessid, sent=[])


class _RecordingSessionHandler:
    """The `obj.sessions` stand-in emit() and _wants_delta both call."""

    def __init__(self, sessions):
        self._sessions = list(sessions)

    def all(self):
        return list(self._sessions)


# ─── Test cases ──────────────────────────────────────────────────────────────

class _DeltaFixture(EvenniaTest):
    """Real rooms, a real serialiser, and a tap on the `msg` of the observer.

    The tap sits AFTER the buffer. Thus, a test on this fixture sees the
    messages that a client receives, in their order. The tap of
    test_freshness.py is on events.emit, before the buffer. That tap cannot
    see a held snapshot that goes out after an event.
    """

    def setUp(self):
        super().setUp()

        from typeclasses.rooms import GridTile

        from systems.interface.statefeed import neighbourhood

        neighbourhood.reset()

        self.tiles = {}

        for x in range(_GRID):
            for y in range(_GRID):
                self.tiles[(x, y)] = GridTile.create(
                    key=f"delta_tile_{x}_{y}", xyz=(x, y, _TEST_MAP))[0]

        self.observer = self.char1
        self.observer.location = self.tiles[(1, 1)]

        # Scenery, and enough of it to matter. The delta/list decision is a
        # FRACTION of the list being replaced, so in a world holding three
        # entities a one-entity change is a third of everything and the whole
        # list is correctly the smaller message. A fixture that small can only
        # ever exercise the fallback.
        self._populate(_SCENERY_COUNT)

        self.session = _make_session()
        subscriptions.subscribe(self.session, const.SUBSCRIBE_ALL)
        self.observer.__dict__["sessions"] = _RecordingSessionHandler(
            [self.session])
        self.observer.db_sessid = "1"

        self.sent = []
        self.observer.msg = self._record

    def tearDown(self):
        from systems.interface.statefeed import neighbourhood

        neighbourhood.reset()
        super().tearDown()

    def _populate(self, count: int) -> None:
        """Fill the grid with scenery, ignoring anything it broadcasts."""
        from evennia.utils.create import create_object
        from typeclasses.objects import Object

        tiles = list(self.tiles.values())

        for index in range(count):
            create_object(Object,
                          key=f"delta_scrap_{index}",
                          location=tiles[index % len(tiles)])

    def _spawn(self, key: str, tile):
        """Create one object and DISCARD the arrival broadcast it triggers.

        Creating or deleting an object fires the room hooks, which publish
        room_add_player / room_remove_player of their own. Those are the
        pre-existing per-entity delta path and are not what these tests are
        about -- clearing here keeps each assertion about the messages
        emit_room_contents itself produced.
        """
        from evennia.utils.create import create_object
        from typeclasses.objects import Object

        made = create_object(Object, key=key, location=tile)
        self.sent = []

        return made

    def _record(self, session=None, **kwargs):
        kwargs.pop("options", None)
        self.sent.append(kwargs)

    def _channels_sent(self):
        names = []

        for message in self.sent:
            for key in message:
                names.append(key)

        return names


class RoomContentsDeltaTests(_DeltaFixture):
    """The decision, against real rooms and a real serialiser."""

    # ─── The full-list paths ─────────────────────────────────────────────

    def test_the_first_publish_is_a_whole_list(self):
        """No snapshot means no basis for a diff."""
        events.emit_room_contents(self.observer)

        self.assertEqual(self._channels_sent(), [const.CHANNEL_ROOM_PLAYERS])

    def test_a_forced_publish_is_always_a_whole_list(self):
        """
        Resync is the one call that re-seeds a client whose state has gone
        wrong, so it must never trust the snapshot it is repairing.
        """
        events.emit_room_contents(self.observer)
        self.sent = []

        events.emit_room_contents(self.observer, force=True)

        self.assertEqual(self._channels_sent(), [const.CHANNEL_ROOM_PLAYERS])

    def test_a_client_that_cannot_follow_deltas_gets_whole_lists(self):
        """
        The version gate. An old build subscribes to every channel it knows
        about, which does not include this one, and must keep receiving lists
        rather than silently ceasing to update.
        """
        subscriptions.unsubscribe(
            self.session, [const.CHANNEL_ROOM_PLAYERS_DELTA])

        events.emit_room_contents(self.observer)
        self.sent = []
        self.observer.location = self.tiles[(2, 1)]
        events.emit_room_contents(self.observer)

        self.assertEqual(self._channels_sent(), [const.CHANNEL_ROOM_PLAYERS])

    def test_one_stale_session_forces_whole_lists_for_all_of_them(self):
        """
        EVERY session, not any. A delta reaching the new client and skipping
        the old one would leave the old one frozen.
        """
        old_client = _make_session(sessid=2)
        subscriptions.subscribe(old_client, [const.CHANNEL_ROOM_PLAYERS])
        self.observer.__dict__["sessions"] = _RecordingSessionHandler(
            [self.session, old_client])

        events.emit_room_contents(self.observer)
        self.sent = []
        self.observer.location = self.tiles[(2, 1)]
        events.emit_room_contents(self.observer)

        self.assertEqual(self._channels_sent(), [const.CHANNEL_ROOM_PLAYERS])

    # ─── The payoff ──────────────────────────────────────────────────────

    def test_a_move_that_changes_nothing_visible_sends_nothing(self):
        """
        THE POINT OF F7. STATEFEED_ENTITY_RADIUS is 10 and every live map is
        smaller than that, so a step does not change which entities are in
        range -- and the right number of messages for "nothing changed" is
        zero, not one 43 KB list.
        """
        events.emit_room_contents(self.observer)
        self.sent = []

        self.observer.location = self.tiles[(2, 1)]
        sent = events.emit_room_contents(self.observer)

        self.assertEqual(sent, 0)
        self.assertEqual(self.sent, [])

    def test_an_entity_coming_into_view_arrives_as_a_delta(self):
        """A genuine change is still delivered, and as the smaller message."""
        events.emit_room_contents(self.observer)
        self.sent = []

        newcomer = self._spawn("delta_newcomer", self.tiles[(0, 0)])
        events.emit_room_contents(self.observer)

        self.assertEqual(self._channels_sent(),
                         [const.CHANNEL_ROOM_PLAYERS_DELTA])

        body = self.sent[0][const.CHANNEL_ROOM_PLAYERS_DELTA]
        added_ids = [entity["id"] for entity in body["added"]]

        self.assertIn(newcomer.id, added_ids)
        self.assertEqual(body["removed"], [])

    def test_an_entity_leaving_view_is_reported_as_a_removal(self):
        doomed = self._spawn("delta_doomed", self.tiles[(0, 0)])
        events.emit_room_contents(self.observer)

        doomed_id = doomed.id
        doomed.delete()
        self.sent = []
        events.emit_room_contents(self.observer)

        body = self.sent[0][const.CHANNEL_ROOM_PLAYERS_DELTA]

        self.assertEqual(body["removed"], [doomed_id])
        self.assertEqual(body["added"], [])

    def test_the_observer_is_absent_from_their_own_delta(self):
        """
        The exclusion is preserved on BOTH paths. A client already knows where
        it put the camera, and CharAvatarPayload documents the contract.
        """
        events.emit_room_contents(self.observer)
        self.sent = []

        self._spawn("delta_bystander", self.tiles[(1, 1)])
        events.emit_room_contents(self.observer)

        body = self.sent[0][const.CHANNEL_ROOM_PLAYERS_DELTA]
        added_ids = [entity["id"] for entity in body["added"]]

        self.assertNotIn(self.observer.id, added_ids)
        self.assertNotIn(self.observer.id, body["removed"])

    # ─── Falling back ────────────────────────────────────────────────────

    def test_a_wholesale_change_falls_back_to_the_whole_list(self):
        """
        A teleport replaces every entity at once. Sent as a delta that would be
        every entity added and every entity removed -- strictly worse than the
        list it replaces.
        """
        from typeclasses.rooms import GridTile

        from systems.interface.statefeed import neighbourhood

        events.emit_room_contents(self.observer)
        self.sent = []

        far = GridTile.create(key="delta_far", xyz=(0, 0, "delta_other_map"))[0]
        neighbourhood.reset()
        self.observer.location = far
        events.emit_room_contents(self.observer)

        self.assertEqual(self._channels_sent(), [const.CHANNEL_ROOM_PLAYERS])

    def test_a_send_that_reached_nobody_leaves_no_snapshot(self):
        """
        The self-healing rule. Recording a snapshot for a message no client
        received would diff the NEXT move against a state that never existed.
        """
        events.emit_room_contents(self.observer)

        self.observer.__dict__["sessions"] = _RecordingSessionHandler([])
        self.sent = []
        events.emit_room_contents(self.observer)

        recorded = getattr(self.observer.ndb,
                           const.ROOM_PLAYERS_SNAPSHOT_ATTR, "unset")

        self.assertIsNone(recorded)

    def test_a_recovered_client_gets_a_whole_list_not_a_delta(self):
        """The consequence of the rule above, end to end."""
        events.emit_room_contents(self.observer)

        self.observer.__dict__["sessions"] = _RecordingSessionHandler([])
        events.emit_room_contents(self.observer)

        self.observer.__dict__["sessions"] = _RecordingSessionHandler(
            [self.session])
        self.sent = []
        events.emit_room_contents(self.observer)

        self.assertEqual(self._channels_sent(), [const.CHANNEL_ROOM_PLAYERS])


class ArrivalTickTests(_DeltaFixture):
    """What a client draws after a tick that both arrives and picks up.

    The defect (10/21/2026): `goto (x,y) then get credits` runs its get in
    the tick that reaches the tile. The arrival built the whole list at once,
    and the buffer held it. The get sent its remove at once. Then the flush
    sent the held list, and the list still named the stack. The client drew
    a stack that the player carried.
    """

    def _client_view(self) -> set:
        """Replay every message in its order, as the client does. Returns the
        ids that the client holds at the end."""
        ids = set()

        for message in self.sent:
            for channel, body in message.items():
                if channel == const.CHANNEL_ROOM_PLAYERS:
                    ids = {entity["id"] for entity in body["entities"]}
                elif channel == const.CHANNEL_ROOM_PLAYERS_DELTA:
                    ids -= set(body["removed"])
                    ids |= {entity["id"] for entity in body["added"]}
                elif channel == const.CHANNEL_ROOM_PLAYER_ADD:
                    ids.add(body["entity"]["id"])
                elif channel == const.CHANNEL_ROOM_PLAYER_REMOVE:
                    ids.discard(body["entity_id"])

        return ids

    def _tick(self, *moves) -> None:
        """Open a tick, run the moves in it, and flush the buffer."""
        from systems.interface.statefeed import buffer

        buffer.reset()
        self.addCleanup(buffer.reset)
        buffer.begin_tick()

        for mover, destination, move_type in moves:
            mover.move_to(destination, quiet=True, move_type=move_type)

        buffer.flush()

    def test_a_pickup_in_the_arrival_tick_leaves_no_stack_drawn(self):
        # No snapshot yet, so the arrival sends the whole list. That is the
        # path that held the stale list. A sparse area takes the same path
        # on most steps. There, a change of one entity is more than half of
        # the list.
        stack = self._spawn("delta_credits", self.tiles[(2, 2)])

        self._tick((self.observer, self.tiles[(2, 2)], "move"),
                   (stack, self.observer, "get"))

        self.assertNotIn(stack.id, self._client_view())

    def test_the_arrival_list_still_reaches_the_mover(self):
        """The list waits for the flush. It must not wait for ever."""
        bystander = self._spawn("delta_bystander", self.tiles[(2, 2)])

        self._tick((self.observer, self.tiles[(2, 2)], "move"))

        self.assertIn(bystander.id, self._client_view())

    def test_a_pickup_outside_a_tick_leaves_no_stack_drawn(self):
        """A typed `get` runs outside the tick. The list comes at the end of
        the reactor turn. Here, a direct drain of the buffer is that end."""
        from systems.interface.statefeed import buffer

        buffer.reset()
        self.addCleanup(buffer.reset)
        stack = self._spawn("delta_credits", self.tiles[(2, 2)])

        self.observer.move_to(self.tiles[(2, 2)], quiet=True)
        stack.move_to(self.observer, quiet=True, move_type="get")
        buffer.drain_stale()

        self.assertNotIn(stack.id, self._client_view())


class DeltaThresholdTests(unittest.TestCase):
    """The size rule, which needs no database."""

    def test_a_small_change_is_worth_sending(self):
        worth = events._delta_is_worth_sending({1}, set(), set(range(100)))

        self.assertTrue(worth)

    def test_a_change_larger_than_half_the_list_is_not(self):
        worth = events._delta_is_worth_sending(set(range(60)), set(),
                                               set(range(100)))

        self.assertFalse(worth)

    def test_an_empty_destination_is_never_a_delta(self):
        """
        Walking into an empty neighbourhood: the delta would be all removals
        and the list it replaces is two bytes.
        """
        worth = events._delta_is_worth_sending(set(), {1, 2, 3}, set())

        self.assertFalse(worth)
