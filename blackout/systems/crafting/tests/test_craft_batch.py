"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/01/2026
Description: Tests for crafting_service.get_max_craftable and the paced
             multi-craft batch loop in systems.crafting.craft_batch.

Run with:
    evennia test --settings settings.py systems.crafting
"""



from unittest.mock import patch

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from systems.crafting import craft_batch, crafting_service
from systems.crafting.constants import CRAFTING_BUSY_COOLDOWN_KEY, MAX_CRAFT_BATCH_SIZE
from world.item_database import ITEM_DB


RECIPE_KEY = "rusty metal dust"
SWORD_RECIPE_KEY = "rusty scrap shortsword"


class _CraftBatchTestCase(EvenniaCommandTest):
    """Shared setup: a character able to craft 'rusty metal dust', which
    needs one hammer (tool, not consumed) and one rusty_metal_chunk per
    craft (consumed, required_level 0)."""

    def setUp(self) -> None:
        super().setUp()

        self.hammer = ITEM_DB["hammer"].create(location=self.char1)

    def _give_chunks(self, count):
        for _ in range(count):
            ITEM_DB["rusty_metal_chunk"].create(location=self.char1)


class TestGetMaxCraftable(_CraftBatchTestCase):

    def test_unknown_recipe_is_zero(self):
        self.assertEqual(crafting_service.get_max_craftable(self.char1, "not a recipe"), 0)

    def test_limited_by_materials_on_hand(self):
        self._give_chunks(3)

        self.assertEqual(crafting_service.get_max_craftable(self.char1, RECIPE_KEY), 3)

    def test_zero_without_the_required_tool(self):
        self.hammer.delete()
        self._give_chunks(5)

        self.assertEqual(crafting_service.get_max_craftable(self.char1, RECIPE_KEY), 0)

    def test_zero_with_no_materials(self):
        self.assertEqual(crafting_service.get_max_craftable(self.char1, RECIPE_KEY), 0)

    def test_capped_at_max_batch_size(self):
        self._give_chunks(MAX_CRAFT_BATCH_SIZE + 20)

        self.assertEqual(
            crafting_service.get_max_craftable(self.char1, RECIPE_KEY), MAX_CRAFT_BATCH_SIZE
        )


class TestStartBatch(_CraftBatchTestCase):

    def test_start_batch_crafts_first_item_immediately(self):
        self._give_chunks(3)

        with patch.object(craft_batch, "delay") as mock_delay:
            started, _message = craft_batch.start_batch(self.char1, RECIPE_KEY, 3)

        self.assertTrue(started)
        mock_delay.assert_called_once()

        active = craft_batch.get_active_batch(self.char1)
        self.assertEqual(active["crafted"], 1)
        self.assertEqual(active["remaining"], 2)
        self.assertEqual(active["total"], 3)

    def test_start_batch_clamps_to_max_craftable(self):
        self._give_chunks(2)

        with patch.object(craft_batch, "delay"):
            craft_batch.start_batch(self.char1, RECIPE_KEY, 10)

        active = craft_batch.get_active_batch(self.char1)
        self.assertEqual(active["total"], 2)

    def test_single_item_batch_leaves_nothing_active(self):
        self._give_chunks(1)

        with patch.object(craft_batch, "delay") as mock_delay:
            started, _message = craft_batch.start_batch(self.char1, RECIPE_KEY, 1)

        self.assertTrue(started)
        mock_delay.assert_not_called()
        self.assertIsNone(craft_batch.get_active_batch(self.char1))

    def test_refuses_to_start_over_an_active_batch(self):
        self._give_chunks(5)

        with patch.object(craft_batch, "delay"):
            craft_batch.start_batch(self.char1, RECIPE_KEY, 3)
            started, message = craft_batch.start_batch(self.char1, RECIPE_KEY, 1)

        self.assertFalse(started)
        self.assertIn("already crafting", message)

    def test_refuses_while_busy_cooldown_is_still_running(self):
        """The busy cooldown outlives the batch Attribute by design -- it is
        armed on the final item too, so it is still ticking down for a
        moment after get_active_batch has already gone back to None."""
        self._give_chunks(1)
        self.char1.cooldowns.add(CRAFTING_BUSY_COOLDOWN_KEY, 10)

        started, message = craft_batch.start_batch(self.char1, RECIPE_KEY, 1)

        self.assertFalse(started)
        self.assertIn("still finishing up", message)

    def test_refuses_when_materials_are_missing(self):
        started, message = craft_batch.start_batch(self.char1, RECIPE_KEY, 1)

        self.assertFalse(started)
        self.assertIn("Cannot craft", message)


class TestCancelBatch(_CraftBatchTestCase):

    def test_cancel_returns_false_when_nothing_is_active(self):
        self.assertFalse(craft_batch.cancel_batch(self.char1))

    def test_cancel_stops_the_next_scheduled_item(self):
        self._give_chunks(5)

        with patch.object(craft_batch, "delay"):
            craft_batch.start_batch(self.char1, RECIPE_KEY, 3)

        self.assertTrue(craft_batch.cancel_batch(self.char1))
        self.assertIsNone(craft_batch.get_active_batch(self.char1))

        # The delayed continuation firing after cancellation must be a
        # silent no-op, not a crash or a resumed batch.
        craft_batch._craft_one(self.char1, RECIPE_KEY)

        self.assertIsNone(craft_batch.get_active_batch(self.char1))


class _SwordRecipeTestCase(EvenniaCommandTest):
    """Shared setup: a character able to craft the 2-sheet shortsword
    (metalsmith Lv.2+, hammer carried, anvil in the room)."""

    def setUp(self) -> None:
        super().setUp()

        self.char1.skills.add_xp("metalsmith", 10000)
        self.hammer = ITEM_DB["hammer"].create(location=self.char1)
        create_object(
            "typeclasses.skill_facilities.AnvilFacility",
            key="Anvil",
            location=self.room1,
        )

    def _give_sheets(self, count):
        for _ in range(count):
            ITEM_DB["rusty_scrap_metal"].create(location=self.char1)


class TestMultiMaterialRecipes(_SwordRecipeTestCase):
    """The shortsword takes two rusty scrap metal sheets per craft; every
    service-layer count must be in units, not objects."""

    def test_max_craftable_is_sheets_divided_by_two(self):
        self._give_sheets(5)

        self.assertEqual(crafting_service.get_max_craftable(self.char1, SWORD_RECIPE_KEY), 2)

    def test_max_craftable_rounds_down_with_odd_sheets(self):
        self._give_sheets(3)

        self.assertEqual(crafting_service.get_max_craftable(self.char1, SWORD_RECIPE_KEY), 1)

    def test_max_craftable_zero_with_a_single_sheet(self):
        self._give_sheets(1)

        self.assertEqual(crafting_service.get_max_craftable(self.char1, SWORD_RECIPE_KEY), 0)

    def test_check_craftable_reports_shortfall_once(self):
        self._give_sheets(1)

        can_craft, reasons = crafting_service.check_craftable(self.char1, SWORD_RECIPE_KEY)

        self.assertFalse(can_craft)
        self.assertEqual(reasons.count("Missing rusty scrap metal (1/2)"), 1)

    def test_display_data_shows_required_two(self):
        self._give_sheets(5)

        data = crafting_service.get_recipe_display_data(self.char1, SWORD_RECIPE_KEY)
        details = data["material_details"]

        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["required"], 2)
        self.assertEqual(details[0]["owned"], 5)

    def test_batch_of_two_consumes_exactly_four_sheets(self):
        self._give_sheets(5)

        with patch.object(craft_batch, "delay"):
            started, _message = craft_batch.start_batch(self.char1, SWORD_RECIPE_KEY, 2)

        self.assertTrue(started)
        craft_batch._craft_one(self.char1, SWORD_RECIPE_KEY)

        sheets_left = [obj for obj in self.char1.contents if obj.key == "rusty scrap metal"]
        self.assertEqual(len(sheets_left), 1)
        self.assertIsNone(craft_batch.get_active_batch(self.char1))
