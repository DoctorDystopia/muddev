"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Guards for the four tables that a chunk file names: the floor
             types, the areas, the wall styles, and the object kinds.

             Run from blackout/:
                 ../evenv/Scripts/evennia.exe test --settings test_settings.py world.tests.test_tile_content

             NO CENSUS HERE. A new floor type, a new area, and a new sign are
             intended content. Each case below checks a relationship:

             - Every key is a legal chunk file name.
             - Every kind names a category that exists, and a spawner that
               exists.
             - The chunk file holds the words of a sign, and the label cap
               never cuts them.
             - Every world chunk file names only rows of these tables.
"""

import os
import re
import unittest

from assets.pipeline import records as model_records
from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.interface.statefeed import constants as feed_const
from typeclasses import spawners
from world import areas
from world import floor_types
from world import object_kinds
from world import tile_checks
from world import wall_styles

# The game directory, two levels above this file.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

_WORLD_CHUNK_DIRECTORY = os.path.join(_GAME_DIR, tile_const.CHUNK_DIRECTORY)

_NAME_RE = re.compile(tile_const.CHUNK_NAME_PATTERN)

# Each table, by the name a failure message gives it.
_TABLES: tuple = (
    ("floor type", floor_types.FLOOR_TYPES),
    ("area", areas.AREAS),
    ("wall style", wall_styles.WALL_STYLES),
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
        self.assertIn(wall_styles.DEFAULT_WALL_STYLE, wall_styles.WALL_STYLES)

    def test_the_default_wall_style_is_the_style_of_a_format_one_file(self):
        # A format 1 file reads as the chunk file default on every tile. The
        # table must give that name a row, or every old wall loses its style.
        self.assertEqual(wall_styles.DEFAULT_WALL_STYLE,
                         tile_const.DEFAULT_WALL_STYLE)

    def test_every_wall_style_stands_above_the_ground(self):
        for key, style in wall_styles.WALL_STYLES.items():
            with self.subTest(style=key):
                self.assertIsInstance(style.height, int)
                self.assertGreater(style.height, 0)


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

    def test_the_text_category_is_a_category(self):
        self.assertIn(tile_const.OBJECT_TEXT_CATEGORY,
                      tile_const.OBJECT_CATEGORIES)
        self.assertEqual(
            object_kinds.OBJECT_KINDS[object_kinds.SIGNPOST_KIND].category,
            tile_const.OBJECT_TEXT_CATEGORY)

    def test_the_label_cap_never_cuts_a_chunk_text(self):
        # labels.normalise cuts at WORLD_LABEL_MAX_CHARS. A sign must show
        # every word that its chunk file holds.
        self.assertLessEqual(tile_const.CHUNK_TEXT_MAX_CHARS,
                             feed_const.WORLD_LABEL_MAX_CHARS)

    def test_every_kind_that_stands_something_up_has_a_spawner(self):
        # A sign, a landmark, a transition, a climb, and decor stand up
        # nothing of their own. Every other kind must name its spawner.
        spawnless = (tile_const.OBJECT_CATEGORY_CLIMB,
                     tile_const.OBJECT_CATEGORY_DECOR,
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

    def test_decor_is_scenery_and_nothing_more(self):
        # DESIGN-0013 section 6.5. A decor kind with no scenery draws
        # nothing, and a name would name the tile of every crate.
        for key, kind in object_kinds.OBJECT_KINDS.items():
            if kind.category != tile_const.OBJECT_CATEGORY_DECOR:
                continue

            with self.subTest(kind=key):
                self.assertTrue(kind.scenery)
                self.assertEqual(kind.name, "")
                self.assertEqual(kind.preview, ())

    def test_the_unpinned_kinds_are_the_decor_kinds(self):
        decor = {key for key, kind in object_kinds.OBJECT_KINDS.items()
                 if kind.category == tile_const.OBJECT_CATEGORY_DECOR}

        self.assertEqual(object_kinds.UNPINNED_KINDS, decor)

    def test_a_kind_with_a_room_name_has_a_room_desc(self):
        for key, kind in object_kinds.OBJECT_KINDS.items():
            with self.subTest(kind=key):
                self.assertEqual(bool(kind.name), bool(kind.desc))

    def test_a_kind_with_a_spawner_has_no_scenery(self):
        # The entity of a spawner is already on the screen. Scenery on the
        # same tile would draw the thing two times.
        for key, kind in object_kinds.OBJECT_KINDS.items():
            if not kind.scenery:
                continue

            with self.subTest(kind=key):
                self.assertEqual(kind.spawner, "")

    def test_every_scenery_key_names_a_model_record_or_a_primitive(self):
        served = set()

        for path in model_records.record_paths():
            served.update(model_records.load_record(path).keys)

        for key, kind in object_kinds.OBJECT_KINDS.items():
            if not kind.scenery:
                continue

            with self.subTest(kind=key, scenery=kind.scenery):
                is_model = kind.scenery in served
                is_primitive = kind.scenery in tile_const.SCENERY_PRIMITIVES
                self.assertNotEqual(is_model, is_primitive,
                                    "a scenery key names a model record or "
                                    "a primitive, never both")

    def test_no_primitive_is_also_a_model_record(self):
        # When art arrives, the key leaves SCENERY_PRIMITIVES. A key in both
        # places would draw the primitive and never the art.
        served = set()

        for path in model_records.record_paths():
            served.update(model_records.load_record(path).keys)

        for primitive in tile_const.SCENERY_PRIMITIVES:
            with self.subTest(primitive=primitive):
                self.assertNotIn(primitive, served)

    def test_every_climb_shows_scenery(self):
        # A player must see where to type `climb`.
        for key, kind in object_kinds.OBJECT_KINDS.items():
            if kind.category != tile_const.OBJECT_CATEGORY_CLIMB:
                continue

            with self.subTest(kind=key):
                self.assertTrue(kind.scenery)

    def test_every_transition_shows_the_teleporter(self):
        # A transition tile was a bare tile after Phase 4b. The pad tells a
        # player where the map ends.
        for key, kind in object_kinds.OBJECT_KINDS.items():
            if kind.category != tile_const.OBJECT_CATEGORY_TRANSITION:
                continue

            with self.subTest(kind=key):
                self.assertEqual(kind.scenery,
                                 object_kinds.TRANSITION_SCENERY)

    def test_every_area_has_room_texts(self):
        for key, area in areas.AREAS.items():
            with self.subTest(area=key):
                self.assertTrue(area.name)
                self.assertTrue(area.desc)


class WorldChunkTests(unittest.TestCase):
    """Every world chunk file names only rows of the four tables."""

    def test_every_name_in_a_world_chunk_file_is_a_row(self):
        found = chunkfile.load_directory(_WORLD_CHUNK_DIRECTORY)

        for chunk in found:
            used = (
                ("floor type", chunk.floor_names, floor_types.FLOOR_TYPES),
                ("area", chunk.area_names, areas.AREAS),
                ("wall style", chunk.wall_names, wall_styles.WALL_STYLES),
                ("object kind", [thing.kind for thing in chunk.objects],
                 object_kinds.OBJECT_KINDS),
            )

            for label, names, table in used:
                for name in names:
                    with self.subTest(chunk=chunk.file_name(), table=label,
                                      name=name):
                        self.assertIn(name, table)

    def test_the_world_passes_every_content_check(self):
        """Each transition and each climb lands on an open tile. Each void
        tile has the Blocked flag. The world has one respawn point. The rules live in
        `world/tile_checks.py`. The editor runs the same rules. A note warns
        and does not fail: the world may hold a closed pocket on purpose."""
        found = tile_checks.check_world(
            chunkfile.load_directory(_WORLD_CHUNK_DIRECTORY))

        self.assertEqual([finding.message for finding in found
                          if not finding.is_note()], [])
