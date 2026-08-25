"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: deposit_many / withdraw_many over runs of interchangeable items.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.banking
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.banking.handler import BankHandler
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.items import BaseItem


class TestBulkTransfers(EvenniaTest):
    """Depositing/withdrawing several separate copies of a non-stackable."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.handler = BankHandler(self.char1)

    def _make_pile(self, count, key="rusty scrap metal"):
        return [
            create_object(BaseItem, key=key, location=self.char1)
            for _ in range(count)
        ]

    def _make_stack(self, key="credits", quantity=10):
        obj = create_object(BaseItem, key=key, location=self.char1)
        obj.attributes.add("stackable", True)
        obj.attributes.add("quantity", quantity)
        return obj

    def test_deposit_many_moves_every_copy(self):
        pile = self._make_pile(7)

        result = self.handler.deposit_many(pile)

        self.assertTrue(result.success)
        self.assertEqual(result.moved_count, 7)
        self.assertEqual(self.handler.count_items(), 7)
        for obj in pile:
            self.assertNotIn(obj, self.char1.contents)

    def test_deposit_many_honours_a_count(self):
        pile = self._make_pile(7)

        result = self.handler.deposit_many(pile, 3)

        self.assertTrue(result.success)
        self.assertEqual(result.moved_count, 3)
        self.assertEqual(self.handler.count_items(), 3)
        still_carried = [obj for obj in pile if obj in self.char1.contents]
        self.assertEqual(len(still_carried), 4)

    def test_deposit_many_of_empty_list_does_nothing(self):
        result = self.handler.deposit_many([])

        self.assertFalse(result.success)
        self.assertEqual(result.moved_count, 0)
        self.assertEqual(self.handler.count_items(), 0)

    def test_deposit_many_counts_stack_units_not_objects(self):
        # A single stack contributes its whole size, so the unit count that
        # the menu prompts with matches what actually moves.
        stack = self._make_stack(quantity=10)

        result = self.handler.deposit_many([stack], 4)

        self.assertEqual(result.moved_count, 4)
        stored = self.handler.list_items()
        self.assertEqual(stored[0].quantity, 4)

    def test_withdraw_many_returns_every_copy(self):
        pile = self._make_pile(5)
        self.handler.deposit_many(pile)
        stored = self.handler.list_items()

        result = self.handler.withdraw_many(stored)

        self.assertTrue(result.success)
        self.assertEqual(result.moved_count, 5)
        self.assertEqual(self.handler.count_items(), 0)

    def test_withdraw_many_honours_a_count(self):
        pile = self._make_pile(5)
        self.handler.deposit_many(pile)
        stored = self.handler.list_items()

        result = self.handler.withdraw_many(stored, 2)

        self.assertTrue(result.success)
        self.assertEqual(result.moved_count, 2)
        self.assertEqual(self.handler.count_items(), 3)

    def test_find_items_by_name_returns_the_whole_run(self):
        self.handler.deposit_many(self._make_pile(4))

        matches = self.handler.find_items_by_name("rusty scrap metal")

        self.assertEqual(len(matches), 4)

    def test_find_items_by_name_never_mixes_keys(self):
        self.handler.deposit_many(self._make_pile(4))
        self.handler.deposit_many(self._make_pile(2, key="rusty metal chunk"))

        matches = self.handler.find_items_by_name("rusty")

        keys = {obj.key for obj in matches}
        self.assertEqual(len(keys), 1, keys)

    def test_find_item_by_name_still_returns_one(self):
        self.handler.deposit_many(self._make_pile(4))

        match = self.handler.find_item_by_name("rusty scrap metal")

        self.assertIsNotNone(match)
        self.assertEqual(match.key, "rusty scrap metal")
