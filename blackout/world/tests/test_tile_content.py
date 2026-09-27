"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Guards for the three tables that a chunk file names: the floor
             types, the areas, and the object kinds.

             Run from blackout/:
                 ../evenv/Scripts/evennia.exe test --settings test_settings.py world.tests.test_tile_content

             NO CENSUS HERE. A new floor type, a new area, and a new sign are
             intended content. Each case below checks a relationship:

             - Every key is a legal chunk file name.
             - Every kind names a category that exists, and a spawner that
               exists.
             - A sign has words, and nothing else has words.
             - Every world chunk file names only rows of these tables.
"""

import os
import re
import unittest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from typeclasses import spawners
from world import areas
from world import floor_types
from world import object_kinds

# The game directory, two levels above this file.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

_WORLD_CHUNK_DIRECTORY = os.path.join(_GAME_DIR, tile_const.CHUNK_DIRECTORY)

_NAME_RE = re.compile(tile_const.CHUNK_NAME_PATTERN)

# Each table, by the name a failure message gives it.
_TABLES: tuple = (
    ("floor type", floor_types.FLOOR_TYPES),
    ("area", areas.AREAS),
    ("object kind", object_kinds.OBJECT_KINDS),
)


class TableShapeTests(unittest.TestCase):
    """Every row of every table is a legal chunk file name."""

    def test_every_key_is_a_legal_chunk_file_name(self):
        for label, table in _TABLES:
            for key, row in table.items():
                with self.subTest(table=label, key=key):
                    self.assertIsNotNone(_NAME_RE.search(key))
                    self.assertEqual(row.key, key)

    def test_the_defaults_are_rows_of_their_tables(self):
        self.assertIn(floor_types.DEFAULT_FLOOR_TYPE, floor_types.FLOOR_TYPES)
        self.assertIn(areas.DEFAULT_AREA, areas.AREAS)


class ObjectKindTests(unittest.TestCase):
    """Every object kind can stand something up in Phase 4."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        spawners.load_all_spawners()

    def test_every_kind_names_a_category_that_exists(self):
        for key, kind in object_kinds.OBJECT_KINDS.items():
            with self.subTest(kind=key):
                self.assertIn(kind.category, tile_const.OBJECT_CATEGORIES)

    def test_every_spawner_is_a_registered_spawner(self):
        for key, kind in object_kinds.OBJECT_KINDS.items():
            if not kind.spawner:
                continue

            with self.subTest(kind=key, spawner=kind.spawner):
                self.assertIn(kind.spawner, spawners.SPAWNER_REGISTRY)

    def test_a_sign_has_words_and_nothing_else_does(self):
        for key, kind in object_kinds.OBJECT_KINDS.items():
            is_sign = kind.category == tile_const.OBJECT_CATEGORY_SIGN

            with self.subTest(kind=key):
                self.assertEqual(bool(kind.label), is_sign)

    def test_every_kind_that_stands_something_up_has_a_spawner(self):
        # A sign, a landmark, a transition, and a climb stand up nothing of
        # their own. Every other kind must name its spawner.
        spawnless = (tile_const.OBJECT_CATEGORY_CLIMB,
                     tile_const.OBJECT_CATEGORY_LANDMARK,
                     tile_const.OBJECT_CATEGORY_SIGN,
                     tile_const.OBJECT_CATEGORY_TRANSITION)

        for key, kind in object_kinds.OBJECT_KINDS.items():
            with self.subTest(kind=key):
                self.assertEqual(bool(kind.spawner),
                                 kind.category not in spawnless)

    def test_a_transition_has_a_target_and_nothing_else_does(self):
        for key, kind in object_kinds.OBJECT_KINDS.items():
            is_transition = (kind.category
                             == tile_const.OBJECT_CATEGORY_TRANSITION)

            with self.subTest(kind=key):
                self.assertEqual(bool(kind.target), is_transition)

                if is_transition:
                    self.assertEqual(len(kind.target), 2)
                    self.assertTrue(all(isinstance(value, int)
                                        for value in kind.target))

    def test_a_climb_has_directions_and_nothing_else_does(self):
        # Phase 7. A climb lists its ways, each a word of CLIMB_PLANE_STEPS,
        # with no repeat.
        for key, kind in object_kinds.OBJECT_KINDS.items():
            is_climb = kind.category == tile_const.OBJECT_CATEGORY_CLIMB

            with self.subTest(kind=key):
                self.assertEqual(bool(kind.climbs), is_climb)
                self.assertEqual(len(set(kind.climbs)), len(kind.climbs))

                for way in kind.climbs:
                    self.assertIn(way, tile_const.CLIMB_PLANE_STEPS)

    def test_a_kind_with_a_room_name_has_a_room_desc(self):
        for key, kind in object_kinds.OBJECT_KINDS.items():
            with self.subTest(kind=key):
                self.assertEqual(bool(kind.name), bool(kind.desc))

    def test_every_area_has_room_texts(self):
        for key, area in areas.AREAS.items():
            with self.subTest(area=key):
                self.assertTrue(area.name)
                self.assertTrue(area.desc)


class WorldChunkTests(unittest.TestCase):
    """Every world chunk file names only rows of the three tables."""

    def test_every_name_in_a_world_chunk_file_is_a_row(self):
        found = chunkfile.load_directory(_WORLD_CHUNK_DIRECTORY)

        for chunk in found:
            used = (
                ("floor type", chunk.floor_names, floor_types.FLOOR_TYPES),
                ("area", chunk.area_names, areas.AREAS),
                ("object kind", [thing.kind for thing in chunk.objects],
                 object_kinds.OBJECT_KINDS),
            )

            for label, names, table in used:
                for name in names:
                    with self.subTest(chunk=chunk.file_name(), table=label,
                                      name=name):
                        self.assertIn(name, table)

    def test_every_placed_transition_lands_on_an_open_tile(self):
        """A walker that steps onto a transition must have a place to land.
        The converter test checked this until DESIGN-0011 Phase 4b."""
        found = chunkfile.load_directory(_WORLD_CHUNK_DIRECTORY)
        grid = chunkfile.build_grid(found)
        placed = {thing.kind for chunk in found for thing in chunk.objects}

        for key in sorted(placed):
            kind = object_kinds.OBJECT_KINDS.get(key)

            if kind is None or not kind.target:
                continue

            with self.subTest(kind=key):
                self.assertTrue(grid.has_tile(*kind.target))
                flags = grid.flags_at(*kind.target)
                self.assertFalse(flags & tile_const.FLAGS_UNWALKABLE)
