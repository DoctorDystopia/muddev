"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/15/2026
Description: Tests for InventoryHandler.move_slot -- the rearrange the 3D
             inventory pane's drag gesture rests on.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py items
"""

from evennia.utils.test_resources import EvenniaTest

from items.inventory.handler import SLOTS_TOTAL, InventoryError
from world.item_database import ITEM_DB


# Public constant definitions

FIRST_SLOT = 0
SECOND_SLOT = 1
DISTANT_SLOT = 20


class TestMoveSlot(EvenniaTest):
    """Swap semantics, bounds, and the invariants a rearrange must not break."""

    def _carry(self, item_key: str = "rusty_metal_chunk"):
        return ITEM_DB[item_key].create(location=self.char1)

    def test_moving_into_an_empty_slot_relocates_the_item(self):
        item = self._carry()

        self.char1.inventory.move_slot(FIRST_SLOT, DISTANT_SLOT)

        self.assertEqual(self.char1.inventory.find_slot(item), DISTANT_SLOT)

    def test_moving_into_an_empty_slot_leaves_the_source_empty(self):
        self._carry()

        self.char1.inventory.move_slot(FIRST_SLOT, DISTANT_SLOT)
        vacated = self.char1.inventory.get_slot_content(FIRST_SLOT)

        self.assertIsNone(vacated)

    def test_moving_onto_an_occupied_slot_swaps_the_two(self):
        first = self._carry("rusty_metal_chunk")
        second = self._carry("rusty_scrap_metal")

        self.char1.inventory.move_slot(FIRST_SLOT, SECOND_SLOT)

        self.assertEqual(self.char1.inventory.find_slot(first), SECOND_SLOT)
        self.assertEqual(self.char1.inventory.find_slot(second), FIRST_SLOT)

    def test_a_swap_never_changes_how_many_slots_are_used(self):
        self._carry("rusty_metal_chunk")
        self._carry("rusty_scrap_metal")
        before = self.char1.inventory.count_used()

        self.char1.inventory.move_slot(FIRST_SLOT, DISTANT_SLOT)

        self.assertEqual(self.char1.inventory.count_used(), before)

    def test_dropping_a_stack_onto_a_matching_stack_does_not_merge(self):
        """A cosmetic rearrange must never delete an object. add_item owns
        merging, and it does it on pickup."""
        stack = ITEM_DB["credits"].create(location=self.char1, quantity=10)
        other = ITEM_DB["rusty_metal_dust"].create(
            location=self.char1, quantity=5
        )

        self.char1.inventory.move_slot(FIRST_SLOT, SECOND_SLOT)

        self.assertEqual(self.char1.inventory.count_used(), 2)
        self.assertEqual(stack.quantity, 10)
        self.assertEqual(other.quantity, 5)

    def test_moving_a_slot_onto_itself_reports_no_change(self):
        self._carry()

        changed = self.char1.inventory.move_slot(FIRST_SLOT, FIRST_SLOT)

        self.assertFalse(changed)

    def test_moving_between_two_empty_slots_reports_no_change(self):
        changed = self.char1.inventory.move_slot(DISTANT_SLOT, DISTANT_SLOT + 1)

        self.assertFalse(changed)

    def test_a_real_move_reports_that_it_changed_something(self):
        self._carry()

        changed = self.char1.inventory.move_slot(FIRST_SLOT, DISTANT_SLOT)

        self.assertTrue(changed)

    def test_a_slot_past_the_end_of_the_grid_is_refused(self):
        self._carry()

        with self.assertRaises(InventoryError):
            self.char1.inventory.move_slot(FIRST_SLOT, SLOTS_TOTAL)

    def test_a_negative_slot_is_refused(self):
        self._carry()

        with self.assertRaises(InventoryError):
            self.char1.inventory.move_slot(-1, FIRST_SLOT)

    def test_an_arrangement_survives_a_sync(self):
        """sync() repairs stale ids and files unslotted contents. It must not
        repack a grid the player arranged by hand."""
        item = self._carry()
        self.char1.inventory.move_slot(FIRST_SLOT, DISTANT_SLOT)

        self.char1.inventory.sync()

        self.assertEqual(self.char1.inventory.find_slot(item), DISTANT_SLOT)
