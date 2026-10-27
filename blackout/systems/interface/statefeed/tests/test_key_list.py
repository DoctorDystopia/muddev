"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/25/2026
Description: Tests for the key list of the model wizard (`key_list.py`):
             the file in git is a new render, the wizard reads it, and each
             owner of an asset key puts its key in the list.

             No test names an asset key. Each expectation comes from
             ITEM_DB, NPC_DB, OBJECT_KINDS and the statefeed constants. No
             test touches the database.
"""

import os
import unittest

from assets.pipeline import records, wizard
from systems.core.tilegrid import constants as tile_const
from world.item_database import ITEM_DB
from world.npc_database import NPC_DB
from world.object_kinds import OBJECT_KINDS

from .. import constants as const
from .. import key_list


# ─── Private constant definitions ────────────────────────────────────────────

_RUN_EXPORT = "Run:\n    python scripts/export_client_constants.py"

# The keys of one row of the list.
_ROW_KEYS = {"key", "owner", "kind", "name"}


# ─── Tests ───────────────────────────────────────────────────────────────────

class KeyListTests(unittest.TestCase):
    """
    The key list names each asset key that the server sends for an entity
    or stands as scenery.

    The list is a generated file in git. The model wizard reads it, because
    the pipeline runs with no Django and cannot import ITEM_DB.
    """

    @classmethod
    def setUpClass(cls):
        cls.rows = key_list.key_rows()
        cls.pairs = {(row["key"], row["owner"]) for row in cls.rows}
        cls.keys = {row["key"] for row in cls.rows}

    def test_the_file_in_git_matches_a_new_render(self):
        """A stale list offers the keys of the past."""
        path = key_list.output_path()

        self.assertTrue(os.path.isfile(path),
                        "%s is not there. %s" % (path, _RUN_EXPORT))

        with open(path, "r", encoding="utf-8", newline="") as handle:
            committed = handle.read().replace("\r\n", "\n")

        self.assertEqual(committed, key_list.render(),
                         "%s is stale. %s" % (os.path.basename(path),
                                              _RUN_EXPORT))

    def test_the_wizard_reads_the_file_back_as_the_rows(self):
        self.assertEqual(wizard.read_key_list(key_list.output_path()),
                         self.rows)

    def test_the_list_has_rows(self):
        """The vacuity guard of the loops below."""
        self.assertTrue(self.rows)

    def test_every_row_has_the_four_fields_and_a_key_a_record_can_have(self):
        for row in self.rows:
            with self.subTest(key=row["key"], owner=row["owner"]):
                self.assertEqual(set(row), _ROW_KEYS)
                self.assertTrue(records.is_key(row["key"]))

    def test_every_item_is_named_by_its_own_key(self):
        for key in ITEM_DB:
            with self.subTest(item=key):
                self.assertIn((key, key), self.pairs)

    def test_every_npc_def_names_its_model(self):
        for key, npc_def in NPC_DB.items():
            with self.subTest(npc=key):
                self.assertIn((npc_def.resolved_asset_key(), key), self.pairs)

    def test_every_preview_and_every_model_scenery_is_named(self):
        for key, kind in OBJECT_KINDS.items():
            named = [kind.preview[0]] if kind.preview else []
            named += [kind.scenery] if kind.scenery else []

            for asset_key in named:
                listed = (asset_key != const.ASSET_KEY_GENERIC
                          and asset_key not in tile_const.SCENERY_PRIMITIVES)

                with self.subTest(kind=key, asset_key=asset_key):
                    self.assertEqual((asset_key, key) in self.pairs, listed)

    def test_no_fallback_key_and_no_primitive_is_listed(self):
        never = {const.ASSET_KEY_GENERIC} | set(tile_const.SCENERY_PRIMITIVES)

        self.assertEqual(self.keys & never, set())

    def test_the_rows_are_sorted_and_unique(self):
        pairs = [(row["key"], row["owner"]) for row in self.rows]

        self.assertEqual(pairs, sorted(set(pairs)))
