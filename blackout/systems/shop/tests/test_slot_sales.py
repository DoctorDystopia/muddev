"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/02/2026
Description: Tests for the slot-addressed sale -- perform_sell, sell_entry_for
             and _is_sellable.

             The bug these exist to prevent is the one drop already had and
             was fixed for: eight identical rusty metal chunks are a real
             inventory, and a graphical client right-clicking the eighth of
             them must not sell the first. get_sell_items groups by KEY, which
             is right for a menu the player reads and wrong for a slot the
             player clicked, so the slot path builds its own single-object
             SellEntry.

Run with:
    evennia test --settings test_settings.py systems.shop
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from systems.shop import messages, shop_service
from typeclasses.items import BaseItem
from typeclasses.npcs import ShopkeepNPC
from world.item_database import ITEM_DB

# Non-stackable, tradeable, worth something. Eight of these are eight objects,
# which is what makes the slot-targeting question real.
CHUNK_KEY = "rusty_metal_chunk"

# Stackable, so one object carries a quantity and a partial sale writes onto
# the survivor rather than moving anything.
DUST_KEY = "rusty_metal_dust"

PILE_SIZE = 8
STARTING_CREDITS = 100


class SlotSaleTestBase(EvenniaCommandTest):
    """A shopkeeper in the room and a seller carrying something."""

    def setUp(self):
        super().setUp()
        self.shopkeep = create_object(
            ShopkeepNPC, key="Shopkeeper", location=self.room1)
        self.shopkeep.db.shopdef_key = "oasis_shop"
        ITEM_DB[shop_service.CREDITS_ITEM_KEY].create(
            location=self.char1, quantity=STARTING_CREDITS
        )
        self.char1.inventory.sync()

    def _pile(self, count=PILE_SIZE, key=CHUNK_KEY):
        """`count` separate objects of one kind, in grid order."""
        made = [ITEM_DB[key].create(location=self.char1) for _ in range(count)]
        self.char1.inventory.sync()

        return made

    def _slot_number(self, obj):
        """The 1-based slot the player and the pane both name."""
        return self.char1.inventory.find_slot(obj) + 1


class TestASlotNamesOneObject(SlotSaleTestBase):
    """The whole reason this path exists."""

    def test_selling_the_last_slot_sells_that_object(self):
        pile = self._pile()
        target = pile[-1]
        slot = self._slot_number(target)

        shop_service.perform_sell(self.char1, self.shopkeep, str(slot))

        self.assertEqual(target.location, self.shopkeep)
        for survivor in pile[:-1]:
            self.assertEqual(survivor.location, self.char1)

    def test_selling_one_slot_leaves_the_rest_of_the_pile(self):
        pile = self._pile()
        slot = self._slot_number(pile[0])

        shop_service.perform_sell(self.char1, self.shopkeep, str(slot))

        still_carried = [obj for obj in pile if obj.location == self.char1]
        self.assertEqual(len(still_carried), PILE_SIZE - 1)

    def test_a_unique_name_sells_that_object(self):
        pile = self._pile(count=1)

        shop_service.perform_sell(
            self.char1, self.shopkeep, ITEM_DB[CHUNK_KEY].name)

        self.assertEqual(pile[0].location, self.shopkeep)

    def test_an_ambiguous_name_sells_nothing(self):
        """`sell` is SLOT-addressed, and the name form inherits caller.search
        -- which refuses a name matching several objects and says so itself.

        This is the same refusal `equip` and `drop` give, and it is the point:
        a name the server cannot resolve to one object must not resolve to
        the lowest-numbered one. A player who means a particular chunk uses
        its slot number, or Evennia's own `2-rusty metal chunk`.
        """
        pile = self._pile()

        sold = shop_service.perform_sell(
            self.char1, self.shopkeep, ITEM_DB[CHUNK_KEY].name)

        self.assertFalse(sold)
        still_carried = [obj for obj in pile if obj.location == self.char1]
        self.assertEqual(len(still_carried), PILE_SIZE)


class TestQuantities(SlotSaleTestBase):

    def test_no_quantity_sells_the_whole_stack(self):
        stack = ITEM_DB[DUST_KEY].create(location=self.char1, quantity=6)
        self.char1.inventory.sync()
        slot = self._slot_number(stack)

        shop_service.perform_sell(self.char1, self.shopkeep, str(slot))

        self.assertFalse(stack.pk, "the drained stack should be deleted")

    def test_a_partial_quantity_leaves_the_remainder(self):
        stack = ITEM_DB[DUST_KEY].create(location=self.char1, quantity=6)
        self.char1.inventory.sync()
        slot = self._slot_number(stack)

        shop_service.perform_sell(self.char1, self.shopkeep, f"{slot} 2")

        self.assertEqual(stack.db.quantity, 4)

    def test_a_quantity_above_the_stack_clamps(self):
        """Asking for more than is there is a reasonable way to say 'all of
        it' -- parse_quantity's rule, applied to the same question."""
        stack = ITEM_DB[DUST_KEY].create(location=self.char1, quantity=3)
        self.char1.inventory.sync()
        slot = self._slot_number(stack)

        shop_service.perform_sell(self.char1, self.shopkeep, f"{slot} 99")

        self.assertFalse(stack.pk)

    def test_all_sells_every_carried_copy(self):
        """`all` widened on 09/02/2026. It used to mean "the stack in that
        slot", which for a non-stackable was one object and made Sell All
        indistinguishable from Sell 1."""
        pile = self._pile(count=3)
        slot = self._slot_number(pile[0])

        shop_service.perform_sell(self.char1, self.shopkeep, f"{slot} all")

        still_carried = [obj for obj in pile if obj.location == self.char1]
        self.assertEqual(len(still_carried), 0)

    def test_all_typed_at_a_high_slot_still_takes_the_whole_group(self):
        pile = self._pile(count=3)
        slot = self._slot_number(pile[-1])

        shop_service.perform_sell(self.char1, self.shopkeep, f"{slot} all")

        still_carried = [obj for obj in pile if obj.location == self.char1]
        self.assertEqual(len(still_carried), 0)

    def test_a_sale_pays(self):
        stack = ITEM_DB[DUST_KEY].create(location=self.char1, quantity=4)
        self.char1.inventory.sync()
        slot = self._slot_number(stack)
        before = shop_service.credits_count(self.char1)

        shop_service.perform_sell(self.char1, self.shopkeep, f"{slot} 2")

        after = shop_service.credits_count(self.char1)
        self.assertGreater(after, before)


class TestWhatTheShopRefuses(SlotSaleTestBase):
    """Every refusal is _is_sellable's answer, read once.

    Asserted against the predicate rather than against a list of item keys,
    so an item added tomorrow is covered without an edit here.
    """

    def _refused(self, obj):
        slot = self._slot_number(obj)
        sold = shop_service.perform_sell(self.char1, self.shopkeep, str(slot))

        self.assertFalse(sold)
        self.assertFalse(shop_service._is_sellable(obj))
        self.assertIsNone(
            shop_service.sell_entry_for(self.char1, self.shopkeep, obj))

    def test_currency_is_refused(self):
        credits = None

        for obj in self.char1.contents:
            if shop_service._is_currency(obj):
                credits = obj

        self._refused(credits)

    def test_an_untradeable_item_is_refused(self):
        obj = create_object(BaseItem, key="bound relic", location=self.char1)
        obj.attributes.add("tradeable", False)
        obj.attributes.add("value", 50)
        self.char1.inventory.sync()

        self._refused(obj)

    def test_a_worthless_item_is_refused(self):
        obj = create_object(BaseItem, key="scrap of nothing", location=self.char1)
        obj.attributes.add("value", 0)
        self.char1.inventory.sync()

        self._refused(obj)

    def test_the_refusal_names_the_shopkeeper_and_the_item(self):
        """A refusal that named neither would read as a broken click.

        Keyword assertions, not the whole sentence, so a copy edit does not
        fail this.
        """
        line = messages.format_not_wanted(self.shopkeep.key, "scrap of nothing")

        self.assertIn(self.shopkeep.key, line)
        self.assertIn("scrap of nothing", line)


class TestSellEntryPricing(SlotSaleTestBase):

    def test_a_slot_entry_holds_only_the_object_it_names(self):
        pile = self._pile()

        entry = shop_service.sell_entry_for(self.char1, self.shopkeep, pile[3])

        self.assertEqual(entry.items, [pile[3]])
        self.assertEqual(entry.count, 1)

    def test_a_slot_entry_prices_as_the_menu_does(self):
        """The miser factor has one owner, so a slot sale and a menu sale of
        the same object must pay the same."""
        pile = self._pile(count=1)
        grouped = shop_service.get_sell_items(self.char1, self.shopkeep)
        matching = [e for e in grouped if e.name == pile[0].key]

        entry = shop_service.sell_entry_for(self.char1, self.shopkeep, pile[0])

        self.assertEqual(entry.unit_price, matching[0].unit_price)

    def test_a_stack_entry_counts_its_units(self):
        stack = ITEM_DB[DUST_KEY].create(location=self.char1, quantity=5)

        entry = shop_service.sell_entry_for(self.char1, self.shopkeep, stack)

        self.assertEqual(entry.count, 5)


class TestBadArguments(SlotSaleTestBase):

    def test_a_bare_sell_names_nothing(self):
        sold = shop_service.perform_sell(self.char1, self.shopkeep, "")

        self.assertFalse(sold)

    def test_an_empty_slot_sells_nothing(self):
        sold = shop_service.perform_sell(self.char1, self.shopkeep, "31")

        self.assertFalse(sold)

    def test_a_name_that_matches_nothing_sells_nothing(self):
        sold = shop_service.perform_sell(
            self.char1, self.shopkeep, "imaginary widget")

        self.assertFalse(sold)


class TestGroupsOfNonStackables(SlotSaleTestBase):
    """Eight rusty metal chunks are eight objects, and 1 / X / All has to mean
    something for all three.

    The rule, and the asymmetry in it, is shop_service._entry_for_request:
    ONE means the slot you named, MORE means the group from the lowest slot
    up. Sell 1 keeping the clicked slot is what stops the 08/17/2026 bug
    coming back -- right-clicking the eighth chunk and selling the first.
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

    def test_one_sells_the_slot_you_named_not_the_lowest(self):
        pile = self._sorted_pile()
        target = pile[-1]
        slot = self._slot_number(target)

        shop_service.perform_sell(self.char1, self.shopkeep, f"{slot} 1")

        self.assertEqual(target.location, self.shopkeep)
        self.assertEqual(pile[0].location, self.char1)

    def test_more_than_one_starts_at_the_lowest_slot(self):
        pile = self._sorted_pile()
        slot = self._slot_number(pile[-1])

        shop_service.perform_sell(self.char1, self.shopkeep, f"{slot} 3")

        for early in pile[:3]:
            self.assertEqual(early.location, self.shopkeep)
        for late in pile[3:]:
            self.assertEqual(late.location, self.char1)

    def test_a_group_sale_pays_for_every_copy(self):
        pile = self._sorted_pile(count=4)
        slot = self._slot_number(pile[0])
        entry = shop_service.sell_entry_for(self.char1, self.shopkeep, pile[0])
        unit_price = entry.unit_price
        before = shop_service.credits_count(self.char1)

        shop_service.perform_sell(self.char1, self.shopkeep, f"{slot} 3")

        after = shop_service.credits_count(self.char1)
        self.assertEqual(after - before, unit_price * 3)

    def test_a_quantity_above_the_group_clamps_to_it(self):
        pile = self._sorted_pile(count=3)
        slot = self._slot_number(pile[0])

        shop_service.perform_sell(self.char1, self.shopkeep, f"{slot} 99")

        still_carried = [obj for obj in pile if obj.location == self.char1]
        self.assertEqual(len(still_carried), 0)

    def test_a_group_never_reaches_a_different_item(self):
        pile = self._sorted_pile(count=3)
        other = ITEM_DB["rusty_scrap_metal"].create(location=self.char1)
        self.char1.inventory.sync()
        slot = self._slot_number(pile[0])

        shop_service.perform_sell(self.char1, self.shopkeep, f"{slot} all")

        self.assertEqual(other.location, self.char1)

    def test_the_group_entry_is_slot_ascending(self):
        pile = self._sorted_pile()

        entry = shop_service.sell_entry_for_group(
            self.char1, self.shopkeep, pile[-1])

        self.assertEqual(entry.items, pile)

    def test_the_group_entry_counts_every_copy(self):
        pile = self._sorted_pile()

        entry = shop_service.sell_entry_for_group(
            self.char1, self.shopkeep, pile[0])

        self.assertEqual(entry.count, PILE_SIZE)

    def test_an_omitted_quantity_still_means_the_named_slot_alone(self):
        pile = self._sorted_pile()
        target = pile[-1]

        shop_service.perform_sell(
            self.char1, self.shopkeep, str(self._slot_number(target)))

        self.assertEqual(target.location, self.shopkeep)
        still_carried = [obj for obj in pile if obj.location == self.char1]
        self.assertEqual(len(still_carried), PILE_SIZE - 1)
