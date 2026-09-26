"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for the tile room index and pool, and for a step on the
             tile grid.

             EvenniaTestCase, not EvenniaTest: nothing here needs the two
             stock characters. The mover is a plain Object, because a step
             does not care what moves.
"""

from evennia.utils.create import create_object
from evennia.utils.test_resources import EvenniaTestCase

from systems.core.tilegrid import constants as const
from systems.core.tilegrid import movement
from systems.core.tilegrid.grid import Chunk, TileGrid
from systems.core.tilegrid.rooms import TileRooms
from typeclasses.objects import Object
from typeclasses.rooms import TileRoom


# ─── Private constant definitions ────────────────────────────────────────────

_START = (10, 10)
_EAST = (11, 10)

# A pool that holds one room, so a second release must delete.
_POOL_OF_ONE = 1

# A radius and the tiles inside and outside of it, for rooms_near.
_RADIUS = 3
_INSIDE = (13, 13)
_OUTSIDE = (14, 10)


# ─── Private helper routines ─────────────────────────────────────────────────

def _thing(key: str = "thing"):
    return create_object(Object, key=key)


# ─── Tests ───────────────────────────────────────────────────────────────────

class TileRoomsTests(EvenniaTestCase):

    def setUp(self):
        super().setUp()
        self.rooms = TileRooms()

    def test_a_new_room_carries_the_xyzgrid_coordinates(self):
        room = self.rooms.ensure_room(*_START)

        self.assertIsInstance(room, TileRoom)
        self.assertEqual(room.xyz, (_START[0], _START[1], const.WORLD_Z))
        found = TileRoom.objects.filter_xyz(
            xyz=(_START[0], _START[1], const.WORLD_Z))
        self.assertEqual(list(found), [room])

    def test_the_same_tile_gets_the_same_room(self):
        first = self.rooms.ensure_room(*_START)
        second = self.rooms.ensure_room(*_START)

        self.assertIs(first, second)
        self.assertEqual(self.rooms.live_count(), 1)

    def test_a_room_that_holds_a_thing_is_not_released(self):
        room = self.rooms.ensure_room(*_START)
        thing = _thing()
        thing.move_to(room, quiet=True)

        self.assertFalse(self.rooms.release(room))
        self.assertIs(self.rooms.room_at(*_START), room)

    def test_an_empty_room_waits_in_the_pool_with_no_coordinates(self):
        room = self.rooms.ensure_room(*_START)

        self.assertTrue(self.rooms.release(room))
        self.assertIsNone(self.rooms.room_at(*_START))
        self.assertEqual(self.rooms.pool_count(), 1)
        in_world = TileRoom.objects.filter_xyz(
            xyz=(_START[0], _START[1], const.WORLD_Z))
        in_pool = TileRoom.objects.filter_xyz(
            xyz=(_START[0], _START[1], self.rooms.pool_z))
        self.assertFalse(in_world.exists())
        self.assertEqual(list(in_pool), [room])

    def test_a_pooled_room_moves_to_the_next_tile(self):
        room = self.rooms.ensure_room(*_START)
        self.rooms.release(room)
        reused = self.rooms.ensure_room(*_EAST)

        self.assertIs(reused, room)
        self.assertEqual(reused.xyz, (_EAST[0], _EAST[1], const.WORLD_Z))
        self.assertEqual(self.rooms.pool_count(), 0)
        found = TileRoom.objects.filter_xyz(
            xyz=(_EAST[0], _EAST[1], const.WORLD_Z))
        self.assertEqual(list(found), [room])

    def test_the_tag_rows_match_the_cached_coordinates(self):
        # The pool writes the join rows past the TagHandler. A fresh read of
        # the rows must give what the cached xyz says.
        room = self.rooms.ensure_room(*_START)
        self.rooms.release(room)
        self.rooms.ensure_room(*_EAST)
        room.__dict__.pop("_xyz", None)
        room.tags.reset_cache()

        self.assertEqual(room.xyz, (_EAST[0], _EAST[1], const.WORLD_Z))
        self.assertEqual(len(room.tags.all(return_key_and_category=True)), 3)

    def test_a_full_pool_deletes_the_room(self):
        rooms = TileRooms(pool_capacity=_POOL_OF_ONE)
        first = rooms.ensure_room(*_START)
        second = rooms.ensure_room(*_EAST)
        rooms.release(first)
        second_id = second.id

        self.assertTrue(rooms.release(second))
        self.assertEqual(rooms.pool_count(), _POOL_OF_ONE)
        self.assertFalse(TileRoom.objects.filter(id=second_id).exists())

    def test_a_room_of_another_world_is_not_released(self):
        other = TileRooms(world_z="another_world")
        room = other.ensure_room(*_START)

        self.assertFalse(self.rooms.release(room))
        self.assertIs(other.room_at(*_START), room)

    def test_rooms_near_follows_the_metric(self):
        for tile in (_START, _INSIDE, _OUTSIDE):
            self.rooms.ensure_room(*tile)

        near = self.rooms.rooms_near(_START[0], _START[1], _RADIUS)
        near_tiles = sorted((room.xyz[0], room.xyz[1]) for room in near)

        self.assertEqual(near_tiles, sorted([_START, _INSIDE]))

    def test_rooms_near_takes_the_callers_metric(self):
        for tile in (_START, _INSIDE):
            self.rooms.ensure_room(*tile)

        def euclidean(dx, dy, radius):
            return dx * dx + dy * dy <= radius * radius

        near = self.rooms.rooms_near(_START[0], _START[1], _RADIUS,
                                     metric=euclidean)

        self.assertEqual([room.xyz[:2] for room in near], [_START])

    def test_load_rebuilds_the_index_and_the_pool(self):
        live = self.rooms.ensure_room(*_START)
        pooled = self.rooms.ensure_room(*_EAST)
        self.rooms.release(pooled)
        fresh = TileRooms()

        fresh.load()

        self.assertEqual(fresh.room_at(*_START), live)
        self.assertEqual(fresh.pool_count(), 1)


class StepTests(EvenniaTestCase):

    def setUp(self):
        super().setUp()
        self.grid = TileGrid()
        self.chunk = Chunk(0, 0)
        self.grid.add_chunk(self.chunk)
        self.rooms = TileRooms()
        self.mover = _thing("mover")
        movement.place(self.rooms, self.mover, *_START, quiet=True)

    def _block(self, tile):
        size = const.CHUNK_SIZE
        self.chunk.flags[tile[1] * size + tile[0]] = const.FLAG_BLOCKED

    def test_a_step_moves_the_mover_and_frees_the_room_behind(self):
        start_room = self.mover.location
        result = movement.step(self.grid, self.rooms, self.mover, "east",
                               quiet=True)

        self.assertEqual(result, const.STEP_OK)
        self.assertEqual(self.mover.location.xyz[:2], _EAST)
        self.assertIsNone(self.rooms.room_at(*_START))
        self.assertEqual(self.rooms.pool_count(), 1)
        self.assertNotEqual(self.mover.location, start_room)

    def test_a_step_back_reuses_the_pooled_room(self):
        movement.step(self.grid, self.rooms, self.mover, "east", quiet=True)
        pooled_room = self.rooms._pool[0]
        movement.step(self.grid, self.rooms, self.mover, "west", quiet=True)

        self.assertIs(self.mover.location, pooled_room)
        self.assertEqual(self.rooms.live_count(), 1)

    def test_a_room_that_holds_a_thing_stays_behind(self):
        _thing("dropped").move_to(self.mover.location, quiet=True)
        movement.step(self.grid, self.rooms, self.mover, "east", quiet=True)

        self.assertIsNotNone(self.rooms.room_at(*_START))
        self.assertEqual(self.rooms.live_count(), 2)

    def test_a_refused_step_makes_no_room(self):
        self._block(_EAST)
        result = movement.step(self.grid, self.rooms, self.mover, "east",
                               quiet=True)

        self.assertEqual(result, const.STEP_BLOCKED)
        self.assertEqual(self.mover.location.xyz[:2], _START)
        self.assertIsNone(self.rooms.room_at(*_EAST))

    def test_a_move_that_evennia_refuses_gives_the_new_room_back(self):
        self.mover.at_pre_move = lambda *args, **kwargs: False
        result = movement.step(self.grid, self.rooms, self.mover, "east",
                               quiet=True)

        self.assertEqual(result, const.STEP_MOVE_REFUSED)
        self.assertIsNone(self.rooms.room_at(*_EAST))
        self.assertEqual(self.mover.location.xyz[:2], _START)

    def test_an_unknown_direction_is_refused(self):
        result = movement.step(self.grid, self.rooms, self.mover, "up")

        self.assertEqual(result, const.STEP_NOT_ADJACENT)
