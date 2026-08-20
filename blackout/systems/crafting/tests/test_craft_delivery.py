"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/17/2026
Description: Tests for how perform_craft hands a finished item to the
             crafter, and for the state-feed snapshot that follows a craft.

             The bug these cover: outputs were delivered with
             `obj.location = caller`, which does not fire at_object_receive,
             so a crafted item reached the character's contents without an
             inventory slot and without publishing anything. The 3D client's
             inventory pane therefore stayed frozen through a whole batch
             craft -- the consumed inputs published nothing either, because
             obj.delete() does not fire at_object_leave.

Run with:
    evennia test --settings settings.py systems.crafting
"""



from unittest import mock

from evennia.utils.test_resources import EvenniaCommandTest

from items.inventory.handler import InventoryHandler
from systems.crafting import crafting_service
from systems.crafting.registry import RECIPE_REGISTRY
from systems.crafting.tests.test_blackout_recipe import DustConsumingRecipe
from world.item_database import ITEM_DB


class CraftDeliveryTestBase(EvenniaCommandTest):
    """Registers a tool-free, skill-free recipe so perform_craft can be
    driven by key without dragging an anvil and a skill level into every
    test."""

    recipe_key = DustConsumingRecipe.name

    def setUp(self):
        super().setUp()
        RECIPE_REGISTRY[self.recipe_key] = DustConsumingRecipe
        self.addCleanup(RECIPE_REGISTRY.pop, self.recipe_key, None)

    def _give_dust(self, quantity):
        """Put one stack of the recipe's only input in the crafter's grid."""
        return ITEM_DB["rusty_metal_dust"].create(
            location=self.char1, quantity=quantity
        )


class TestCraftedOutputDelivery(CraftDeliveryTestBase):
    """Where a finished item ends up, and whether the grid knows about it."""

    def test_output_occupies_an_inventory_slot(self):
        self._give_dust(2)

        result = crafting_service.perform_craft(self.char1, self.recipe_key)

        self.assertTrue(result)
        crafted = result[0]
        self.assertEqual(crafted.location, self.char1)
        slot = self.char1.inventory.find_slot(crafted)
        self.assertGreaterEqual(slot, 0)

    def test_output_falls_to_the_ground_when_the_grid_is_full(self):
        self._give_dust(2)

        with mock.patch.object(InventoryHandler, "can_accept", return_value=False):
            result = crafting_service.perform_craft(self.char1, self.recipe_key)

        self.assertTrue(result)
        crafted = result[0]
        self.assertEqual(crafted.location, self.char1.location)


class TestCraftPublishesInventory(CraftDeliveryTestBase):
    """The state-feed snapshot the graphical inventory pane redraws from."""

    def test_successful_craft_publishes_a_snapshot(self):
        self._give_dust(2)

        with mock.patch(
            "systems.statefeed.events.emit_inventory"
        ) as emit_inventory:
            crafting_service.perform_craft(self.char1, self.recipe_key)

        emit_inventory.assert_called_with(self.char1)

    def test_publish_survives_a_raising_feed(self):
        """The batch loop calls this from a delay callback, so a feed that
        raises must not take the craft down with it."""
        self._give_dust(2)

        with mock.patch(
            "systems.statefeed.events.emit_inventory",
            side_effect=RuntimeError("feed exploded"),
        ):
            result = crafting_service.perform_craft(self.char1, self.recipe_key)

        self.assertTrue(result)
