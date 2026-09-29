"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/26/2026
Description: Tests for `world/tile_checks.py`, the content rules of a tile
             world, and the Python half of their parity with the editor.

             Run from blackout/:
                 ../evenv/Scripts/evennia.exe test --settings test_settings.py world.tests.test_tile_checks

             `godot/tests/test_terrain_checks.gd` is the GDScript half. It
             reads the same fixtures and the same expected.json.
"""

import json
import os
import unittest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import syncstamp
from world import tile_checks
from world.tests import check_fixture_builder as builder


def _read_text(path: str) -> str:
    """Read a file with its line ends as LF. Git may check out CRLF."""
    with open(path, encoding="utf-8") as handle:
        return handle.read().replace("\r\n", "\n")


class FixtureTests(unittest.TestCase):
    """The committed fixtures are the output of the builder."""

    def test_each_fixture_file_is_the_builder_output(self):
        for chunk_file in builder.build_fixtures():
            path = os.path.join(builder.FIXTURE_DIRECTORY, chunk_file.file_name())

            with self.subTest(file=chunk_file.file_name()):
                self.assertEqual(_read_text(path), chunkfile.to_text(chunk_file))

    def test_expected_json_is_the_builder_list(self):
        path = os.path.join(builder.FIXTURE_DIRECTORY, builder.EXPECTED_FILE)

        self.assertEqual(_read_text(path), builder.expected_text())

    def test_the_gdscript_twin_reads_these_fixtures(self):
        # The GDScript half of the parity names the fixture directory as
        # text. A move of the fixtures must move that line too.
        game_dir = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        twin = os.path.join(os.path.dirname(game_dir), "godot", "addons",
                            "blackout_terrain", "terrain_checks.gd")
        relative = os.path.relpath(builder.FIXTURE_DIRECTORY, game_dir)

        self.assertIn('"%s"' % relative.replace(os.sep, "/"), _read_text(twin))

    def test_the_fixture_stamp_matches_the_fixture_files(self):
        # The GDScript TerrainSyncState must find no change against it.
        path = os.path.join(builder.FIXTURE_DIRECTORY, builder.STAMP_FILE)

        self.assertEqual(syncstamp.changed_files(
            builder.FIXTURE_DIRECTORY, syncstamp.read_stamp(path)), [])

    def test_every_rule_has_a_finding_in_the_fixture(self):
        # A rule with no case in the fixture has no parity with the editor.
        covered = {row[0] for row in builder.EXPECTED}

        for rule in tile_checks.RULES:
            with self.subTest(rule=rule):
                self.assertIn(rule, covered)


class CheckWorldTests(unittest.TestCase):

    def test_the_fixture_world_gives_the_expected_findings(self):
        path = os.path.join(builder.FIXTURE_DIRECTORY, builder.EXPECTED_FILE)
        expected = [tuple(row) for row in json.loads(_read_text(path))]
        found = tile_checks.check_world(
            chunkfile.load_directory(builder.FIXTURE_DIRECTORY))

        self.assertEqual([finding.key() for finding in found], expected)

    def test_each_finding_has_a_message(self):
        found = tile_checks.check_world(builder.build_fixtures())

        for finding in found:
            with self.subTest(finding=finding.key()):
                self.assertTrue(finding.message)

    def test_an_empty_world_has_no_respawn_point(self):
        found = tile_checks.check_world([])

        self.assertEqual([finding.key() for finding in found],
                         [(tile_checks.RULE_RESPAWN_COUNT, 0, 0, 0)])

    def test_a_fixed_world_gives_no_finding(self):
        ground, upper = builder.build_fixtures()
        ground.objects = [thing for thing in ground.objects
                          if (thing.x, thing.y) in ((1, 1), (10, 10))]
        upper.objects = []
        upper.flags[30 * tile_const.CHUNK_SIZE + 30] = tile_const.FLAG_BLOCKED

        self.assertEqual(tile_checks.check_world([ground, upper]), [])
