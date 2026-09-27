"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/26/2026
Description: Tests for the room Z of each plane (DESIGN-0011 Phase 7), and for
             a TileWorld with more than one plane. No database.
"""

import unittest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as const
from systems.core.tilegrid.planes import plane_of_z, plane_z
from systems.core.tilegrid.world import TileWorld


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = const.CHUNK_SIZE
_UPPER = const.GROUND_PLANE + 1

# A tile that plane 1 opens and that plane 0 blocks.
_UPSTAIRS = (5, 5)

_KIND = "respawn_point"


# ─── Private helper routines ─────────────────────────────────────────────────

def _chunk(plane: int, open_tiles=(), objects=()) -> chunkfile.ChunkFile:
    """
    One chunk (0, 0) on a plane. Every tile is blocked but `open_tiles`, the
    way an upper floor covers only its building.
    """
    tile_count = _SIZE * _SIZE
    flags = [const.FLAG_BLOCKED] * tile_count

    for x, y in open_tiles:
        flags[y * _SIZE + x] = const.FLAG_NONE

    return chunkfile.ChunkFile(
        cx=0, cy=0, plane=plane, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=flags, areas=[0] * tile_count,
        objects=list(objects))


# ─── Tests ───────────────────────────────────────────────────────────────────

class PlaneZTests(unittest.TestCase):

    def test_plane_zero_keeps_the_world_name(self):
        # No room of plane 0 needed a migration.
        self.assertEqual(plane_z(const.GROUND_PLANE), const.WORLD_Z)

    def test_every_plane_has_its_own_z_and_reads_back(self):
        seen = set()

        for plane in range(const.GROUND_PLANE, const.PLANE_MAX + 1):
            with self.subTest(plane=plane):
                z = plane_z(plane)

                self.assertNotIn(z, seen)
                self.assertEqual(plane_of_z(z), plane)
                seen.add(z)

    def test_a_pool_z_is_on_no_plane(self):
        for plane in range(const.GROUND_PLANE, const.PLANE_MAX + 1):
            with self.subTest(plane=plane):
                pool = plane_z(plane) + const.POOL_Z_SUFFIX

                self.assertIsNone(plane_of_z(pool))

    def test_a_z_of_no_plane_reads_none(self):
        for z in (None, "", "oasis", const.WORLD_Z + "_p",
                  plane_z(const.PLANE_MAX) + "0"):
            with self.subTest(z=z):
                self.assertIsNone(plane_of_z(z))


class TwoPlaneWorldTests(unittest.TestCase):

    def setUp(self):
        placed = [chunkfile.ChunkObject(_KIND, *_UPSTAIRS)]
        self.world = TileWorld([_chunk(const.GROUND_PLANE),
                                _chunk(_UPPER, [_UPSTAIRS], placed)])

    def test_the_world_has_a_plane_for_every_number(self):
        numbers = [plane.plane for plane in self.world.planes()]

        self.assertEqual(numbers,
                         list(range(const.GROUND_PLANE, const.PLANE_MAX + 1)))

    def test_each_plane_reads_its_own_chunk_file(self):
        upper = self.world.plane(_UPPER)

        self.assertFalse(self.world.grid.flags_at(*_UPSTAIRS)
                         == const.FLAG_NONE)
        self.assertEqual(upper.grid.flags_at(*_UPSTAIRS), const.FLAG_NONE)

    def test_each_plane_keeps_its_own_objects_and_pins(self):
        upper = self.world.plane(_UPPER)

        self.assertEqual(upper.kinds_at(*_UPSTAIRS), [_KIND])
        self.assertEqual(self.world.kinds_at(*_UPSTAIRS), [])
        self.assertTrue(upper.rooms.is_pinned(*_UPSTAIRS))
        self.assertFalse(self.world.rooms.is_pinned(*_UPSTAIRS))

    def test_each_plane_has_the_rooms_of_its_own_z(self):
        for tile_plane in self.world.planes():
            with self.subTest(plane=tile_plane.plane):
                self.assertEqual(tile_plane.world_z, plane_z(tile_plane.plane))
                self.assertIs(self.world.plane_for_z(tile_plane.world_z),
                              tile_plane)

    def test_a_plane_with_no_chunk_file_is_all_blocked(self):
        empty = self.world.plane(const.PLANE_MAX)

        self.assertFalse(empty.has_chunks())
        self.assertEqual(empty.grid.flags_at(*_UPSTAIRS), const.FLAG_BLOCKED)

    def test_the_world_reads_of_plane_zero_stay(self):
        self.assertIs(self.world.grid, self.world.plane(const.GROUND_PLANE).grid)
        self.assertIs(self.world.rooms,
                      self.world.plane(const.GROUND_PLANE).rooms)
        self.assertEqual(self.world.world_z, const.WORLD_Z)
