"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for eating -- the heal, the cap, and the two delays.

             Time is advanced, never waited on. The eat delay is a comparison
             against BlackoutTickEngine.current_tick(), so moving the engine's
             tick counter IS moving time as far as the mechanic is concerned --
             the same trick the curing tests play with a wall-clock deadline,
             and for the same reason: a 1.8-second delay should not cost a test
             1.8 seconds.

Run with:
    evennia test --settings test_settings.py systems.gameplay.consumables
"""



import unittest
from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.crafting.constants import (
    CATEGORY_CURING,
    CATEGORY_GASTRONOMY,
)
from systems.gameplay.consumables import constants as consumable_const
from systems.gameplay.consumables import service as consumables
from systems.interface.statefeed.constants import (
    ITEM_FAMILIES,
    ITEM_FAMILY_FOOD,
    ITEM_FAMILY_MATERIAL,
    ITEM_FAMILY_PRIORITY,
)
from world.item_database import ITEM_DB



# Private constant definitions

# The cheapest food, used wherever a test needs "some food".
_CHUCK = "mutant_raider_cured_chuck"

# The deepest one, for the cases where the waste has to hurt.
_PRIME_SANDWICH = "mutant_raider_prime_cured_meat_sandwich"



def _outputs_of_category(category):
    """The item keys one crafting category produces.

    Reads the recipe registry, so "is this a cured meat" is answered by the
    recipe that makes it rather than by how its key is spelled.
    """
    from systems.gameplay.crafting.registry import RECIPE_REGISTRY

    keys = {
        recipe_cls.output_item_keys[0]
        for recipe_cls in RECIPE_REGISTRY.values()
        if recipe_cls.category == category and recipe_cls.output_item_keys
    }

    return keys



def _food_keys():
    """Every ItemDef that declares a heal amount.

    Derived, so a food added to ITEM_DB is covered by every loop below without
    being named in this file.
    """
    keys = [
        key
        for key, item_def in ITEM_DB.items()
        if item_def.heal_amount is not None
    ]

    return keys



class TestTheFoodTable(unittest.TestCase):
    """What ITEM_DB says about food, asserted as relationships.

    No DB at all -- this is the data table, and plain unittest.TestCase is the
    cheapest base that can read it.
    """

    def test_some_food_exists(self):
        self.assertTrue(_food_keys())

    def test_every_food_heals_a_positive_amount(self):
        for key in _food_keys():
            with self.subTest(food=key):
                self.assertGreater(ITEM_DB[key].heal_amount, 0)

    def test_every_food_declares_the_food_family(self):
        """The tag is how a client draws it; heal_amount is how it is eaten.

        Both, on every food: a heal_amount with no tag renders as an anonymous
        lump, and a tag with no heal_amount renders as food and refuses to be
        eaten.
        """
        for key in _food_keys():
            item_def = ITEM_DB[key]
            categories = [category for _value, category in item_def.tags]
            with self.subTest(food=key):
                self.assertIn(ITEM_FAMILY_FOOD, categories)

    def test_every_food_is_still_a_crafting_material(self):
        """Dropping it would strand Gastronomy's recipes.

        The sandwich finds a cured chuck by the crafting_material tag, so food
        must belong to BOTH families -- which is the clearest case in the game
        of an item being more than one thing.
        """
        for key in _food_keys():
            item_def = ITEM_DB[key]
            categories = [category for _value, category in item_def.tags]
            with self.subTest(food=key):
                self.assertIn(ITEM_FAMILY_MATERIAL, categories)

    def test_food_outranks_material_in_the_family_priority(self):
        """Which mesh a two-family item falls back to.

        Behind material, every food in the game would render as the lump it was
        before food existed -- and nothing would error.
        """
        order = list(ITEM_FAMILY_PRIORITY)

        self.assertLess(
            order.index(ITEM_FAMILY_FOOD), order.index(ITEM_FAMILY_MATERIAL)
        )

    def test_the_family_is_in_the_membership_set(self):
        self.assertIn(ITEM_FAMILY_FOOD, ITEM_FAMILIES)

    def test_nothing_but_food_declares_a_heal_amount(self):
        """A sword with a heal_amount would be edible, and nothing would say so."""
        for key, item_def in ITEM_DB.items():
            if item_def.heal_amount is None:
                continue
            categories = [category for _value, category in item_def.tags]
            with self.subTest(item=key):
                self.assertIn(ITEM_FAMILY_FOOD, categories)

    def test_the_cured_meats_swing_sooner_than_the_cooked_meals(self):
        """The Cooked karambwan property, as a relationship.

        Which foods are "cured meats" is asked of the RECIPE REGISTRY, not of
        the item key. The first version of this test matched on the
        `mutant_raider_cured_` prefix and failed on the cured meat SANDWICH,
        which is a Gastronomy meal whose name happens to start that way -- the
        exact reason CLAUDE.md wants a relationship derived from the source of
        truth rather than a naming convention.
        """
        standard = consumable_const.STANDARD_ATTACK_DELAY_TICKS
        fast = consumable_const.CURED_MEAT_ATTACK_DELAY_TICKS
        self.assertLess(fast, standard)

        cured = _outputs_of_category(CATEGORY_CURING)
        meals = _outputs_of_category(CATEGORY_GASTRONOMY)
        self.assertTrue(cured)
        self.assertTrue(meals)

        for key in cured:
            with self.subTest(cured_cut=key):
                self.assertEqual(
                    ITEM_DB[key].attack_delay_ticks_or_default(), fast)

        for key in meals:
            with self.subTest(meal=key):
                self.assertEqual(
                    ITEM_DB[key].attack_delay_ticks_or_default(), standard)

    def test_every_food_is_made_by_curing_or_gastronomy(self):
        """The classification above is only meaningful if it is exhaustive.

        A food produced by neither stage would be silently exempt from the
        delay check, which is how a prefix match hid a bug once already.
        """
        made = _outputs_of_category(CATEGORY_CURING) | _outputs_of_category(
            CATEGORY_GASTRONOMY)

        self.assertEqual(set(_food_keys()) - made, set())

    def test_every_food_takes_the_standard_eat_delay(self):
        """Nothing is a combo food yet.

        Karambwan's 2 is its ATTACK delay; its eat delay is the ordinary 3, and
        so is everything's here. A food that shortened the EAT delay would be a
        combo food, which is a mechanic nobody has asked for.
        """
        standard = consumable_const.STANDARD_EAT_DELAY_TICKS

        for key in _food_keys():
            with self.subTest(food=key):
                self.assertEqual(
                    ITEM_DB[key].eat_delay_ticks_or_default(), standard
                )

    def test_a_meal_heals_more_than_the_cured_cuts_that_made_it(self):
        """The spreadsheet's one explicit healing promise.

        "Heals more than cured meat eaten raw" -- asserted against the recipe's
        actual inputs rather than against two names, so it still holds if the
        sandwich is ever rebuilt from different cuts.
        """
        from systems.gameplay.crafting.registry import RECIPE_REGISTRY

        sandwich_key = "mutant_raider_cured_meat_sandwich"
        recipe = next(
            cls
            for cls in RECIPE_REGISTRY.values()
            if cls.output_item_keys == [sandwich_key]
        )

        meal_heal = ITEM_DB[sandwich_key].heal_amount
        for ingredient in recipe.consumable_tags:
            with self.subTest(ingredient=ingredient):
                self.assertGreater(meal_heal, ITEM_DB[ingredient].heal_amount)

    def test_no_food_can_fill_a_starting_character_from_empty(self):
        """A 10 HP pool against a ladder topping out at 12.

        The deepest sandwich nearly fills a new character and no food exceeds
        the pool by much, which is the shape "a supplement, not a reset button"
        was chosen for. A food healing 40 would make the rest of the ladder
        pointless, and nothing else in the repo would notice.
        """
        starting_max_hp = 10
        dearest = max(ITEM_DB[key].heal_amount for key in _food_keys())

        self.assertLessEqual(dearest, starting_max_hp + 2)



class TestIsEdible(EvenniaTest):
    """What the service will and will not accept, on real objects."""

    def test_food_is_edible(self):
        food = ITEM_DB[_CHUCK].create(location=self.char1)

        self.assertTrue(consumables.is_edible(food))
        self.assertEqual(
            consumables.heal_amount_of(food), ITEM_DB[_CHUCK].heal_amount
        )

    def test_an_ordinary_item_is_not_edible(self):
        chunk = ITEM_DB["rusty_metal_chunk"].create(location=self.char1)

        self.assertFalse(consumables.is_edible(chunk))
        self.assertIsNone(consumables.heal_amount_of(chunk))

    def test_a_character_is_not_edible(self):
        """Every failed `eat` lands in heal_amount_of first."""
        self.assertFalse(consumables.is_edible(self.char1))

    def test_none_is_not_edible(self):
        self.assertFalse(consumables.is_edible(None))

    def test_a_zero_heal_amount_is_not_food(self):
        """Zero is what an author writes by accident.

        Treating it as food that heals nothing would put an inert item in the
        pane's Eat menu; treating it as not-food refuses it with a message.
        """
        food = ITEM_DB[_CHUCK].create(location=self.char1)
        food.db.heal_amount = 0

        self.assertFalse(consumables.is_edible(food))

    def test_a_food_tag_alone_does_not_make_a_thing_edible(self):
        """A family tag is a LOOK, not a rule.

        The same trap an ItemDef tagged `weapon` with no combat_styles walks
        into, asserted here so the two systems keep the same answer.
        """
        chunk = ITEM_DB["rusty_metal_chunk"].create(location=self.char1)
        chunk.tags.add("rusty_metal_chunk", category=ITEM_FAMILY_FOOD)

        self.assertFalse(consumables.is_edible(chunk))



class EatingTestBase(EvenniaTest):
    """A character with food and a controllable clock."""

    def setUp(self):
        super().setUp()
        self.char1.db.max_hp = 20
        self.char1.hp = 20

    def _give(self, item_key, quantity=1):
        return ITEM_DB[item_key].create(location=self.char1, quantity=quantity)

    def _engine(self):
        from systems.core.tick.engine import get_tick_engine

        return get_tick_engine()

    def _advance_ticks(self, count):
        """Move the engine's tick counter forward.

        The substitute for sleeping, and it works precisely because readiness is
        a comparison against this number and nothing else -- there is no
        countdown anywhere to keep in step with it.
        """
        engine = self._engine()
        engine.ndb.tick_number = (engine.ndb.tick_number or 0) + count

    def _carried_named(self, item_name):
        return [obj for obj in self.char1.contents if obj.db_key == item_name]



class TestEatingHeals(EatingTestBase):
    """The heal, the cap, and the waste."""

    def test_eating_restores_hit_points(self):
        self.char1.hp = 10
        food = self._give(_CHUCK)
        expected = ITEM_DB[_CHUCK].heal_amount

        eaten = consumables.eat(self.char1, food)

        self.assertTrue(eaten)
        self.assertEqual(self.char1.hp, 10 + expected)

    def test_healing_is_capped_at_max_hp(self):
        self.char1.hp = self.char1.max_hp - 1
        food = self._give(_PRIME_SANDWICH)

        consumables.eat(self.char1, food)

        self.assertEqual(self.char1.hp, self.char1.max_hp)

    def test_eating_at_full_health_is_allowed_and_wastes_the_food(self):
        """OSRS behaviour, and the answer to "can I bin a prime sandwich".

        Yes. The cap is not a refusal: the item is consumed, the delays apply,
        and nothing is healed.
        """
        self.char1.hp = self.char1.max_hp
        food = self._give(_PRIME_SANDWICH)
        food_name = food.db_key

        eaten = consumables.eat(self.char1, food)

        self.assertTrue(eaten)
        self.assertEqual(self.char1.hp, self.char1.max_hp)
        self.assertEqual(self._carried_named(food_name), [])

    def test_healing_is_flat_and_not_scaled_by_the_eater(self):
        """A cured chuck restores the same amount at any max HP.

        The design answer was flat per item, so what varies with Fortitude is
        how much of the bar the food covers, never the number.
        """
        expected = ITEM_DB[_CHUCK].heal_amount

        self.char1.db.max_hp = 100
        self.char1.hp = 50
        consumables.eat(self.char1, self._give(_CHUCK))
        healed_at_high = self.char1.hp - 50

        setattr(self.char1.ndb, consumable_const.NEXT_EAT_TICK_ATTR, None)
        self.char1.db.max_hp = 20
        self.char1.hp = 5
        consumables.eat(self.char1, self._give(_CHUCK))
        healed_at_low = self.char1.hp - 5

        self.assertEqual(healed_at_high, expected)
        self.assertEqual(healed_at_low, expected)

    def test_an_inedible_item_is_refused_and_not_destroyed(self):
        chunk = self._give("rusty_metal_chunk")
        chunk_name = chunk.db_key

        eaten = consumables.eat(self.char1, chunk)

        self.assertFalse(eaten)
        self.assertEqual(len(self._carried_named(chunk_name)), 1)



class TestEatingConsumes(EatingTestBase):
    """What happens to the item."""

    def test_a_non_stackable_food_is_deleted(self):
        food = self._give(_CHUCK)
        food_name = food.db_key

        consumables.eat(self.char1, food)

        self.assertEqual(self._carried_named(food_name), [])

    def test_a_stackable_food_loses_one_unit(self):
        """Eating one must not bin the other nine.

        No food stacks today, so this is driven on an object made stackable by
        hand -- the branch exists because the moment a food does stack, the
        alternative is deleting the whole stack on the first bite.
        """
        food = self._give(_CHUCK)
        food.db.stackable = True
        food.db.quantity = 3

        consumables.eat(self.char1, food)

        self.assertFalse(food.pk is None)
        self.assertEqual(food.quantity, 2)

    def test_the_last_unit_of_a_stack_deletes_the_object(self):
        food = self._give(_CHUCK)
        food.db.stackable = True
        food.db.quantity = 1

        consumables.eat(self.char1, food)

        self.assertIsNone(food.pk)

    def test_eating_publishes_the_inventory(self):
        """obj.delete() does not fire at_object_leave.

        Without an explicit publish the pane keeps drawing a sandwich the
        player has already eaten.
        """
        food = self._give(_CHUCK)

        with mock.patch(
            "systems.interface.statefeed.events.emit_inventory"
        ) as emit_inventory:
            consumables.eat(self.char1, food)

        emit_inventory.assert_called_with(self.char1)



class TestTheEatDelay(EatingTestBase):
    """The delay that works outside combat."""

    def test_a_fresh_character_may_eat_at_once(self):
        self.assertEqual(consumables.ticks_until_can_eat(self.char1), 0)

    def test_eating_arms_the_delay(self):
        self.char1.hp = 1
        consumables.eat(self.char1, self._give(_CHUCK))

        remaining = consumables.ticks_until_can_eat(self.char1)

        self.assertEqual(
            remaining, consumable_const.STANDARD_EAT_DELAY_TICKS
        )

    def test_a_second_bite_is_refused_while_the_delay_stands(self):
        self.char1.hp = 1
        consumables.eat(self.char1, self._give(_CHUCK))
        second = self._give(_CHUCK)
        second_name = second.db_key

        eaten = consumables.eat(self.char1, second)

        self.assertFalse(eaten)
        self.assertEqual(len(self._carried_named(second_name)), 1)

    def test_a_refused_bite_heals_nothing(self):
        self.char1.hp = 1
        consumables.eat(self.char1, self._give(_CHUCK))
        hp_after_first = self.char1.hp

        consumables.eat(self.char1, self._give(_CHUCK))

        self.assertEqual(self.char1.hp, hp_after_first)

    def test_the_delay_expires_as_the_clock_advances(self):
        self.char1.hp = 1
        consumables.eat(self.char1, self._give(_CHUCK))

        self._advance_ticks(consumable_const.STANDARD_EAT_DELAY_TICKS)

        self.assertEqual(consumables.ticks_until_can_eat(self.char1), 0)

    def test_a_second_bite_lands_once_the_delay_expires(self):
        self.char1.hp = 1
        consumables.eat(self.char1, self._give(_CHUCK))
        self._advance_ticks(consumable_const.STANDARD_EAT_DELAY_TICKS)

        eaten = consumables.eat(self.char1, self._give(_CHUCK))

        self.assertTrue(eaten)

    def test_the_delay_is_stored_in_ndb_and_not_in_db(self):
        """A persisted tick number would outlive the counter it is compared to.

        current_tick() resets to zero on a reload, so a db value written at tick
        50,000 would refuse food for eight hours after the next restart. Being
        as ephemeral as the clock is the correctness property, and combat's
        cooldown_ticks is ndb for the same reason.
        """
        self.char1.hp = 1
        consumables.eat(self.char1, self._give(_CHUCK))

        stored_ndb = getattr(
            self.char1.ndb, consumable_const.NEXT_EAT_TICK_ATTR, None
        )
        stored_db = self.char1.attributes.get(
            consumable_const.NEXT_EAT_TICK_ATTR, default=None
        )

        self.assertTrue(stored_ndb)
        self.assertIsNone(stored_db)



class TestTheAttackDelay(EatingTestBase):
    """The delay that only means something in a fight."""

    class _FakeHandler:
        """Stands in for BlackoutCombatHandler's cooldown counter.

        A real handler means a real fight: two combatants, a weapon and a
        tickable script, to observe one integer. What is under test is which
        integer is written and how, so the counter is all the double needs --
        and using one keeps the test honest about the coupling being exactly
        ndb.cooldown_ticks.
        """

        def __init__(self, cooldown_ticks=0, is_active=True):
            self.is_active = is_active
            self.ndb = mock.Mock()
            self.ndb.cooldown_ticks = cooldown_ticks

    def _eat_with_handler(self, handler, item_key=_CHUCK):
        food = self._give(item_key)
        with mock.patch.object(
            type(self.char1), "combat", new=handler
        ):
            consumables.eat(self.char1, food)

    def test_eating_in_combat_pushes_back_the_next_swing(self):
        handler = self._FakeHandler(cooldown_ticks=0)

        self._eat_with_handler(handler)

        expected = ITEM_DB[_CHUCK].attack_delay_ticks_or_default()
        self.assertEqual(handler.ndb.cooldown_ticks, expected)

    def test_a_cured_meat_delays_less_than_a_cooked_meal(self):
        cured = self._FakeHandler(cooldown_ticks=0)
        meal = self._FakeHandler(cooldown_ticks=0)

        self._eat_with_handler(cured, _CHUCK)
        setattr(self.char1.ndb, consumable_const.NEXT_EAT_TICK_ATTR, None)
        self._eat_with_handler(meal, "mutant_raider_steak")

        self.assertLess(cured.ndb.cooldown_ticks, meal.ndb.cooldown_ticks)

    def test_a_longer_standing_cooldown_is_not_brought_forward(self):
        """Eating mid-recovery must not speed a slow weapon up.

        The delay is MAXED with what is standing rather than assigned, so a
        speed-6 weapon four ticks into its recovery is not handed a two-tick
        cooldown instead.
        """
        handler = self._FakeHandler(cooldown_ticks=5)

        self._eat_with_handler(handler)

        self.assertEqual(handler.ndb.cooldown_ticks, 5)

    def test_eating_twice_does_not_compound_the_delay(self):
        """Maxed rather than added, the other half of the same decision."""
        handler = self._FakeHandler(cooldown_ticks=0)

        self._eat_with_handler(handler)
        first = handler.ndb.cooldown_ticks
        setattr(self.char1.ndb, consumable_const.NEXT_EAT_TICK_ATTR, None)
        self._eat_with_handler(handler)

        self.assertEqual(handler.ndb.cooldown_ticks, first)

    def test_an_inactive_handler_is_not_charged(self):
        """A handler row can outlive the fight it was made for."""
        handler = self._FakeHandler(cooldown_ticks=0, is_active=False)

        self._eat_with_handler(handler)

        self.assertEqual(handler.ndb.cooldown_ticks, 0)

    def test_eating_outside_combat_still_works(self):
        """No handler, no attack delay, and no error.

        The documented simplification: a player who eats and THEN opens combat
        swings immediately, because there was nothing to charge.
        """
        self.char1.hp = 1
        food = self._give(_CHUCK)

        eaten = consumables.eat(self.char1, food)

        self.assertTrue(eaten)
        self.assertGreater(self.char1.hp, 1)
