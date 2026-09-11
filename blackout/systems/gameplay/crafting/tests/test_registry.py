"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/01/2026
Description: Regression tests for the recipe registry that replaced the
             crafting contrib's private _load_recipes / _RECIPE_CLASSES.

Run with:
    evennia test --settings settings.py systems.gameplay.crafting
"""



import importlib
import inspect
import unittest

from django.conf import settings
from evennia.contrib.game_systems.crafting.crafting import (
    CraftingRecipe,
    CraftingRecipeBase,
)

from systems.gameplay.crafting import crafting_service
from systems.gameplay.crafting.blackout_recipe import BlackoutRecipe
from systems.gameplay.crafting.constants import (
    CATEGORY_FOUNDRY,
    CATEGORY_METALSMITH,
    CRAFTING_CATEGORIES,
)
from systems.gameplay.crafting.registry import RECIPE_REGISTRY, _is_registrable_recipe



class TestRecipeDiscovery(unittest.TestCase):
    """What the registry does and does not pick up."""

    def test_registry_is_populated(self):
        self.assertTrue(RECIPE_REGISTRY)

    def test_every_entry_is_a_real_recipe(self):
        for recipe_name, recipe_cls in RECIPE_REGISTRY.items():
            self.assertTrue(issubclass(recipe_cls, BlackoutRecipe))
            self.assertEqual(recipe_cls.name, recipe_name)

    def test_every_recipe_in_a_configured_module_is_registered(self):
        """Discovery must find every recipe the configured modules define.

        Derived from the modules themselves rather than from a frozen list of
        names: the bug worth catching is a recipe silently failing to
        register, and a hardcoded census cannot tell that apart from someone
        legitimately adding a seventh recipe. The predecessor of this test
        asserted a literal six-name list and failed the moment the metalsmith
        module grew.
        """
        defined = self._recipe_names_defined_in_configured_modules()

        self.assertTrue(defined, "no recipes found in CRAFT_RECIPE_MODULES")
        self.assertEqual(sorted(RECIPE_REGISTRY), sorted(defined))

    def _recipe_names_defined_in_configured_modules(self):
        """Every recipe name the configured modules define, found by import.

        Deliberately reimplements discovery instead of calling the registry's
        own helper -- a test that reuses the code under test proves nothing.

        The placeholder-name filter is the fourth condition and it is not
        optional. A recipe module may define an abstract base of its own to
        share declarations across its recipes (rendering_recipes does), and
        such a base satisfies the other three checks exactly: it subclasses
        BlackoutRecipe, it is defined in the module, and it is a class. What it
        does not have is a name -- it inherits the contrib's, which is the same
        thing the registry keys on to exclude it.
        """
        names = []
        for module_path in settings.CRAFT_RECIPE_MODULES:
            module = importlib.import_module(module_path)
            for _attr_name, candidate in vars(module).items():
                if not inspect.isclass(candidate):
                    continue
                if not issubclass(candidate, BlackoutRecipe):
                    continue
                if candidate.__module__ != module_path:
                    continue
                if candidate.name in (CraftingRecipe.name, CraftingRecipeBase.name):
                    continue
                names.append(candidate.name)

        return names

    def test_an_abstract_recipe_base_is_not_registered(self):
        """A module-private base class must not reach the craft menu.

        rendering_recipes._RenderingRecipe declares a category, a skill and a
        tool but no name, so it is a perfectly valid recipe in every respect
        except being one. The registry's placeholder-name filter is what keeps
        it out; without it the menu grows a 'crafting recipe' entry that
        consumes nothing and produces nothing.
        """
        module = importlib.import_module(
            "systems.gameplay.crafting.recipes.rendering_recipes"
        )
        abstract_base = module._RenderingRecipe

        self.assertEqual(abstract_base.name, CraftingRecipe.name)
        self.assertNotIn(abstract_base, RECIPE_REGISTRY.values())

    def test_base_class_is_not_registered(self):
        """BlackoutRecipe is imported into both recipe modules, so a naive
        namespace scan would count it as a recipe -- it inherits
        CraftingRecipe's placeholder name and an empty category. The contrib's
        loader also excludes it (callables_from_module filters on the defining
        module), so this is a guard against regressing our own filter, not a
        contrib bug being fixed."""
        registered = list(RECIPE_REGISTRY.values())

        self.assertNotIn(BlackoutRecipe, registered)
        self.assertNotIn(CraftingRecipe, registered)
        self.assertNotIn(CraftingRecipeBase, registered)
        self.assertNotIn(CraftingRecipe.name, RECIPE_REGISTRY)

    def test_imported_class_is_rejected_by_module_check(self):
        """The __module__ filter is what does the work above."""
        defining_module = BlackoutRecipe.__module__
        importing_module = "systems.gameplay.crafting.recipes.metalsmith_recipes"

        is_registrable = _is_registrable_recipe(BlackoutRecipe, importing_module)
        self.assertFalse(is_registrable)
        self.assertNotEqual(defining_module, importing_module)

    def test_every_registered_recipe_has_a_real_category(self):
        """Derived from CRAFTING_CATEGORIES, not a literal pair.

        BlackoutRecipe.__init_subclass__ already raises at import on a category
        outside that tuple, so what this actually guards is the tuple staying
        the one owner of the list -- adding Rendering must not mean editing a
        second census here.
        """
        for recipe_name, recipe_cls in RECIPE_REGISTRY.items():
            with self.subTest(recipe=recipe_name):
                self.assertIn(
                    recipe_cls.category,
                    CRAFTING_CATEGORIES,
                    msg=f"{recipe_name} has category {recipe_cls.category!r}",
                )



class TestServiceUsesRegistry(unittest.TestCase):
    """crafting_service's three read paths, now backed by the registry."""

    def test_no_uncategorized_category(self):
        """get_categories buckets any recipe with an unset category under
        'Uncategorized'. Nothing should land there."""
        categories = crafting_service.get_categories()

        self.assertNotIn("Uncategorized", categories)

    def test_every_live_category_is_a_declared_one(self):
        """Asserts the relationship, not a census.

        One direction only, deliberately. Every category the service reports
        must be declared in CRAFTING_CATEGORIES -- the other direction would
        fail the moment a category is declared ahead of the recipes that fill
        it, which is exactly how Curing and Gastronomy will arrive.
        """
        categories = crafting_service.get_categories()

        self.assertTrue(categories)
        for category in categories:
            with self.subTest(category=category):
                self.assertIn(category, CRAFTING_CATEGORIES)

    def test_get_recipe_class_resolves_exactly(self):
        recipe_cls = crafting_service.get_recipe_class("rusty metal dust")

        self.assertIsNotNone(recipe_cls)
        self.assertEqual(recipe_cls.name, "rusty metal dust")

    def test_get_recipe_class_does_not_fuzzy_match(self):
        """The contrib's craft() resolves names by prefix/substring. The
        registry is an exact dict lookup, so a partial name must miss rather
        than silently pick a recipe the player did not ask for."""
        self.assertIsNone(crafting_service.get_recipe_class("rusty"))
        self.assertIsNone(crafting_service.get_recipe_class("unknown recipe"))

    def test_recipes_in_category_match_the_registry(self):
        found = crafting_service.get_recipes_in_category(CATEGORY_METALSMITH)
        found_names = [key for key, _cls in found]

        expected = [
            name
            for name, cls in RECIPE_REGISTRY.items()
            if cls.category == CATEGORY_METALSMITH
        ]
        self.assertEqual(sorted(found_names), sorted(expected))

    def test_recipes_in_category_respects_facility_restriction(self):
        """A facility whose allowed_categories excludes the requested
        category must not leak that category's recipes, even if some
        recipe happens to carry it (a Furnace asking for Metalsmith)."""

        class _FakeFacility:
            allowed_categories = [CATEGORY_FOUNDRY]

        found = crafting_service.get_recipes_in_category(
            CATEGORY_METALSMITH, facility=_FakeFacility()
        )

        self.assertEqual(found, [])

    def test_recipes_in_category_facility_allows_matching_category(self):
        class _FakeFacility:
            allowed_categories = [CATEGORY_METALSMITH]

        found = crafting_service.get_recipes_in_category(
            CATEGORY_METALSMITH, facility=_FakeFacility()
        )
        found_names = [key for key, _cls in found]

        expected = [
            name
            for name, cls in RECIPE_REGISTRY.items()
            if cls.category == CATEGORY_METALSMITH
        ]
        self.assertEqual(sorted(found_names), sorted(expected))

    def test_recipes_for_facility_matches_only_allowed_categories(self):
        """A single-category facility (e.g. a Furnace) sees only its own
        category's recipes, never the other skill's."""

        class _FakeFurnace:
            allowed_categories = [CATEGORY_FOUNDRY]

        found = crafting_service.get_recipes_for_facility(_FakeFurnace())
        found_categories = {cls.category for _key, cls in found}

        self.assertEqual(found_categories, {CATEGORY_FOUNDRY})

    def test_recipes_for_facility_spans_multiple_allowed_categories(self):
        """A facility allowing EVERY category sees every recipe.

        allowed_categories is CRAFTING_CATEGORIES rather than the two it used
        to name: the claim is that a facility restricted to nothing and a
        facility allowed everything agree, and naming a subset turned that into
        an accidental census that broke when Rendering landed.
        """

        class _FakeMultiTool:
            allowed_categories = list(CRAFTING_CATEGORIES)

        found = crafting_service.get_recipes_for_facility(_FakeMultiTool())
        found_names = [key for key, _cls in found]

        self.assertEqual(sorted(found_names), sorted(RECIPE_REGISTRY))

    def test_recipes_for_facility_with_no_allowed_categories_returns_everything(self):
        class _FakeOpenFacility:
            allowed_categories = None

        found = crafting_service.get_recipes_for_facility(_FakeOpenFacility())
        found_names = [key for key, _cls in found]

        self.assertEqual(sorted(found_names), sorted(RECIPE_REGISTRY))
