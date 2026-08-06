"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/31/2026
Description: Tests for the shared deposit/withdraw transfer flow in
             systems/menus/banking_menu.py.

The central regression guarded here: an EvMenu *node* must return
(text, options). EvMenu._execute_node treats any non-tuple return as display
text, so a node that returns a node NAME prints that name at the player
instead of navigating. The deposit/withdraw quantity and custom-quantity
nodes used to do exactly that.
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.menus import banking_menu
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.items import BaseItem


class _BankingMenuTest(EvenniaTest):
    """Shared fixture: a Blackout character with a real bank handler."""

    character_typeclass = BlackoutCharacter

    def _make_item(self, key="rusty metal chunk", quantity=None):
        obj = create_object(BaseItem, key=key, location=self.char1)
        if quantity is not None:
            obj.attributes.add("stackable", True)
            obj.attributes.add("quantity", quantity)
        return obj


class TestSelectNodes(_BankingMenuTest):

    def test_deposit_select_reports_empty_inventory(self):
        for obj in list(self.char1.contents):
            obj.delete()

        text, options = banking_menu.node_deposit_select(self.char1)

        self.assertIn("not carrying anything", text)

    def test_withdraw_select_reports_empty_bank(self):
        text, options = banking_menu.node_withdraw_select(self.char1)

        self.assertIn("bank vault is empty", text)

    def test_deposit_select_lists_carried_items(self):
        item = self._make_item()

        text, options = banking_menu.node_deposit_select(self.char1)

        descs = [opt["desc"] for opt in options]
        self.assertTrue(any(item.key in d for d in descs), descs)


class TestNodesReturnRenderedOutput(_BankingMenuTest):
    """Nodes must hand EvMenu a (text, options) pair, never a node name."""

    def test_deposit_quantity_nonstackable_returns_tuple(self):
        item = self._make_item()

        result = banking_menu.node_deposit_quantity(self.char1, item_id=item.id)

        self.assertIsInstance(result, tuple)
        self.assertNotIsInstance(result, str)
        text, _options = result
        # Must be the re-rendered picker, not the literal node name.
        self.assertNotEqual(text.strip(), "node_deposit_select")

    def test_deposit_quantity_nonstackable_actually_deposits(self):
        item = self._make_item()

        banking_menu.node_deposit_quantity(self.char1, item_id=item.id)

        stored = self.char1.bank.list_items()
        self.assertIn(item, stored)
        self.assertNotIn(item, self.char1.contents)

    def test_withdraw_quantity_nonstackable_returns_tuple(self):
        item = self._make_item()
        self.char1.bank.deposit(item)
        banked = self.char1.bank.list_items()[0]

        result = banking_menu.node_withdraw_quantity(self.char1, item_id=banked.id)

        self.assertIsInstance(result, tuple)
        text, _options = result
        self.assertNotEqual(text.strip(), "node_withdraw_select")

    def test_custom_qty_missing_item_returns_tuple(self):
        result = banking_menu.node_deposit_custom_qty(self.char1, "", item_id=-1)

        self.assertIsInstance(result, tuple)


class TestQuantityPrompting(_BankingMenuTest):

    def test_stackable_offers_quantity_choices(self):
        item = self._make_item(key="credits", quantity=10)

        text, options = banking_menu.node_deposit_quantity(self.char1, item_id=item.id)

        descs = [opt["desc"] for opt in options]
        self.assertIn("1", descs)
        self.assertIn("All (10)", descs)
        self.assertIn("You have 10.", text)

    def test_withdraw_prompt_uses_bank_stock_label(self):
        item = self._make_item(key="credits", quantity=10)
        self.char1.bank.deposit(item)
        banked = self.char1.bank.list_items()[0]

        text, _options = banking_menu.node_withdraw_quantity(
            self.char1, item_id=banked.id
        )

        self.assertIn("Bank has 10.", text)

    def test_custom_qty_rejects_non_numeric(self):
        item = self._make_item(key="credits", quantity=10)

        text, options = banking_menu.node_deposit_custom_qty(
            self.char1, "abc", item_id=item.id, max_qty=10, custom_qty_state="awaiting"
        )

        # Still prompting, and nothing was transferred.
        self.assertIn("How many to deposit?", text)
        self.assertEqual(self.char1.bank.count_items(), 0)

    def test_custom_qty_transfers_requested_amount(self):
        item = self._make_item(key="credits", quantity=10)

        banking_menu.node_deposit_custom_qty(
            self.char1, "4", item_id=item.id, max_qty=10, custom_qty_state="awaiting"
        )

        stored = self.char1.bank.list_items()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].quantity, 4)

    def test_custom_qty_clamps_to_available(self):
        item = self._make_item(key="credits", quantity=10)

        banking_menu.node_deposit_custom_qty(
            self.char1, "999", item_id=item.id, max_qty=10, custom_qty_state="awaiting"
        )

        stored = self.char1.bank.list_items()
        self.assertEqual(stored[0].quantity, 10)


class TestExecuteGoto(_BankingMenuTest):
    """The goto-callable half of the flow DOES return a node name."""

    def test_deposit_goto_returns_select_node_name(self):
        item = self._make_item(key="credits", quantity=10)

        result = banking_menu.DEPOSIT_FLOW.execute_goto(
            self.char1, "", item_id=item.id, count="all"
        )

        self.assertEqual(result, "node_deposit_select")
        self.assertEqual(self.char1.bank.count_items(), 1)

    def test_withdraw_goto_returns_select_node_name(self):
        item = self._make_item(key="credits", quantity=10)
        self.char1.bank.deposit(item)
        banked = self.char1.bank.list_items()[0]

        result = banking_menu.WITHDRAW_FLOW.execute_goto(
            self.char1, "", item_id=banked.id, count="all"
        )

        self.assertEqual(result, "node_withdraw_select")
        self.assertEqual(self.char1.bank.count_items(), 0)
