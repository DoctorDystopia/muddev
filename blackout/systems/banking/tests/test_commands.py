"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: The deposit / withdraw / balance commands on a bank node.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.banking
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from typeclasses.bank_nodes import BankNode, CmdBalance, CmdDeposit, CmdWithdraw
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.items import BaseItem


class TestBankCommands(EvenniaCommandTest):
    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.bank_node = create_object(
            BankNode, key="bank terminal", location=self.room1
        )
        self.test_item = create_object(BaseItem, key="GoldCoin", location=self.char1)
        self.test_item2 = create_object(BaseItem, key="SilverRing", location=self.char1)

    def test_cmd_deposit(self):
        response = self.call(
            CmdDeposit(), " GoldCoin", caller=self.char1, obj=self.bank_node
        )
        self.assertIn("deposit", response.lower())

    def test_cmd_deposit_no_args(self):
        response = self.call(
            CmdDeposit(), "", caller=self.char1, obj=self.bank_node
        )
        self.assertIn("what", response.lower())

    def test_cmd_withdraw(self):
        self.char1.bank.deposit(self.test_item)
        response = self.call(
            CmdWithdraw(), " GoldCoin", caller=self.char1, obj=self.bank_node
        )
        self.assertIn("withdraw", response.lower())

    def test_cmd_withdraw_empty_bank(self):
        response = self.call(
            CmdWithdraw(), "", caller=self.char1, obj=self.bank_node
        )
        self.assertIn("empty", response.lower())

    def test_cmd_balance_empty(self):
        response = self.call(
            CmdBalance(), "", caller=self.char1, obj=self.bank_node
        )
        self.assertIn("empty", response.lower())

    def test_cmd_balance_with_items(self):
        self.char1.bank.deposit(self.test_item)
        self.char1.bank.deposit(self.test_item2)
        response = self.call(
            CmdBalance(), "", caller=self.char1, obj=self.bank_node
        )
        self.assertIn("GoldCoin", response)
        self.assertIn("SilverRing", response)

    def test_cmd_deposit_then_balance(self):
        self.call(CmdDeposit(), " GoldCoin", caller=self.char1, obj=self.bank_node)
        response = self.call(
            CmdBalance(), "", caller=self.char1, obj=self.bank_node
        )
        self.assertIn("GoldCoin", response)

    def test_deposit_and_withdraw_cycle(self):
        self.call(CmdDeposit(), " GoldCoin", caller=self.char1, obj=self.bank_node)
        self.assertNotIn(self.test_item, self.char1.contents)
        self.call(CmdWithdraw(), " GoldCoin", caller=self.char1, obj=self.bank_node)
        self.assertIn(self.test_item, self.char1.contents)

    def _make_pile(self, count, key="rusty scrap metal"):
        return [
            create_object(BaseItem, key=key, location=self.char1)
            for _ in range(count)
        ]

    def test_cmd_deposit_takes_a_multi_word_name(self):
        self._make_pile(1)

        self.call(
            CmdDeposit(), " rusty scrap metal", caller=self.char1, obj=self.bank_node
        )

        self.assertEqual(self.char1.bank.count_items(), 1)

    def test_cmd_deposit_banks_every_copy_by_default(self):
        self._make_pile(6)

        self.call(
            CmdDeposit(), " rusty scrap metal", caller=self.char1, obj=self.bank_node
        )

        self.assertEqual(self.char1.bank.count_items(), 6)

    def test_cmd_deposit_honours_a_trailing_quantity(self):
        self._make_pile(6)

        self.call(
            CmdDeposit(), " rusty scrap metal 2", caller=self.char1, obj=self.bank_node
        )

        self.assertEqual(self.char1.bank.count_items(), 2)

    def test_cmd_deposit_accepts_all(self):
        self._make_pile(6)

        self.call(
            CmdDeposit(), " rusty scrap metal all", caller=self.char1, obj=self.bank_node
        )

        self.assertEqual(self.char1.bank.count_items(), 6)

    def test_cmd_deposit_unknown_item_explains(self):
        response = self.call(
            CmdDeposit(), " nonexistent thing", caller=self.char1, obj=self.bank_node
        )

        self.assertIn("aren't carrying", response)

    def test_cmd_withdraw_takes_a_trailing_quantity(self):
        self.char1.bank.deposit_many(self._make_pile(6))

        self.call(
            CmdWithdraw(), " rusty scrap metal 4", caller=self.char1, obj=self.bank_node
        )

        self.assertEqual(self.char1.bank.count_items(), 2)

    def test_cmd_balance_totals_identical_items(self):
        self.char1.bank.deposit_many(self._make_pile(5))

        response = self.call(CmdBalance(), "", caller=self.char1, obj=self.bank_node)

        self.assertIn("x5", response)
        self.assertEqual(response.count("rusty scrap metal"), 1, response)
