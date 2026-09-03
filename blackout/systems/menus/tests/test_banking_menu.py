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

from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.menus import banking_menu
from systems.statefeed.text import line_of
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.items import BaseItem


def _visible_descs(options):
    """The descs a player would actually see on a node.

    Options with no `desc` are the hidden ones -- EvMenu's `_default`, which
    node_deposit_select arms so that a slot-addressed `deposit` typed (or
    right-clicked) while the menu holds the cmdset still reaches the server.
    A hidden option has nothing to display and is not part of the list any of
    these tests are describing.
    """
    return [opt["desc"] for opt in options if "desc" in opt]


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

        descs = _visible_descs(options)
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


class TestGroupedTransfers(_BankingMenuTest):
    """Identical non-stackables list as one row and move in one action."""

    def _make_pile(self, count, key="rusty scrap metal"):
        return [self._make_item(key=key) for _ in range(count)]

    def test_identical_items_collapse_to_one_option(self):
        self._make_pile(5)

        _text, options = banking_menu.node_deposit_select(self.char1)

        descs = _visible_descs(options)
        matching = [d for d in descs if "rusty scrap metal" in d]
        self.assertEqual(len(matching), 1, descs)
        self.assertIn("(x5)", matching[0])

    def test_differing_items_stay_separate(self):
        self._make_pile(2)
        self._make_item(key="rusty metal chunk")

        _text, options = banking_menu.node_deposit_select(self.char1)

        descs = _visible_descs(options)
        self.assertTrue(any("rusty scrap metal (x2)" in d for d in descs), descs)
        self.assertTrue(any("rusty metal chunk" in d for d in descs), descs)

    def test_pile_offers_a_quantity_prompt(self):
        pile = self._make_pile(4)
        ids = [obj.id for obj in pile]

        text, options = banking_menu.node_deposit_quantity(self.char1, item_ids=ids)

        descs = _visible_descs(options)
        self.assertIn("You have 4.", text)
        self.assertIn("All (4)", descs)
        # Nothing moved just by asking how many.
        self.assertEqual(self.char1.bank.count_items(), 0)

    def test_deposit_all_of_a_pile_in_one_action(self):
        pile = self._make_pile(6)
        ids = [obj.id for obj in pile]

        banking_menu.DEPOSIT_FLOW.execute_goto(
            self.char1, "", item_ids=ids, count="all"
        )

        self.assertEqual(self.char1.bank.count_items(), 6)
        for obj in pile:
            self.assertNotIn(obj, self.char1.contents)

    def test_deposit_partial_pile_leaves_the_rest_carried(self):
        pile = self._make_pile(6)
        ids = [obj.id for obj in pile]

        banking_menu.node_deposit_custom_qty(
            self.char1, "4", item_ids=ids, max_qty=6, custom_qty_state="awaiting"
        )

        self.assertEqual(self.char1.bank.count_items(), 4)
        still_carried = [obj for obj in pile if obj in self.char1.contents]
        self.assertEqual(len(still_carried), 2)

    def test_withdraw_all_of_a_pile_in_one_action(self):
        pile = self._make_pile(5)
        self.char1.bank.deposit_many(pile)
        banked_ids = [obj.id for obj in self.char1.bank.list_items()]

        banking_menu.WITHDRAW_FLOW.execute_goto(
            self.char1, "", item_ids=banked_ids, count="all"
        )

        self.assertEqual(self.char1.bank.count_items(), 0)

    def test_single_item_still_transfers_without_prompting(self):
        item = self._make_item()

        result = banking_menu.node_deposit_quantity(self.char1, item_ids=[item.id])

        self.assertIsInstance(result, tuple)
        self.assertIn(item, self.char1.bank.list_items())

    def test_grouped_deposit_reports_one_line(self):
        pile = self._make_pile(5)
        ids = [obj.id for obj in pile]
        self.char1.msg = mock.MagicMock()

        banking_menu.DEPOSIT_FLOW.execute_goto(
            self.char1, "", item_ids=ids, count="all"
        )

        deposit_lines = [
            line_of(call.args[0])
            for call in self.char1.msg.call_args_list
            if call.args and "deposit" in line_of(call.args[0])
        ]
        self.assertEqual(len(deposit_lines), 1, deposit_lines)
        self.assertIn("(x5)", deposit_lines[0])


class TestQuantityPrompting(_BankingMenuTest):

    def test_stackable_offers_quantity_choices(self):
        item = self._make_item(key="credits", quantity=10)

        text, options = banking_menu.node_deposit_quantity(self.char1, item_id=item.id)

        descs = _visible_descs(options)
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
