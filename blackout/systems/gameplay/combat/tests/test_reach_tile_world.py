"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for the NPC step on the tile world: `step_toward_room`
             with no exits. A one-chunk world, built in memory.
"""

from evennia.utils.create import create_object
from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.pathfind import find_path
from systems.core.tilegrid.sight import has_line_of_sight
from systems.core.tilegrid.world import TileWorld, get_world, set_world
from systems.gameplay.combat import constants as combat_const
from systems.gameplay.combat import reach
from systems.gameplay.combat.auras.targeting import within_metric
from world import tile_travel
from world.object_kinds import OBJECT_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE

_START = (10, 10)
_GOAL = (15, 10)

# East of the start. A transition here must not pull the NPC through.
_EAST = (11, 10)

# A reach wider than the distance from _START to _GOAL, and narrower than the
# distance from _START to _FAR_GOAL. Not a weapon value: a test number.
_BOW_REACH = 7
_FAR_GOAL = (30, 10)

# A block across the straight line from _START to _FAR_GOAL, over the near
# edge of the ring. The walk must go around its north end.
_WALL_FLAGS = {(x, y): tile_const.FLAG_BLOCKED
               for x in range(21, 27) for y in range(0, 15)}

# A tile on the straight line from _START to _GOAL, for the sight cases.
_BETWEEN = (13, 10)

_THING_TYPECLASS = "typeclasses.objects.Object"

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


class NearestTileInReachTests(EvenniaTestCase):
    """
    Where `attack` walks to when it cannot reach (handoff debt 16). The walk
    follows the path to the target and stops at its first tile in reach.
    """

    def setUp(self):
        super().setUp()
        self.attacker = create_object(_THING_TYPECLASS, key="archer")
        self.target = create_object(_THING_TYPECLASS, key="raider")

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def _stand(self, attacker_tile, target_tile, flags=None):
        world = _world(flags or {}, [])
        set_world(world)
        movement.place(world.rooms, self.attacker, *attacker_tile, quiet=True)
        movement.place(world.rooms, self.target, *target_tile, quiet=True)

        return world

    def _in_reach_from(self, tile, radius):
        target = tile_travel.tile_of(self.target)

        return within_metric(target[0] - tile[0], target[1] - tile[1], radius)

    def test_a_melee_attacker_walks_onto_the_target_tile(self):
        self._stand(_START, _GOAL)

        destination = reach.nearest_tile_in_reach(
            self.attacker, self.target, combat_const.MELEE_REACH_TILES)

        self.assertEqual(destination, _GOAL)

    def test_a_ranged_attacker_stops_at_its_own_reach(self):
        # The bug: on the tile world most ring tiles have no room, so the
        # archer walked onto the tile of the raider.
        self._stand(_START, _FAR_GOAL)

        destination = reach.nearest_tile_in_reach(
            self.attacker, self.target, _BOW_REACH)

        self.assertNotEqual(destination, _FAR_GOAL)
        self.assertTrue(self._in_reach_from(destination, _BOW_REACH))

    def test_the_walk_stops_at_the_first_tile_in_reach(self):
        self._stand(_START, _FAR_GOAL)
        path = find_path(get_world().grid, _START, _FAR_GOAL)

        destination = reach.nearest_tile_in_reach(
            self.attacker, self.target, _BOW_REACH)
        before = path[path.index(destination) - 1]

        self.assertFalse(self._in_reach_from(before, _BOW_REACH))

    def test_a_block_on_the_straight_line_is_walked_around(self):
        world = self._stand(_START, _FAR_GOAL, _WALL_FLAGS)

        destination = reach.nearest_tile_in_reach(
            self.attacker, self.target, _BOW_REACH)

        self.assertFalse(world.grid.flags_at(*destination)
                         & tile_const.FLAGS_UNWALKABLE)
        self.assertIsNotNone(find_path(world.grid, _START, destination))
        self.assertTrue(self._in_reach_from(destination, _BOW_REACH))

    def test_an_attacker_in_reach_stays_where_it_is(self):
        self._stand(_START, _GOAL)

        destination = reach.nearest_tile_in_reach(
            self.attacker, self.target, _BOW_REACH)

        self.assertEqual(destination, _START)

    def test_a_block_on_the_line_stops_a_shot_in_reach(self):
        self._stand(_START, _GOAL, {_BETWEEN: tile_const.FLAG_BLOCKED})

        self.assertTrue(reach.in_reach(self.attacker, self.target, _BOW_REACH))
        self.assertFalse(reach.has_sight(self.attacker, self.target))
        self.assertFalse(
            reach.can_strike(self.attacker, self.target, _BOW_REACH))

    def test_water_on_the_line_does_not_stop_a_shot(self):
        self._stand(_START, _GOAL, {_BETWEEN: tile_const.FLAG_WATER})

        self.assertTrue(
            reach.can_strike(self.attacker, self.target, _BOW_REACH))

    def test_melee_never_needs_sight(self):
        # Melee reaches only its own tile, where nothing stands between.
        self._stand(_START, _START)

        self.assertTrue(reach.can_strike(
            self.attacker, self.target, combat_const.MELEE_REACH_TILES))

    def test_a_shot_with_no_sight_walks_to_the_first_tile_with_sight(self):
        world = self._stand(_START, _GOAL, {_BETWEEN: tile_const.FLAG_BLOCKED})

        destination = reach.nearest_tile_in_reach(
            self.attacker, self.target, _BOW_REACH)

        self.assertNotEqual(destination, _START)
        self.assertTrue(has_line_of_sight(world.grid, destination, _GOAL))
        self.assertTrue(self._in_reach_from(destination, _BOW_REACH))

    def test_sight_off_the_tile_world_is_not_stopped(self):
        self._stand(_START, _GOAL)
        self.target.location = create_object(
            "typeclasses.rooms.Room", key="elsewhere")

        self.assertTrue(reach.has_sight(self.attacker, self.target))

    def test_a_target_off_the_tile_world_has_no_tile(self):
        self._stand(_START, _GOAL)
        self.target.location = create_object(
            "typeclasses.rooms.Room", key="elsewhere")

        self.assertIsNone(
            reach.nearest_tile_in_reach(self.attacker, self.target, _BOW_REACH))


class OutOfSightRefusalTests(EvenniaTest):
    """The queue check refuses a shot with no sight, and says why."""

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def test_a_shot_with_no_sight_is_refused_with_its_own_message(self):
        from systems.gameplay.combat.combat import (
            combat_profile,
            ensure_combat_handler,
        )
        from typeclasses.npc_spawners import spawn_npc

        world = _world({_BETWEEN: tile_const.FLAG_BLOCKED}, [])
        set_world(world)
        movement.place(world.rooms, self.char1, *_START, quiet=True)
        raider = spawn_npc("mutant_raider", world.rooms.ensure_room(*_GOAL))
        handler = ensure_combat_handler(self.char1)
        handler.init_runtime_state()
        handler.ndb.active_weapon_data = dict(
            combat_profile(self.char1), max_range=_BOW_REACH)
        seen = []
        self.char1.msg = lambda text=None, **kwargs: seen.append(text)

        accepted = handler._validate_attack(
            {"kind": "attack", "target": raider})

        self.assertFalse(accepted)
        self.assertIn("clear shot", seen[0][0].lower())
