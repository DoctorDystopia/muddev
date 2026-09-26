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
from systems.core.tilegrid.pathfind import find_path


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = const.CHUNK_SIZE

# The column of the wall in the detour case, and the one gap in it.
_WALL_X = 20
_GAP_Y = 50


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

    def test_the_same_question_gets_the_same_path(self):
        grid = _open_grid()
        first = find_path(grid, (5, 5), (25, 9))
        second = find_path(grid, (5, 5), (25, 9))

        self.assertEqual(first, second)
