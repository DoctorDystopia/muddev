"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for the tile grid arrays and the step rule. No database.
"""

import unittest

from systems.core.tilegrid import constants as const
from systems.core.tilegrid.grid import Chunk, TileGrid


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = const.CHUNK_SIZE
_SIDE = const.CORNERS_PER_SIDE

# A tile well inside chunk (0, 0), so all eight neighbours are loaded.
_MIDDLE = (10, 10)


# ─── Private helper routines ─────────────────────────────────────────────────

def _set_flags(chunk: Chunk, x: int, y: int, flags: int) -> None:
    """Set the flags of a tile of chunk (0, 0)."""
    chunk.flags[y * _SIZE + x] = flags


def _set_corner(chunk: Chunk, x: int, y: int, height: int) -> None:
    """Set one corner height of chunk (0, 0)."""
    chunk.heights[y * _SIDE + x] = height


def _one_chunk_grid():
    """Return a grid with one open, flat chunk at (0, 0), and the chunk."""
    grid = TileGrid()
    chunk = Chunk(0, 0)
    grid.add_chunk(chunk)

    return grid, chunk


def _neighbour(direction: str) -> tuple:
    offset = const.DIRECTION_OFFSETS[direction]

    return (_MIDDLE[0] + offset[0], _MIDDLE[1] + offset[1])


# ─── Tests ───────────────────────────────────────────────────────────────────

class ChunkShapeTests(unittest.TestCase):

    def test_a_new_chunk_has_the_chunk_shape(self):
        chunk = Chunk(0, 0)

        self.assertEqual(len(chunk.heights), _SIDE * _SIDE)
        self.assertEqual(len(chunk.flags), _SIZE * _SIZE)
        self.assertEqual(len(chunk.floors), _SIZE * _SIZE)

    def test_a_chunk_with_the_wrong_shape_is_refused(self):
        with self.assertRaises(ValueError):
            Chunk(0, 0, heights=[0] * (_SIZE * _SIZE))

        with self.assertRaises(ValueError):
            Chunk(0, 0, flags=[0])


class TileLookupTests(unittest.TestCase):

    def test_a_tile_off_the_grid_is_blocked(self):
        grid, _chunk = _one_chunk_grid()

        self.assertFalse(grid.has_tile(_SIZE, 0))
        self.assertTrue(grid.flags_at(_SIZE, 0) & const.FLAG_BLOCKED)

    def test_negative_coordinates_find_their_own_chunk(self):
        grid = TileGrid()
        chunk = Chunk(-1, -1)
        chunk.flags[(_SIZE - 1) * _SIZE + (_SIZE - 1)] = const.FLAG_WATER
        grid.add_chunk(chunk)

        self.assertTrue(grid.has_tile(-1, -1))
        self.assertFalse(grid.has_tile(0, 0))
        self.assertEqual(grid.flags_at(-1, -1), const.FLAG_WATER)

    def test_the_tile_height_is_the_lowest_corner(self):
        grid, chunk = _one_chunk_grid()
        x, y = _MIDDLE

        _set_corner(chunk, x, y, 5)
        _set_corner(chunk, x + 1, y, 3)
        _set_corner(chunk, x, y + 1, 7)
        _set_corner(chunk, x + 1, y + 1, 4)

        self.assertEqual(grid.corner_heights(x, y), (5, 3, 7, 4))
        self.assertEqual(grid.tile_height(x, y), 3)

    def test_the_last_tile_reads_the_edge_corners_of_its_own_chunk(self):
        grid, chunk = _one_chunk_grid()
        last = _SIZE - 1
        _set_corner(chunk, _SIZE, _SIZE, 9)

        self.assertEqual(grid.corner_heights(last, last)[3], 9)


class StepRuleTests(unittest.TestCase):

    def test_every_direction_is_open_on_open_ground(self):
        grid, _chunk = _one_chunk_grid()

        for direction in const.DIRECTION_OFFSETS:
            with self.subTest(direction=direction):
                result = grid.check_step(_MIDDLE, _neighbour(direction))
                self.assertEqual(result, const.STEP_OK)

    def test_only_a_neighbour_is_a_step(self):
        grid, _chunk = _one_chunk_grid()
        far = (_MIDDLE[0] + 2, _MIDDLE[1])

        self.assertEqual(grid.check_step(_MIDDLE, far), const.STEP_NOT_ADJACENT)
        self.assertEqual(grid.check_step(_MIDDLE, _MIDDLE),
                         const.STEP_NOT_ADJACENT)

    def test_a_blocked_or_water_tile_refuses_entry(self):
        for flag in (const.FLAG_BLOCKED, const.FLAG_WATER):
            with self.subTest(flag=flag):
                grid, chunk = _one_chunk_grid()
                target = _neighbour("north")
                _set_flags(chunk, target[0], target[1], flag)

                self.assertEqual(grid.check_step(_MIDDLE, target),
                                 const.STEP_BLOCKED)

    def test_the_edge_of_the_world_refuses_entry(self):
        grid, _chunk = _one_chunk_grid()
        edge = (_SIZE - 1, 5)

        self.assertEqual(grid.check_step(edge, (_SIZE, 5)), const.STEP_OFF_GRID)

    def test_a_wall_on_either_side_of_an_edge_refuses_the_step(self):
        cases = (
            ("leaving", _MIDDLE, const.FLAG_WALL_NORTH),
            ("entering", _neighbour("north"), const.FLAG_WALL_SOUTH),
        )

        for label, tile, flag in cases:
            with self.subTest(side=label):
                grid, chunk = _one_chunk_grid()
                _set_flags(chunk, tile[0], tile[1], flag)

                self.assertEqual(grid.check_step(_MIDDLE, _neighbour("north")),
                                 const.STEP_WALL)

    def test_a_wall_blocks_only_its_own_edge(self):
        grid, chunk = _one_chunk_grid()
        _set_flags(chunk, _MIDDLE[0], _MIDDLE[1], const.FLAG_WALL_NORTH)

        self.assertEqual(grid.check_step(_MIDDLE, _neighbour("east")),
                         const.STEP_OK)

    def test_a_diagonal_may_not_cut_a_blocked_corner(self):
        for side in ("north", "east"):
            with self.subTest(blocked=side):
                grid, chunk = _one_chunk_grid()
                tile = _neighbour(side)
                _set_flags(chunk, tile[0], tile[1], const.FLAG_BLOCKED)

                self.assertEqual(
                    grid.check_step(_MIDDLE, _neighbour("northeast")),
                    const.STEP_CORNER)

    def test_a_diagonal_may_not_pass_a_wall_at_the_corner(self):
        # A wall on the east edge of the north tile stands between that tile
        # and the northeast target. One leg is shut, so the diagonal is too.
        grid, chunk = _one_chunk_grid()
        north = _neighbour("north")
        _set_flags(chunk, north[0], north[1], const.FLAG_WALL_EAST)

        self.assertEqual(grid.check_step(_MIDDLE, _neighbour("northeast")),
                         const.STEP_CORNER)

    def test_no_walk_limit_means_no_height_rule(self):
        grid, chunk = _one_chunk_grid()
        target = _neighbour("north")

        for dx in (0, 1):
            for dy in (0, 1):
                _set_corner(chunk, target[0] + dx, target[1] + dy, 100)

        self.assertEqual(grid.check_step(_MIDDLE, target, walk_limit=None),
                         const.STEP_OK)

    def test_the_walk_limit_refuses_a_climb_or_a_drop_above_it(self):
        grid, chunk = _one_chunk_grid()
        target = _neighbour("east")
        limit = 2

        for dx in (0, 1):
            for dy in (0, 1):
                _set_corner(chunk, target[0] + dx, target[1] + dy, limit + 1)

        # The start tile shares two corners with the target. Its lowest
        # corner stays 0, so the rise is limit + 1 both ways.
        self.assertEqual(grid.check_step(_MIDDLE, target, walk_limit=limit),
                         const.STEP_TOO_STEEP)
        self.assertEqual(grid.check_step(target, _MIDDLE, walk_limit=limit),
                         const.STEP_TOO_STEEP)
        self.assertEqual(grid.check_step(_MIDDLE, target, walk_limit=limit + 1),
                         const.STEP_OK)
