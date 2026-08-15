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

from commands.get_cmds import GetCmd
from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB

# Public constant definitions

STACKABLE_KEY = "credits"
NON_STACKABLE_KEY = "hammer"
EXISTING_STACK_QTY = 40
GROUND_STACK_QTY = 63


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
