"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Tests for world.maps.manifest, the reader behind
             scripts/map_manifest.json.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py world

Every case writes its own manifest to a temp file and reads it back, so
nothing here depends on which maps the repo currently ships. The repo's real
manifest is checked too, but only for parseability -- asserting its contents
would make adding a map a two-file edit, which is the opposite of the point.
"""

import json
import os
import tempfile
import unittest

from world.maps import manifest as map_manifest


# Private constant definitions

_GOOD_MANIFEST = {
    "maps": [
        {"module": "world.maps.alpha", "zcoord": "alpha"},
        {"module": "world.maps.beta", "zcoord": "beta"},
    ]
}


class ManifestReadTest(unittest.TestCase):
    """Parsing, projection and validation of a manifest file."""

    def setUp(self):
        """Give each test a private directory to write manifests into."""
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)

    def _write(self, payload):
        """Write payload (a dict, or raw text) to a manifest file, returning its path."""
        path = os.path.join(self._tempdir.name, "map_manifest.json")

        if isinstance(payload, str):
            text = payload
        else:
            text = json.dumps(payload)

        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

        return path

    def test_loads_entries_in_order(self):
        """Entries come back as MapEntry objects, in manifest order."""
        path = self._write(_GOOD_MANIFEST)

        entries = map_manifest.load_entries(path)

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].module, "world.maps.alpha")
        self.assertEqual(entries[0].zcoord, "alpha")
        self.assertEqual(entries[1].zcoord, "beta")

    def test_projections_match_entry_order(self):
        """zcoords_of and modules_of preserve the manifest's ordering."""
        path = self._write(_GOOD_MANIFEST)
        entries = map_manifest.load_entries(path)

        zcoords = map_manifest.zcoords_of(entries)
        modules = map_manifest.modules_of(entries)

        self.assertEqual(zcoords, ["alpha", "beta"])
        self.assertEqual(modules, ["world.maps.alpha", "world.maps.beta"])

    def test_strips_stray_whitespace(self):
        """Surrounding whitespace is stripped from both fields.

        A trailing carriage return in a module path used to reach
        `xyzgrid add` intact and drop the map from a rebuild, with the '\\r' in
        the error message scrolling the complaint off its own line.
        """
        path = self._write(
            {"maps": [{"module": " world.maps.alpha\r", "zcoord": "alpha \n"}]}
        )

        entries = map_manifest.load_entries(path)

        self.assertEqual(entries[0].module, "world.maps.alpha")
        self.assertEqual(entries[0].zcoord, "alpha")

    def test_missing_file_raises_manifest_error(self):
        """A path that does not exist is a ManifestError, not an OSError."""
        path = os.path.join(self._tempdir.name, "absent.json")

        with self.assertRaises(map_manifest.ManifestError):
            map_manifest.load_entries(path)

    def test_invalid_json_raises_manifest_error(self):
        """Malformed JSON is a ManifestError, not a ValueError."""
        path = self._write("{ not json")

        with self.assertRaises(map_manifest.ManifestError):
            map_manifest.load_entries(path)

    def test_empty_map_list_raises(self):
        """An empty 'maps' list would wipe the grid, so it is rejected."""
        path = self._write({"maps": []})

        with self.assertRaises(map_manifest.ManifestError):
            map_manifest.load_entries(path)

    def test_missing_zcoord_raises(self):
        """A row without a z-coordinate is rejected."""
        path = self._write({"maps": [{"module": "world.maps.alpha"}]})

        with self.assertRaises(map_manifest.ManifestError):
            map_manifest.load_entries(path)

    def test_blank_module_raises(self):
        """A row with an empty module path is rejected."""
        path = self._write({"maps": [{"module": "   ", "zcoord": "alpha"}]})

        with self.assertRaises(map_manifest.ManifestError):
            map_manifest.load_entries(path)

    def test_duplicate_zcoord_raises(self):
        """Two rows claiming one z-coordinate is fatal."""
        path = self._write(
            {
                "maps": [
                    {"module": "world.maps.alpha", "zcoord": "alpha"},
                    {"module": "world.maps.other", "zcoord": "alpha"},
                ]
            }
        )

        with self.assertRaises(map_manifest.ManifestError):
            map_manifest.load_entries(path)


class ShippedManifestTest(unittest.TestCase):
    """The manifest actually checked into scripts/."""

    def test_repo_manifest_parses(self):
        """The shipped manifest is readable and every row is well formed."""
        entries = map_manifest.load_entries()

        self.assertTrue(entries)

    def test_repo_manifest_modules_are_map_modules(self):
        """Every listed module lives under world.maps."""
        entries = map_manifest.load_entries()
        modules = map_manifest.modules_of(entries)

        for module in modules:
            self.assertTrue(module.startswith("world.maps."), module)
