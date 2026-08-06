"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/03/2026
Description: Tests for the quantity-aware input validation and consumption
             in BlackoutRecipe. This replaces the crafting contrib's
             one-object-per-slot matching so a single stackable object can
             satisfy multiple required units (e.g. a recipe needing two
             rusty metal dust from one stack).

Run with:
    evennia test --settings settings.py systems.crafting
"""



from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from systems.crafting.blackout_recipe import BlackoutRecipe
from systems.crafting.constants import CATEGORY_METALSMITH
from systems.crafting.recipes.metalsmith_recipes import RustyScrapShortswordRecipe
from world.item_database import ITEM_DB


class DustConsumingRecipe(BlackoutRecipe):
    """Test-only recipe: consumes two units of rusty metal dust per craft.

    Dust is stackable, so a single stack object must fill both slots.
    """

    name = "test dust consumer"
    category = CATEGORY_METALSMITH

    consumable_tags = ["rusty_metal_dust", "rusty_metal_dust"]
    consumable_names = ["rusty metal dust", "rusty metal dust"]

    output_item_keys = ["rusty_metal_chunk"]

    success_message = "You test-craft a chunk."


class TestStackableConsumption(EvenniaCommandTest):
    """Recipe-layer tests: input matching and consumption by units."""

    def _craft_with(self, *inputs):
        recipe = DustConsumingRecipe(self.char1, *inputs)
        return recipe.craft()

    def test_single_stack_satisfies_both_slots(self):
        dust = ITEM_DB["rusty_metal_dust"].create(location=self.char1, quantity=3)

        result = self._craft_with(dust)

        self.assertTrue(result)
        self.assertEqual(dust.quantity, 1)

    def test_whole_stack_consumed_when_quantity_is_exact(self):
        dust = ITEM_DB["rusty_metal_dust"].create(location=self.char1, quantity=2)

        result = self._craft_with(dust)

        self.assertTrue(result)
        self.assertNotIn(dust, self.char1.contents)
        leftovers = [obj for obj in self.char1.contents if obj.key == "rusty metal dust"]
        self.assertEqual(leftovers, [])

    def test_insufficient_stack_fails_without_consuming(self):
        dust = ITEM_DB["rusty_metal_dust"].create(location=self.char1, quantity=1)

        result = self._craft_with(dust)

        self.assertIsNone(result)
        self.assertEqual(dust.quantity, 1)

    def test_unrelated_extra_consumable_is_ignored(self):
        dust = ITEM_DB["rusty_metal_dust"].create(location=self.char1, quantity=3)
        extra = ITEM_DB["rusty_scrap_metal"].create(location=self.char1)

        result = self._craft_with(dust, extra)

        self.assertTrue(result)
        self.assertEqual(dust.quantity, 1)
        self.assertIn(extra, self.char1.contents)


class TestNonStackableMultiInput(EvenniaCommandTest):
    """The sword recipe's two non-stackable sheets are consumed one object
    per slot, exactly as before -- the reimplemented validation must not
    regress single-unit inputs."""

    def setUp(self) -> None:
        super().setUp()

        self.char1.skills.add_xp("metalsmith", 10000)
        self.hammer = ITEM_DB["hammer"].create(location=self.char1)
        self.anvil = create_object(
            "typeclasses.skill_facilities.AnvilFacility",
            key="Anvil",
            location=self.room1,
        )

    def test_two_sheets_produce_one_sword(self):
        sheets = [
            ITEM_DB["rusty_scrap_metal"].create(location=self.char1) for _ in range(2)
        ]

        recipe = RustyScrapShortswordRecipe(self.char1, self.anvil, self.hammer, *sheets)
        result = recipe.craft()

        self.assertTrue(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].key, "rusty scrap shortsword")
        self.assertNotIn(sheets[0], self.char1.contents)
        self.assertNotIn(sheets[1], self.char1.contents)

    def test_single_sheet_fails_without_consuming(self):
        sheet = ITEM_DB["rusty_scrap_metal"].create(location=self.char1)

        recipe = RustyScrapShortswordRecipe(self.char1, self.anvil, self.hammer, sheet)
        result = recipe.craft()

        self.assertIsNone(result)
        self.assertIn(sheet, self.char1.contents)
