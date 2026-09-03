"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/02/2026
Description: Tests for the slot-addressed deposit, and for the equipped-item
             claim CmdDeposit's docstring has always made.

             Two things are guarded here.

             The first is targeting. `deposit 7` used to search for an item
             literally NAMED "7" and find nothing, so the slot form took a
             form that had never worked. It has to reach slot seven and no
             other, while the name form goes on meaning every carried copy of
             that name -- which is what the banking menu's grouped rows are
             built on and must not change.

             The second is the docstring. EquipmentHandler.equip holds an
             equipped object at location=None, so _find_carried_group's search
             over caller.contents could never see one and the promise to
             unequip first was untrue for as long as it was written. The route
             taken is EquipmentHandler.remove rather than .unequip, because
             unequip raises at 32/32 -- which would have made `deposit sword`
             fail exactly when the deposit was about to free a slot.

Run with:
    evennia test --settings test_settings.py systems.banking
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from items.equipment.constants import MAX_INVENTORY_SLOTS
from typeclasses.bank_nodes import BankNode, perform_deposit
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.items import BaseItem
from world.item_database import ITEM_DB

# Non-stackable, so a pile of them is a pile of objects and slot targeting is
# a real question.
CHUNK_KEY = "rusty_metal_chunk"

# Stackable, so one object carries a quantity a partial deposit writes onto.
DUST_KEY = "rusty_metal_dust"

PILE_SIZE = 5


class SlotDepositTestBase(EvenniaCommandTest):
    """A bank terminal in the room and a character carrying things."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.bank_node = create_object(
            BankNode, key="bank terminal", location=self.room1)
        self.char1.inventory.sync()

    def _pile(self, count=PILE_SIZE, key=CHUNK_KEY):
        made = [ITEM_DB[key].create(location=self.char1) for _ in range(count)]
        self.char1.inventory.sync()

        return made

    def _slot_number(self, obj):
        return self.char1.inventory.find_slot(obj) + 1

    def _stored_ids(self):
        return {obj.id for obj in self.char1.bank.list_items()}


class TestASlotNamesOneObject(SlotDepositTestBase):

    def test_a_slot_banks_that_object_alone(self):
        pile = self._pile()
        target = pile[-1]

        perform_deposit(self.char1, str(self._slot_number(target)))

        self.assertIn(target.id, self._stored_ids())
        for survivor in pile[:-1]:
            self.assertNotIn(survivor.id, self._stored_ids())

    def test_a_name_still_banks_the_whole_run(self):
        """The group-addressed form is what the menu's rows are built on and
        is deliberately untouched: eleven scrap plates are one row and one
        deposit."""
        pile = self._pile()

        perform_deposit(self.char1, ITEM_DB[CHUNK_KEY].name)

        stored = self._stored_ids()
        for obj in pile:
            self.assertIn(obj.id, stored)

    def test_a_slot_quantity_banks_part_of_a_stack(self):
        stack = ITEM_DB[DUST_KEY].create(location=self.char1, quantity=6)
        self.char1.inventory.sync()

        perform_deposit(self.char1, f"{self._slot_number(stack)} 2")

        self.assertEqual(stack.db.quantity, 4)

    def test_a_slot_with_all_banks_the_whole_stack(self):
        stack = ITEM_DB[DUST_KEY].create(location=self.char1, quantity=6)
        self.char1.inventory.sync()

        perform_deposit(self.char1, f"{self._slot_number(stack)} all")

        self.assertNotIn(stack, self.char1.contents)


class TestEquippedItemsAreUnequippedFirst(SlotDepositTestBase):
    """What CmdDeposit's docstring has always said, now true."""

    def _equip_something(self, key="rusty_scrap_shortsword"):
        weapon = ITEM_DB[key].create(location=self.char1)
        self.char1.inventory.sync()
        self.char1.equipment.equip(weapon)

        return weapon

    def test_an_equipped_item_is_not_in_contents(self):
        """The premise. If this ever stops being true the rest of this class
        is testing nothing."""
        weapon = self._equip_something()

        self.assertNotIn(weapon, self.char1.contents)
        self.assertTrue(self.char1.equipment.is_equipped(weapon))

    def test_an_equipped_item_can_be_banked_by_name(self):
        weapon = self._equip_something()

        perform_deposit(self.char1, weapon.key)

        self.assertIn(weapon.id, self._stored_ids())
        self.assertFalse(self.char1.equipment.is_equipped(weapon))

    def test_the_slot_it_occupied_is_released(self):
        weapon = self._equip_something()
        slot = self.char1.equipment.get_current_slot(weapon)

        perform_deposit(self.char1, weapon.key)

        self.assertIsNone(self.char1.equipment.slots.get(slot))

    def test_a_full_inventory_does_not_block_it(self):
        """The reason the route is EquipmentHandler.remove and not .unequip.

        unequip returns the object to the inventory first and raises at
        32/32, so the round trip manufactured a failure on the one operation
        that was about to free space.
        """
        weapon = self._equip_something()
        filler = []

        while self.char1.inventory.count_used() < MAX_INVENTORY_SLOTS:
            filler.append(ITEM_DB[CHUNK_KEY].create(location=self.char1))
            self.char1.inventory.sync()

        self.assertEqual(self.char1.inventory.count_used(), MAX_INVENTORY_SLOTS)

        perform_deposit(self.char1, weapon.key)

        self.assertIn(weapon.id, self._stored_ids())

    def test_a_carried_copy_is_preferred_over_the_worn_one(self):
        """_bankable_candidates lists contents first, so a player holding a
        spare banks the loose one."""
        weapon = self._equip_something()
        spare = ITEM_DB["rusty_scrap_shortsword"].create(location=self.char1)
        self.char1.inventory.sync()

        perform_deposit(self.char1, f"{self._slot_number(spare)}")

        self.assertIn(spare.id, self._stored_ids())
        self.assertTrue(self.char1.equipment.is_equipped(weapon))


class TestBadArguments(SlotDepositTestBase):

    def test_a_bare_deposit_names_nothing(self):
        banked = perform_deposit(self.char1, "")

        self.assertFalse(banked)

    def test_an_empty_slot_banks_nothing(self):
        banked = perform_deposit(self.char1, "31")

        self.assertFalse(banked)

    def test_a_name_that_matches_nothing_banks_nothing(self):
        create_object(BaseItem, key="a real thing", location=self.char1)
        self.char1.inventory.sync()

        banked = perform_deposit(self.char1, "imaginary widget")

        self.assertFalse(banked)


class TestGroupsOfNonStackables(SlotDepositTestBase):
    """The mirror of the sell side, and it has to stay the mirror.

    bank_nodes._slot_targets and shop_service._entry_for_request encode one
    rule between them: ONE means the slot you named, MORE means the group from
    the lowest slot up. If they disagreed, Sell 1 and Deposit 1 would mean
    different copies of the same eight chunks.
    """

    def _sorted_pile(self, count=PILE_SIZE):
        """A pile, ordered the way the grid holds it."""
        self._pile(count=count)
        self.char1.inventory.sync()
        ordered = []

        for _index, obj in self.char1.inventory.all_items():
            if obj.key == ITEM_DB[CHUNK_KEY].name:
                ordered.append(obj)

        return ordered

    def test_one_banks_the_slot_you_named_not_the_lowest(self):
        pile = self._sorted_pile()
        target = pile[-1]

        perform_deposit(self.char1, f"{self._slot_number(target)} 1")

        stored = self._stored_ids()
        self.assertIn(target.id, stored)
        self.assertNotIn(pile[0].id, stored)

    def test_more_than_one_starts_at_the_lowest_slot(self):
        pile = self._sorted_pile()

        perform_deposit(self.char1, f"{self._slot_number(pile[-1])} 3")

        stored = self._stored_ids()
        for early in pile[:3]:
            self.assertIn(early.id, stored)
        for late in pile[3:]:
            self.assertNotIn(late.id, stored)

    def test_all_banks_every_carried_copy(self):
        pile = self._sorted_pile(count=4)

        perform_deposit(self.char1, f"{self._slot_number(pile[0])} all")

        stored = self._stored_ids()
        for obj in pile:
            self.assertIn(obj.id, stored)

    def test_an_omitted_quantity_still_means_the_named_slot_alone(self):
        pile = self._sorted_pile()
        target = pile[-1]

        perform_deposit(self.char1, str(self._slot_number(target)))

        stored = self._stored_ids()
        self.assertIn(target.id, stored)
        self.assertNotIn(pile[0].id, stored)

    def test_a_group_never_reaches_a_different_item(self):
        pile = self._sorted_pile(count=3)
        other = ITEM_DB["rusty_scrap_metal"].create(location=self.char1)
        self.char1.inventory.sync()

        perform_deposit(self.char1, f"{self._slot_number(pile[0])} all")

        self.assertNotIn(other.id, self._stored_ids())

    def test_a_slot_group_never_reaches_worn_gear(self):
        """carried_group reads the inventory handler, and equipped objects are
        held at location=None. Only the NAME form reaches worn gear, and that
        form takes all of it deliberately -- a slot-addressed `all` stripping
        what the player is wearing would be a very expensive surprise."""
        worn = ITEM_DB["rusty_scrap_shortsword"].create(location=self.char1)
        self.char1.inventory.sync()
        self.char1.equipment.equip(worn)
        spare = ITEM_DB["rusty_scrap_shortsword"].create(location=self.char1)
        self.char1.inventory.sync()

        perform_deposit(self.char1, f"{self._slot_number(spare)} all")

        self.assertIn(spare.id, self._stored_ids())
        self.assertTrue(self.char1.equipment.is_equipped(worn))


class TestWithdrawIsUnaffected(SlotDepositTestBase):
    """`withdraw` targets the VAULT, which has no slots.

    split_item_and_count went three-valued so `deposit 7 all` could differ
    from `deposit 7`. Withdraw has no such distinction to make, so it maps the
    keyword straight back to "as many as there are" -- and this is what keeps
    that mapping honest.
    """

    def test_all_and_an_omitted_quantity_withdraw_the_same(self):
        from typeclasses.bank_nodes import CmdWithdraw

        for phrasing in ("", " all"):
            with self.subTest(phrasing=phrasing or "(omitted)"):
                pile = self._pile(count=3)
                perform_deposit(self.char1, ITEM_DB[CHUNK_KEY].name)
                banked = len(self.char1.bank.list_items())
                self.assertEqual(banked, 3)

                self.call(
                    CmdWithdraw(),
                    f" {ITEM_DB[CHUNK_KEY].name}{phrasing}",
                    caller=self.char1,
                    obj=self.bank_node,
                )

                self.assertEqual(len(self.char1.bank.list_items()), 0)
                for obj in pile:
                    obj.delete()
                self.char1.inventory.sync()
