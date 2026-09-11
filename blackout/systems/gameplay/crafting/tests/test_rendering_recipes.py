"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for the Rendering stage of the food chain -- the four
             recipes that turn a Butchery cut into tallow or lean meat, and
             the cooker facility that gates them.

             Nothing here asserts a census of the four. What it asserts is the
             RELATIONSHIPS the spreadsheet describes, derived from the recipe
             classes themselves: every Rendering recipe consumes a cut that
             Butchery actually yields, produces an item that exists, is worked
             at the cooker and nowhere else, and is reachable from the cooker's
             craft menu. A fifth recipe added to the module is covered by all
             of them on the next run.

             The one number taken literally is the level ladder, because the
             off-by-two between a tier's tallow and its meat is a DESIGN
             decision from the spreadsheet rather than a consequence of
             anything in the code, so nothing but a test can notice it
             changing.

Run with:
    evennia test --settings test_settings.py systems.gameplay.crafting
"""



import unittest

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.crafting import crafting_service
from systems.gameplay.crafting.constants import (
    CATEGORY_RENDERING,
    TOOL_TAG_CATEGORY,
)
from systems.gameplay.crafting.registry import RECIPE_REGISTRY
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.gatherables import GATHERABLE_REGISTRY
from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill
from typeclasses.skill_facilities import RenderingCookerFacility
from world.item_database import ITEM_DB



# Private constant definitions

# The tool tag the cooker stamps on itself and every Rendering recipe asks
# for. Spelled once here so a test that renames it fails in one place.
_COOKER_TOOL_TAG = "rendering_cooker"



def _rendering_recipes():
    """
    Purpose: Every registered recipe in the Rendering category.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a list of (recipe name, recipe class) pairs.

    Module Globals:
        RECIPE_REGISTRY read.

    Methodology:
        Read off the registry by category rather than imported by name from
        the recipe module, so a recipe that fails to register is a FAILING
        test rather than an invisible one -- importing the classes directly
        would test the module and say nothing about discovery.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    matches = [
        (name, recipe_cls)
        for name, recipe_cls in RECIPE_REGISTRY.items()
        if recipe_cls.category == CATEGORY_RENDERING
    ]

    return matches



def _butchery_yield_keys():
    """
    Purpose: Every item key Butchery can produce from any node.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a set of item key strings.

    Module Globals:
        GATHERABLE_REGISTRY read.

    Methodology:
        Walks the gatherable registry rather than naming the two cuts, because
        the claim under test is that Rendering consumes what Butchery makes --
        naming the cuts would restate the answer in the question and would not
        notice a third cut arriving with no recipe behind it.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    keys = {
        entry.item_key
        for gatherable_def in GATHERABLE_REGISTRY.values()
        for entry in gatherable_def.yields
        if entry.skill_key == skill_constants.BUTCHERY_SKILL_KEY
    }

    return keys



class TestRenderingSkillExists(unittest.TestCase):
    """The skill the recipes name has to be a real, discovered skill."""

    def test_rendering_is_registered(self):
        self.assertIn(skill_constants.RENDERING_SKILL_KEY, SKILL_REGISTRY)

    def test_rendering_is_a_processing_skill(self):
        skill_cls = SKILL_REGISTRY[skill_constants.RENDERING_SKILL_KEY]

        self.assertEqual(skill_cls.category, "Processing")

    def test_rendering_has_no_execute_body(self):
        """A processing skill's behaviour is its recipes.

        Foundry's shape, and the design doc is explicit that an `execute()`
        appearing below Butchery is a signal the design has drifted rather
        than a feature. Asserted by identity against BaseSkill so an override
        is caught even if it happens to do nothing.
        """
        skill_cls = SKILL_REGISTRY[skill_constants.RENDERING_SKILL_KEY]

        self.assertIs(skill_cls.execute, BaseSkill.execute)



class TestRenderingRecipeShape(unittest.TestCase):
    """What every Rendering recipe must be true of, whatever it makes."""

    def setUp(self):
        self.recipes = _rendering_recipes()

    def test_the_category_is_populated(self):
        self.assertTrue(
            self.recipes,
            "no recipes registered in the Rendering category -- check "
            "settings.CRAFT_RECIPE_MODULES",
        )

    def test_every_recipe_teaches_rendering(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(
                    recipe_cls.required_skill,
                    skill_constants.RENDERING_SKILL_KEY,
                )
                self.assertGreater(recipe_cls.xp_reward, 0)

    def test_every_recipe_is_worked_at_the_cooker(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(recipe_cls.tool_tags, [_COOKER_TOOL_TAG])

    def test_every_recipe_names_its_tool_for_the_player(self):
        """tool_names is what the error message says is missing.

        An empty list falls back to the TAG capitalised -- the player is told
        they need a "Rendering_cooker", which is not a thing in the world.
        """
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(
                    len(recipe_cls.tool_names), len(recipe_cls.tool_tags)
                )
                self.assertTrue(all(recipe_cls.tool_names))

    def test_every_recipe_consumes_exactly_one_butchery_cut(self):
        """Rendering is a one-in one-out stage.

        The multi-input recipes are Gastronomy's, and the distinction is load
        bearing: a rendering recipe that quietly took two cuts would make the
        tallow-or-meat choice free.
        """
        cut_keys = _butchery_yield_keys()

        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(len(recipe_cls.consumable_tags), 1)
                self.assertIn(recipe_cls.consumable_tags[0], cut_keys)

    def test_every_recipe_names_its_input_for_the_player(self):
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertEqual(
                    len(recipe_cls.consumable_names),
                    len(recipe_cls.consumable_tags),
                )
                self.assertTrue(all(recipe_cls.consumable_names))

    def test_every_input_name_matches_the_item_it_names(self):
        """consumable_names is prose the player reads; the tag is the fact.

        They are separate fields and nothing makes them agree, so a cut
        renamed in ITEM_DB leaves the recipe telling the player to find an
        item by a name no longer in the game.
        """
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

    def test_no_recipe_renders_a_cut_into_itself(self):
        """A recipe whose output is its input is an infinite XP loop."""
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                self.assertNotIn(
                    recipe_cls.output_item_keys[0], recipe_cls.consumable_tags
                )

    def test_every_output_is_a_crafting_material(self):
        """Rendering makes INGREDIENTS, not food.

        The spreadsheet's "eat to heal HP" column is empty for every Rendering
        row: food starts at Curing. What this pins is that the outputs are
        tagged as materials downstream recipes can find, which is the only
        thing that makes them reachable at all.
        """
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                item_def = ITEM_DB[recipe_cls.output_item_keys[0]]
                categories = [category for _value, category in item_def.tags]
                self.assertIn("crafting_material", categories)

    def test_every_output_is_tagged_under_its_own_key(self):
        """A downstream recipe finds an input by tag VALUE.

        Gastronomy's steak asks for `mutant_raider_tallow`; if the tallow is
        tagged as anything else the recipe is unfillable with the item sitting
        in the bag. The same contract materials.py has followed since the
        metal chain.
        """
        for name, recipe_cls in self.recipes:
            with self.subTest(recipe=name):
                item_key = recipe_cls.output_item_keys[0]
                item_def = ITEM_DB[item_key]
                values = [value for value, _category in item_def.tags]
                self.assertIn(item_key, values)

    def test_each_output_is_produced_by_exactly_one_recipe(self):
        """Two recipes sharing an output would be two routes to one item.

        The spreadsheet does have such a pair -- the two Curing recipes that
        both make a cured chuck -- and says so in a note. Rendering has none,
        so a duplicate here is a copy-paste rather than a design.
        """
        produced = [
            recipe_cls.output_item_keys[0] for _name, recipe_cls in self.recipes
        ]

        self.assertEqual(len(produced), len(set(produced)))



class TestRenderingLevelLadder(unittest.TestCase):
    """The spreadsheet's level and XP gates, which only a test can hold.

    A literal table, unlike everything above it. These numbers are not derived
    from anything -- they are Nick's answer to "what should the curve feel
    like" -- so there is no source of truth to assert against except the sheet
    itself, transcribed here.
    """

    # recipe name -> (required_level, xp_reward), from the Recipes tab of
    # `Blackout - Crafting Recipes (3-tab restructure)`.
    EXPECTED = {
        "mutant raider tallow": (0, 10),
        "mutant raider fatless meat": (2, 15),
        "mutant raider prime tallow": (10, 20),
        "mutant raider prime meat": (12, 30),
    }

    def test_the_spreadsheet_rows_are_all_registered(self):
        """One direction only: every row in the sheet exists in the game.

        Not the reverse -- a fifth Rendering recipe is content being added as
        intended, and a test that failed on it would be the census CLAUDE.md
        warns about.
        """
        for recipe_name in self.EXPECTED:
            with self.subTest(recipe=recipe_name):
                self.assertIn(recipe_name, RECIPE_REGISTRY)

    def test_each_row_carries_the_level_and_xp_from_the_sheet(self):
        for recipe_name, (level, xp) in self.EXPECTED.items():
            recipe_cls = RECIPE_REGISTRY[recipe_name]
            with self.subTest(recipe=recipe_name):
                self.assertEqual(recipe_cls.required_level, level)
                self.assertEqual(recipe_cls.xp_reward, xp)

    def test_the_meat_of_a_tier_gates_above_its_tallow(self):
        """The +2 is the shape of the stage, stated as a relationship.

        Tallow is what Rendering is learned on and the lean cut is the reward
        for staying with it. Asserted per tier so flattening the curve fails
        here with a message about the design rather than about two integers.
        """
        tiers = (
            ("mutant raider tallow", "mutant raider fatless meat"),
            ("mutant raider prime tallow", "mutant raider prime meat"),
        )

        for tallow_name, meat_name in tiers:
            with self.subTest(tier=tallow_name):
                tallow = RECIPE_REGISTRY[tallow_name]
                meat = RECIPE_REGISTRY[meat_name]
                self.assertGreater(
                    meat.required_level, tallow.required_level
                )
                self.assertGreater(meat.xp_reward, tallow.xp_reward)

    def test_the_prime_tier_gates_above_the_chuck_tier(self):
        """A filet product must never be cheaper than a chuck product.

        The filet itself needs Butchery 10; a prime render reachable at
        Rendering 2 would be a tier the player could see and not use.
        """
        chuck_ceiling = max(
            RECIPE_REGISTRY[name].required_level
            for name in ("mutant raider tallow", "mutant raider fatless meat")
        )
        prime_floor = min(
            RECIPE_REGISTRY[name].required_level
            for name in (
                "mutant raider prime tallow",
                "mutant raider prime meat",
            )
        )

        self.assertGreater(prime_floor, chuck_ceiling)



class TestRenderingCookerFacility(EvenniaTest):
    """The facility, built for real, because its tags are set in a hook.

    RenderingCookerFacility's tag is added in at_object_creation, so nothing
    short of creating one proves the recipes can find it. EvenniaTest rather
    than EvenniaTestCase because spawning an object needs a room to put it in.
    """

    def setUp(self):
        super().setUp()
        self.cooker = RenderingCookerFacility.create(
            "Rendering Cooker", location=self.room1
        )[0]

    def test_the_cooker_carries_the_tool_tag_every_recipe_asks_for(self):
        tags = self.cooker.tags.get(
            category=TOOL_TAG_CATEGORY, return_list=True
        )

        self.assertIn(_COOKER_TOOL_TAG, tags)

    def test_the_cooker_offers_every_rendering_recipe(self):
        found = crafting_service.get_recipes_for_facility(self.cooker)
        found_names = {name for name, _cls in found}

        expected = {name for name, _cls in _rendering_recipes()}
        self.assertEqual(found_names, expected)

    def test_the_cooker_offers_nothing_from_another_skill(self):
        """allowed_categories is the whole restriction.

        A cooker listing the furnace's recipes would let a player smelt metal
        in a fat vat, and the reason it cannot is one list on the class -- so
        that list is what is checked, through the service the menu uses.
        """
        found = crafting_service.get_recipes_for_facility(self.cooker)
        categories = {recipe_cls.category for _name, recipe_cls in found}

        self.assertEqual(categories, {CATEGORY_RENDERING})

    def test_the_cooker_cannot_be_picked_up(self):
        """A facility is furniture. The superuser test account walked off with
        the furnace once; the get:false() lock is what stopped it."""
        can_get = self.cooker.access(self.char1, "get")

        self.assertFalse(can_get)

    def test_the_cooker_affords_crafting_to_a_client(self):
        """The statefeed reads these off the class through getattr.

        Without them a graphical client cannot tell a facility from a dropped
        item and offers to pick it up -- which is what happened to the furnace
        before ASSET_KIND_STATION existed.
        """
        self.assertTrue(self.cooker.asset_key)
        self.assertTrue(self.cooker.asset_kind)
        self.assertEqual(self.cooker.interact_verb, "craft")

    def test_the_cooker_does_not_borrow_the_furnace_asset_key(self):
        """Neither has art today and both draw the procedural station mesh,
        so sharing a key costs nothing until the day one is packed -- at
        which point the furnace silently becomes a cooker."""
        from typeclasses.skill_facilities import FurnaceFacility

        self.assertNotEqual(
            RenderingCookerFacility.asset_key, FurnaceFacility.asset_key
        )



class TestRenderingACut(EvenniaTest):
    """A render driven all the way through, cut in and tallow out.

    Everything above reads declarations. This drives the stage the way a
    player does -- stand at the cooker holding a chuck and craft -- because
    the declarations can all be right while the stage is unreachable: a tool
    the service does not find in the ROOM, a cut the consumable matcher does
    not see in the bag, a level gate reading a skill nobody has.
    """

    tallow_recipe = "mutant raider tallow"
    fatless_recipe = "mutant raider fatless meat"

    def setUp(self):
        super().setUp()
        self.cooker = RenderingCookerFacility.create(
            "Rendering Cooker", location=self.char1.location
        )[0]

    def _give_chuck(self):
        """Put one raw chuck in the crafter's hands, the way Butchery would."""
        return ITEM_DB["mutant_raider_raw_chuck"].create(location=self.char1)

    def _carried_keys(self):
        """The item keys the crafter is holding, for before/after comparison."""
        return [obj.db_key for obj in self.char1.contents]

    def test_a_chuck_renders_into_tallow(self):
        self._give_chuck()

        result = crafting_service.perform_craft(self.char1, self.tallow_recipe)

        self.assertTrue(result)
        self.assertEqual(
            result[0].db_key, ITEM_DB["mutant_raider_tallow"].name
        )

    def test_the_chuck_is_consumed(self):
        self._give_chuck()
        chuck_name = ITEM_DB["mutant_raider_raw_chuck"].name

        crafting_service.perform_craft(self.char1, self.tallow_recipe)

        self.assertNotIn(chuck_name, self._carried_keys())

    def test_a_render_awards_rendering_xp(self):
        """Compared against progress INTO the level, which is what is stored.

        The handler keeps XP per level and zeroes it on a level-up, so this
        reading only holds while one render cannot clear level 0 -- 10 XP
        against the 75 the curve asks for. That is asserted rather than
        assumed, so if the curve is ever retuned this fails with the reason
        instead of quietly comparing 10 to 0.
        """
        expected = RECIPE_REGISTRY[self.tallow_recipe].xp_reward
        before, needed, _remaining = self.char1.skills.get_xp_level(
            skill_constants.RENDERING_SKILL_KEY
        )
        self.assertLess(
            before + expected,
            needed,
            "one render now levels Rendering; this test can no longer read "
            "the award off per-level progress",
        )
        self._give_chuck()

        crafting_service.perform_craft(self.char1, self.tallow_recipe)

        after, _needed, _remaining = self.char1.skills.get_xp_level(
            skill_constants.RENDERING_SKILL_KEY
        )
        self.assertEqual(after - before, expected)

    def test_nothing_renders_without_a_cooker_in_reach(self):
        """The cooker is furniture, so the tool check is a ROOM scan.

        Moved out rather than deleted: deleting it would also delete the
        character's room on some paths, and what is under test is the distance
        between player and facility, not the facility existing.
        """
        self._give_chuck()
        self.cooker.location = self.room2

        result = crafting_service.perform_craft(self.char1, self.tallow_recipe)

        self.assertFalse(result)

    def test_nothing_renders_without_a_cut(self):
        result = crafting_service.perform_craft(self.char1, self.tallow_recipe)

        self.assertFalse(result)

    def test_a_level_gated_render_is_refused_at_level_zero(self):
        """Fatless meat needs Rendering 2 and a fresh character has 0.

        The gate is BlackoutRecipe.pre_craft's skill check, and the thing
        worth pinning is that being refused costs the player nothing -- a gate
        that ate the chuck on the way to saying no would be worse than no gate.
        """
        self._give_chuck()
        chuck_name = ITEM_DB["mutant_raider_raw_chuck"].name

        result = crafting_service.perform_craft(self.char1, self.fatless_recipe)

        self.assertFalse(result)
        self.assertIn(chuck_name, self._carried_keys())

    def test_the_same_render_succeeds_once_the_level_is_met(self):
        """The other half of the gate, so a refusal that never lifts fails.

        set_level is the skills handler's own write path -- the same one a
        content migration or a moderator tool uses -- rather than an XP award
        sized to cross the boundary, which would be a second place the curve
        is encoded.
        """
        required = RECIPE_REGISTRY[self.fatless_recipe].required_level
        self.char1.skills.set_level(
            skill_constants.RENDERING_SKILL_KEY, required
        )
        self._give_chuck()

        result = crafting_service.perform_craft(self.char1, self.fatless_recipe)

        self.assertTrue(result)
        self.assertEqual(
            result[0].db_key, ITEM_DB["mutant_raider_fatless_meat"].name
        )

    def test_tallow_stacks_and_rendered_meat_does_not(self):
        """Two renders of the same thing, to prove the stack flag is live.

        Declared on the ItemDef and honoured by the inventory handler, not by
        anything in this chain -- which is exactly why it is worth one test:
        the decision that tallow stacks was a design answer, and nothing else
        in the repo would notice it being dropped.
        """
        required = RECIPE_REGISTRY[self.fatless_recipe].required_level
        self.char1.skills.set_level(
            skill_constants.RENDERING_SKILL_KEY, required
        )

        for recipe_key in (
            self.tallow_recipe,
            self.tallow_recipe,
            self.fatless_recipe,
            self.fatless_recipe,
        ):
            self._give_chuck()
            crafting_service.perform_craft(self.char1, recipe_key)

        tallow = self._carried_named(ITEM_DB["mutant_raider_tallow"].name)
        meat = self._carried_named(ITEM_DB["mutant_raider_fatless_meat"].name)

        self.assertEqual(len(tallow), 1)
        self.assertEqual(tallow[0].quantity, 2)
        self.assertEqual(len(meat), 2)

    def _carried_named(self, item_name):
        """Every carried object going by item_name, stacks unmerged."""
        return [obj for obj in self.char1.contents if obj.db_key == item_name]
