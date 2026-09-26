"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for the NPC step on the tile world: `step_toward_room`
             with no exits. A one-chunk world, built in memory.
"""

from evennia.utils.test_resources import EvenniaTest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from systems.gameplay.combat import reach
from world.object_kinds import OBJECT_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE

_START = (10, 10)
_GOAL = (15, 10)

# East of the start. A transition here must not pull the NPC through.
_EAST = (11, 10)

_TRANSITION = next(key for key, kind in OBJECT_KINDS.items()
                   if kind.category == tile_const.OBJECT_CATEGORY_TRANSITION)


# ─── Private helper routines ─────────────────────────────────────────────────

def _world(flags: dict, objects: list) -> TileWorld:
    tile_count = _SIZE * _SIZE
    grid_flags = [0] * tile_count

    for (x, y), bits in flags.items():
        grid_flags[y * _SIZE + x] = bits

    chunk_file = chunkfile.ChunkFile(
        cx=0, cy=0, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=grid_flags, areas=[0] * tile_count,
        objects=objects)
    world = TileWorld([chunk_file])
    world.rooms.load()

    return world


# ─── Tests ───────────────────────────────────────────────────────────────────

class TileWorldChaseTests(EvenniaTest):

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def _start(self, flags=None, objects=()):
        world = _world(flags or {}, list(objects))
        set_world(world)
        movement.place(world.rooms, self.obj1, *_START, quiet=True)
        goal_room = world.rooms.ensure_room(*_GOAL)

        return world, goal_room

    def _tile(self):
        x, y, _z = self.obj1.location.xyz

        return (int(x), int(y))

    def test_the_step_goes_one_tile_and_strictly_closer(self):
        _world_, goal_room = self._start()
        before = reach.room_distance(self.obj1.location, goal_room)

        self.assertTrue(reach.step_toward_room(self.obj1, goal_room))
        self.assertLess(reach.room_distance(self.obj1.location, goal_room),
                        before)
        self.assertEqual(max(abs(self._tile()[0] - _START[0]),
                             abs(self._tile()[1] - _START[1])), 1)

    def test_a_block_straight_ahead_is_a_dead_end(self):
        # The greedy rule of step_toward_room: no step is strictly closer,
        # because the block also closes both diagonals (no corner cutting).
        _world_, goal_room = self._start({_EAST: tile_const.FLAG_BLOCKED})

        self.assertFalse(reach.step_toward_room(self.obj1, goal_room))
        self.assertEqual(self._tile(), _START)

    def test_a_transition_tile_is_never_a_step(self):
        placed = [chunkfile.ChunkObject(_TRANSITION, *_EAST)]
        _world_, goal_room = self._start(objects=placed)
        reach.step_toward_room(self.obj1, goal_room)

        self.assertNotEqual(self._tile(), _EAST)
        self.assertLess(abs(self._tile()[0] - _START[0]), 2)

    def test_no_closer_step_means_no_move(self):
        _world_, goal_room = self._start()
        here_room = self.obj1.location

        self.assertFalse(reach.step_toward_room(self.obj1, here_room))
        self.assertEqual(self._tile(), _START)
