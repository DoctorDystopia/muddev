"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/21/2026
Description: Tests for the item list of the terrain editor
             (`spawn_items.py`): the file in git is a new render, each row
             agrees with ITEM_DB, and the editor draws each row with the
             key and the family that the feed sends for the item.

             No test names an item key. Each expectation comes from ITEM_DB
             and the dev tool tag. The identity test makes one item of each
             row, so it needs the database. The other tests touch none.
"""

import json
import os
import unittest

from evennia.utils.test_resources import EvenniaTestCase

from systems.devtools.constants import DEV_TOOL_TAG_CATEGORY
from world.item_database import ITEM_DB

from .. import figure_catalog, serializers, spawn_items


# ─── Private constant definitions ────────────────────────────────────────────

_RUN_EXPORT = "Run:\n    python scripts/export_client_constants.py"

# The keys of one row of the list.
_ROW_KEYS = {"key", "name", "family", "stackable"}


# ─── Private helper routines ─────────────────────────────────────────────────

def _is_dev_tool(item_def) -> bool:
    """Return True if the item carries the dev tool tag."""
    return DEV_TOOL_TAG_CATEGORY in {category for _key, category in item_def.tags}


# ─── Tests ───────────────────────────────────────────────────────────────────

class ItemListTests(unittest.TestCase):
    """
    The item list of the terrain editor agrees with ITEM_DB.

    The list is a generated file in git. The editor reads it to fill the
    Item field of an item spawn, because GDScript cannot import ITEM_DB.
    """

    @classmethod
    def setUpClass(cls):
        cls.rows = spawn_items.item_rows()
        cls.by_key = {row["key"]: row for row in cls.rows}

    def test_the_file_in_git_matches_a_new_render(self):
        """A stale list shows the author the items of the past."""
        path = spawn_items.output_path()

        self.assertTrue(os.path.isfile(path),
                        "%s is not there. %s" % (path, _RUN_EXPORT))

        with open(path, "r", encoding="utf-8", newline="") as handle:
            committed = handle.read().replace("\r\n", "\n")

        self.assertEqual(committed, spawn_items.render(),
                         "%s is stale. %s" % (os.path.basename(path),
                                              _RUN_EXPORT))

    def test_the_list_has_items(self):
        """The vacuity guard of the loops below."""
        self.assertTrue(self.rows)

    def test_every_row_names_an_item_of_item_db_with_its_facts(self):
        for row in self.rows:
            with self.subTest(key=row["key"]):
                self.assertEqual(set(row), _ROW_KEYS)
                self.assertIn(row["key"], ITEM_DB)
                item_def = ITEM_DB[row["key"]]
                self.assertEqual(row["name"], item_def.name)
                self.assertEqual(row["stackable"], bool(item_def.stackable))
                self.assertEqual(row["family"],
                                 figure_catalog.family_of(item_def))

    def test_every_item_but_a_dev_tool_is_in_the_list(self):
        # A dev tool exists, or the rule tests nothing.
        self.assertTrue(any(_is_dev_tool(item_def)
                            for item_def in ITEM_DB.values()))

        for key, item_def in ITEM_DB.items():
            with self.subTest(key=key):
                self.assertEqual(key in self.by_key, not _is_dev_tool(item_def))

    def test_the_keys_are_sorted_and_unique(self):
        keys = [row["key"] for row in self.rows]

        self.assertEqual(keys, sorted(set(keys)))

    def test_stacking_follows_the_rows(self):
        self.assertEqual(spawn_items.stacking(),
                         {row["key"]: row["stackable"] for row in self.rows})

    def test_the_text_reads_back_as_the_rows(self):
        text = spawn_items.text_of(self.rows)
        parsed = json.loads(text)

        self.assertTrue(text.endswith("\n"))
        self.assertIsInstance(parsed["format"], int)
        self.assertEqual(parsed["items"], self.rows)


class FeedIdentityTests(EvenniaTestCase):
    """
    The editor draws the item of a spawn by the key and the family of its
    row, as the client draws an item on the ground. Thus, the feed must
    name the same two for the entity that the item makes. A corpse is the
    case that could drift: its typeclass declares its own asset kind and
    its own asset key, and `_classify` reads those first.
    """

    def test_the_feed_names_each_row_by_its_key_and_family(self):
        for row in spawn_items.item_rows():
            with self.subTest(key=row["key"]):
                item = ITEM_DB[row["key"]].create(location=None)
                kind, asset_key = serializers._classify(item)
                family = serializers._mesh_family(item, kind)
                item.delete()

                self.assertEqual(asset_key, row["key"])
                self.assertEqual(family, row["family"])
