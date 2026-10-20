"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/20/2026
Description: Tests for the moment that a finished craft sends. The skill of
             the recipe names the moment in `craft_moment`, and
             crafting_service.perform_craft sends it. The client plays the
             sound of the moment (godot/world/sound_cues.gd).

Run with:
    evennia test --settings test_settings.py systems.gameplay.crafting
"""



import unittest
from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.crafting import crafting_service
from systems.gameplay.crafting.registry import RECIPE_REGISTRY
from systems.gameplay.crafting.tests.test_blackout_recipe import DustConsumingRecipe
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed_events
from world.item_database import ITEM_DB



class _MetalsmithDustRecipe(DustConsumingRecipe):
    """Test-only recipe under Metalsmith, at level 0, with no tool."""

    name = "test metalsmith dust consumer"
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 0



class _FoundryDustRecipe(DustConsumingRecipe):
    """Test-only recipe under Foundry, at level 0, with no tool."""

    name = "test foundry dust consumer"
    required_skill = skill_constants.SKILL_KEY_FOUNDRY
    required_level = 0



class TestCraftMoment(EvenniaTest):
    """A finished craft sends the moment of its skill, one time."""

    def setUp(self):
        super().setUp()

        for recipe_cls in (_MetalsmithDustRecipe, _FoundryDustRecipe,
                           DustConsumingRecipe):
            RECIPE_REGISTRY[recipe_cls.name] = recipe_cls
            self.addCleanup(RECIPE_REGISTRY.pop, recipe_cls.name, None)


    def _give_dust(self, quantity):
        """Put one stack of the only input of the recipe in the grid."""
        return ITEM_DB["rusty_metal_dust"].create(
            location=self.char1, quantity=quantity
        )


    def _craft(self, recipe_cls):
        """Craft one item and give the mock of emit_moment."""
        with mock.patch.object(feed_events, "emit_moment") as emitted:
            result = crafting_service.perform_craft(self.char1, recipe_cls.name)

        return result, emitted


    def test_a_metalsmith_craft_sends_the_moment_of_the_skill(self):
        """The client plays the metal sound one time for each item."""
        self._give_dust(2)

        result, emitted = self._craft(_MetalsmithDustRecipe)

        self.assertTrue(result)
        emitted.assert_called_once_with(
            self.char1, feed_const.MOMENT_METALSMITH_CRAFT)


    def test_a_foundry_craft_sends_the_moment_of_the_skill(self):
        """The furnace plays its own sound, not the sound of the anvil."""
        self._give_dust(2)

        result, emitted = self._craft(_FoundryDustRecipe)

        self.assertTrue(result)
        emitted.assert_called_once_with(
            self.char1, feed_const.MOMENT_FOUNDRY_CRAFT)


    def test_a_refused_craft_sends_nothing(self):
        """No material, no item, and thus no sound."""
        result, emitted = self._craft(_MetalsmithDustRecipe)

        self.assertFalse(result)
        emitted.assert_not_called()


    def test_a_skill_with_no_craft_moment_sends_nothing(self):
        self._give_dust(2)
        metalsmith = SKILL_REGISTRY[skill_constants.SKILL_KEY_METALSMITH]

        with mock.patch.object(metalsmith, "craft_moment", None):
            result, emitted = self._craft(_MetalsmithDustRecipe)

        self.assertTrue(result)
        emitted.assert_not_called()


    def test_a_recipe_with_no_skill_sends_nothing(self):
        self._give_dust(2)

        result, emitted = self._craft(DustConsumingRecipe)

        self.assertTrue(result)
        emitted.assert_not_called()



class TestEveryCraftMomentIsSent(unittest.TestCase):

    def test_every_craft_moment_is_a_moment_the_feed_sends(self):
        """A typed name that is not in MOMENTS sends nothing, so it fails here."""
        for key, skill_class in SKILL_REGISTRY.items():
            moment = getattr(skill_class, "craft_moment", None)

            if moment is None:
                continue

            with self.subTest(skill=key):
                self.assertIn(moment, feed_const.MOMENTS)
