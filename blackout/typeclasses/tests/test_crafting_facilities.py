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

from systems.crafting.registry import RECIPE_REGISTRY
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.crafting_facilities import CmdCraft
from typeclasses.skill_facilities import AnvilFacility, FurnaceFacility


class TestCraftMenuFacilityFiltering(EvenniaCommandTest):
    """A facility's craft menu must list only its own category's recipes."""

    character_typeclass = BlackoutCharacter

    def _listed_recipe_names(self):
        """The recipe names the open menu is offering.

        A row reads "<name> (<Skill> Lv.N) - requires <materials>", so the
        name is everything before the skill gate. Split rather than searched
        for: every metalsmith row NAMES rusty scrap metal as a material, and
        a substring check cannot tell that from the foundry recipe that
        makes it.
        """
        options = self.char1.ndb._evmenu.test_options

        return {opt["desc"].split(" (")[0] for opt in options}

    def _recipe_names_in_categories(self, categories):
        """Every registered recipe whose category is one of categories."""
        return {
            cls.name
            for cls in RECIPE_REGISTRY.values()
            if cls.category in categories
        }

    def test_furnace_menu_shows_only_foundry_recipes(self):
        furnace = create_object(FurnaceFacility, key="Foundry Furnace", location=self.room1)

        self.call(CmdCraft(), "", obj=furnace)

        expected = self._recipe_names_in_categories(FurnaceFacility.allowed_categories)

        self.assertTrue(expected)
        self.assertEqual(self._listed_recipe_names(), expected)

    def test_anvil_menu_shows_only_metalsmith_recipes(self):
        anvil = create_object(AnvilFacility, key="Metalsmith Anvil", location=self.room1)

        self.call(CmdCraft(), "", obj=anvil)

        expected = self._recipe_names_in_categories(AnvilFacility.allowed_categories)

        self.assertTrue(expected)
        self.assertEqual(self._listed_recipe_names(), expected)

    def test_menu_lists_recipes_by_skill_then_level(self):
        """The list climbs like the skills sheet does, not alphabetically.

        The old menu sorted by name, which put the Lv.10 battleaxe second and
        the Lv.14 shortsword last -- a player could not read where they were
        on the ladder.
        """
        anvil = create_object(AnvilFacility, key="Metalsmith Anvil", location=self.room1)

        self.call(CmdCraft(), "", obj=anvil)

        options = self.char1.ndb._evmenu.test_options
        by_name = {cls.name: cls for cls in RECIPE_REGISTRY.values()}
        listed = [by_name[name] for name in
                  [opt["desc"].split(" (")[0] for opt in options]]
        keys = [(cls.required_skill, cls.required_level, cls.name)
                for cls in listed]

        self.assertEqual(keys, sorted(keys))

    def test_a_repeated_material_is_shown_as_a_count(self):
        """Three of the same scrap reads "3x rusty scrap metal", once."""
        anvil = create_object(AnvilFacility, key="Metalsmith Anvil", location=self.room1)

        self.call(CmdCraft(), "", obj=anvil)

        options = self.char1.ndb._evmenu.test_options
        by_name = {cls.name: cls for cls in RECIPE_REGISTRY.values()}

        for opt in options:
            name = opt["desc"].split(" (")[0]
            recipe_cls = by_name[name]

            with self.subTest(recipe=name):
                for mat_name in set(recipe_cls.consumable_names or ()):
                    count = list(recipe_cls.consumable_names).count(mat_name)

                    if count > 1:
                        self.assertIn(f"{count}x {mat_name}", opt["desc"])
                        self.assertNotIn(f"{mat_name}, {mat_name}", opt["desc"])
