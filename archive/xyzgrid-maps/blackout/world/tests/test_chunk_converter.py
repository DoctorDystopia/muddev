"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for `world/maps/chunk_converter.py`. Each case converts
             every map of the manifest in memory and checks the result
             against the xyzgrid parse of the same map. No database.

             Run from blackout/:
                 ../evenv/Scripts/evennia.exe test --settings test_settings.py world.tests.test_chunk_converter
"""

import importlib
import unittest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid.pathfind import find_path
from world.areas import AREAS
from world.maps import chunk_converter
from world.maps import manifest as map_manifest
from world.object_kinds import OBJECT_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE

# The four cardinal offsets.
_CARDINALS = tuple(tile_const.EDGE_WALL_LEAVING)

_TRANSITION = tile_const.OBJECT_CATEGORY_TRANSITION


# ─── Private helper routines ─────────────────────────────────────────────────

def _map_data_of(entry) -> dict:
    """Return the XYMAP_DATA of one manifest entry."""
    module = importlib.import_module(entry.module)

    for map_data in module.XYMAP_DATA_LIST:
        if map_data["zcoord"] == entry.zcoord:
            return map_data

    raise LookupError(entry.zcoord)


# ─── Tests ───────────────────────────────────────────────────────────────────

class ChunkConverterTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.entries = map_manifest.load_entries()
        cls.map_data = {entry.zcoord: _map_data_of(entry)
                        for entry in cls.entries}
        cls.conversions = {z: chunk_converter.convert_map(data)
                           for z, data in cls.map_data.items()}
        cls.parsed = {z: chunk_converter.parse_map(data)
                      for z, data in cls.map_data.items()}
        cls.grid = chunkfile.build_grid(
            [c.chunk_file for c in cls.conversions.values()])

    def test_every_manifest_map_has_a_chunk_and_an_area(self):
        for entry in self.entries:
            with self.subTest(map=entry.zcoord):
                self.assertIn(entry.zcoord, chunk_converter.MAP_CHUNKS)
                self.assertIn(entry.zcoord, AREAS)

    def test_each_map_has_its_own_chunk(self):
        chunks = [chunk_converter.MAP_CHUNKS[z] for z in self.conversions]

        self.assertEqual(len(chunks), len(set(chunks)))

    def test_the_output_is_a_legal_chunk_file(self):
        for zcoord, conversion in self.conversions.items():
            with self.subTest(map=zcoord):
                text = chunkfile.to_text(conversion.chunk_file)
                self.assertEqual(chunkfile.parse_text(text),
                                 conversion.chunk_file)

    def test_every_node_is_a_walkable_tile(self):
        for zcoord, xymap in self.parsed.items():
            chunk_file = self.conversions[zcoord].chunk_file

            for node in xymap.node_index_map.values():
                with self.subTest(map=zcoord, node=(node.X, node.Y)):
                    flags = chunk_file.flags[node.Y * _SIZE + node.X]
                    self.assertFalse(flags & tile_const.FLAGS_UNWALKABLE)

    def test_every_xyzgrid_link_is_a_walk_no_longer_than_its_tiles(self):
        for zcoord, xymap in self.parsed.items():
            cx, cy = chunk_converter.MAP_CHUNKS[zcoord]
            origin = (cx * _SIZE, cy * _SIZE)

            for start, end, chain in chunk_converter.link_chains(xymap):
                with self.subTest(map=zcoord, link=(start, end)):
                    begin = (origin[0] + start[0], origin[1] + start[1])
                    goal = (origin[0] + end[0], origin[1] + end[1])
                    path = find_path(self.grid, begin, goal)
                    self.assertIsNotNone(path)
                    self.assertLessEqual(len(path), len(chain) - 1)

    def test_every_open_edge_is_a_link_or_a_listed_join(self):
        # A step between two walkable neighbours is legal only where a link
        # of the map runs, or where the converter lists the join it added.
        for zcoord, xymap in self.parsed.items():
            conversion = self.conversions[zcoord]
            linked = set()

            for _start, _end, chain in chunk_converter.link_chains(xymap):
                linked.update(frozenset(pair) for pair in zip(chain, chain[1:]))

            allowed = linked | conversion.added_edges
            cx, cy = chunk_converter.MAP_CHUNKS[zcoord]

            for x, y in conversion.walkable:
                for dx, dy in _CARDINALS:
                    there = (x + dx, y + dy)
                    here_world = (cx * _SIZE + x, cy * _SIZE + y)
                    there_world = (here_world[0] + dx, here_world[1] + dy)
                    legal = self.grid.check_step(here_world, there_world)

                    if legal != tile_const.STEP_OK:
                        continue

                    with self.subTest(map=zcoord, edge=((x, y), there)):
                        self.assertIn(frozenset(((x, y), there)), allowed)

    def test_every_transition_node_has_its_kind(self):
        for zcoord, conversion in self.conversions.items():
            with self.subTest(map=zcoord):
                missed = [row for row in conversion.unmatched
                          if str(row[2]).startswith("transition")]
                self.assertEqual(missed, [])

    def test_every_transition_kind_is_placed_and_lands_on_a_walkable_tile(self):
        placed = {thing.kind for conversion in self.conversions.values()
                  for thing in conversion.chunk_file.objects}

        for key, kind in OBJECT_KINDS.items():
            if kind.category != _TRANSITION:
                continue

            with self.subTest(kind=key):
                self.assertIn(key, placed)
                flags = self.grid.flags_at(*kind.target)
                self.assertFalse(flags & tile_const.FLAGS_UNWALKABLE)

    def test_every_placed_kind_is_a_row(self):
        for zcoord, conversion in self.conversions.items():
            for thing in conversion.chunk_file.objects:
                with self.subTest(map=zcoord, kind=thing.kind):
                    self.assertIn(thing.kind, OBJECT_KINDS)
