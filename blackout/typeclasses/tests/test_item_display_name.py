"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Regression tests for BaseItem.get_display_name -- a
             stackable item's quantity must be visible wherever Evennia
             renders its name (room look, get/drop announcements), not
             just in the inventory grid.

Run with:
    evennia test --settings settings.py typeclasses.tests.test_item_display_name
"""

from evennia.utils.test_resources import EvenniaTest

from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB

STACKABLE_KEY = "credits"
NON_STACKABLE_KEY = "hammer"


class TestItemDisplayName(EvenniaTest):
    """A stackable item's display name must carry its stack size."""

    character_typeclass = BlackoutCharacter

    def test_stack_of_one_shows_no_quantity_suffix(self):
        item = ITEM_DB[STACKABLE_KEY].create(location=self.room1, quantity=1)

        self.assertEqual(item.get_display_name(self.char1), item.name)

    def test_stack_above_one_shows_quantity_suffix(self):
        item = ITEM_DB[STACKABLE_KEY].create(location=self.room1, quantity=85)

        self.assertEqual(item.get_display_name(self.char1), f"{item.name} (x85)")

    def test_non_stackable_item_shows_no_quantity_suffix(self):
        item = ITEM_DB[NON_STACKABLE_KEY].create(location=self.room1)

        self.assertEqual(item.get_display_name(self.char1), item.name)

    def test_room_look_shows_stack_quantity(self):
        ITEM_DB[STACKABLE_KEY].create(location=self.room1, quantity=85)

        appearance = self.room1.return_appearance(self.char1)

        self.assertIn("(x85)", appearance)
