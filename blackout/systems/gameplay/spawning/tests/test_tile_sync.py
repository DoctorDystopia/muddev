"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for the tile sync: the plan, and each of its four verbs.
             The kinds come from the kind table by category, not by name.
"""

from evennia.utils.test_resources import EvenniaTestCase

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid.world import TileWorld
from systems.gameplay.spawning import tile_sync
from world.object_kinds import OBJECT_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE


def _first_of(category: str) -> str:
    """Return the first kind key of a category."""
    for key, kind in OBJECT_KINDS.items():
        if kind.category == category:
            return key

    raise LookupError(category)


_FACILITY = _first_of(tile_const.OBJECT_CATEGORY_FACILITY)
_SIGN = _first_of(tile_const.OBJECT_CATEGORY_SIGN)
_TRANSITION = _first_of(tile_const.OBJECT_CATEGORY_TRANSITION)

# The tiles of the test world.
_FACILITY_TILE = (4, 4)
_TRANSITION_TILE = (9, 9)


# ─── Private helper routines ─────────────────────────────────────────────────

def _world(objects: list) -> TileWorld:
    """A loaded one-chunk world with these (kind, x, y) objects."""
    tile_count = _SIZE * _SIZE
    chunk_file = chunkfile.ChunkFile(
        cx=0, cy=0, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=[0] * tile_count,
        areas=[0] * tile_count,
        objects=[chunkfile.ChunkObject(kind, x, y) for kind, x, y in objects])
    world = TileWorld([chunk_file])
    world.rooms.load()

    return world


def _placed():
    """The standard objects: a signed facility, and a lone transition."""
    return [(_FACILITY, *_FACILITY_TILE), (_SIGN, *_FACILITY_TILE),
            (_TRANSITION, *_TRANSITION_TILE)]


def _verbs(actions) -> dict:
    return {action.tile: action.verb for action in actions}


# ─── Tests ───────────────────────────────────────────────────────────────────

class TileSyncTests(EvenniaTestCase):

    def test_a_fresh_world_plans_new_tiles_and_skips_a_transition(self):
        world = _world(_placed())
        actions = tile_sync.plan(world)

        self.assertEqual(_verbs(actions), {_FACILITY_TILE: tile_sync.VERB_NEW})
        self.assertEqual(actions[0].kinds, (_FACILITY, _SIGN))

    def test_the_plan_changes_nothing(self):
        world = _world(_placed())
        tile_sync.plan(world)

        self.assertIsNone(world.rooms.room_at(*_FACILITY_TILE))

    def test_apply_stands_up_each_kind_and_records_it(self):
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        room = world.rooms.room_at(*_FACILITY_TILE)

        self.assertIsNotNone(room)
        self.assertTrue(room.contents)
        self.assertEqual(room.attributes.get(tile_sync.TILE_KINDS_ATTR),
                         [_FACILITY, _SIGN])

    def test_a_second_run_is_a_refresh_that_adds_nothing(self):
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        room = world.rooms.room_at(*_FACILITY_TILE)
        before = len(room.contents)
        actions = tile_sync.plan(world)
        tile_sync.apply(world, actions)

        self.assertEqual(_verbs(actions),
                         {_FACILITY_TILE: tile_sync.VERB_REFRESH})
        self.assertEqual(len(room.contents), before)

    def test_a_new_kind_list_is_a_change(self):
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        edited = _world([(_FACILITY, *_FACILITY_TILE)])
        actions = tile_sync.plan(edited)
        tile_sync.apply(edited, actions)
        room = edited.rooms.room_at(*_FACILITY_TILE)

        self.assertEqual(_verbs(actions),
                         {_FACILITY_TILE: tile_sync.VERB_CHANGED})
        self.assertEqual(room.attributes.get(tile_sync.TILE_KINDS_ATTR),
                         [_FACILITY])

    def test_a_tile_that_lost_every_kind_is_cleared_and_released(self):
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        emptied = _world([])
        actions = tile_sync.plan(emptied)
        tile_sync.apply(emptied, actions)

        self.assertEqual(_verbs(actions),
                         {_FACILITY_TILE: tile_sync.VERB_REMOVED})
        self.assertIsNone(emptied.rooms.room_at(*_FACILITY_TILE))

    def test_a_placed_tile_is_pinned(self):
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        room = world.rooms.room_at(*_FACILITY_TILE)

        for thing in list(room.contents):
            thing.delete()

        self.assertFalse(world.rooms.release(room))
        self.assertIs(world.rooms.room_at(*_FACILITY_TILE), room)
