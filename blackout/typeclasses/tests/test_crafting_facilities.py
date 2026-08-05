"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Regression test for CmdCraft's facility-filtered recipe list.

CmdCraft used to pass facility=self.obj straight into EvMenu's own
**kwargs, which only become attributes on the menu instance
(caller.ndb._evmenu.facility) and are never forwarded to the start node.
crafting_menu.start() read kwargs.get("facility"), got None on every open,
and crafting_service.get_recipes_for_facility(None) falls through its
"no restriction" branch -- so every facility showed every recipe in the
registry instead of only its own category's.
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.crafting_facilities import CmdCraft
from typeclasses.skill_facilities import AnvilFacility, FurnaceFacility


class TestCraftMenuFacilityFiltering(EvenniaCommandTest):
    """A facility's craft menu must list only its own category's recipes."""

    character_typeclass = BlackoutCharacter

    def test_furnace_menu_shows_only_foundry_recipes(self):
        furnace = create_object(FurnaceFacility, key="Foundry Furnace", location=self.room1)

        self.call(CmdCraft(), "", obj=furnace)

        options = self.char1.ndb._evmenu.test_options
        descs = " ".join(opt["desc"] for opt in options)

        self.assertIn("rusty scrap metal", descs)
        self.assertNotIn("rusty scrap axe", descs)
        self.assertNotIn("rusty scrap shortsword", descs)
        self.assertNotIn("rusty scrap spear", descs)
        self.assertNotIn("rusty metal dust", descs)

    def test_anvil_menu_shows_only_metalsmith_recipes(self):
        anvil = create_object(AnvilFacility, key="Metalsmith Anvil", location=self.room1)

        self.call(CmdCraft(), "", obj=anvil)

        options = self.char1.ndb._evmenu.test_options
        descs = " ".join(opt["desc"] for opt in options)

        self.assertIn("rusty scrap axe", descs)
        self.assertIn("rusty scrap shortsword", descs)
        self.assertIn("rusty scrap spear", descs)
        self.assertIn("rusty metal dust", descs)
        self.assertNotIn("rusty scrap metal [", descs)
