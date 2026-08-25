"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: Vault slot accounting -- one slot per item NAME, not per object.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.banking
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.banking.handler import BANK_MAX_UNIQUE_KEYS, VAULT_FULL_ERROR, BankHandler
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.items import BaseItem


class TestSlotAccounting(EvenniaTest):
    """A vault slot is one item NAME, not one object.

    The cap was compared against len(room.contents) for its whole life, so a
    run of non-stackables burned a slot per copy and the vault filled roughly
    eleven times too fast.
    """

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.handler = BankHandler(self.char1)

    def _make_pile(self, count, key="rusty scrap metal"):
        return [
            create_object(BaseItem, key=key, location=self.char1)
            for _ in range(count)
        ]

    def test_an_empty_vault_uses_no_slots(self):
        self.assertEqual(self.handler.used_slots(), 0)
        self.assertEqual(self.handler.free_slots(), BANK_MAX_UNIQUE_KEYS)

    def test_many_copies_of_one_name_occupy_one_slot(self):
        self.handler.deposit_many(self._make_pile(11))

        self.assertEqual(self.handler.count_items(), 11)
        self.assertEqual(self.handler.used_slots(), 1)

    def test_each_distinct_name_costs_a_slot(self):
        self.handler.deposit_many(self._make_pile(3, key="rusty scrap metal"))
        self.handler.deposit_many(self._make_pile(2, key="rusty metal chunk"))

        self.assertEqual(self.handler.used_slots(), 2)

    def test_names_differing_only_by_case_share_a_slot(self):
        """Agrees with _has_existing_stack and with items/stacking.py, which
        both match names case-insensitively."""
        first = create_object(BaseItem, key="Credits", location=self.char1)
        second = create_object(BaseItem, key="credits", location=self.char1)
        self.handler.deposit(first)
        self.handler.deposit(second)

        self.assertEqual(self.handler.used_slots(), 1)

    def test_a_vault_full_of_one_name_still_accepts_new_names(self):
        """The regression: 200 scrap plates used to read as 200 slots and
        lock the vault, when they occupy one."""
        self.handler.deposit_many(self._make_pile(BANK_MAX_UNIQUE_KEYS * 2))
        newcomer = create_object(BaseItem, key="something else", location=self.char1)

        result = self.handler.deposit(newcomer)

        self.assertTrue(result.success)
        self.assertEqual(self.handler.used_slots(), 2)

    def test_the_cap_refuses_the_slot_after_the_last(self):
        room = self.handler._get_bank_room()
        for i in range(BANK_MAX_UNIQUE_KEYS):
            create_object(BaseItem, key=f"Filler{i}", location=room)
        newcomer = create_object(BaseItem, key="OneTooMany", location=self.char1)

        result = self.handler.deposit(newcomer)

        self.assertFalse(result.success)
        self.assertEqual(result.error, VAULT_FULL_ERROR)
        self.assertEqual(self.handler.free_slots(), 0)

    def test_withdrawing_a_whole_name_frees_its_slot(self):
        self.handler.deposit_many(self._make_pile(4))
        stored = self.handler.list_items()

        self.handler.withdraw_many(stored)

        self.assertEqual(self.handler.used_slots(), 0)
