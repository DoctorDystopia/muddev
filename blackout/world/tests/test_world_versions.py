"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/28/2026
Description: Tests for the world versions (`world/world_versions.py`): the
             shelf of saved worlds that the Versions tab of the terrain
             editor and `scripts/world_versions.py` switch between.

             Run from blackout/:
                 ../evenv/Scripts/evennia.exe test --settings test_settings.py world.tests.test_world_versions

             The cases build a small game directory in a temporary
             directory. No file of the repository changes. The last class
             reads the shelf of the repository: each version must read, and
             each name of it must be a row of its table, because a switch
             puts those names into the world.

             NO CENSUS HERE. The shelf may hold any number of versions, none
             included.
"""

import json
import os
import shutil
import tempfile
import unittest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import syncstamp
from world import areas
from world import floor_types
from world import object_kinds
from world import wall_styles
from world import world_versions as versions

# Each name list of a chunk file and its table.
_NAME_LISTS: tuple = (
    ("floor_names", floor_types.FLOOR_TYPES),
    ("area_names", areas.AREAS),
    ("wall_names", wall_styles.WALL_STYLES),
)


def _blank(cx: int, cy: int) -> chunkfile.ChunkFile:
    tiles = tile_const.CHUNK_SIZE * tile_const.CHUNK_SIZE

    return chunkfile.ChunkFile(
        cx=cx, cy=cy, plane=0, floor_names=[floor_types.DEFAULT_FLOOR_TYPE],
        area_names=[areas.DEFAULT_AREA],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tiles, flags=[0] * tiles, areas=[0] * tiles)


class _ShelfCase(unittest.TestCase):
    """A game directory with a world of two chunks, in a temporary place."""

    def setUp(self):
        self.game_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.game_dir)
        self.chunks = versions.chunks_path(self.game_dir)
        os.makedirs(self.chunks)
        self._write(_blank(0, 0))
        self._write(_blank(1, 0))

    def _write(self, chunk: chunkfile.ChunkFile) -> str:
        path = os.path.join(self.chunks, chunk.file_name())
        chunkfile.write_file(path, chunk)

        return path

    def _raise_a_corner(self, name: str) -> None:
        chunk = chunkfile.read_file(os.path.join(self.chunks, name))
        chunk.heights[0] += 1
        self._write(chunk)

    def _keys(self) -> list:
        return [version.key for version in versions.list_versions(self.game_dir)]


class KeyRuleTests(unittest.TestCase):
    """A key is a legal chunk file name, and a note is one short line."""

    def test_a_legal_key_has_no_problem(self):
        self.assertEqual(versions.key_problem("market_v2"), "")

    def test_an_illegal_key_names_its_problem(self):
        for key in ("", "Market", "a-b", "a b", "../x"):
            with self.subTest(key=key):
                self.assertTrue(versions.key_problem(key))

    def test_a_note_is_one_line_with_a_cap(self):
        self.assertEqual(versions.note_problem(""), "")
        self.assertEqual(versions.note_problem("two gates"), "")
        self.assertTrue(versions.note_problem("a\nb"))
        self.assertTrue(versions.note_problem(
            "x" * (tile_const.VERSION_NOTE_MAX_CHARS + 1)))


class SaveTests(_ShelfCase):
    """A save copies every chunk file and writes the meta file."""

    def test_a_save_copies_the_world_and_lists_it(self):
        saved = versions.save_version("first", "two chunks", game_dir=self.game_dir)

        self.assertEqual(saved.chunk_count, 2)
        self.assertEqual(sorted(os.listdir(saved.path)),
                         ["chunk_0_0_p0.json", "chunk_1_0_p0.json",
                          tile_const.VERSION_META_FILE])
        self.assertEqual(self._keys(), ["first"])

        listed = versions.list_versions(self.game_dir)[0]

        self.assertEqual(listed.note, "two chunks")
        self.assertTrue(listed.saved)
        self.assertEqual(syncstamp.directory_digests(saved.path),
                         syncstamp.directory_digests(self.chunks))

    def test_a_saved_version_is_the_current_one(self):
        versions.save_version("first", game_dir=self.game_dir)

        self.assertEqual(versions.current_key(self.game_dir), "first")
        self.assertEqual(versions.differences("first", self.game_dir), [])

    def test_a_save_refuses_a_key_that_exists_unless_told(self):
        versions.save_version("first", game_dir=self.game_dir)

        with self.assertRaises(versions.VersionError):
            versions.save_version("first", game_dir=self.game_dir)

        self._write(_blank(2, 0))
        saved = versions.save_version("first", overwrite=True,
                                      game_dir=self.game_dir)

        self.assertEqual(saved.chunk_count, 3)

    def test_an_overwrite_drops_the_files_the_world_lost(self):
        versions.save_version("first", game_dir=self.game_dir)
        os.remove(os.path.join(self.chunks, "chunk_1_0_p0.json"))
        versions.save_version("first", overwrite=True, game_dir=self.game_dir)

        self.assertEqual(versions.current_key(self.game_dir), "first")
        self.assertNotIn("chunk_1_0_p0.json",
                         os.listdir(versions.version_path("first", self.game_dir)))

    def test_a_save_refuses_a_bad_key_and_an_empty_world(self):
        with self.assertRaises(versions.VersionError):
            versions.save_version("Bad Key", game_dir=self.game_dir)

        for name in os.listdir(self.chunks):
            os.remove(os.path.join(self.chunks, name))

        with self.assertRaises(versions.VersionError):
            versions.save_version("first", game_dir=self.game_dir)

    def test_an_empty_shelf_lists_nothing(self):
        self.assertEqual(versions.list_versions(self.game_dir), [])
        self.assertEqual(versions.current_key(self.game_dir), "")


class SwitchTests(_ShelfCase):
    """A switch replaces the chunk files, and it never drops unsaved work."""

    def setUp(self):
        super().setUp()
        versions.save_version("flat", game_dir=self.game_dir)
        self._raise_a_corner("chunk_0_0_p0.json")
        self._write(_blank(2, 0))
        versions.save_version("hill", "a corner up, a third chunk",
                              game_dir=self.game_dir)

    def test_a_switch_restores_each_file_and_removes_the_extra(self):
        changed = versions.switch_to("flat", game_dir=self.game_dir)

        self.assertEqual(changed, [("chunk_0_0_p0.json", syncstamp.STATE_CHANGED),
                                   ("chunk_2_0_p0.json", syncstamp.STATE_NEW)])
        self.assertEqual(sorted(os.listdir(self.chunks)),
                         ["chunk_0_0_p0.json", "chunk_1_0_p0.json"])
        self.assertEqual(versions.current_key(self.game_dir), "flat")

    def test_a_switch_to_the_current_version_changes_nothing(self):
        self.assertEqual(versions.switch_to("hill", game_dir=self.game_dir), [])

    def test_a_switch_refuses_to_drop_a_world_that_no_version_holds(self):
        self._raise_a_corner("chunk_1_0_p0.json")

        self.assertEqual(versions.current_key(self.game_dir), "")

        with self.assertRaises(versions.VersionError):
            versions.switch_to("flat", game_dir=self.game_dir)

        self.assertEqual(versions.current_key(self.game_dir), "")

    def test_a_drop_switches_anyway(self):
        self._raise_a_corner("chunk_1_0_p0.json")
        versions.switch_to("flat", drop=True, game_dir=self.game_dir)

        self.assertEqual(versions.current_key(self.game_dir), "flat")

    def test_a_switch_refuses_a_version_that_is_not_there(self):
        with self.assertRaises(versions.VersionError):
            versions.switch_to("nowhere", game_dir=self.game_dir)

    def test_a_cycle_comes_back_to_the_same_bytes(self):
        before = syncstamp.directory_digests(self.chunks)

        versions.switch_to("flat", game_dir=self.game_dir)
        versions.switch_to("hill", game_dir=self.game_dir)

        self.assertEqual(syncstamp.directory_digests(self.chunks), before)


class RenameAndRemoveTests(_ShelfCase):
    """A rename moves the directory. A removal deletes it whole."""

    def test_a_rename_keeps_the_files_and_the_note(self):
        versions.save_version("first", "the note", game_dir=self.game_dir)
        versions.rename_version("first", "second", game_dir=self.game_dir)

        self.assertEqual(self._keys(), ["second"])
        self.assertEqual(versions.list_versions(self.game_dir)[0].note, "the note")
        self.assertEqual(versions.current_key(self.game_dir), "second")

    def test_a_rename_refuses_a_bad_or_taken_key(self):
        versions.save_version("first", game_dir=self.game_dir)
        versions.save_version("second", game_dir=self.game_dir)

        for new in ("First", "second"):
            with self.subTest(new=new):
                with self.assertRaises(versions.VersionError):
                    versions.rename_version("first", new, game_dir=self.game_dir)

        with self.assertRaises(versions.VersionError):
            versions.rename_version("third", "fourth", game_dir=self.game_dir)

    def test_a_removal_deletes_the_version_and_leaves_the_world(self):
        versions.save_version("first", game_dir=self.game_dir)
        versions.remove_version("first", game_dir=self.game_dir)

        self.assertEqual(self._keys(), [])
        self.assertEqual(len(os.listdir(self.chunks)), 2)

        with self.assertRaises(versions.VersionError):
            versions.remove_version("first", game_dir=self.game_dir)


class MetaFileTests(_ShelfCase):
    """A hand-made version needs no meta file. A bad meta file is refused."""

    def _make_by_hand(self, key: str) -> str:
        path = versions.version_path(key, self.game_dir)
        shutil.copytree(self.chunks, path)

        return path

    def test_a_copied_directory_is_a_version_with_no_note(self):
        self._make_by_hand("copied")
        listed = versions.list_versions(self.game_dir)[0]

        self.assertEqual((listed.key, listed.note, listed.saved, listed.chunk_count),
                         ("copied", "", "", 2))
        self.assertEqual(versions.current_key(self.game_dir), "copied")

    def test_a_file_on_the_shelf_is_not_a_version(self):
        os.makedirs(versions.shelf_path(self.game_dir))

        with open(os.path.join(versions.shelf_path(self.game_dir), "README.md"),
                  "w", encoding="utf-8") as handle:
            handle.write("# The shelf\n")

        self.assertEqual(versions.list_versions(self.game_dir), [])

    def test_a_bad_meta_file_is_refused(self):
        path = self._make_by_hand("copied")
        meta = os.path.join(path, tile_const.VERSION_META_FILE)
        bad = (
            "{",
            json.dumps({versions.FORMAT_KEY: 99}),
            json.dumps({versions.FORMAT_KEY: tile_const.VERSION_FORMAT_VERSION,
                        "extra": 1}),
            json.dumps({versions.FORMAT_KEY: tile_const.VERSION_FORMAT_VERSION,
                        versions.NOTE_KEY: 5}),
            json.dumps({versions.FORMAT_KEY: tile_const.VERSION_FORMAT_VERSION,
                        versions.NOTE_KEY: "a\nb"}),
        )

        for text in bad:
            with self.subTest(text=text):
                with open(meta, "w", encoding="utf-8") as handle:
                    handle.write(text)

                with self.assertRaises(versions.VersionError):
                    versions.list_versions(self.game_dir)

    def test_a_directory_with_a_bad_key_is_refused(self):
        self._make_by_hand("Bad")

        with self.assertRaises(versions.VersionError):
            versions.list_versions(self.game_dir)


class RepositoryShelfTests(unittest.TestCase):
    """Each version of the repository reads, and names only rows."""

    def test_every_version_reads_and_names_rows(self):
        for version in versions.list_versions():
            with self.subTest(version=version.key):
                chunks = chunkfile.load_directory(version.path)

                self.assertEqual(len(chunks), version.chunk_count)
                self.assertEqual(chunkfile.seam_mismatches(chunks), [])

                for chunk in chunks:
                    for key, table in _NAME_LISTS:
                        for name in getattr(chunk, key):
                            self.assertIn(name, table, "%s names %s" % (
                                chunk.file_name(), name))

                    for thing in chunk.objects:
                        self.assertIn(thing.kind, object_kinds.OBJECT_KINDS)
