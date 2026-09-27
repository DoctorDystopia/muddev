"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/26/2026
Description: Tests for line of sight on the tile grid. No database.

The rule is in the Obsidian vault, 03_Systems/Combat_System.md, "Line of
sight": walls and Blocked tiles stop a shot. Water and height do not.
"""

import random
import unittest

from systems.core.tilegrid import constants as const
from systems.core.tilegrid.grid import Chunk, TileGrid
from systems.core.tilegrid.sight import has_line_of_sight


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = const.CHUNK_SIZE
_SIDE = const.CORNERS_PER_SIDE

_START = (10, 10)
_EAST_GOAL = (16, 10)
_NORTH_GOAL = (10, 16)

# One tile on the straight line from _START to _EAST_GOAL.
_ON_THE_LINE = (13, 10)

# A seeded walk over many random lines, for the shape of each walk.
_SEED = 20260926
_LINE_COUNT = 500

# A height far above the walk limit. Height must not stop a shot.
_MOUNTAIN = const.WALK_LIMIT * 10


# ─── Private helper routines ─────────────────────────────────────────────────

def _grid():
    """Return a grid of 3 x 3 open, flat chunks around the origin chunk."""
    grid = TileGrid()
    chunk = None

    for cx in (-1, 0, 1):
        for cy in (-1, 0, 1):
            made = Chunk(cx, cy)
            grid.add_chunk(made)

            if (cx, cy) == (0, 0):
                chunk = made

    return grid, chunk


def _set_flags(chunk, tile, flags):
    chunk.flags[tile[1] * _SIZE + tile[0]] = flags


class _RecordingGrid:
    """A grid that records each tile the walk reads, in order."""

    def __init__(self, grid):
        self._grid = grid
        self.reads = []

    def flags_at(self, x, y):
        self.reads.append((x, y))

        return self._grid.flags_at(x, y)


# ─── Tests ───────────────────────────────────────────────────────────────────

class LineOfSightRuleTests(unittest.TestCase):

    def test_a_tile_sees_itself(self):
        grid, _chunk = _grid()

        self.assertTrue(has_line_of_sight(grid, _START, _START))

    def test_open_ground_gives_sight(self):
        grid, _chunk = _grid()

        for goal in (_EAST_GOAL, _NORTH_GOAL, (16, 16), (4, 13), (7, 3)):
            with self.subTest(goal=goal):
                self.assertTrue(has_line_of_sight(grid, _START, goal))

    def test_a_blocked_tile_on_the_line_stops_the_shot(self):
        grid, chunk = _grid()
        _set_flags(chunk, _ON_THE_LINE, const.FLAG_BLOCKED)

        self.assertFalse(has_line_of_sight(grid, _START, _EAST_GOAL))
        self.assertFalse(has_line_of_sight(grid, _EAST_GOAL, _START))

    def test_a_blocked_goal_does_not_stop_the_shot(self):
        grid, chunk = _grid()
        _set_flags(chunk, _EAST_GOAL, const.FLAG_BLOCKED)

        self.assertTrue(has_line_of_sight(grid, _START, _EAST_GOAL))

    def test_water_does_not_stop_the_shot(self):
        grid, chunk = _grid()
        _set_flags(chunk, _ON_THE_LINE, const.FLAG_WATER)

        self.assertTrue(has_line_of_sight(grid, _START, _EAST_GOAL))

    def test_height_does_not_stop_the_shot(self):
        grid, chunk = _grid()

        for dx in (0, 1):
            for dy in (0, 1):
                corner = (_ON_THE_LINE[1] + dy) * _SIDE + _ON_THE_LINE[0] + dx
                chunk.heights[corner] = _MOUNTAIN

        self.assertTrue(has_line_of_sight(grid, _START, _EAST_GOAL))

    def test_a_wall_on_the_crossed_edge_stops_the_shot(self):
        # The same edge, stored on either of its two tiles.
        west_of_line = (_ON_THE_LINE[0] - 1, _ON_THE_LINE[1])

        for tile, flag in ((_ON_THE_LINE, const.FLAG_WALL_WEST),
                           (west_of_line, const.FLAG_WALL_EAST)):
            with self.subTest(flag=flag):
                grid, chunk = _grid()
                _set_flags(chunk, tile, flag)

                self.assertFalse(has_line_of_sight(grid, _START, _EAST_GOAL))

    def test_a_wall_along_the_line_does_not_stop_the_shot(self):
        # A north wall is parallel to an east shot. The line crosses no
        # north edge.
        grid, chunk = _grid()
        _set_flags(chunk, _ON_THE_LINE, const.FLAG_WALL_NORTH)

        self.assertTrue(has_line_of_sight(grid, _START, _EAST_GOAL))

    def test_the_edge_of_the_world_stops_the_shot(self):
        grid, _chunk = _grid()
        beyond = (_SIZE * 2 + 5, 10)

        self.assertFalse(has_line_of_sight(grid, _START, beyond))


class LineOfSightWalkTests(unittest.TestCase):
    """The shape of the walk, on many seeded lines."""

    def test_each_walk_crosses_one_edge_at_a_time_and_ends_on_the_goal(self):
        grid, _chunk = _grid()
        rng = random.Random(_SEED)
        low, high = -_SIZE + 1, _SIZE * 2 - 2

        for _line in range(_LINE_COUNT):
            start = (rng.randint(low, high), rng.randint(low, high))
            goal = (rng.randint(low, high), rng.randint(low, high))

            if start == goal:
                continue

            recorder = _RecordingGrid(grid)

            with self.subTest(start=start, goal=goal):
                self.assertTrue(has_line_of_sight(recorder, start, goal))

                # Each crossing reads the tile it leaves, then the tile it
                # enters. The entered tiles must form a chain of edges.
                entered = recorder.reads[1::2]
                chain = [start] + entered

                for here, there in zip(chain, chain[1:]):
                    step = abs(there[0] - here[0]) + abs(there[1] - here[1])
                    self.assertEqual(step, 1, (here, there))

                self.assertEqual(entered[-1], goal)
