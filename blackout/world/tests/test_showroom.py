"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/03/2026
Description: Tests for the showroom (`world/showroom.py`): the generated
             world that holds one of each item and one of each object kind,
             and its server settings (`server/conf/showroom_settings.py`).

             Run from blackout/:
                 ../evenv/Scripts/evennia.exe test --settings test_settings.py world.tests.test_showroom

             NO CENSUS HERE. Each expectation comes from its owner:
             `spawn_items.item_rows()` for the items, OBJECT_KINDS for the
             kinds, and the live settings for the ports. A new item or kind
             thus breaks no test.

             No case touches a database or a file of the repository. The
             write cases use a temporary directory.
"""

import importlib
import os
import shutil
import tempfile
import unittest
from collections import Counter

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import spawn_items
from world import object_kinds
from world import showroom
from world import tile_checks

# The settings modules, by dotted path.
_LIVE_SETTINGS: str = "server.conf.settings"
_SHOWROOM_SETTINGS: str = "server.conf.showroom_settings"

# The settings that name a play port. Each must differ from the live value.
_PLAY_PORT_SETTINGS: tuple = ("WEBSOCKET_CLIENT_PORT", "AMP_PORT",
                              "GODOT_CLIENT_WEBSOCKET_PORT")

# The host names of this machine. Django refuses each other host.
_LOCAL_HOSTS: frozenset = frozenset({"localhost", "127.0.0.1"})

# More items than one chunk holds, for the growth case.
_MANY_ITEMS: int = tile_const.CHUNK_SIZE * tile_const.CHUNK_SIZE // 4


def _objects(room) -> list:
    """Return each ChunkObject of a showroom, over all of its chunk files."""
    found = []

    for chunk_file in room.chunk_files:
        found.extend(chunk_file.objects)

    return found


def _fake_rows(count: int, family: str) -> list:
    """Return `count` item rows of one family, as `item_rows` gives them."""
    rows = []

    for number in range(count):
        rows.append({"key": f"showroom_test_{number:05d}",
                     "name": f"Test item {number}",
                     "family": family, "stackable": False})

    return rows


class ShowroomOfTheGameTests(unittest.TestCase):
    """The showroom of the real items and kinds."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rows = spawn_items.item_rows()
        cls.room = showroom.build(cls.rows)
        cls.objects = _objects(cls.room)

    def test_each_item_has_one_spawn(self):
        spawned = Counter(thing.spawn.get(tile_const.SPAWN_ITEM_KEY)
                          for thing in self.objects if thing.spawn)

        for row in self.rows:
            with self.subTest(item=row["key"]):
                self.assertEqual(spawned[row["key"]], 1)

        self.assertEqual(set(spawned), {row["key"] for row in self.rows})

    def test_each_spawn_respawns_at_the_minimum(self):
        for thing in self.objects:
            if not thing.spawn:
                continue

            with self.subTest(item=thing.spawn[tile_const.SPAWN_ITEM_KEY]):
                self.assertEqual(chunkfile.spawn_problem(thing.spawn), "")
                self.assertEqual(thing.spawn[tile_const.SPAWN_RESPAWN_KEY],
                                 tile_const.SPAWN_RESPAWN_MIN)

    def test_each_kind_is_placed_or_skipped_with_a_reason(self):
        placed = Counter(thing.kind for thing in self.objects)
        skipped = dict(self.room.skipped_kinds)

        for key, kind in object_kinds.OBJECT_KINDS.items():
            with self.subTest(kind=key):
                if kind.category in showroom.SKIPPED_CATEGORIES:
                    self.assertEqual(placed[key], 0)
                    self.assertIn(key, skipped)
                elif key in showroom.LAYOUT_KINDS:
                    self.assertGreaterEqual(placed[key], 1)
                else:
                    self.assertEqual(placed[key], 1)
                    self.assertNotIn(key, skipped)

    def test_the_world_passes_the_content_checks(self):
        findings = tile_checks.check_world(self.room.chunk_files,
                                           spawn_items.stacking())

        self.assertEqual(findings, [])

    def test_each_chunk_file_reads_back_the_same(self):
        for chunk_file in self.room.chunk_files:
            with self.subTest(chunk=chunk_file.file_name()):
                text = chunkfile.to_text(chunk_file)
                again = chunkfile.parse_text(text)

                self.assertEqual(chunkfile.to_text(again), text)

    def test_each_sign_counts_its_aisle(self):
        signs = [thing.text for thing in self.objects
                 if thing.kind == object_kinds.SIGNPOST_KIND]

        self.assertEqual(signs, [aisle.label for aisle in self.room.aisles])

        for aisle in self.room.aisles:
            with self.subTest(aisle=aisle.label):
                self.assertIn(f"({len(aisle.entries)})", aisle.label)

    def test_each_object_faces_the_entrance(self):
        self.assertEqual(tile_const.ROTATION_STEPS[showroom.FACING], (0, -1))

        for thing in self.objects:
            self.assertEqual(thing.rotation, showroom.FACING)


class ShowroomGrowthTests(unittest.TestCase):
    """A showroom of content that the game does not hold today."""

    def test_a_long_aisle_continues_into_the_chunk_to_the_north(self):
        family = feed_const.ITEM_FAMILY_PRIORITY[0]
        rows = _fake_rows(_MANY_ITEMS, family)
        stacking = {row["key"]: False for row in rows}
        room = showroom.build(rows)

        self.assertGreater(len(room.chunk_files), 1)
        self.assertEqual([chunk.cy for chunk in room.chunk_files],
                         list(range(len(room.chunk_files))))
        self.assertEqual(tile_checks.check_world(room.chunk_files, stacking),
                         [])

    def test_a_family_with_no_priority_comes_after_the_known_ones(self):
        known = feed_const.ITEM_FAMILY_PRIORITY[0]
        new_family = "showroom_test_family"
        rows = _fake_rows(1, new_family) + _fake_rows(1, known)
        rows[1]["key"] = "showroom_test_known"

        aisles = showroom.item_aisles(rows)
        firsts = [aisle.entries[0][1][tile_const.SPAWN_ITEM_KEY]
                  for aisle in aisles]

        self.assertEqual(firsts, ["showroom_test_known",
                                  "showroom_test_00000"])

    def test_a_new_category_gets_its_own_aisle(self):
        base = next(iter(object_kinds.OBJECT_KINDS.values()))
        new_kind = object_kinds.ObjectKind("showroom_test_kind",
                                           "showroom_test_category")
        kinds = {base.key: base, new_kind.key: new_kind}

        aisles, skipped = showroom.kind_aisles(kinds)
        entries = [aisle.entries for aisle in aisles]

        self.assertIn((("showroom_test_kind", {}),), entries)
        self.assertEqual(skipped, [])


class ShowroomWriteTests(unittest.TestCase):
    """`showroom.write` in a temporary directory."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.directory = os.path.join(self.root, "showroom")
        self.room = showroom.build(_fake_rows(1, feed_const.ITEM_FAMILY_GENERIC))

    def test_it_refuses_the_live_chunk_directory(self):
        os.makedirs(self.directory)
        stale = os.path.join(self.directory,
                             chunkfile.chunk_file_name(5, 5, 0))

        with open(stale, "w", encoding="utf-8") as handle:
            handle.write("{}")

        with self.assertRaises(ValueError):
            showroom.write(self.room, self.directory, self.directory)

        self.assertTrue(os.path.exists(stale))

    def test_it_replaces_each_chunk_file_and_keeps_other_files(self):
        os.makedirs(self.directory)
        stale = os.path.join(self.directory,
                             chunkfile.chunk_file_name(5, 5, 0))
        readme = os.path.join(self.directory, "README.md")

        for path in (stale, readme):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{}")

        written = showroom.write(self.room, self.directory,
                                 os.path.join(self.root, "chunks"))

        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.exists(readme))
        names = sorted(os.listdir(self.directory))
        expected = sorted([os.path.basename(path) for path in written]
                          + ["README.md"])
        self.assertEqual(names, expected)


class ShowroomSettingsTests(unittest.TestCase):
    """The showroom server never shares a fact with the live server."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.live = importlib.import_module(_LIVE_SETTINGS)
        cls.showroom = importlib.import_module(_SHOWROOM_SETTINGS)

    def test_it_has_its_own_database(self):
        live = self.live.DATABASES["default"]["NAME"]
        own = self.showroom.DATABASES["default"]["NAME"]

        self.assertNotEqual(os.path.normcase(live), os.path.normcase(own))

    def test_it_has_its_own_chunk_directory(self):
        live = os.path.join(self.live.GAME_DIR, tile_const.CHUNK_DIRECTORY)
        own = self.showroom.TILE_WORLD_DIR

        self.assertTrue(own)
        self.assertNotEqual(os.path.normcase(os.path.abspath(live)),
                            os.path.normcase(os.path.abspath(own)))

    def test_each_play_port_differs_from_the_live_port(self):
        for name in _PLAY_PORT_SETTINGS:
            with self.subTest(setting=name):
                self.assertNotEqual(getattr(self.showroom, name),
                                    getattr(self.live, name))

        self.assertTrue(set(self.showroom.TELNET_PORTS).isdisjoint(
            self.live.TELNET_PORTS))

    def test_it_listens_on_the_local_host_only(self):
        self.assertTrue(self.showroom.LOCKDOWN_MODE)
        self.assertLessEqual(set(self.showroom.ALLOWED_HOSTS), _LOCAL_HOSTS)
