"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Tests that retire the shopkeep cleanup script.

ShopkeepCleanup cut the holdings of a shopkeep to 20 objects once a day,
from 07/13/2026 to 11/03/2026. The held units now decay, through
systems/gameplay/shop/held.py. ScriptDB rows of the script stay in a live
database until something deletes them. Two things delete them. The class
deletes its own row at the next server start. `retire_cleanup_script`
deletes a row of either retired path at each tile sync.
"""

from evennia import create_object, create_script
from evennia.utils.test_resources import EvenniaTestCase
from evennia.utils.utils import class_from_module

from typeclasses import npcs
from typeclasses.npcs import ShopkeepNPC


# A plain script, for a row that carries a retired path.
_PLAIN_SCRIPT = "evennia.scripts.scripts.DefaultScript"


class TestTheCleanupIsRetired(EvenniaTestCase):
    """No new row, and every old row goes."""

    def _retired_rows(self, shopkeep) -> list:
        """The scripts on this NPC under a retired path."""
        attached = list(shopkeep.scripts.all())

        return [script for script in attached
                if script.typeclass_path in npcs.RETIRED_SHOPKEEP_CLEANUP_SCRIPTS]

    def _row_with_path(self, shopkeep, path: str):
        """A script on the shopkeep whose row names `path`. The class of
        the row stays a plain script, as Evennia loads a stale path."""
        script = create_script(_PLAIN_SCRIPT, obj=shopkeep, key="old trim")
        script.db_typeclass_path = path
        script.save(update_fields=["db_typeclass_path"])

        return script

    def test_a_new_shopkeep_carries_no_cleanup_script(self):
        shopkeep = create_object(ShopkeepNPC, key="test keep")

        self.assertEqual([], self._retired_rows(shopkeep))
        self.assertFalse(shopkeep.attributes.has(npcs.RETIRED_MAX_HELD_ATTR))

    def test_the_retire_deletes_a_row_of_each_retired_path(self):
        shopkeep = create_object(ShopkeepNPC, key="test keep")

        for path in npcs.RETIRED_SHOPKEEP_CLEANUP_SCRIPTS:
            self._row_with_path(shopkeep, path)

        shopkeep.retire_cleanup_script()

        self.assertEqual([], self._retired_rows(shopkeep))

    def test_the_retire_removes_the_cap_attribute(self):
        shopkeep = create_object(ShopkeepNPC, key="test keep")
        shopkeep.attributes.add(npcs.RETIRED_MAX_HELD_ATTR, 20)

        shopkeep.retire_cleanup_script()

        self.assertFalse(shopkeep.attributes.has(npcs.RETIRED_MAX_HELD_ATTR))

    def test_the_retire_rides_the_tile_sync(self):
        shopkeep = create_object(ShopkeepNPC, key="test keep")
        self._row_with_path(shopkeep, npcs.SHOPKEEP_CLEANUP_SCRIPT)

        shopkeep.refresh_from_def()

        self.assertEqual([], self._retired_rows(shopkeep))

    def test_the_current_path_still_imports_the_shell(self):
        """A row of this path must load the class that deletes it. A stale
        path loads a plain script, which cannot."""
        loaded = class_from_module(npcs.SHOPKEEP_CLEANUP_SCRIPT)

        self.assertIs(npcs.ShopkeepCleanup, loaded)

    def test_the_shell_deletes_its_row_at_server_start(self):
        shopkeep = create_object(ShopkeepNPC, key="test keep")
        script = create_script(npcs.SHOPKEEP_CLEANUP_SCRIPT, obj=shopkeep)

        script.at_server_start()

        self.assertIsNone(script.pk)

    def test_the_shell_deletes_its_row_at_a_repeat(self):
        shopkeep = create_object(ShopkeepNPC, key="test keep")
        script = create_script(npcs.SHOPKEEP_CLEANUP_SCRIPT, obj=shopkeep)

        script.at_repeat()

        self.assertIsNone(script.pk)
