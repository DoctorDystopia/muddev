"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for the Curing recipes, the chamber, and the deferred-craft
             hook that connects them to the generic craft menu.

             The first class here exists because of a bug made while writing
             this stage. CuringRecipe was declared before
             BlackoutRecipe.deferred_handler existed and never set it, so every
             curing recipe ran as an ordinary instant craft: the chamber handed
             over cured meat with no wait, and nothing raised. One missing
             attribute disabled the entire mechanic, which is precisely the
             failure a declaration-driven design is prone to -- so the
             declaration is asserted.

Run with:
    evennia test --settings test_settings.py systems.gameplay.curing
"""



import unittest

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.crafting import crafting_service
from systems.gameplay.crafting.blackout_recipe import BlackoutRecipe
from systems.gameplay.crafting.constants import (
    CATEGORY_CURING,
    TOOL_TAG_CATEGORY,
)
from systems.gameplay.crafting.registry import RECIPE_REGISTRY
from systems.gameplay.curing import constants as curing_constants
from systems.gameplay.curing.recipe import CuringRecipe
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill
from typeclasses.skill_facilities import (
    CuringChamberFacility,
    FurnaceFacility,
)
from world.item_database import ITEM_DB



# Private constant definitions

_CHAMBER_TOOL_TAG = "curing_chamber"

_CHUCK_RECIPE = "mutant raider cured chuck"



def _curing_recipes():
    """Every registered recipe in the Curing category, read off the registry.

    By category rather than imported by name, so a recipe that fails to
    register fails these tests instead of disappearing from them.
    """
    matches = [
        (name, recipe_cls)
        for name, recipe_cls in RECIPE_REGISTRY.items()
        if recipe_cls.category == CATEGORY_CURING
    ]

    return matches



class TestEveryCureIsActuallyDeferred(unittest.TestCase):
    """The one attribute that makes the stage exist.

    Asserted three ways -- on the base, on each recipe, and through the
    resolver crafting_service actually calls -- because the bug that prompted
    this class was invisible to every behavioural test that did not check the
    clock.
    """

    def test_the_base_class_names_a_deferred_handler(self):
        self.assertEqual(CuringRecipe.deferred_handler, "curing")

    def test_every_curing_recipe_inherits_it(self):
        for name, recipe_cls in _curing_recipes():
            with self.subTest(recipe=name):
                self.assertEqual(recipe_cls.deferred_handler, "curing")

    def test_an_ordinary_recipe_is_not_deferred(self):
        """The default has to be "finishes now", or every craft in the game
        would be waiting for a handler nothing has."""
        self.assertIsNone(BlackoutRecipe.deferred_handler)

    def test_the_handler_name_resolves_on_a_character(self):
        """A name that resolves to nothing is refused rather than run instantly.

        Checked against the attribute Character actually declares, so renaming
        the handler accessor without renaming the string fails here instead of
        silently turning cures into instant crafts.
        """
        from typeclasses.characters import Character

        handler_name = CuringRecipe.deferred_handler

        self.assertTrue(hasattr(Character, handler_name))

    def test_no_other_category_is_deferred(self):
        """Curing is the only timed stage today.

        A rendering or foundry recipe that picked up a handler name would stop
        producing anything, and the craft menu would look unchanged.
        """
        for name, recipe_cls in RECIPE_REGISTRY.items():
            if recipe_cls.category == CATEGORY_CURING:
                continue
            with self.subTest(recipe=name):
                self.assertIsNone(recipe_cls.deferred_handler)



class TestCuringRecipeShape(unittest.TestCase):
    """What every Curing recipe must be true of."""

    def setUp(self):
        self.recipes = _curing_recipes()

    def test_the_category_is_populated(self):
        self.assertTrue(
            self.recipes,
            "no recipes registered in the Curing category -- check "
            "settings.CRAFT_RECIPE_MODULES",
        )

    def test_every_recipe_teaches_curing(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(
                    recipe_cls.required_skill,
                    skill_constants.CURING_SKILL_KEY,
                )
                self.assertGreater(recipe_cls.xp_reward, 0)

    def test_every_recipe_takes_real_time(self):
        """A zero duration is an instant craft wearing a Curing label."""
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertGreater(recipe_cls.cure_seconds, 0)

    def test_a_recipe_with_no_duration_is_refused_at_import(self):
        """__init_subclass__ is the guard, so the failure is a failed start.

        Declaring the subclass inside the test is the only way to exercise it:
        the check runs when the class statement executes.
        """
        with self.assertRaises(ValueError):

            class _NoDuration(CuringRecipe):
                name = "no duration"
                consumable_tags = ["mutant_raider_raw_chuck"]
                output_item_keys = ["mutant_raider_cured_chuck"]

    def test_an_abstract_subclass_may_omit_the_duration(self):
        """The guard keys on having a name, so a further base is still legal."""

        class _AbstractTier(CuringRecipe):
            cure_seconds = 0.0

        self.assertEqual(_AbstractTier.name, BlackoutRecipe.name)

    def test_every_recipe_is_worked_at_the_chamber(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(recipe_cls.tool_tags, [_CHAMBER_TOOL_TAG])

    def test_every_recipe_consumes_exactly_one_real_item(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(len(recipe_cls.consumable_tags), 1)
                self.assertIn(recipe_cls.consumable_tags[0], ITEM_DB)

    def test_every_input_name_matches_the_item_it_names(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                item_key = recipe_cls.consumable_tags[0]
                self.assertEqual(
                    recipe_cls.consumable_names[0], ITEM_DB[item_key].name
                )

    def test_every_recipe_produces_exactly_one_real_item(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(len(recipe_cls.output_item_keys), 1)
                self.assertIn(recipe_cls.output_item_keys[0], ITEM_DB)

    def test_each_output_is_produced_by_exactly_one_recipe(self):
        """The spreadsheet's note claims two Curing recipes share an output.

        The Outputs column says otherwise, and Gastronomy settles it: the
        sandwich consumes a cured chuck AND a cured fatless meat, so they have
        to be two different items. This asserts the reading the code took.
        """
        produced = [
            recipe_cls.output_item_keys[0] for _name, recipe_cls in self.recipes
        ]

        self.assertEqual(len(produced), len(set(produced)))

    def test_no_recipe_cures_a_thing_into_itself(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertNotIn(
                    recipe_cls.output_item_keys[0], recipe_cls.consumable_tags
                )

    def test_the_second_pass_recipes_consume_rendering_output(self):
        """Curing takes raw cuts AND rendered components.

        The skill-tree map's "second processing pass", and the thing that makes
        the two facilities worth standing near each other. Derived from what
        Rendering actually produces rather than from a list of names, so a
        renamed rendering output fails here.
        """
        rendered = {
            recipe_cls.output_item_keys[0]
            for _name, recipe_cls in RECIPE_REGISTRY.items()
            if recipe_cls.required_skill == skill_constants.RENDERING_SKILL_KEY
        }
        consumed = {
            recipe_cls.consumable_tags[0]
            for _name, recipe_cls in self.recipes
        }

        self.assertTrue(consumed & rendered)



class TestCuringSkill(unittest.TestCase):
    """The skill the recipes name."""

    def test_curing_is_registered(self):
        self.assertIn(skill_constants.CURING_SKILL_KEY, SKILL_REGISTRY)

    def test_curing_is_a_processing_skill(self):
        skill_cls = SKILL_REGISTRY[skill_constants.CURING_SKILL_KEY]

        self.assertEqual(skill_cls.category, "Processing")

    def test_curing_has_no_execute_body(self):
        """The timing lives in the handler, not in a skill body."""
        skill_cls = SKILL_REGISTRY[skill_constants.CURING_SKILL_KEY]

        self.assertIs(skill_cls.execute, BaseSkill.execute)



class TestCuringChamber(EvenniaTest):
    """The facility, built for real -- its tags and cmdsets are set in a hook."""

    def setUp(self):
        super().setUp()
        self.chamber = CuringChamberFacility.create(
            "Curing Chamber", location=self.room1
        )[0]

    def test_the_chamber_carries_the_tool_tag_every_recipe_asks_for(self):
        tags = self.chamber.tags.get(
            category=TOOL_TAG_CATEGORY, return_list=True
        )

        self.assertIn(_CHAMBER_TOOL_TAG, tags)

    def test_the_chamber_offers_every_curing_recipe(self):
        found = crafting_service.get_recipes_for_facility(self.chamber)
        found_names = {name for name, _cls in found}

        expected = {name for name, _cls in _curing_recipes()}
        self.assertEqual(found_names, expected)

    def test_the_chamber_offers_nothing_from_another_skill(self):
        found = crafting_service.get_recipes_for_facility(self.chamber)
        categories = {recipe_cls.category for _name, recipe_cls in found}

        self.assertEqual(categories, {CATEGORY_CURING})

    def test_the_chamber_keeps_both_craft_and_collect(self):
        """A second cmdset must JOIN the default, not replace it.

        An object has exactly one default cmdset and CraftingFacility already
        spends it on `craft`. add_default again would swap `craft` out for
        `collect`, leaving a chamber nothing could be started at -- and the
        chamber would still look correct in every other test here.
        """
        command_keys = {
            command.key
            for cmdset in self.chamber.cmdset.all()
            for command in cmdset.commands
        }

        self.assertIn("craft", command_keys)
        self.assertIn("collect", command_keys)

    def test_the_chamber_cannot_be_picked_up(self):
        can_get = self.chamber.access(self.char1, "get")

        self.assertFalse(can_get)

    def test_the_chamber_affords_crafting_to_a_client(self):
        self.assertTrue(self.chamber.asset_key)
        self.assertTrue(self.chamber.asset_kind)
        self.assertEqual(self.chamber.interact_verb, "craft")

    def test_the_chamber_does_not_borrow_another_facilitys_asset_key(self):
        self.assertNotEqual(
            CuringChamberFacility.asset_key, FurnaceFacility.asset_key
        )



class TestTheCraftMenuRespectsSlots(EvenniaTest):
    """The generic readers the craft menu drives, on a deferred recipe.

    get_max_craftable caps "craft all" and check_craftable is what craft_batch
    re-asks between items. Both had to learn about capacity: a batch that
    sailed past a full chamber would report items crafted that were silently
    dropped on the floor of the handler.
    """

    def setUp(self):
        super().setUp()
        self.chamber = CuringChamberFacility.create(
            "Curing Chamber", location=self.char1.location
        )[0]

    def _give_chucks(self, count):
        for _ in range(count):
            ITEM_DB["mutant_raider_raw_chuck"].create(location=self.char1)

    def test_craft_all_is_capped_by_free_slots_not_by_materials(self):
        """Five chucks, one slot. The cap is one."""
        self._give_chucks(5)

        most = crafting_service.get_max_craftable(self.char1, _CHUCK_RECIPE)

        self.assertEqual(most, 1)

    def test_craft_all_rises_with_a_second_slot(self):
        second_threshold = curing_constants.CURING_SLOT_LEVELS[1]
        self.char1.skills.set_level(
            skill_constants.CURING_SKILL_KEY, second_threshold
        )
        self._give_chucks(5)

        most = crafting_service.get_max_craftable(self.char1, _CHUCK_RECIPE)

        self.assertEqual(most, 2)

    def test_a_full_chamber_caps_at_zero(self):
        self._give_chucks(2)
        crafting_service.perform_craft(self.char1, _CHUCK_RECIPE)

        most = crafting_service.get_max_craftable(self.char1, _CHUCK_RECIPE)

        self.assertEqual(most, 0)

    def test_a_full_chamber_is_reported_as_a_reason(self):
        """The batch loop halts on this, so it has to say something true."""
        self._give_chucks(2)
        crafting_service.perform_craft(self.char1, _CHUCK_RECIPE)

        can_craft, reasons = crafting_service.check_craftable(
            self.char1, _CHUCK_RECIPE
        )

        self.assertFalse(can_craft)
        self.assertTrue(any("slot" in reason.lower() for reason in reasons))

    def test_an_empty_chamber_is_craftable(self):
        self._give_chucks(1)

        can_craft, reasons = crafting_service.check_craftable(
            self.char1, _CHUCK_RECIPE
        )

        self.assertTrue(can_craft, msg=str(reasons))

    def test_an_immediate_recipe_is_uncapped_by_curing(self):
        """_deferred_capacity must distinguish None from 0.

        Returning 0 for a recipe with no handler would make every craft in the
        game impossible, and the furnace is the cheapest proof it does not.
        """
        furnace = FurnaceFacility.create(
            "Furnace", location=self.char1.location
        )[0]
        ITEM_DB["rusty_metal_chunk"].create(location=self.char1)

        most = crafting_service.get_max_craftable(
            self.char1, "rusty scrap metal"
        )

        self.assertGreaterEqual(most, 1)
        self.assertTrue(furnace)
