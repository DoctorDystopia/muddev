"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Regression tests for GetCmd -- picking up a stackable item
             that merges into an existing inventory stack must not crash
             the pickup announcement.

Run with:
    evennia test --settings settings.py commands.tests.test_get_cmd
"""

from evennia.utils.test_resources import EvenniaCommandTest

from commands.get_cmds import GetCmd, _is_single_stacked_group
from items.inventory.handler import SLOTS_TOTAL
from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB

# Public constant definitions

STACKABLE_KEY = "credits"
NON_STACKABLE_KEY = "hammer"
DUPLICATE_DROP_KEY = "rusty_metal_chunk"
EXISTING_STACK_QTY = 40
GROUND_STACK_QTY = 63
DUPLICATE_DROP_COUNT = 2


class TestGetCmdStackMerge(EvenniaCommandTest):
    """
    Purpose: Reproduces the crash from picking up a stackable item while
    already carrying a stack of the same key. `InventoryHandler.add_item`
    merges the two and deletes the incoming object, nulling its primary
    key; vanilla `CmdGet` then dereferences that deleted object to build
    the pickup announcement.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """

    character_typeclass = BlackoutCharacter

    def test_get_merges_into_existing_stack_without_crashing(self):
        ITEM_DB[STACKABLE_KEY].create(location=self.char1, quantity=EXISTING_STACK_QTY)
        ITEM_DB[STACKABLE_KEY].create(location=self.room1, quantity=GROUND_STACK_QTY)

        response = self.call(GetCmd(), STACKABLE_KEY, caller=self.char1)

        self.assertIn("pick up", response.lower())
        self.assertIn(f"(x{GROUND_STACK_QTY})", response)
        merged_stack = self.char1.search(STACKABLE_KEY, location=self.char1)
        self.assertIsNotNone(merged_stack)
        self.assertEqual(merged_stack.quantity, EXISTING_STACK_QTY + GROUND_STACK_QTY)

    def test_get_without_existing_stack_still_announces_pickup(self):
        ITEM_DB[NON_STACKABLE_KEY].create(location=self.room1)

        response = self.call(GetCmd(), NON_STACKABLE_KEY, caller=self.char1)

        self.assertIn("pick up", response.lower())
        picked_up = self.char1.search(NON_STACKABLE_KEY, location=self.char1)
        self.assertIsNotNone(picked_up)


class TestGetCmdDuplicateGroundItems(EvenniaCommandTest):
    """
    Purpose: Reproduces the loot-drop scenario where a kill drops several
    separate instances of the same non-stackable item (e.g. two "rusty
    metal chunk" objects rather than one quantity-2 stack). A bare `get
    <name>` must resolve to the lowest-numbered instance instead of
    forcing the player to retype the target with a "-1"/"-2" suffix,
    since a click in the 3D pane has no way to supply one.

    Author: Nick Hobar
    Creation date: 08/15/2026
    """

    character_typeclass = BlackoutCharacter

    def test_get_with_no_count_resolves_to_lowest_numbered_duplicate(self):
        item_def = ITEM_DB[DUPLICATE_DROP_KEY]
        for _ in range(DUPLICATE_DROP_COUNT):
            item_def.create(location=self.room1)

        response = self.call(GetCmd(), item_def.name, caller=self.char1)

        self.assertNotIn("more than one match", response.lower())
        self.assertIn("pick up", response.lower())
        carried = self.char1.search(item_def.name, location=self.char1, quiet=True)
        self.assertEqual(len(carried), 1)
        remaining_on_ground = self.room1.search(item_def.name, location=self.room1, quiet=True)
        self.assertEqual(len(remaining_on_ground), DUPLICATE_DROP_COUNT - 1)


class TestGetCmdFullInventory(EvenniaCommandTest):
    """
    Purpose: Reproduces the bug where `get` kept succeeding past
    "Carrying 32/32 slots" -- InventoryHandler.add_item raised
    InventoryError when full, but Character.at_object_receive caught
    and swallowed it *after* move_to had already placed the object in
    the character's contents (evennia move_to step 8 happens after the
    location change). The item sat there with no grid slot: invisible
    to `inv`, uncounted against the 32-slot cap, but still real. The
    fix moved the capacity check to at_pre_object_receive (step 3),
    which runs before the object leaves its source and can refuse the
    move outright.

    Author: Nick Hobar
    Creation date: 08/16/2026
    """

    character_typeclass = BlackoutCharacter

    def _fill_all_slots(self):
        for _ in range(SLOTS_TOTAL):
            ITEM_DB[NON_STACKABLE_KEY].create(location=self.char1)

    def test_get_is_refused_once_the_grid_is_full(self):
        self._fill_all_slots()
        dropped = ITEM_DB[NON_STACKABLE_KEY].create(location=self.room1)

        response = self.call(GetCmd(), NON_STACKABLE_KEY, caller=self.char1)

        self.assertIn("inventory is completely full", response.lower())
        self.assertEqual(dropped.location, self.room1)
        self.assertEqual(self.char1.inventory.count_used(), SLOTS_TOTAL)

    def test_get_still_merges_into_an_existing_stack_when_full(self):
        for _ in range(SLOTS_TOTAL - 1):
            ITEM_DB[NON_STACKABLE_KEY].create(location=self.char1)
        ITEM_DB[STACKABLE_KEY].create(location=self.char1, quantity=EXISTING_STACK_QTY)
        ITEM_DB[STACKABLE_KEY].create(location=self.room1, quantity=GROUND_STACK_QTY)

        response = self.call(GetCmd(), STACKABLE_KEY, caller=self.char1)

        self.assertIn("pick up", response.lower())
        merged_stack = self.char1.search(STACKABLE_KEY, location=self.char1)
        self.assertEqual(merged_stack.quantity, EXISTING_STACK_QTY + GROUND_STACK_QTY)
        self.assertEqual(self.char1.inventory.count_used(), SLOTS_TOTAL)


class TestIsSingleStackedGroup(EvenniaCommandTest):
    """
    Purpose: Unit-tests `_is_single_stacked_group` directly against
    distinct display names, since forcing a real ambiguous-but-distinct
    multimatch through the full `get` command would depend on two live
    items sharing a partial name in ITEM_DB.

    Author: Nick Hobar
    Creation date: 08/15/2026
    """

    character_typeclass = BlackoutCharacter

    def test_true_for_two_identical_duplicates(self):
        item_def = ITEM_DB[DUPLICATE_DROP_KEY]
        first = item_def.create(location=self.room1)
        second = item_def.create(location=self.room1)

        self.assertTrue(_is_single_stacked_group(self.char1, [first, second]))

    def test_false_for_a_single_match(self):
        item_def = ITEM_DB[DUPLICATE_DROP_KEY]
        only = item_def.create(location=self.room1)

        self.assertFalse(_is_single_stacked_group(self.char1, [only]))

    def test_false_for_distinct_items(self):
        chunk = ITEM_DB[DUPLICATE_DROP_KEY].create(location=self.room1)
        hammer = ITEM_DB[NON_STACKABLE_KEY].create(location=self.room1)

        self.assertFalse(_is_single_stacked_group(self.char1, [chunk, hammer]))
