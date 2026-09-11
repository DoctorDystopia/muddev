"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for CuringHandler -- slots, deadlines, and the two halves
             of a cure.

             Time is controlled, never waited on. Every test that needs a cure
             to finish rewrites the stored deadline into the past rather than
             sleeping, which is the only way a 5-minute game mechanic can have
             a 2-millisecond test. That is also exactly what the design makes
             possible: readiness is a comparison against time.time() and
             nothing else, so moving the deadline IS moving time as far as the
             handler is concerned.

Run with:
    evennia test --settings test_settings.py systems.gameplay.curing
"""



import time
import unittest

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.crafting import crafting_service
from systems.gameplay.crafting.registry import RECIPE_REGISTRY
from systems.gameplay.curing import constants as curing_constants
from systems.gameplay.curing.recipe import CuringRecipe
from systems.gameplay.progression.skills import constants as skill_constants
from typeclasses.skill_facilities import CuringChamberFacility
from world.item_database import ITEM_DB



# Private constant definitions

# The level-0 recipe, used wherever a test needs "a cure" rather than a
# particular one.
_CHUCK_RECIPE = "mutant raider cured chuck"

# The level-2 recipe, whose input is a RENDERING output rather than a cut.
_FATLESS_RECIPE = "mutant raider cured fatless meat"



class TestSlotsForLevel(unittest.TestCase):
    """The slot table, which is the level curve's second job.

    Plain unittest.TestCase -- this is arithmetic over a tuple and touches no
    database at all.
    """

    def test_the_starting_level_gets_a_slot(self):
        """Zero slots at level 0 would be a deadlock, not a curve."""
        slots = curing_constants.slots_for_level(0)

        self.assertGreaterEqual(slots, 1)

    def test_every_threshold_adds_exactly_one_slot(self):
        """Derived from the table, so a third slot needs no edit here."""
        thresholds = curing_constants.CURING_SLOT_LEVELS

        for expected, level in enumerate(thresholds, start=1):
            with self.subTest(level=level):
                self.assertEqual(
                    curing_constants.slots_for_level(level), expected
                )

    def test_a_level_between_thresholds_keeps_the_lower_count(self):
        thresholds = curing_constants.CURING_SLOT_LEVELS
        first, second = thresholds[0], thresholds[1]
        between = second - 1

        self.assertEqual(
            curing_constants.slots_for_level(between),
            curing_constants.slots_for_level(first),
        )

    def test_the_table_is_ascending(self):
        """A threshold out of order would make a later slot unreachable."""
        thresholds = list(curing_constants.CURING_SLOT_LEVELS)

        self.assertEqual(thresholds, sorted(thresholds))
        self.assertEqual(len(thresholds), len(set(thresholds)))



class TestFormatRemaining(unittest.TestCase):
    """The countdown line, including the rounding decision."""

    def test_under_a_minute_omits_the_minutes(self):
        self.assertEqual(curing_constants.format_remaining(12), "12s")

    def test_over_a_minute_gives_both(self):
        self.assertEqual(curing_constants.format_remaining(252), "4m 12s")

    def test_a_part_second_rounds_up(self):
        """Rounding down prints "0s" for a cure that is not ready.

        Being told 1s once and finding it ready is better than being told 0s
        and being refused.
        """
        self.assertEqual(curing_constants.format_remaining(0.4), "1s")

    def test_negative_is_treated_as_zero(self):
        """An overdue cure reads 0s rather than a minus sign."""
        self.assertEqual(curing_constants.format_remaining(-30), "0s")



class CuringTestBase(EvenniaTest):
    """A character standing at a chamber, holding whatever a test gives them."""

    def setUp(self):
        super().setUp()
        self.chamber = CuringChamberFacility.create(
            "Curing Chamber", location=self.char1.location
        )[0]

    def _give(self, item_key):
        return ITEM_DB[item_key].create(location=self.char1)

    def _give_chuck(self):
        return self._give("mutant_raider_raw_chuck")

    def _start(self, recipe_key=_CHUCK_RECIPE):
        """Start a cure the way the craft menu does, through the service."""
        return crafting_service.perform_craft(self.char1, recipe_key)

    def _slots(self):
        """The raw stored slot list, for tests that must move a deadline."""
        return self.char1.attributes.get(
            curing_constants.CURING_SLOTS_ATTR, default=[]
        )

    def _finish_everything(self):
        """Move every stored deadline into the past.

        The substitute for sleeping. Rewrites the deadline in place rather than
        replacing the list, because Evennia hands back a _SaverList and
        rebinding it would lose the write-through the handler relies on.
        """
        past = time.time() - 1
        for slot in self._slots():
            slot[curing_constants.SLOT_DUE_AT_KEY] = past

    def _carried_named(self, item_name):
        return [obj for obj in self.char1.contents if obj.db_key == item_name]

    def _set_curing_level(self, level):
        self.char1.skills.set_level(skill_constants.CURING_SKILL_KEY, level)



class TestStartingACure(CuringTestBase):
    """What putting meat in the chamber does, and does not do."""

    def test_a_fresh_character_has_one_slot_and_none_used(self):
        self.assertEqual(self.char1.curing.slot_total(), 1)
        self.assertEqual(self.char1.curing.slot_used(), 0)
        self.assertTrue(self.char1.curing.has_free_slot())

    def test_starting_a_cure_claims_a_slot(self):
        self._give_chuck()

        self._start()

        self.assertEqual(self.char1.curing.slot_used(), 1)

    def test_starting_a_cure_consumes_the_input(self):
        self._give_chuck()
        chuck_name = ITEM_DB["mutant_raider_raw_chuck"].name

        self._start()

        self.assertEqual(self._carried_named(chuck_name), [])

    def test_starting_a_cure_produces_nothing_yet(self):
        """The whole point of the stage, asserted directly.

        A cure that handed over the cured meat at once would pass every other
        test in this file.
        """
        self._give_chuck()
        cured_name = ITEM_DB["mutant_raider_cured_chuck"].name

        self._start()

        self.assertEqual(self._carried_named(cured_name), [])

    def test_starting_a_cure_awards_no_xp(self):
        """XP is for the cured meat, and there is none yet."""
        before, _needed, _rest = self.char1.skills.get_xp_level(
            skill_constants.CURING_SKILL_KEY
        )
        self._give_chuck()

        self._start()

        after, _needed, _rest = self.char1.skills.get_xp_level(
            skill_constants.CURING_SKILL_KEY
        )
        self.assertEqual(after, before)

    def test_the_deadline_is_the_recipes_own_duration(self):
        self._give_chuck()
        recipe_cls = RECIPE_REGISTRY[_CHUCK_RECIPE]
        started_at = time.time()

        self._start()

        due_at = self._slots()[0][curing_constants.SLOT_DUE_AT_KEY]
        elapsed = due_at - started_at
        self.assertAlmostEqual(elapsed, recipe_cls.cure_seconds, delta=5)

    def test_a_cure_cannot_start_with_no_input(self):
        result = self._start()

        self.assertFalse(result)
        self.assertEqual(self.char1.curing.slot_used(), 0)

    def test_a_level_gated_cure_is_refused_and_costs_nothing(self):
        """The fatless recipe needs Curing 2; a fresh character has 0."""
        self._give("mutant_raider_fatless_meat")
        meat_name = ITEM_DB["mutant_raider_fatless_meat"].name

        result = self._start(_FATLESS_RECIPE)

        self.assertFalse(result)
        self.assertEqual(self.char1.curing.slot_used(), 0)
        self.assertEqual(len(self._carried_named(meat_name)), 1)

    def test_nothing_starts_without_a_chamber_in_reach(self):
        self._give_chuck()
        self.chamber.location = self.room2

        result = self._start()

        self.assertFalse(result)
        self.assertEqual(self.char1.curing.slot_used(), 0)



class TestSlotLimits(CuringTestBase):
    """Slots free on COLLECTION, not on completion. The stage rests on it."""

    def test_a_second_cure_is_refused_while_the_first_runs(self):
        self._give_chuck()
        self._start()
        self._give_chuck()

        result = self._start()

        self.assertFalse(result)
        self.assertEqual(self.char1.curing.slot_used(), 1)

    def test_a_refused_second_cure_keeps_its_input(self):
        """Being turned away must not cost the meat.

        start() checks the slot BEFORE validating the input for exactly this
        reason -- the other order eats the chuck and then says no.
        """
        self._give_chuck()
        self._start()
        self._give_chuck()
        chuck_name = ITEM_DB["mutant_raider_raw_chuck"].name

        self._start()

        self.assertEqual(len(self._carried_named(chuck_name)), 1)

    def test_a_finished_cure_still_occupies_its_slot(self):
        self._give_chuck()
        self._start()
        self._finish_everything()

        self.assertEqual(self.char1.curing.slot_used(), 1)
        self.assertFalse(self.char1.curing.has_free_slot())

    def test_collecting_frees_the_slot(self):
        self._give_chuck()
        self._start()
        self._finish_everything()

        self.char1.curing.collect()

        self.assertEqual(self.char1.curing.slot_used(), 0)
        self.assertTrue(self.char1.curing.has_free_slot())

    def test_level_ten_opens_a_second_slot(self):
        second_threshold = curing_constants.CURING_SLOT_LEVELS[1]
        self._set_curing_level(second_threshold)

        self.assertEqual(self.char1.curing.slot_total(), 2)

    def test_two_cures_run_at_once_on_two_slots(self):
        second_threshold = curing_constants.CURING_SLOT_LEVELS[1]
        self._set_curing_level(second_threshold)
        self._give_chuck()
        self._start()
        self._give_chuck()

        result = self._start()

        self.assertIsNotNone(result)
        self.assertEqual(self.char1.curing.slot_used(), 2)

    def test_capacity_is_never_negative(self):
        """slot_total shrinks if a level ever drops; capacity must not go under.

        A negative capacity reads as "less than full" to anything doing
        arithmetic on it, which would let a cure start into a slot that is not
        there.
        """
        second_threshold = curing_constants.CURING_SLOT_LEVELS[1]
        self._set_curing_level(second_threshold)
        self._give_chuck()
        self._start()
        self._give_chuck()
        self._start()

        self._set_curing_level(0)

        self.assertEqual(self.char1.curing.capacity_remaining(), 0)
        self.assertFalse(self.char1.curing.has_free_slot())



class TestCollecting(CuringTestBase):
    """The second half of a cure."""

    def test_collecting_early_delivers_nothing_and_keeps_the_slot(self):
        self._give_chuck()
        self._start()

        delivered = self.char1.curing.collect()

        self.assertEqual(delivered, [])
        self.assertEqual(self.char1.curing.slot_used(), 1)

    def test_collecting_a_finished_cure_delivers_the_output(self):
        self._give_chuck()
        self._start()
        self._finish_everything()

        delivered = self.char1.curing.collect()

        self.assertEqual(len(delivered), 1)
        self.assertEqual(
            delivered[0].db_key, ITEM_DB["mutant_raider_cured_chuck"].name
        )

    def test_the_output_occupies_an_inventory_slot(self):
        """Delivery goes through the crafting path for this reason.

        create(location=) does not fire at_object_receive, so a hand-rolled
        delivery leaves the meat in the character's contents with no grid slot
        and publishes nothing to the client.
        """
        self._give_chuck()
        self._start()
        self._finish_everything()

        delivered = self.char1.curing.collect()

        slot = self.char1.inventory.find_slot(delivered[0])
        self.assertGreaterEqual(slot, 0)

    def test_collecting_pays_the_xp(self):
        recipe_cls = RECIPE_REGISTRY[_CHUCK_RECIPE]
        before, needed, _rest = self.char1.skills.get_xp_level(
            skill_constants.CURING_SKILL_KEY
        )
        self.assertLess(
            before + recipe_cls.xp_reward,
            needed,
            "one cure now levels Curing; this test can no longer read the "
            "award off per-level progress",
        )
        self._give_chuck()
        self._start()
        self._finish_everything()

        self.char1.curing.collect()

        after, _needed, _rest = self.char1.skills.get_xp_level(
            skill_constants.CURING_SKILL_KEY
        )
        self.assertEqual(after - before, recipe_cls.xp_reward)

    def test_collecting_twice_delivers_once(self):
        self._give_chuck()
        self._start()
        self._finish_everything()

        first = self.char1.curing.collect()
        second = self.char1.curing.collect()

        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_collecting_with_nothing_curing_is_safe(self):
        delivered = self.char1.curing.collect()

        self.assertEqual(delivered, [])

    def test_only_the_finished_slot_is_collected(self):
        """Two slots, one due. The unfinished one must survive.

        collect() walks the list backwards and pops by index; forwards with a
        pop would skip the entry after each removal, which is the bug this
        test exists to catch.
        """
        second_threshold = curing_constants.CURING_SLOT_LEVELS[1]
        self._set_curing_level(second_threshold)
        self._give_chuck()
        self._start()
        self._finish_everything()
        self._give_chuck()
        self._start()

        delivered = self.char1.curing.collect()

        self.assertEqual(len(delivered), 1)
        self.assertEqual(self.char1.curing.slot_used(), 1)

    def test_two_finished_cures_collect_together(self):
        second_threshold = curing_constants.CURING_SLOT_LEVELS[1]
        self._set_curing_level(second_threshold)
        for _ in range(2):
            self._give_chuck()
            self._start()
        self._finish_everything()

        delivered = self.char1.curing.collect()

        self.assertEqual(len(delivered), 2)
        self.assertEqual(self.char1.curing.slot_used(), 0)



class TestPendingReport(CuringTestBase):
    """The read API the chamber's commands and any future feed channel use."""

    def test_nothing_curing_reports_nothing(self):
        self.assertEqual(self.char1.curing.pending(), [])

    def test_a_running_cure_reports_its_name_and_state(self):
        self._give_chuck()
        self._start()

        entry = self.char1.curing.pending()[0]

        self.assertEqual(entry["recipe_key"], _CHUCK_RECIPE)
        self.assertEqual(entry["item_name"], _CHUCK_RECIPE)
        self.assertEqual(entry["state"], curing_constants.SLOT_STATE_CURING)
        self.assertGreater(entry["remaining"], 0)

    def test_a_finished_cure_reports_ready_with_no_remaining(self):
        self._give_chuck()
        self._start()
        self._finish_everything()

        entry = self.char1.curing.pending()[0]

        self.assertEqual(entry["state"], curing_constants.SLOT_STATE_READY)
        self.assertEqual(entry["remaining"], 0)

    def test_ready_keys_names_only_finished_cures(self):
        second_threshold = curing_constants.CURING_SLOT_LEVELS[1]
        self._set_curing_level(second_threshold)
        self._give_chuck()
        self._start()
        self._finish_everything()
        self._give_chuck()
        self._start()

        ready = self.char1.curing.ready_keys()

        self.assertEqual(ready, [_CHUCK_RECIPE])

    def test_report_order_is_start_order(self):
        second_threshold = curing_constants.CURING_SLOT_LEVELS[1]
        self._set_curing_level(second_threshold)
        self._give_chuck()
        self._start()
        self._give("mutant_raider_fatless_meat")
        self._start(_FATLESS_RECIPE)

        keys = [entry["recipe_key"] for entry in self.char1.curing.pending()]

        self.assertEqual(keys, [_CHUCK_RECIPE, _FATLESS_RECIPE])



class TestARenamedRecipe(CuringTestBase):
    """A slot stores a recipe KEY, and a key is a string in a database row.

    CLAUDE.md's rule for those is that the reader refuses an unresolvable one
    rather than passing it on -- EvMenu reading __dict__ off a None module is
    the cautionary tale. Here "refuses" means the slot is freed: a rename must
    cost the player one item, never a slot they can never reuse.
    """

    def _orphan_the_slot(self):
        self._give_chuck()
        self._start()
        self._finish_everything()
        self._slots()[0][curing_constants.SLOT_RECIPE_KEY] = "no such recipe"

    def test_an_unresolvable_slot_delivers_nothing(self):
        self._orphan_the_slot()

        delivered = self.char1.curing.collect()

        self.assertEqual(delivered, [])

    def test_an_unresolvable_slot_is_freed_rather_than_stuck(self):
        self._orphan_the_slot()

        self.char1.curing.collect()

        self.assertEqual(self.char1.curing.slot_used(), 0)
        self.assertTrue(self.char1.curing.has_free_slot())

    def test_an_unresolvable_slot_still_reports_rather_than_vanishing(self):
        """A report that silently omits a slot is worse than an odd name."""
        self._orphan_the_slot()

        entry = self.char1.curing.pending()[0]

        self.assertEqual(entry["item_name"], "no such recipe")



class TestPersistence(CuringTestBase):
    """Survival across a handler rebuild, which is what a restart looks like.

    lazy_property caches the handler into obj.__dict__, so popping that entry
    and reading the attribute back is the same path a fresh process takes.
    """

    def test_a_cure_survives_the_handler_being_rebuilt(self):
        self._give_chuck()
        self._start()

        self.char1.__dict__.pop("curing", None)

        self.assertEqual(self.char1.curing.slot_used(), 1)

    def test_the_deadline_survives_too(self):
        self._give_chuck()
        self._start()
        before = self._slots()[0][curing_constants.SLOT_DUE_AT_KEY]

        self.char1.__dict__.pop("curing", None)
        after = self.char1.curing.pending()[0]

        self.assertGreater(after["remaining"], 0)
        self.assertEqual(
            self._slots()[0][curing_constants.SLOT_DUE_AT_KEY], before
        )

    def test_a_cure_that_came_due_while_away_is_simply_due(self):
        """No catch-up pass, because readiness is a comparison and nothing else.

        This is what buys the design its absence of a Script: a deadline in the
        past is ready, whether the server was running when it passed or not.
        """
        self._give_chuck()
        self._start()
        self._finish_everything()

        self.char1.__dict__.pop("curing", None)

        self.assertEqual(self.char1.curing.ready_keys(), [_CHUCK_RECIPE])
