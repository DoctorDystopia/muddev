"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/26/2026
Description: Tests for the sweep of the tile rooms (handoff debt 13): a room
             that a teleport, a logout, or a delete left empty goes back.

             EvenniaTestCase, not EvenniaTest: nothing here needs the two
             stock characters.
"""

from types import SimpleNamespace
from unittest import mock

from evennia.utils.create import create_object
from evennia.utils.test_resources import EvenniaTestCase

from systems.core.tick.engine import PHASE_START
from systems.core.tilegrid import constants as const
from systems.core.tilegrid import movement
from systems.core.tilegrid import sweep
from systems.core.tilegrid.rooms import TileRooms
from systems.core.tilegrid.world import get_world, set_world
from typeclasses.objects import Object


# ─── Private constant definitions ────────────────────────────────────────────

_START = (10, 10)
_OTHER = (20, 20)

_ROOM_TYPECLASS = "typeclasses.rooms.Room"


# ─── Tests ───────────────────────────────────────────────────────────────────

class TileRoomsSweepTests(EvenniaTestCase):

    def setUp(self):
        super().setUp()
        self.rooms = TileRooms()
        self.thing = create_object(Object, key="walker")
        movement.place(self.rooms, self.thing, *_START, quiet=True)
        self.room = self.rooms.room_at(*_START)

    def test_a_teleport_away_leaves_a_room_that_the_sweep_gives_back(self):
        elsewhere = create_object(_ROOM_TYPECLASS, key="elsewhere")
        self.thing.move_to(elsewhere, quiet=True, move_type="teleport")

        self.assertIs(self.rooms.room_at(*_START), self.room)
        self.assertEqual(self.rooms.sweep(), 1)
        self.assertIsNone(self.rooms.room_at(*_START))

    def test_a_logout_leaves_a_room_that_the_sweep_gives_back(self):
        # Evennia logs a character out with a bare location write. No move
        # hook runs.
        self.thing.location = None

        self.assertEqual(self.rooms.sweep(), 1)
        self.assertIsNone(self.rooms.room_at(*_START))

    def test_a_delete_leaves_a_room_that_the_sweep_gives_back(self):
        self.thing.delete()

        self.assertEqual(self.rooms.sweep(), 1)
        self.assertIsNone(self.rooms.room_at(*_START))

    def test_a_room_that_holds_a_thing_stays(self):
        self.assertEqual(self.rooms.sweep(), 0)
        self.assertIs(self.rooms.room_at(*_START), self.room)

    def test_a_pinned_room_stays_when_it_is_empty(self):
        self.rooms.pin([_START])
        self.thing.location = None

        self.assertEqual(self.rooms.sweep(), 0)
        self.assertIs(self.rooms.room_at(*_START), self.room)

    def test_a_deleted_room_leaves_the_index(self):
        # A staff `destroy` deletes the room. The index must not keep it.
        other = self.rooms.ensure_room(*_OTHER)
        other.delete()

        self.rooms.sweep()

        self.assertIsNone(self.rooms.room_at(*_OTHER))

    def test_a_second_sweep_finds_nothing(self):
        self.thing.location = None
        self.rooms.sweep()

        self.assertEqual(self.rooms.sweep(), 0)


class SweepOnTickTests(EvenniaTestCase):

    def setUp(self):
        super().setUp()
        self.rooms = TileRooms()
        self.rooms.ensure_room(*_START)
        sweep._ticks_since_sweep = 0

    def tearDown(self):
        set_world(None)
        sweep._ticks_since_sweep = 0
        super().tearDown()

    def test_the_sweep_waits_for_its_tick(self):
        set_world(SimpleNamespace(sweep_rooms=self.rooms.sweep))

        for _tick in range(const.SWEEP_EVERY_TICKS - 1):
            sweep.on_tick()

        self.assertIsNotNone(self.rooms.room_at(*_START))

        sweep.on_tick()

        self.assertIsNone(self.rooms.room_at(*_START))

    def test_no_loaded_world_means_no_sweep(self):
        set_world(None)

        with mock.patch("systems.core.tilegrid.world.load_world") as load:
            self.assertEqual(sweep.sweep_loaded_world(), 0)

        load.assert_not_called()


class SweepAttachTests(EvenniaTestCase):
    """The sweep starts with the world. A test world attaches nothing."""

    def setUp(self):
        super().setUp()
        self._was_attached = sweep._attached
        sweep._attached = False
        set_world(None)

    def tearDown(self):
        sweep._attached = self._was_attached
        set_world(None)
        super().tearDown()

    def _patched_hook(self):
        return mock.patch("systems.core.tick.engine.register_phase_hook")

    def test_loading_the_world_attaches_the_sweep(self):
        with self._patched_hook() as hook:
            get_world()

        hook.assert_called_once_with(PHASE_START, sweep.on_tick)

    def test_a_second_attach_attaches_nothing(self):
        with self._patched_hook() as hook:
            sweep.attach()
            sweep.attach()

        self.assertEqual(hook.call_count, 1)

    def test_a_test_world_attaches_nothing(self):
        with self._patched_hook() as hook:
            set_world(SimpleNamespace(sweep_rooms=TileRooms().sweep))

        hook.assert_not_called()
