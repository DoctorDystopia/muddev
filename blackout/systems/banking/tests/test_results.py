"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: The TransferResult contract, and the guarantee that the handler
             never messages a session.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.banking
"""

from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.banking.handler import (
    BANK_MAX_UNIQUE_KEYS,
    NOTHING_GIVEN_ERROR,
    VAULT_FULL_ERROR,
    BankHandler,
)
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.items import BaseItem


class TestTransferResults(EvenniaTest):
    """The contract the menu and the commands both render against.

    These could not be written before: the handler messaged the player
    directly and returned an object-or-None, so "why did nothing move?" was
    only ever answerable by reading the text it printed.
    """

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.handler = BankHandler(self.char1)

    def _make_stack(self, key="credits", quantity=10):
        obj = create_object(BaseItem, key=key, location=self.char1)
        obj.attributes.add("stackable", True)
        obj.attributes.add("quantity", quantity)

        return obj

    def _fill_vault(self):
        """Occupy every unique-key slot in the vault."""
        room = self.handler._get_bank_room()

        for i in range(BANK_MAX_UNIQUE_KEYS):
            create_object(BaseItem, key=f"Filler{i}", location=room)

    def test_a_successful_deposit_reports_what_moved(self):
        item = create_object(BaseItem, key="TestItem", location=self.char1)

        result = self.handler.deposit(item)

        self.assertTrue(result.success)
        self.assertEqual(result.moved_count, 1)
        self.assertEqual(result.item_name, "TestItem")
        self.assertEqual(result.error, "")

    def test_a_stack_deposit_reports_its_units_not_one(self):
        stack = self._make_stack(quantity=10)

        result = self.handler.deposit(stack)

        self.assertEqual(result.moved_count, 10)

    def test_a_partial_deposit_reports_only_what_was_taken(self):
        stack = self._make_stack(quantity=10)

        result = self.handler.deposit(stack, count=4)

        self.assertTrue(result.success)
        self.assertEqual(result.moved_count, 4)

    def test_a_full_vault_refuses_with_a_reason(self):
        self._fill_vault()
        item = create_object(BaseItem, key="OneTooMany", location=self.char1)

        result = self.handler.deposit(item)

        self.assertFalse(result.success)
        self.assertEqual(result.error, VAULT_FULL_ERROR)
        self.assertIn(item, self.char1.contents)

    def test_a_full_vault_still_accepts_a_key_it_already_holds(self):
        """The cap counts unique keys, not objects, so an existing entry
        costs nothing further."""
        stack = self._make_stack(key="credits", quantity=5)
        self.handler.deposit(stack)
        self._fill_vault()
        more = self._make_stack(key="credits", quantity=5)

        result = self.handler.deposit(more)

        self.assertTrue(result.success)

    def test_the_name_survives_a_merge_that_deletes_the_source(self):
        """merge() destroys the incoming object, so item_name has to be read
        before it goes."""
        first = self._make_stack(key="credits", quantity=5)
        self.handler.deposit(first)
        second = self._make_stack(key="credits", quantity=5)

        result = self.handler.deposit(second)

        self.assertEqual(result.item_name, "credits")

    def test_an_empty_run_is_not_a_success(self):
        result = self.handler.deposit_many([])

        self.assertFalse(result.success)
        self.assertEqual(result.error, NOTHING_GIVEN_ERROR)

    def test_a_same_key_deposit_run_is_all_or_nothing(self):
        """A vault slot holds one NAME, however many objects that covers, so
        a run of identical items costs one slot and either all of it fits or
        none of it does. A full vault refuses a new name, not more of a name
        it already holds."""
        room = self.handler._get_bank_room()
        for i in range(BANK_MAX_UNIQUE_KEYS - 2):
            create_object(BaseItem, key=f"Filler{i}", location=room)
        pile = [
            create_object(BaseItem, key="rusty scrap metal", location=self.char1)
            for _ in range(5)
        ]

        result = self.handler.deposit_many(pile)

        self.assertTrue(result.success)
        self.assertEqual(result.moved_count, 5)
        self.assertEqual(result.error, "")

    def test_a_run_stopped_partway_reports_both_halves(self):
        """The case the menu prints two lines for: some of it moved, and the
        player still needs to know why the rest did not. Reached through
        inventory space, which fills per object, rather than the vault cap,
        which a same-key run cannot trip -- see the test above."""
        from items.equipment.constants import MAX_INVENTORY_SLOTS

        pile = [
            create_object(BaseItem, key="rusty scrap metal", location=self.char1)
            for _ in range(5)
        ]
        self.handler.deposit_many(pile)

        free_slots = 2
        for i in range(MAX_INVENTORY_SLOTS - free_slots):
            create_object(BaseItem, key=f"Filler{i}", location=self.char1)

        stored = self.handler.list_items()
        result = self.handler.withdraw_many(stored)

        self.assertTrue(result.success)
        self.assertEqual(result.moved_count, free_slots)
        self.assertTrue(result.error)
        self.assertEqual(self.handler.count_items(), 5 - free_slots)

class TestHandlerSaysNothing(EvenniaTest):
    """The point of the refactor: storage routines must not talk to a session.

    A msg() call here is what stopped BankHandler from being reusable by the
    3D webclient or any other non-telnet front end.
    """

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.handler = BankHandler(self.char1)
        self.char1.msg = mock.MagicMock()

    def test_a_successful_deposit_says_nothing(self):
        item = create_object(BaseItem, key="TestItem", location=self.char1)

        self.handler.deposit(item)

        self.char1.msg.assert_not_called()

    def test_a_refused_deposit_says_nothing(self):
        room = self.handler._get_bank_room()
        for i in range(BANK_MAX_UNIQUE_KEYS):
            create_object(BaseItem, key=f"Filler{i}", location=room)
        item = create_object(BaseItem, key="OneTooMany", location=self.char1)

        self.handler.deposit(item)

        self.char1.msg.assert_not_called()

    def test_a_failed_withdrawal_says_nothing(self):
        self.handler.withdraw(99999)

        self.char1.msg.assert_not_called()

    def test_a_bulk_transfer_says_nothing(self):
        pile = [
            create_object(BaseItem, key="rusty scrap metal", location=self.char1)
            for _ in range(3)
        ]

        self.handler.deposit_many(pile)

        self.char1.msg.assert_not_called()
