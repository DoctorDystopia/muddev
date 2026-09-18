"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/17/2026
Description: Tests for world.maps.scope, the reader behind the --map and
             --tile flags of scripts/map_sync.py.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py world

Every case builds its own MapEntry list, so nothing here depends on which maps
the repo currently ships. The module touches no database, so plain
unittest.TestCase is the right base class.
"""

import unittest

from world.maps.manifest import MapEntry
from world.maps.scope import ScopeError, build_scope, parse_tile_ref


# Private constant definitions

_ENTRIES = [
    MapEntry(module="world.maps.alpha", zcoord="alpha"),
    MapEntry(module="world.maps.beta", zcoord="beta"),
    MapEntry(module="world.maps.gamma", zcoord="gamma"),
]


class TileRefParseTest(unittest.TestCase):
    """One --tile argument, from text to a coordinate."""

    def test_parses_map_and_coordinates(self):
        """A well-formed argument gives the map and both coordinates."""
        tile = parse_tile_ref("beta:12,4", _ENTRIES)

        self.assertEqual(tile.zcoord, "beta")
        self.assertEqual(tile.xy, (12, 4))

    def test_tolerates_surrounding_whitespace(self):
        """Spaces around any field are stripped rather than rejected."""
        tile = parse_tile_ref("  beta : 12 , 4  ", _ENTRIES)

        self.assertEqual(tile.zcoord, "beta")
        self.assertEqual(tile.xy, (12, 4))

    def test_rejects_a_missing_map_name(self):
        """A bare coordinate names no map, so it cannot be resolved."""
        with self.assertRaises(ScopeError):
            parse_tile_ref("12,4", _ENTRIES)

    def test_rejects_a_wrong_number_of_coordinates(self):
        """Two coordinates are required, never one and never three."""
        for text in ("beta:12", "beta:12,4,7"):
            with self.subTest(text=text):
                with self.assertRaises(ScopeError):
                    parse_tile_ref(text, _ENTRIES)

    def test_rejects_a_non_numeric_coordinate(self):
        """A coordinate that is not a whole number is an operator typo."""
        with self.assertRaises(ScopeError):
            parse_tile_ref("beta:x,4", _ENTRIES)

    def test_rejects_a_map_outside_the_manifest(self):
        """A tile on an unlisted map must not reach the purge."""
        with self.assertRaises(ScopeError) as caught:
            parse_tile_ref("delta:1,1", _ENTRIES)

        for entry in _ENTRIES:
            self.assertIn(entry.zcoord, str(caught.exception))


class BuildScopeTest(unittest.TestCase):
    """Resolving both flags together into what one run may touch."""

    def test_no_flags_covers_every_manifest_map(self):
        """An unscoped run rebuilds the manifest, in manifest order."""
        scope = build_scope([], [], _ENTRIES)

        self.assertTrue(scope.is_full)
        self.assertEqual(list(scope.whole_maps), [entry.zcoord for entry in _ENTRIES])
        self.assertEqual(scope.tiles, ())

    def test_named_maps_come_back_in_manifest_order(self):
        """The manifest decides the order, not the order of the flags."""
        scope = build_scope(["gamma", "alpha"], [], _ENTRIES)

        self.assertFalse(scope.is_full)
        self.assertEqual(list(scope.whole_maps), ["alpha", "gamma"])

    def test_a_named_map_is_a_whole_map(self):
        """--map rebuilds end to end, so no tile list narrows it."""
        scope = build_scope(["beta"], [], _ENTRIES)

        self.assertTrue(scope.is_whole_map("beta"))
        self.assertEqual(scope.tiles_of("beta"), ())

    def test_tiles_bring_in_their_own_map(self):
        """A map reached only by --tile is in scope, but not as a whole map."""
        scope = build_scope([], ["beta:1,2"], _ENTRIES)

        self.assertIn("beta", scope.zcoords)
        self.assertFalse(scope.is_whole_map("beta"))
        self.assertEqual([tile.xy for tile in scope.tiles_of("beta")], [(1, 2)])

    def test_a_map_flag_absorbs_a_tile_flag_on_the_same_map(self):
        """The whole map is the superset, so the tile row is redundant."""
        scope = build_scope(["beta"], ["beta:1,2"], _ENTRIES)

        self.assertTrue(scope.is_whole_map("beta"))
        self.assertEqual(scope.tiles, ())

    def test_a_map_flag_leaves_a_tile_on_another_map_alone(self):
        """One run may rebuild a whole map and a single tile elsewhere."""
        scope = build_scope(["alpha"], ["beta:1,2"], _ENTRIES)

        self.assertTrue(scope.is_whole_map("alpha"))
        self.assertFalse(scope.is_whole_map("beta"))
        self.assertEqual(set(scope.zcoords), {"alpha", "beta"})

    def test_zcoords_lists_each_map_once(self):
        """Several tiles on one map still name that map one time."""
        scope = build_scope([], ["beta:1,2", "beta:3,4"], _ENTRIES)

        self.assertEqual(list(scope.zcoords), ["beta"])
        self.assertEqual(len(scope.tiles_of("beta")), 2)

    def test_a_scoped_run_is_never_full(self):
        """is_full guards the prune, so any flag at all must clear it."""
        for maps, tiles in (["alpha"], []), ([], ["alpha:1,1"]):
            with self.subTest(maps=maps, tiles=tiles):
                scope = build_scope(maps, tiles, _ENTRIES)

                self.assertFalse(scope.is_full)

    def test_rejects_a_map_outside_the_manifest(self):
        """A misspelled map costs an error, never a rebuild of the wrong one."""
        with self.assertRaises(ScopeError):
            build_scope(["delta"], [], _ENTRIES)


class DescribeTest(unittest.TestCase):
    """The one line an operator checks a run against before it deletes anything."""

    def test_an_unscoped_run_says_so(self):
        """A full run names no map, because it covers all of them."""
        description = build_scope([], [], _ENTRIES).describe()

        self.assertIn("manifest", description)

    def test_a_mixed_run_names_both_halves(self):
        """Every map in scope appears, and every tile coordinate with it."""
        scope = build_scope(["alpha"], ["beta:1,2"], _ENTRIES)
        description = scope.describe()

        self.assertIn("alpha", description)
        self.assertIn("beta", description)
        self.assertIn("1,2", description)
