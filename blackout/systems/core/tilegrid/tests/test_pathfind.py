"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for A* on the tile grid. No database.
"""

import random
import unittest
from collections import deque

from systems.core.tilegrid import constants as const
from systems.core.tilegrid.grid import Chunk, TileGrid
from systems.core.tilegrid.pathfind import find_nearest_path, find_path


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = const.CHUNK_SIZE

# The column of the wall in the detour case, and the one gap in it.
_WALL_X = 20
_GAP_Y = 50

# The start of the box case, in the middle of the chunk, and the farthest
# goal on each axis from it. Every tile of that square is a goal.
_BOX_START = (_SIZE // 2, _SIZE // 2)
_BOX_RADIUS = 6


# ─── Private helper routines ─────────────────────────────────────────────────

def _open_grid(chunks=((0, 0),)):
    grid = TileGrid()

    for cx, cy in chunks:
        grid.add_chunk(Chunk(cx, cy))

    return grid


def _block(grid, x: int, y: int) -> None:
    """Block one tile of the grid. The chunk must be loaded."""
    chunk = grid._chunks[(x // _SIZE, y // _SIZE)]
    chunk.flags[(y % _SIZE) * _SIZE + (x % _SIZE)] = const.FLAG_BLOCKED


def _chebyshev(start, goal) -> int:
    return max(abs(goal[0] - start[0]), abs(goal[1] - start[1]))


def _squared(tile, goal) -> int:
    return (goal[0] - tile[0]) ** 2 + (goal[1] - tile[1]) ** 2


def _block_ring(grid, centre, radius: int) -> None:
    """Block every tile within `radius` of `centre`, but `centre` itself."""
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            if (dx, dy) != (0, 0):
                _block(grid, centre[0] + dx, centre[1] + dy)


def _steps_from(grid, start) -> dict:
    """
    The steps from `start` to every tile that a walk reaches, by a
    breadth-first search that asks check_step about every step.
    """
    seen = {start: 0}
    queue = deque([start])

    while queue:
        node = queue.popleft()

        for dx, dy in const.DIRECTION_OFFSETS.values():
            neighbour = (node[0] + dx, node[1] + dy)

            if neighbour in seen:
                continue

            if grid.check_step(node, neighbour) != const.STEP_OK:
                continue

            seen[neighbour] = seen[node] + 1
            queue.append(neighbour)

    return seen


# The flag bits that the random grid draws from, with no bit as the most
# likely value. Walls and water make the search take its slow path.
_RANDOM_FLAG_CHOICES = (
    const.FLAG_NONE, const.FLAG_NONE, const.FLAG_NONE, const.FLAG_NONE,
    const.FLAG_BLOCKED, const.FLAG_WATER,
    const.FLAG_WALL_NORTH, const.FLAG_WALL_EAST,
    const.FLAG_WALL_SOUTH, const.FLAG_WALL_WEST,
    const.FLAG_WALL_NORTH | const.FLAG_WALL_WEST,
)

# The height range of the random grid, and the walk limit of the slope case.
_RANDOM_HEIGHT_MAX = 3
_RANDOM_WALK_LIMIT = 1


def _random_grid(seed: int) -> TileGrid:
    """One chunk of seeded random flags and heights."""
    rng = random.Random(seed)
    chunk = Chunk(0, 0)
    chunk.flags[:] = [rng.choice(_RANDOM_FLAG_CHOICES)
                      for _ in chunk.flags]
    chunk.heights[:] = [rng.randint(0, _RANDOM_HEIGHT_MAX)
                        for _ in chunk.heights]
    grid = TileGrid()
    grid.add_chunk(chunk)

    return grid


def _reference_steps(grid, start, goal, walk_limit):
    """
    The length of a shortest walk, by a breadth-first search that asks
    check_step about every step. None if no walk exists.
    """
    seen = {start: 0}
    queue = deque([start])

    while queue:
        node = queue.popleft()

        if node == goal:
            return seen[node]

        for dx, dy in const.DIRECTION_OFFSETS.values():
            neighbour = (node[0] + dx, node[1] + dy)

            if neighbour in seen:
                continue

            if grid.check_step(node, neighbour, walk_limit) != const.STEP_OK:
                continue

            seen[neighbour] = seen[node] + 1
            queue.append(neighbour)

    return None


# ─── Tests ───────────────────────────────────────────────────────────────────

class FindPathTests(unittest.TestCase):

    def assertLegalWalk(self, grid, start, path, goal):
        """Every step of the path is legal, and it ends at the goal."""
        self.assertEqual(path[-1], goal)
        here = start

        for tile in path:
            with self.subTest(step_from=here, step_to=tile):
                self.assertEqual(grid.check_step(here, tile), const.STEP_OK)

            here = tile

    def test_the_start_is_the_goal(self):
        grid = _open_grid()

        self.assertEqual(find_path(grid, (3, 3), (3, 3)), [])

    def test_open_ground_gives_a_shortest_path(self):
        grid = _open_grid()
        start, goal = (2, 3), (40, 17)
        path = find_path(grid, start, goal)

        self.assertEqual(len(path), _chebyshev(start, goal))
        self.assertLegalWalk(grid, start, path, goal)

    def test_a_wall_makes_a_detour_through_its_gap(self):
        grid = _open_grid()

        for y in range(_SIZE):
            if y != _GAP_Y:
                _block(grid, _WALL_X, y)

        start, goal = (_WALL_X - 5, 5), (_WALL_X + 5, 5)
        path = find_path(grid, start, goal)

        self.assertIn((_WALL_X, _GAP_Y), path)
        self.assertLegalWalk(grid, start, path, goal)

    def test_a_walled_off_goal_has_no_path(self):
        grid = _open_grid()
        goal = (30, 30)

        for direction_offset in const.DIRECTION_OFFSETS.values():
            _block(grid, goal[0] + direction_offset[0],
                   goal[1] + direction_offset[1])

        self.assertIsNone(find_path(grid, (1, 1), goal))

    def test_the_limit_stops_a_search_that_could_succeed(self):
        grid = _open_grid()
        start, goal = (0, 0), (60, 60)
        too_few = _chebyshev(start, goal) - 1

        self.assertIsNone(find_path(grid, start, goal, max_expanded=too_few))
        self.assertIsNotNone(find_path(grid, start, goal))

    def test_a_path_crosses_a_chunk_edge(self):
        grid = _open_grid(chunks=((0, 0), (1, 0)))
        start, goal = (_SIZE - 3, 10), (_SIZE + 3, 12)
        path = find_path(grid, start, goal)

        self.assertEqual(len(path), _chebyshev(start, goal))
        self.assertLegalWalk(grid, start, path, goal)

    def test_a_wall_bit_stops_a_step_that_the_flags_alone_allow(self):
        grid = _open_grid()
        chunk = grid._chunks[(0, 0)]
        chunk.flags[5 * _SIZE + 5] = const.FLAG_WALL_EAST
        path = find_path(grid, (5, 5), (6, 5))

        self.assertNotEqual(path, [(6, 5)])
        self.assertLegalWalk(grid, (5, 5), path, (6, 5))

    def test_the_search_agrees_with_check_step_on_every_step(self):
        # The inline flag read must accept exactly what check_step accepts.
        # Each case is a seeded maze of walls, water and blocks. The reference
        # search calls check_step for every step.
        cases = [(seed, limit) for seed in range(12)
                 for limit in (None, _RANDOM_WALK_LIMIT)]

        for seed, walk_limit in cases:
            grid = _random_grid(seed)
            rng = random.Random(seed)
            open_tiles = [(x, y) for y in range(_SIZE) for x in range(_SIZE)
                          if not grid.flags_at(x, y) & const.FLAGS_UNWALKABLE]
            start, goal = rng.sample(open_tiles, 2)

            with self.subTest(seed=seed, walk_limit=walk_limit):
                expected = _reference_steps(grid, start, goal, walk_limit)
                path = find_path(grid, start, goal,
                                 max_expanded=_SIZE * _SIZE,
                                 walk_limit=walk_limit)

                if expected is None:
                    self.assertIsNone(path)
                    continue

                self.assertEqual(len(path), expected)
                here = start

                for tile in path:
                    self.assertEqual(
                        grid.check_step(here, tile, walk_limit),
                        const.STEP_OK)
                    here = tile

    def test_a_walk_on_open_ground_stays_in_its_box(self):
        # The tent bug: a walk of 6 tiles east went 3 tiles north-east and 3
        # tiles south-east. The length was correct, the shape was not. Each
        # tile of a walk on open ground is in the box of its start and goal,
        # so a straight goal gets a straight walk.
        grid = _open_grid()
        start_x, start_y = _BOX_START
        span = range(-_BOX_RADIUS, _BOX_RADIUS + 1)
        goals = [(start_x + dx, start_y + dy) for dx in span for dy in span]

        for goal in goals:
            low_x, high_x = sorted((start_x, goal[0]))
            low_y, high_y = sorted((start_y, goal[1]))

            with self.subTest(goal=goal):
                path = find_path(grid, _BOX_START, goal)
                outside = [(x, y) for x, y in path
                           if not low_x <= x <= high_x
                           or not low_y <= y <= high_y]

                self.assertEqual(len(path), _chebyshev(_BOX_START, goal))
                self.assertEqual(outside, [])

    def test_the_same_question_gets_the_same_path(self):
        grid = _open_grid()
        first = find_path(grid, (5, 5), (25, 9))
        second = find_path(grid, (5, 5), (25, 9))

        self.assertEqual(first, second)


class FindNearestPathTests(unittest.TestCase):
    """The OSRS rule: a walk to a sealed goal ends on the nearest tile."""

    _START = (1, 1)
    _SEALED = (30, 30)

    def assertLegalWalk(self, grid, start, path):
        here = start

        for tile in path:
            with self.subTest(step_from=here, step_to=tile):
                self.assertEqual(grid.check_step(here, tile), const.STEP_OK)

            here = tile

    def test_a_goal_that_a_walk_reaches_gives_the_find_path_walk(self):
        grid = _open_grid()
        goal = (20, 7)

        self.assertEqual(find_nearest_path(grid, self._START, goal),
                         (find_path(grid, self._START, goal), True))

    def test_a_sealed_goal_walks_to_the_nearest_reached_tile(self):
        # The expectation comes from a breadth-first search: of the reached
        # tiles in the square, the lowest (squared distance, steps, x, y).
        grid = _open_grid()
        _block_ring(grid, self._SEALED, 1)
        radius = const.PATH_FALLBACK_RADIUS
        steps = _steps_from(grid, self._START)
        square = [tile for tile in steps
                  if _chebyshev(tile, self._SEALED) <= radius]
        expected = min((_squared(tile, self._SEALED), steps[tile], tile)
                       for tile in square)[-1]

        path, reached = find_nearest_path(grid, self._START, self._SEALED)

        self.assertFalse(reached)
        self.assertEqual(path[-1], expected)
        self.assertEqual(len(path), steps[expected])
        self.assertLegalWalk(grid, self._START, path)

    def test_a_blocked_goal_next_to_the_start_gives_an_empty_walk(self):
        grid = _open_grid()
        goal = (self._START[0] + 1, self._START[1])
        _block(grid, *goal)

        self.assertEqual(find_nearest_path(grid, self._START, goal),
                         ([], False))

    def test_the_radius_bounds_the_nearest_tile(self):
        # The nearest open tile is one tile past the radius.
        grid = _open_grid()
        radius = const.PATH_FALLBACK_RADIUS
        _block_ring(grid, self._SEALED, radius)

        self.assertIsNone(find_nearest_path(grid, self._START, self._SEALED))
        self.assertIsNotNone(find_nearest_path(grid, self._START, self._SEALED,
                                               radius=radius + 1))

    def test_a_goal_far_off_the_grid_has_no_walk(self):
        grid = _open_grid()
        goal = (-(const.PATH_FALLBACK_RADIUS + 1), self._START[1])

        self.assertIsNone(find_nearest_path(grid, self._START, goal))

    def test_the_same_question_gets_the_same_nearest_tile(self):
        grid = _open_grid()
        _block_ring(grid, self._SEALED, 1)
        first = find_nearest_path(grid, self._START, self._SEALED)
        second = find_nearest_path(grid, self._START, self._SEALED)

        self.assertEqual(first, second)
