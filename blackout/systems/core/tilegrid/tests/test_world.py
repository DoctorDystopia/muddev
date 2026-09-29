"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for the tile world: the name reads and the object index.
             No database. The expectations come from the fixture chunk files,
             not from typed values.
"""

import unittest

from systems.core.tilegrid import constants as const
from systems.core.tilegrid.tests import fixture_builder
from systems.core.tilegrid.world import TileWorld, get_world, set_world


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = const.CHUNK_SIZE

# A tile far from every fixture chunk.
_FAR_TILE = (100 * _SIZE, 100 * _SIZE)


# ─── Tests ───────────────────────────────────────────────────────────────────

class TileWorldTests(unittest.TestCase):

    def setUp(self):
        self.chunk_files = fixture_builder.build_fixtures()
        self.world = TileWorld(self.chunk_files)
        self.ground = [f for f in self.chunk_files if f.plane == 0]

    def test_only_the_ground_plane_is_on_the_grid(self):
        for chunk_file in self.chunk_files:
            origin = (chunk_file.cx * _SIZE, chunk_file.cy * _SIZE)
            loaded = self.world.has_tile(*origin)
            is_ground = chunk_file.plane == 0
            ground_here = any((f.cx, f.cy) == (chunk_file.cx, chunk_file.cy)
                              for f in self.ground)

            with self.subTest(chunk=chunk_file.file_name()):
                if is_ground:
                    self.assertTrue(loaded)
                else:
                    self.assertEqual(loaded, ground_here)

    def test_a_name_read_is_the_read_of_the_chunk_file(self):
        for chunk_file in self.ground:
            origin_x = chunk_file.cx * _SIZE
            origin_y = chunk_file.cy * _SIZE

            for lx, ly in ((0, 0), (_SIZE - 1, _SIZE - 1), (17, 42)):
                with self.subTest(chunk=chunk_file.file_name(), tile=(lx, ly)):
                    x, y = origin_x + lx, origin_y + ly
                    self.assertEqual(self.world.area_at(x, y),
                                     chunk_file.area_name(lx, ly))
                    self.assertEqual(self.world.floor_at(x, y),
                                     chunk_file.floor_name(lx, ly))

    def test_a_tile_off_the_grid_has_no_names(self):
        self.assertIsNone(self.world.area_at(*_FAR_TILE))
        self.assertIsNone(self.world.floor_at(*_FAR_TILE))
        self.assertEqual(self.world.kinds_at(*_FAR_TILE), [])

    def test_every_ground_object_is_indexed_at_its_world_tile(self):
        expected = []

        for chunk_file in self.ground:
            expected.extend(chunk_file.global_objects())

        self.assertEqual(sorted(self.world.placed_objects()), sorted(expected))

        for kind, x, y, _rotation in expected:
            with self.subTest(kind=kind, tile=(x, y)):
                self.assertIn(kind, self.world.kinds_at(x, y))

    def test_the_world_z_is_the_z_of_its_rooms(self):
        self.assertEqual(self.world.world_z, self.world.rooms.world_z)


class WorldSingletonTests(unittest.TestCase):

    def tearDown(self):
        set_world(None)

    def test_a_set_world_is_the_world_that_get_world_returns(self):
        world = TileWorld([])
        set_world(world)

        self.assertIs(get_world(), world)
