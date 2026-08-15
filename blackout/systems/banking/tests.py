from evennia import create_object
from evennia.utils.test_resources import EvenniaTest, EvenniaCommandTest

from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.items import BaseItem
from typeclasses.bank_nodes import CmdDeposit, CmdWithdraw, CmdBalance, BankNode
from systems.banking.handler import BankHandler


class TestBankHandler(EvenniaTest):
    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.handler = BankHandler(self.char1)
        self.test_item = create_object(BaseItem, key="TestItem", location=self.char1)

    def test_deposit_moves_item_to_bank(self):
        self.handler.deposit(self.test_item)
        self.assertNotIn(self.test_item, self.char1.contents)
        stored = self.handler.list_items()
        self.assertIn(self.test_item, stored)

    def test_deposit_increments_count(self):
        self.assertEqual(self.handler.count_items(), 0)
        self.handler.deposit(self.test_item)
        self.assertEqual(self.handler.count_items(), 1)

    def test_withdraw_returns_item_to_inventory(self):
        self.handler.deposit(self.test_item)
        withdrawn = self.handler.withdraw(self.test_item.id)
        self.assertIsNotNone(withdrawn)
        self.assertIn(self.test_item, self.char1.contents)

    def test_withdraw_decrements_count(self):
        self.handler.deposit(self.test_item)
        self.handler.withdraw(self.test_item.id)
        self.assertEqual(self.handler.count_items(), 0)

    def test_withdraw_nonexistent_returns_none(self):
        result = self.handler.withdraw(99999)
        self.assertIsNone(result)

    def test_list_items_empty_after_creation(self):
        self.assertEqual(self.handler.list_items(), [])

    def test_list_items_after_deposit(self):
        self.handler.deposit(self.test_item)
        stored = self.handler.list_items()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].key, "TestItem")

    def test_has_item_false_initially(self):
        self.assertFalse(self.handler.has_item("TestItem"))

    def test_has_item_true_after_deposit(self):
        self.handler.deposit(self.test_item)
        self.assertTrue(self.handler.has_item("TestItem"))

    def test_multiple_deposits_and_withdrawals(self):
        item2 = create_object(BaseItem, key="ItemTwo", location=self.char1)
        item3 = create_object(BaseItem, key="ItemThree", location=self.char1)

        self.handler.deposit(self.test_item)
        self.handler.deposit(item2)
        self.assertEqual(self.handler.count_items(), 2)

        self.handler.withdraw(self.test_item.id)
        self.assertEqual(self.handler.count_items(), 1)
        self.assertIn(self.test_item, self.char1.contents)

        self.handler.deposit(item3)
        self.assertEqual(self.handler.count_items(), 2)

    def test_bank_room_is_created_on_first_deposit(self):
        self.assertIsNone(self.char1.db._bank_room)
        self.handler.deposit(self.test_item)
        self.assertIsNotNone(self.char1.db._bank_room)

    def test_bank_room_reused_on_subsequent_deposits(self):
        self.handler.deposit(self.test_item)
        room = self.char1.db._bank_room
        item2 = create_object(BaseItem, key="SecondItem", location=self.char1)
        self.handler.deposit(item2)
        self.assertIs(self.char1.db._bank_room, room)
        self.assertEqual(self.handler.count_items(), 2)

    def test_delete_bank_room_cleans_up(self):
        self.handler.deposit(self.test_item)
        self.handler.delete_bank_room()
        self.assertIsNone(self.char1.db._bank_room)
        self.assertEqual(self.handler.count_items(), 0)

    def test_deposit_equipped_item_unequips_first(self):
        from typeclasses.items import ToolItem
        from items.equipment.constants import WieldLocation
        equip_item = create_object(
            ToolItem, key="EquipItem", location=self.char1
        )
        equip_item.db.use_slot = WieldLocation.MAIN_HAND
        equip_item.db.tool_type = "hammer"
        self.char1.equipment.equip(equip_item)
        self.assertTrue(self.char1.equipment.is_equipped(equip_item))

        self.handler.deposit(equip_item)
        self.assertFalse(self.char1.equipment.is_equipped(equip_item))
        self.assertNotIn(equip_item, self.char1.contents)
        stored = self.handler.list_items()
        self.assertIn(equip_item, stored)

    def test_withdraw_to_full_inventory_fails(self):
        self.handler.deposit(self.test_item)
        from items.equipment.constants import MAX_INVENTORY_SLOTS
        for i in range(MAX_INVENTORY_SLOTS):
            filler = create_object(BaseItem, key=f"Filler{i}", location=self.char1)
        result = self.handler.withdraw(self.test_item.id)
        self.assertIsNone(result)

    # --- Stackable item tests ---

    def _make_stackable(self, key="credits", quantity=10):
        """Create a stackable BaseItem with the given quantity."""
        obj = create_object(BaseItem, key=key, location=self.char1)
        obj.attributes.add("stackable", True)
        obj.attributes.add("quantity", quantity)
        return obj

    def test_deposit_full_stack_no_existing(self):
        """Depositing a full stackable item moves it to the bank."""
        item = self._make_stackable(quantity=10)
        result = self.handler.deposit(item)
        self.assertIsNotNone(result)
        self.assertEqual(self.handler.count_items(), 1)
        stored = self.handler.list_items()
        self.assertEqual(stored[0].quantity, 10)
        self.assertNotIn(item, self.char1.contents)

    def test_deposit_full_stack_existing(self):
        """Depositing a stackable item merges with existing bank stack."""
        item1 = self._make_stackable(key="credits", quantity=10)
        item2 = self._make_stackable(key="credits", quantity=5)
        self.handler.deposit(item1)
        result = self.handler.deposit(item2)
        self.assertEqual(self.handler.count_items(), 1)
        stored = self.handler.list_items()
        self.assertEqual(stored[0].quantity, 15)
        self.assertNotIn(item2, self.char1.contents)

    def test_deposit_partial_stack_no_existing(self):
        """Partial deposit creates a new bank object with correct quantity."""
        item = self._make_stackable(quantity=10)
        result = self.handler.deposit(item, count=3)
        self.assertIsNotNone(result)
        self.assertEqual(self.handler.count_items(), 1)
        stored = self.handler.list_items()
        self.assertEqual(stored[0].quantity, 3)
        # Original should still be in inventory with reduced quantity
        self.assertIn(item, self.char1.contents)
        self.assertEqual(item.quantity, 7)

    def test_deposit_partial_stack_existing(self):
        """Partial deposit merges into existing bank stack."""
        item1 = self._make_stackable(key="credits", quantity=10)
        item2 = self._make_stackable(key="credits", quantity=10)
        self.handler.deposit(item1)
        result = self.handler.deposit(item2, count=3)
        self.assertEqual(self.handler.count_items(), 1)
        stored = self.handler.list_items()
        self.assertEqual(stored[0].quantity, 13)
        self.assertEqual(item2.quantity, 7)

    def test_deposit_partial_stack_zero_quantity_deletes_item(self):
        """Item with quantity 0 after partial deposit is deleted from inventory."""
        item = self._make_stackable(quantity=5)
        self.handler.deposit(item, count=5)
        self.assertNotIn(item, self.char1.contents)
        self.assertEqual(self.handler.count_items(), 1)

    def test_withdraw_full_stack(self):
        """Full withdrawal moves the entire bank object to inventory."""
        item = self._make_stackable(quantity=10)
        self.handler.deposit(item)
        bank_item = self.handler.list_items()[0]
        result = self.handler.withdraw(bank_item.id)
        self.assertIsNotNone(result)
        self.assertEqual(self.handler.count_items(), 0)
        self.assertIn(bank_item, self.char1.contents)

    def test_withdraw_partial_stack(self):
        """Partial withdrawal creates a new inventory object with correct quantity."""
        item = self._make_stackable(quantity=10)
        self.handler.deposit(item)
        bank_item = self.handler.list_items()[0]
        result = self.handler.withdraw(bank_item.id, count=3)
        self.assertIsNotNone(result)
        self.assertEqual(bank_item.quantity, 7)
        self.assertEqual(self.handler.count_items(), 1)

    def test_deposit_withdraw_cycle_preserves_quantity(self):
        """Deposit 10, withdraw 3, deposit 2 — total preserved."""
        item = self._make_stackable(quantity=10)
        self.handler.deposit(item)
        bank_item = self.handler.list_items()[0]

        # Withdraw 3
        self.handler.withdraw(bank_item.id, count=3)
        # Inventory should have 3 credits (may be merged into existing stack)
        inv_credits = sum(
            obj.quantity for obj in self.char1.contents
            if getattr(obj, "is_stackable", False) and obj.key.lower() == "credits"
        )
        self.assertEqual(inv_credits, 3)

        # Deposit 2 back
        deposit_item = None
        for obj in self.char1.contents:
            if getattr(obj, "is_stackable", False) and obj.key.lower() == "credits":
                deposit_item = obj
                break
        self.assertIsNotNone(deposit_item)
        self.handler.deposit(deposit_item, count=2)

        # Bank should have 9 total (7 remaining + 2 deposited)
        bank_credits = sum(
            obj.quantity for obj in self.handler.list_items()
            if getattr(obj, "is_stackable", False) and obj.key.lower() == "credits"
        )
        self.assertEqual(bank_credits, 9)

    def test_creditsitem_deposit_withdraw(self):
        """CreditsItem specifically works through deposit/withdraw cycle.

        Spawned through ITEM_DB rather than create_object: the typeclass no
        longer carries its own stackable/value defaults, because they only
        restated the ItemDef that overwrote them a moment later.
        """
        from world.item_database import ITEM_DB
        credits = ITEM_DB["credits"].create(location=self.char1, quantity=50)

        # Deposit 20
        self.handler.deposit(credits, count=20)
        bank_items = self.handler.list_items()
        self.assertEqual(len(bank_items), 1)
        self.assertEqual(bank_items[0].quantity, 20)
        self.assertEqual(credits.quantity, 30)

        # Withdraw 10
        result = self.handler.withdraw(bank_items[0].id, count=10)
        self.assertIsNotNone(result)

    def test_delete_bank_room_destroys_items(self):
        """delete_bank_room destroys items, does not scatter them."""
        item = self._make_stackable(quantity=10)
        self.handler.deposit(item)
        bank_items = self.handler.list_items()
        bank_item_id = bank_items[0].id

        self.handler.delete_bank_room()

        # Bank room should be gone
        self.assertIsNone(self.char1.db._bank_room)

        # The bank item should be deleted (not scattered to some room)
        from evennia.utils.create import create_object as _co
        # Verify the item no longer exists in any room's contents
        from evennia.objects.objects import DefaultObject
        # The item should not be in char1's contents
        self.assertNotIn(bank_item_id, [obj.id for obj in self.char1.contents])

    def test_deposit_full_stack_count_equals_quantity(self):
        """When depositing full stack, deposit_qty equals item_qty."""
        item = self._make_stackable(quantity=5)
        self.handler.deposit(item)
        stored = self.handler.list_items()
        self.assertEqual(stored[0].quantity, 5)


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

        moved = self.handler.deposit_many(pile)

        self.assertEqual(moved, 7)
        self.assertEqual(self.handler.count_items(), 7)
        for obj in pile:
            self.assertNotIn(obj, self.char1.contents)

    def test_deposit_many_honours_a_count(self):
        pile = self._make_pile(7)

        moved = self.handler.deposit_many(pile, 3)

        self.assertEqual(moved, 3)
        self.assertEqual(self.handler.count_items(), 3)
        still_carried = [obj for obj in pile if obj in self.char1.contents]
        self.assertEqual(len(still_carried), 4)

    def test_deposit_many_of_empty_list_does_nothing(self):
        moved = self.handler.deposit_many([])

        self.assertEqual(moved, 0)
        self.assertEqual(self.handler.count_items(), 0)

    def test_deposit_many_counts_stack_units_not_objects(self):
        # A single stack contributes its whole size, so the unit count that
        # the menu prompts with matches what actually moves.
        stack = self._make_stack(quantity=10)

        moved = self.handler.deposit_many([stack], 4)

        self.assertEqual(moved, 4)
        stored = self.handler.list_items()
        self.assertEqual(stored[0].quantity, 4)

    def test_withdraw_many_returns_every_copy(self):
        pile = self._make_pile(5)
        self.handler.deposit_many(pile)
        stored = self.handler.list_items()

        moved = self.handler.withdraw_many(stored)

        self.assertEqual(moved, 5)
        self.assertEqual(self.handler.count_items(), 0)

    def test_withdraw_many_honours_a_count(self):
        pile = self._make_pile(5)
        self.handler.deposit_many(pile)
        stored = self.handler.list_items()

        moved = self.handler.withdraw_many(stored, 2)

        self.assertEqual(moved, 2)
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


class TestBankHandlerIsolation(EvenniaTest):
    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.handler1 = BankHandler(self.char1)
        self.handler2 = BankHandler(self.char2)
        self.item = create_object(BaseItem, key="SharedName", location=self.char1)

    def test_characters_have_separate_banks(self):
        self.handler1.deposit(self.item)
        self.assertEqual(self.handler1.count_items(), 1)
        self.assertEqual(self.handler2.count_items(), 0)

    def test_char2_cannot_access_char1_items(self):
        self.handler1.deposit(self.item)
        result = self.handler2.withdraw(self.item.id)
        self.assertIsNone(result)


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
