"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: Tests for items/stacking.py -- the single owner of merge, split
             and reduce semantics for stackable items.

These are the rules that used to live in three modules that disagreed, and
they are the only duplication in the repo that could destroy player items, so
the self-merge guard and the delete-at-empty rule are covered explicitly
rather than implied by a higher-level banking test.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py items.tests.test_stacking
"""

from evennia.utils.test_resources import EvenniaTest

from items import stacking
from world.item_database import ITEM_DB


# Public constant definitions

STACKABLE_KEY = "credits"
OTHER_STACKABLE_KEY = "rusty_metal_dust"
PLAIN_KEY = "rusty_metal_chunk"

STARTING_UNITS = 10
INCOMING_UNITS = 4
PARTIAL_UNITS = 3


class _StackingTestBase(EvenniaTest):
    """Shared spawn helpers. Objects are built detached unless a test needs
    a location -- create_object does not fire at_object_receive (CLAUDE.md
    gotcha 5), so nothing merges behind the test's back."""

    def _stack(self, quantity: int = STARTING_UNITS, item_key: str = STACKABLE_KEY):
        item_def = ITEM_DB[item_key]
        obj = item_def.create(location=None, quantity=quantity)

        return obj

    def _plain(self, item_key: str = PLAIN_KEY):
        item_def = ITEM_DB[item_key]
        obj = item_def.create(location=None)

        return obj


class TestPredicates(_StackingTestBase):
    """is_stackable / quantity_of -- the probes every other rule builds on."""

    def test_a_stackable_item_reports_stackable(self):
        obj = self._stack()

        self.assertTrue(stacking.is_stackable(obj))

    def test_a_plain_item_does_not_report_stackable(self):
        obj = self._plain()

        self.assertFalse(stacking.is_stackable(obj))

    def test_none_does_not_report_stackable(self):
        self.assertFalse(stacking.is_stackable(None))

    def test_quantity_of_reads_the_stack_size(self):
        obj = self._stack(STARTING_UNITS)

        self.assertEqual(stacking.quantity_of(obj), STARTING_UNITS)

    def test_a_plain_item_counts_as_one_unit(self):
        obj = self._plain()

        self.assertEqual(stacking.quantity_of(obj), stacking.SINGLE_UNIT)

    def test_quantity_of_none_is_zero(self):
        self.assertEqual(stacking.quantity_of(None), stacking.EMPTY_STACK_QUANTITY)


class TestIsMergeable(_StackingTestBase):
    """The predicate the inventory grid and the bank vault used to disagree on."""

    def test_two_stacks_of_the_same_key_may_merge(self):
        first = self._stack()
        second = self._stack()

        self.assertTrue(stacking.is_mergeable(first, second))

    def test_an_object_may_never_merge_with_itself(self):
        # Self-merge doubles the quantity and then deletes the row -- the item
        # is destroyed and the player is told nothing.
        obj = self._stack()

        self.assertFalse(stacking.is_mergeable(obj, obj))

    def test_different_keys_may_not_merge(self):
        first = self._stack(item_key=STACKABLE_KEY)
        second = self._stack(item_key=OTHER_STACKABLE_KEY)

        self.assertFalse(stacking.is_mergeable(first, second))

    def test_a_plain_item_may_not_merge(self):
        stack = self._stack()
        plain = self._plain()

        self.assertFalse(stacking.is_mergeable(stack, plain))

    def test_two_plain_items_may_not_merge(self):
        first = self._plain()
        second = self._plain()

        self.assertFalse(stacking.is_mergeable(first, second))

    def test_none_operands_may_not_merge(self):
        obj = self._stack()

        self.assertFalse(stacking.is_mergeable(obj, None))
        self.assertFalse(stacking.is_mergeable(None, obj))
        self.assertFalse(stacking.is_mergeable(None, None))

    def test_keys_are_compared_ignoring_case(self):
        # The inventory grid compared keys case-sensitively and the bank did
        # not, so the same two objects merged in a vault and refused to merge
        # in a backpack. One rule now, and it is the permissive one.
        first = self._stack()
        second = self._stack()
        second.key = second.key.upper()

        self.assertTrue(stacking.is_mergeable(first, second))


class TestFindMergeable(_StackingTestBase):
    """Scanning a container for somewhere to put an incoming stack."""

    def test_finds_the_matching_candidate(self):
        target = self._stack()
        decoy = self._stack(item_key=OTHER_STACKABLE_KEY)
        incoming = self._stack()

        found = stacking.find_mergeable([decoy, target], incoming)

        self.assertEqual(found, target)

    def test_returns_none_when_nothing_matches(self):
        decoy = self._plain()
        incoming = self._stack()

        found = stacking.find_mergeable([decoy], incoming)

        self.assertIsNone(found)

    def test_tolerates_none_entries_in_the_container(self):
        target = self._stack()
        incoming = self._stack()

        found = stacking.find_mergeable([None, target], incoming)

        self.assertEqual(found, target)

    def test_never_returns_the_incoming_object_itself(self):
        incoming = self._stack()

        found = stacking.find_mergeable([incoming], incoming)

        self.assertIsNone(found)


class TestAvailableUnits(_StackingTestBase):
    """The tally deposit_many / withdraw_many size themselves against."""

    def test_sums_stack_quantities(self):
        first = self._stack(STARTING_UNITS)
        second = self._stack(INCOMING_UNITS)

        total = stacking.available_units([first, second])

        self.assertEqual(total, STARTING_UNITS + INCOMING_UNITS)

    def test_counts_each_plain_item_as_one(self):
        items = [self._plain(), self._plain(), self._plain()]

        total = stacking.available_units(items)

        self.assertEqual(total, 3 * stacking.SINGLE_UNIT)

    def test_an_empty_run_holds_nothing(self):
        total = stacking.available_units([])

        self.assertEqual(total, 0)


class TestAddUnits(_StackingTestBase):
    """Growing a stack with no second object involved."""

    def test_grows_the_stack(self):
        obj = self._stack(STARTING_UNITS)

        result = stacking.add_units(obj, INCOMING_UNITS)

        self.assertEqual(result, STARTING_UNITS + INCOMING_UNITS)
        self.assertEqual(obj.quantity, STARTING_UNITS + INCOMING_UNITS)

    def test_a_non_positive_count_changes_nothing(self):
        obj = self._stack(STARTING_UNITS)

        result = stacking.add_units(obj, 0)

        self.assertEqual(result, STARTING_UNITS)
        self.assertEqual(obj.quantity, STARTING_UNITS)


class TestReduceUnits(_StackingTestBase):
    """Draining a stack, and the delete-at-empty rule that must not be forgotten."""

    def test_a_partial_draw_leaves_the_object_alive(self):
        obj = self._stack(STARTING_UNITS)

        was_deleted = stacking.reduce_units(obj, PARTIAL_UNITS)

        self.assertFalse(was_deleted)
        self.assertEqual(obj.quantity, STARTING_UNITS - PARTIAL_UNITS)

    def test_draining_the_whole_stack_deletes_it(self):
        obj = self._stack(STARTING_UNITS)

        was_deleted = stacking.reduce_units(obj, STARTING_UNITS)

        self.assertTrue(was_deleted)
        self.assertIsNone(obj.pk)

    def test_over_drawing_deletes_rather_than_going_negative(self):
        obj = self._stack(STARTING_UNITS)

        was_deleted = stacking.reduce_units(obj, STARTING_UNITS + INCOMING_UNITS)

        self.assertTrue(was_deleted)
        self.assertIsNone(obj.pk)

    def test_a_plain_item_is_deleted_outright(self):
        # BaseItem.quantity's setter returns early for a non-stackable, so a
        # subtraction would silently do nothing and leave the item behind.
        obj = self._plain()

        was_deleted = stacking.reduce_units(obj, stacking.SINGLE_UNIT)

        self.assertTrue(was_deleted)
        self.assertIsNone(obj.pk)

    def test_a_non_positive_count_changes_nothing(self):
        obj = self._stack(STARTING_UNITS)

        was_deleted = stacking.reduce_units(obj, 0)

        self.assertFalse(was_deleted)
        self.assertEqual(obj.quantity, STARTING_UNITS)


class TestMerge(_StackingTestBase):
    """Folding one stack into another."""

    def test_combines_the_quantities(self):
        into = self._stack(STARTING_UNITS)
        source = self._stack(INCOMING_UNITS)

        combined = stacking.merge(into, source)

        self.assertEqual(combined, STARTING_UNITS + INCOMING_UNITS)
        self.assertEqual(into.quantity, STARTING_UNITS + INCOMING_UNITS)

    def test_destroys_the_emptied_source(self):
        into = self._stack(STARTING_UNITS)
        source = self._stack(INCOMING_UNITS)

        stacking.merge(into, source)

        self.assertIsNone(source.pk)

    def test_refuses_a_self_merge_without_destroying_the_item(self):
        obj = self._stack(STARTING_UNITS)

        combined = stacking.merge(obj, obj)

        self.assertEqual(combined, STARTING_UNITS)
        self.assertIsNotNone(obj.pk)

    def test_refuses_mismatched_keys_without_touching_either(self):
        into = self._stack(STARTING_UNITS, item_key=STACKABLE_KEY)
        source = self._stack(INCOMING_UNITS, item_key=OTHER_STACKABLE_KEY)

        combined = stacking.merge(into, source)

        self.assertEqual(combined, STARTING_UNITS)
        self.assertIsNotNone(source.pk)
        self.assertEqual(source.quantity, INCOMING_UNITS)


class TestDetachedCopy(_StackingTestBase):
    """The build-detached rule from CLAUDE.md gotcha 4."""

    def test_the_copy_starts_with_no_location(self):
        source = self._stack(STARTING_UNITS)

        copy = stacking.detached_copy(source, PARTIAL_UNITS)

        self.assertIsNone(copy.location)

    def test_the_copy_carries_the_requested_quantity(self):
        source = self._stack(STARTING_UNITS)

        copy = stacking.detached_copy(source, PARTIAL_UNITS)

        self.assertEqual(copy.quantity, PARTIAL_UNITS)

    def test_the_copy_inherits_the_source_attributes(self):
        source = self._stack(STARTING_UNITS)

        copy = stacking.detached_copy(source, PARTIAL_UNITS)

        self.assertEqual(copy.key, source.key)
        self.assertTrue(copy.is_stackable)
        self.assertEqual(copy.item_value, source.item_value)

    def test_the_source_is_left_untouched(self):
        source = self._stack(STARTING_UNITS)

        stacking.detached_copy(source, PARTIAL_UNITS)

        self.assertEqual(source.quantity, STARTING_UNITS)


class TestSplit(_StackingTestBase):
    """Copy, place, then drain -- in that order."""

    def test_the_new_stack_holds_the_requested_units(self):
        source = self._stack(STARTING_UNITS)

        taken = stacking.split(source, PARTIAL_UNITS)

        self.assertEqual(taken.quantity, PARTIAL_UNITS)

    def test_the_source_is_reduced_by_the_same_amount(self):
        source = self._stack(STARTING_UNITS)

        stacking.split(source, PARTIAL_UNITS)

        self.assertEqual(source.quantity, STARTING_UNITS - PARTIAL_UNITS)

    def test_splitting_the_whole_stack_consumes_the_source(self):
        source = self._stack(STARTING_UNITS)

        taken = stacking.split(source, STARTING_UNITS)

        self.assertEqual(taken.quantity, STARTING_UNITS)
        self.assertIsNone(source.pk)

    def test_the_new_stack_lands_at_the_requested_location(self):
        source = self._stack(STARTING_UNITS)

        taken = stacking.split(source, PARTIAL_UNITS, location=self.room1)

        self.assertEqual(taken.location, self.room1)

    def test_a_non_positive_count_produces_nothing(self):
        source = self._stack(STARTING_UNITS)

        taken = stacking.split(source, 0)

        self.assertIsNone(taken)
        self.assertEqual(source.quantity, STARTING_UNITS)
