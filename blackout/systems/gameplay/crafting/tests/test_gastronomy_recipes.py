"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for the Gastronomy stage -- the end of the food chain, and
             the first recipes in the game taking two DIFFERENT inputs.

             That is what most of this file is about. consumable_tags has always
             been a list of UNITS, so the battleaxe's three entries naming one
             tag and a steak's two entries naming two tags are the same
             mechanism; nothing in BlackoutRecipe changed to allow it. Which is
             exactly why it needs testing: a feature that arrives by costing
             nothing has nothing proving it works.

             The chain is also asserted end to end here, because Gastronomy is
             the first stage that can be: a steak's inputs are Rendering
             outputs, and a sandwich's are Curing outputs, so the three stages
             either line up or they do not.

Run with:
    evennia test --settings test_settings.py systems.gameplay.crafting
"""



import unittest

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.crafting import crafting_service
from systems.gameplay.crafting.constants import (
    CRAFT_CATEGORY_CURING,
    CRAFT_CATEGORY_GASTRONOMY,
    CRAFT_CATEGORY_RENDERING,
    TOOL_TAG_CATEGORY,
)
from systems.gameplay.crafting.registry import RECIPE_REGISTRY
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill
from typeclasses.skill_facilities import (
    FurnaceFacility,
    GastroWorktableFacility,
)
from world.item_database import ITEM_DB



# Private constant definitions

_WORKTABLE_TOOL_TAG = "gastro_worktable"

_STEAK_RECIPE = "mutant raider steak"
_SANDWICH_RECIPE = "mutant raider cured meat sandwich"



def _recipes_in(category):
    """Every registered recipe in one category, read off the registry."""
    matches = [
        (name, recipe_cls)
        for name, recipe_cls in RECIPE_REGISTRY.items()
        if recipe_cls.category == category
    ]

    return matches



def _outputs_of(category):
    """The item keys one category produces."""
    keys = {
        recipe_cls.output_item_keys[0]
        for _name, recipe_cls in _recipes_in(category)
    }

    return keys



class TestGastronomyRecipeShape(unittest.TestCase):
    """What every Gastronomy recipe must be true of."""

    def setUp(self):
        self.recipes = _recipes_in(CRAFT_CATEGORY_GASTRONOMY)

    def test_the_category_is_populated(self):
        self.assertTrue(
            self.recipes,
            "no recipes registered in the Gastronomy category -- check "
            "settings.CRAFT_RECIPE_MODULES",
        )

    def test_every_recipe_teaches_gastronomy(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(
                    recipe_cls.required_skill,
                    skill_constants.SKILL_KEY_GASTRONOMY,
                )

    def test_every_recipe_is_worked_at_the_worktable(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(recipe_cls.tool_tags, [_WORKTABLE_TOOL_TAG])

    def test_no_meal_is_deferred(self):
        """A meal is finished when it is ordered.

        Curing is the only timed stage, and a Gastronomy recipe that picked up
        a deferred_handler would stop producing anything while the craft menu
        looked unchanged.
        """
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertIsNone(recipe_cls.deferred_handler)

    def test_every_recipe_produces_exactly_one_real_item(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(len(recipe_cls.output_item_keys), 1)
                self.assertIn(recipe_cls.output_item_keys[0], ITEM_DB)

    def test_each_meal_is_produced_by_exactly_one_recipe(self):
        produced = [
            recipe_cls.output_item_keys[0] for _name, recipe_cls in self.recipes
        ]

        self.assertEqual(len(produced), len(set(produced)))

    def test_nothing_consumes_a_meal(self):
        """Gastronomy is the END of the chain.

        A meal that fed another recipe would mean the chain has another stage
        nobody wrote, and the "eat to heal" promise would have competition for
        the item.
        """
        meals = _outputs_of(CRAFT_CATEGORY_GASTRONOMY)
        consumed_anywhere = {
            tag
            for _name, recipe_cls in RECIPE_REGISTRY.items()
            for tag in recipe_cls.consumable_tags
        }

        self.assertEqual(meals & consumed_anywhere, set())



class TestTwoDifferentInputs(unittest.TestCase):
    """The shape this stage introduces.

    Asserted as a property of the category rather than of four named recipes:
    the claim is that a Gastronomy recipe combines things, and a fifth one that
    took a single input would be a different kind of recipe in the wrong
    category.
    """

    def setUp(self):
        self.recipes = _recipes_in(CRAFT_CATEGORY_GASTRONOMY)

    def test_every_meal_combines_two_distinct_ingredients(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                tags = recipe_cls.consumable_tags
                self.assertEqual(len(tags), 2)
                self.assertEqual(len(set(tags)), 2)

    def test_every_ingredient_is_a_real_item(self):
        for name, recipe_cls in self.recipes:
            for tag in recipe_cls.consumable_tags:
                with self.subTest(recipe=name, ingredient=tag):
                    self.assertIn(tag, ITEM_DB)

    def test_every_ingredient_is_named_for_the_player(self):
        """consumable_names is read positionally against consumable_tags.

        A list one short does not raise -- get_material_summary and the
        missing-material message index into it, so the player is told to find
        an item by whatever name happens to sit at that position.
        """
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(
                    len(recipe_cls.consumable_names),
                    len(recipe_cls.consumable_tags),
                )

    def test_each_ingredient_name_matches_the_item_at_its_position(self):
        """The positional pairing, checked pair by pair.

        Two inputs is the first time these lists can be misaligned rather than
        merely wrong -- a swapped pair names two real items in two wrong places
        and reads perfectly well.
        """
        for name, recipe_cls in self.recipes:
            pairs = zip(recipe_cls.consumable_tags, recipe_cls.consumable_names)
            for item_key, shown_name in pairs:
                with self.subTest(recipe=name, ingredient=item_key):
                    self.assertEqual(shown_name, ITEM_DB[item_key].name)

    def test_no_meal_consumes_its_own_output(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertNotIn(
                    recipe_cls.output_item_keys[0], recipe_cls.consumable_tags
                )



class TestTheChainLinesUp(unittest.TestCase):
    """Gastronomy is the first stage that can assert the whole chain.

    Derived from what the earlier stages actually produce, never from a list of
    names, so a renamed output anywhere upstream fails here rather than leaving
    a recipe nobody can fill.
    """

    def test_every_ingredient_is_made_by_an_earlier_stage(self):
        upstream = _outputs_of(CRAFT_CATEGORY_RENDERING) | _outputs_of(CRAFT_CATEGORY_CURING)

        for name, recipe_cls in _recipes_in(CRAFT_CATEGORY_GASTRONOMY):
            for tag in recipe_cls.consumable_tags:
                with self.subTest(recipe=name, ingredient=tag):
                    self.assertIn(tag, upstream)

    def test_the_steak_is_built_from_rendering_output(self):
        recipe_cls = RECIPE_REGISTRY[_STEAK_RECIPE]
        rendered = _outputs_of(CRAFT_CATEGORY_RENDERING)

        self.assertTrue(set(recipe_cls.consumable_tags) <= rendered)

    def test_the_sandwich_is_built_from_curing_output(self):
        """The sheet's whole point about the sandwich.

        It heals more than cured meat eaten raw because BOTH halves are cured
        -- if either half were a raw or merely rendered cut, the claim would be
        about a different recipe.
        """
        recipe_cls = RECIPE_REGISTRY[_SANDWICH_RECIPE]
        cured = _outputs_of(CRAFT_CATEGORY_CURING)

        self.assertTrue(set(recipe_cls.consumable_tags) <= cured)

    def test_every_rendering_and_curing_output_is_eventually_used(self):
        """No dead ends in the food chain.

        The metal chain has two documented dead ends (the dusts), and the
        spreadsheet flags both. The food chain is supposed to have none: every
        tallow and every cured cut feeds a meal. A new Rendering output with no
        consumer fails here, which is the reminder to either give it one or cut
        it.
        """
        produced = _outputs_of(CRAFT_CATEGORY_RENDERING) | _outputs_of(CRAFT_CATEGORY_CURING)
        consumed = {
            tag
            for _name, recipe_cls in RECIPE_REGISTRY.items()
            for tag in recipe_cls.consumable_tags
        }

        orphans = sorted(produced - consumed)
        self.assertEqual(orphans, [], f"food-chain dead ends: {orphans}")



class TestGastronomySpreadsheetRows(unittest.TestCase):
    """Every recipe in the spreadsheet exists in the game.

    Level requirements and XP rewards are balance values, so no test asserts
    them.
    """

    # Recipe names from the Recipes tab.
    EXPECTED = (
        "mutant raider steak",
        "mutant raider cured meat sandwich",
        "mutant raider prime steak",
        "mutant raider prime cured meat sandwich",
    )

    def test_the_spreadsheet_rows_are_all_registered(self):
        for recipe_name in self.EXPECTED:
            with self.subTest(recipe=recipe_name):
                self.assertIn(recipe_name, RECIPE_REGISTRY)



class TestGastronomySkill(unittest.TestCase):
    """The skill the recipes name."""

    def test_gastronomy_is_registered(self):
        self.assertIn(skill_constants.SKILL_KEY_GASTRONOMY, SKILL_REGISTRY)

    def test_gastronomy_is_a_production_skill(self):
        skill_cls = SKILL_REGISTRY[skill_constants.SKILL_KEY_GASTRONOMY]

        self.assertEqual(skill_cls.category, skill_constants.SKILL_CATEGORY_PRODUCTION)

    def test_gastronomy_has_no_execute_body(self):
        skill_cls = SKILL_REGISTRY[skill_constants.SKILL_KEY_GASTRONOMY]

        self.assertIs(skill_cls.execute, BaseSkill.execute)



class TestGastroWorktable(EvenniaTest):
    """The facility, built for real -- its tag is set in a hook."""

    def setUp(self):
        super().setUp()
        self.worktable = GastroWorktableFacility.create(
            "Gastronomy Worktable", location=self.room1
        )[0]

    def test_the_worktable_carries_the_tool_tag_every_recipe_asks_for(self):
        tags = self.worktable.tags.get(
            category=TOOL_TAG_CATEGORY, return_list=True
        )

        self.assertIn(_WORKTABLE_TOOL_TAG, tags)

    def test_the_worktable_offers_every_gastronomy_recipe(self):
        found = crafting_service.get_recipes_for_facility(self.worktable)
        found_names = {name for name, _cls in found}

        expected = {name for name, _cls in _recipes_in(CRAFT_CATEGORY_GASTRONOMY)}
        self.assertEqual(found_names, expected)

    def test_the_worktable_offers_nothing_from_another_skill(self):
        found = crafting_service.get_recipes_for_facility(self.worktable)
        categories = {recipe_cls.category for _name, recipe_cls in found}

        self.assertEqual(categories, {CRAFT_CATEGORY_GASTRONOMY})

    def test_the_worktable_has_no_collect_verb(self):
        """Only the curing chamber has a second cmdset.

        A worktable offering `collect` would invite the player to come back for
        a meal that was handed to them immediately.
        """
        command_keys = {
            command.key
            for cmdset in self.worktable.cmdset.all()
            for command in cmdset.commands
        }

        self.assertIn("craft", command_keys)
        self.assertNotIn("collect", command_keys)

    def test_the_worktable_cannot_be_picked_up(self):
        can_get = self.worktable.access(self.char1, "get")

        self.assertFalse(can_get)

    def test_the_worktable_affords_crafting_to_a_client(self):
        self.assertTrue(self.worktable.asset_key)
        self.assertTrue(self.worktable.asset_kind)
        self.assertEqual(self.worktable.interact_verb, "craft")

    def test_the_worktable_does_not_borrow_another_facilitys_asset_key(self):
        self.assertNotEqual(
            GastroWorktableFacility.asset_key, FurnaceFacility.asset_key
        )



class TestCookingAMeal(EvenniaTest):
    """A meal cooked all the way through, two ingredients in and one out.

    Everything above reads declarations. The multi-input consumption path is
    the one thing here that could be declared perfectly and still not work:
    _validate_consumables matches one object per entry, and two entries naming
    two tags is a case no shipped recipe had ever exercised.
    """

    recipe_key = _STEAK_RECIPE

    def setUp(self):
        super().setUp()
        self.worktable = GastroWorktableFacility.create(
            "Gastronomy Worktable", location=self.char1.location
        )[0]

    def _give(self, item_key, quantity=1):
        return ITEM_DB[item_key].create(location=self.char1, quantity=quantity)

    def _give_both_ingredients(self):
        self._give("mutant_raider_tallow")
        self._give("mutant_raider_fatless_meat")

    def _carried_named(self, item_name):
        return [obj for obj in self.char1.contents if obj.db_key == item_name]

    def test_two_ingredients_cook_into_one_meal(self):
        self._give_both_ingredients()

        result = crafting_service.perform_craft(self.char1, self.recipe_key)

        self.assertTrue(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0].db_key, ITEM_DB["mutant_raider_steak"].name
        )

    def test_both_ingredients_are_consumed(self):
        self._give_both_ingredients()

        crafting_service.perform_craft(self.char1, self.recipe_key)

        self.assertEqual(
            self._carried_named(ITEM_DB["mutant_raider_tallow"].name), []
        )
        self.assertEqual(
            self._carried_named(ITEM_DB["mutant_raider_fatless_meat"].name), []
        )

    def test_having_only_one_ingredient_cooks_nothing(self):
        """And must not eat the half the player does have."""
        self._give("mutant_raider_tallow")
        tallow_name = ITEM_DB["mutant_raider_tallow"].name

        result = crafting_service.perform_craft(self.char1, self.recipe_key)

        self.assertFalse(result)
        self.assertEqual(len(self._carried_named(tallow_name)), 1)

    def test_having_only_the_other_ingredient_cooks_nothing(self):
        """The mirror case, because the two halves are matched by separate
        entries and a loop that stopped early would pass the first test."""
        self._give("mutant_raider_fatless_meat")
        meat_name = ITEM_DB["mutant_raider_fatless_meat"].name

        result = crafting_service.perform_craft(self.char1, self.recipe_key)

        self.assertFalse(result)
        self.assertEqual(len(self._carried_named(meat_name)), 1)

    def test_two_tallow_and_no_meat_cooks_nothing(self):
        """A doubled ingredient must not satisfy the other entry.

        The sharpest multi-input failure: _validate_consumables walks entries
        and matches an object per entry, so a stackable carrying enough units
        could in principle answer both. Tallow stacks, which makes this
        reachable rather than theoretical.
        """
        self._give("mutant_raider_tallow", quantity=2)

        result = crafting_service.perform_craft(self.char1, self.recipe_key)

        self.assertFalse(result)

    def test_cooking_awards_gastronomy_xp(self):
        recipe_cls = RECIPE_REGISTRY[self.recipe_key]
        before, needed, _rest = self.char1.skills.get_xp_level(
            skill_constants.SKILL_KEY_GASTRONOMY
        )
        self.assertLess(
            before + recipe_cls.xp_reward,
            needed,
            "one meal now levels Gastronomy; this test can no longer read the "
            "award off per-level progress",
        )
        self._give_both_ingredients()

        crafting_service.perform_craft(self.char1, self.recipe_key)

        after, _needed, _rest = self.char1.skills.get_xp_level(
            skill_constants.SKILL_KEY_GASTRONOMY
        )
        self.assertEqual(after - before, recipe_cls.xp_reward)

    def test_the_meal_occupies_an_inventory_slot(self):
        self._give_both_ingredients()

        result = crafting_service.perform_craft(self.char1, self.recipe_key)

        slot = self.char1.inventory.find_slot(result[0])
        self.assertGreaterEqual(slot, 0)

    def test_nothing_cooks_without_a_worktable_in_reach(self):
        self._give_both_ingredients()
        self.worktable.location = self.room2

        result = crafting_service.perform_craft(self.char1, self.recipe_key)

        self.assertFalse(result)

    def test_craft_all_counts_whole_meals_not_ingredients(self):
        """Three tallow and two meat is two steaks, not five and not three.

        get_max_craftable takes the minimum across ingredients. With one input
        that minimum is trivially the only count; two inputs is the first time
        the word "minimum" does any work.
        """
        self._give("mutant_raider_tallow", quantity=3)
        for _ in range(2):
            self._give("mutant_raider_fatless_meat")

        most = crafting_service.get_max_craftable(self.char1, self.recipe_key)

        self.assertEqual(most, 2)

    def test_a_level_gated_meal_is_refused_and_costs_nothing(self):
        """One level below the sandwich's requirement is refused."""
        required = RECIPE_REGISTRY[_SANDWICH_RECIPE].required_level
        if required <= skill_constants.MIN_BASE_SKILL_LEVEL:
            self.skipTest("the sandwich has no level gate to refuse")
        self.char1.skills.set_level(
            skill_constants.SKILL_KEY_GASTRONOMY, required - 1
        )
        self._give("mutant_raider_cured_chuck")
        self._give("mutant_raider_cured_fatless_meat")

        result = crafting_service.perform_craft(self.char1, _SANDWICH_RECIPE)

        self.assertFalse(result)
        self.assertEqual(
            len(self._carried_named(ITEM_DB["mutant_raider_cured_chuck"].name)),
            1,
        )

    def test_the_sandwich_cooks_once_the_level_is_met(self):
        required = RECIPE_REGISTRY[_SANDWICH_RECIPE].required_level
        self.char1.skills.set_level(
            skill_constants.SKILL_KEY_GASTRONOMY, required
        )
        self._give("mutant_raider_cured_chuck")
        self._give("mutant_raider_cured_fatless_meat")

        result = crafting_service.perform_craft(self.char1, _SANDWICH_RECIPE)

        self.assertTrue(result)
        self.assertEqual(
            result[0].db_key,
            ITEM_DB["mutant_raider_cured_meat_sandwich"].name,
        )
