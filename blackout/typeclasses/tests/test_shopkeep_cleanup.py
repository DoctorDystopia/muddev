"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Tests for the shopkeep cleanup script and its typeclass-path
             migration.

ShopkeepCleanup lived in blackout/scripts/ until 08/28/2026 -- the directory
CLAUDE.md calls import-unsafe because everything in it acts on the live
database. Its path was persisted in 34 ScriptDB rows, so every server start
imported out of that directory to resolve them.

Moving the class beside its only user leaves those rows pointing at a module
that no longer exists. `ensure_cleanup_script` is the migration: it rides the
map rebuild the operator is already running, in the same shape spawn_shopkeep
uses to re-stamp `desc` and `shopdef_key` on an NPC that already exists.
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from typeclasses import npcs
from typeclasses.items import BaseItem
from typeclasses.npcs import ShopkeepNPC


class TestShopkeepCleanupAttachment(EvenniaTest):
    """Exactly one cleanup script, under the current path, always."""

    def _cleanup_scripts(self, shopkeep):
        """The cleanup scripts attached to this NPC, by current path."""
        attached = list(shopkeep.scripts.all())

        return [
            script
            for script in attached
            if script.typeclass_path == npcs.SHOPKEEP_CLEANUP_SCRIPT
        ]

    def test_a_new_shopkeep_carries_the_current_path(self):
        """The path the class actually lives at, not the one it used to."""
        shopkeep = create_object(ShopkeepNPC, key="test keep", location=self.room1)

        found = self._cleanup_scripts(shopkeep)

        self.assertEqual(len(found), 1)

    def test_the_legacy_path_is_no_longer_referenced(self):
        """The move is only done when nothing points into scripts/ any more."""
        self.assertNotIn(
            npcs.SHOPKEEP_CLEANUP_SCRIPT,
            npcs.LEGACY_SHOPKEEP_CLEANUP_SCRIPTS,
        )
        for path in npcs.LEGACY_SHOPKEEP_CLEANUP_SCRIPTS:
            with self.subTest(path=path):
                self.assertTrue(path.startswith("scripts."))

    def test_ensure_is_idempotent(self):
        """A rebuild runs this on every spawn; it must not stack timers.

        ScriptHandler.add has no presence check of its own -- it creates
        unconditionally -- so without the guard a shopkeep would collect one
        more daily timer per rebuild.
        """
        shopkeep = create_object(ShopkeepNPC, key="test keep", location=self.room1)

        shopkeep.ensure_cleanup_script()
        shopkeep.ensure_cleanup_script()

        found = self._cleanup_scripts(shopkeep)

        self.assertEqual(len(found), 1)

    def test_a_duplicate_is_pruned_back_to_one(self):
        """Whatever stacked timers already exist are collapsed, not tolerated."""
        shopkeep = create_object(ShopkeepNPC, key="test keep", location=self.room1)
        shopkeep.scripts.add(npcs.SHOPKEEP_CLEANUP_SCRIPT)
        stacked = self._cleanup_scripts(shopkeep)
        self.assertEqual(len(stacked), 2, "fixture failed to stack a second script")

        shopkeep.ensure_cleanup_script()

        found = self._cleanup_scripts(shopkeep)

        self.assertEqual(len(found), 1)


class TestShopkeepCleanupTrim(EvenniaTest):
    """The trim itself, and the cap it reads."""

    def _stock(self, shopkeep, count):
        """Put `count` throwaway items in the shopkeep's pockets."""
        for i in range(count):
            create_object(BaseItem, key=f"test junk {i}", location=shopkeep)

    def test_holdings_under_the_cap_are_left_alone(self):
        shopkeep = create_object(ShopkeepNPC, key="test keep", location=self.room1)
        self._stock(shopkeep, npcs.SHOPKEEP_MAX_HELD_ITEMS - 1)

        script = self._cleanup(shopkeep)
        script.at_repeat()

        self.assertEqual(len(shopkeep.contents), npcs.SHOPKEEP_MAX_HELD_ITEMS - 1)

    def test_holdings_over_the_cap_are_trimmed_to_it(self):
        shopkeep = create_object(ShopkeepNPC, key="test keep", location=self.room1)
        self._stock(shopkeep, npcs.SHOPKEEP_MAX_HELD_ITEMS + 5)

        script = self._cleanup(shopkeep)
        script.at_repeat()

        self.assertEqual(len(shopkeep.contents), npcs.SHOPKEEP_MAX_HELD_ITEMS)

    def test_the_default_cap_matches_what_creation_stamps(self):
        """One owner for the number, read the same way by both.

        The stamp and the script's fallback were a literal 20 in two separate
        files, which is the shape that hid every anvil recipe behind
        "Metalsmith" vs "Metalsmithing".
        """
        shopkeep = create_object(ShopkeepNPC, key="test keep", location=self.room1)

        self.assertEqual(shopkeep.db.max_held_items, npcs.SHOPKEEP_MAX_HELD_ITEMS)

    def _cleanup(self, shopkeep):
        """The one cleanup script on this NPC."""
        attached = list(shopkeep.scripts.all())

        for script in attached:
            if script.typeclass_path == npcs.SHOPKEEP_CLEANUP_SCRIPT:
                return script

        self.fail("shopkeep carries no cleanup script")
