"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/17/2026
Description: Tests for how a shop hands goods over and takes them back --
             where a bought item ends up, what a full grid does to a
             purchase, and whether a sale releases the slot it used.

             The bug these cover: a pre-stocked ware was delivered with
             `obj.location = caller`, which does not fire at_object_receive,
             so a bought item reached the buyer's contents with no inventory
             slot, no stack merge and no state-feed snapshot. Because
             at_pre_object_receive never ran either, the 32/32 veto was
             bypassed and a full player could keep buying. execute_sell had
             the mirror-image problem with at_object_leave.

Run with:
    evennia test --settings settings.py systems.shop
"""


from unittest import mock

from evennia import create_object
from evennia.objects.models import ObjectDB
from evennia.utils.test_resources import EvenniaCommandTest

from items.inventory.handler import InventoryHandler
from systems.shop import shop_service
from typeclasses.npcs import ShopkeepNPC
from world.item_database import ITEM_DB

# In the oasis shop's buy_list, so it is offered as a prototype.
PROTOTYPE_KEY = "hammer"

# NOT in the buy_list, so stocking one in the shopkeeper's contents produces
# the other kind of BuyEntry -- the pre-stocked object that was being handed
# over by direct location assignment.
STOCK_KEY = "rusty_scrap_shortsword"

STARTING_CREDITS = 1000


class ShopTradeTestBase(EvenniaCommandTest):
    """A shopkeeper in the room and a buyer who can afford things."""

    def setUp(self):
        super().setUp()
        self.shopkeep = create_object(
            ShopkeepNPC, key="Shopkeeper", location=self.room1)
        self.shopkeep.db.shopdef_key = "oasis_shop"
        self._give_credits(STARTING_CREDITS)

    def _give_credits(self, amount):
        return ITEM_DB[shop_service.CREDITS_ITEM_KEY].create(
            location=self.char1, quantity=amount
        )

    def _buy_entry(self, key):
        """The BuyEntry the shop menu would have handed to execute_buy."""
        entries = shop_service.get_buy_items(self.shopkeep, self.char1)

        for entry in entries:
            if entry.key == key:
                return entry

        return None

    def _stock_shopkeeper(self):
        """Put one physical ware on the shopkeeper, as a spawner would."""
        return ITEM_DB[STOCK_KEY].create(location=self.shopkeep)

    def _sell_entry(self, name):
        entries = shop_service.get_sell_items(self.char1, self.shopkeep)

        for entry in entries:
            if entry.name == name:
                return entry

        return None


class TestBoughtGoodsReachTheGrid(ShopTradeTestBase):
    """Whether the buyer's 32-slot grid knows about what it just bought."""

    def test_bought_prototype_occupies_an_inventory_slot(self):
        entry = self._buy_entry(PROTOTYPE_KEY)

        result = shop_service.execute_buy(self.char1, self.shopkeep, entry)

        self.assertTrue(result.success)
        self.assertEqual(result.bought_count, 1)
        bought = self.char1.search(entry.name, location=self.char1, quiet=True)
        self.assertTrue(bought)
        slot = self.char1.inventory.find_slot(bought[0])
        self.assertGreaterEqual(slot, 0)

    def test_bought_stock_item_occupies_an_inventory_slot(self):
        stocked = self._stock_shopkeeper()
        entry = self._buy_entry(STOCK_KEY)
        self.assertFalse(entry.is_prototype)

        result = shop_service.execute_buy(self.char1, self.shopkeep, entry)

        self.assertTrue(result.success)
        self.assertEqual(stocked.location, self.char1)
        slot = self.char1.inventory.find_slot(stocked)
        self.assertGreaterEqual(slot, 0)

    def test_the_purchase_is_charged_for(self):
        entry = self._buy_entry(PROTOTYPE_KEY)

        result = shop_service.execute_buy(self.char1, self.shopkeep, entry, 2)

        self.assertEqual(result.bought_count, 2)
        self.assertEqual(result.total_price, 2 * entry.buy_price)
        credits = shop_service.credits_count(self.char1)
        self.assertEqual(credits, STARTING_CREDITS - 2 * entry.buy_price)


class TestAFullGridRefusesThePurchase(ShopTradeTestBase):
    """A buyer at 32/32 keeps their credits and the shop keeps its goods --
    nothing is dropped on the shop floor, which is the one thing a purchase
    can do that a craft cannot."""

    def test_purchase_fails_and_credits_are_refunded(self):
        entry = self._buy_entry(PROTOTYPE_KEY)

        with mock.patch.object(InventoryHandler, "can_accept", return_value=False):
            result = shop_service.execute_buy(self.char1, self.shopkeep, entry)

        self.assertFalse(result.success)
        self.assertEqual(result.error, shop_service._NO_ROOM_ERROR)
        credits = shop_service.credits_count(self.char1)
        self.assertEqual(credits, STARTING_CREDITS)

    def test_no_undeliverable_copy_is_left_behind(self):
        entry = self._buy_entry(PROTOTYPE_KEY)

        with mock.patch.object(InventoryHandler, "can_accept", return_value=False):
            shop_service.execute_buy(self.char1, self.shopkeep, entry)

        # Anywhere at all: carried, on the floor, or detached at location
        # None, which is where a refused move_to leaves a fresh spawn.
        strays = ObjectDB.objects.filter(db_key=entry.name)
        self.assertEqual(strays.count(), 0)

    def test_stocked_ware_stays_with_the_shopkeeper(self):
        stocked = self._stock_shopkeeper()
        entry = self._buy_entry(STOCK_KEY)

        with mock.patch.object(InventoryHandler, "can_accept", return_value=False):
            result = shop_service.execute_buy(self.char1, self.shopkeep, entry)

        self.assertFalse(result.success)
        self.assertEqual(stocked.location, self.shopkeep)
        self.assertNotEqual(stocked.location, self.room1)

    def test_a_partial_delivery_refunds_the_rest(self):
        entry = self._buy_entry(PROTOTYPE_KEY)

        # Room for one of the three, then the grid fills up.
        with mock.patch.object(
            InventoryHandler, "can_accept", side_effect=[True, False]
        ):
            result = shop_service.execute_buy(self.char1, self.shopkeep, entry, 3)

        self.assertTrue(result.success)
        self.assertEqual(result.bought_count, 1)
        self.assertEqual(result.total_price, entry.buy_price)
        credits = shop_service.credits_count(self.char1)
        self.assertEqual(credits, STARTING_CREDITS - entry.buy_price)


class TestSoldGoodsLeaveTheGrid(ShopTradeTestBase):
    """The mirror image: at_object_leave has to run, or the slot stays
    spoken for by an item the shopkeeper now owns."""

    def test_sold_item_releases_its_inventory_slot(self):
        sword = ITEM_DB[STOCK_KEY].create(location=self.char1)
        self.assertGreaterEqual(self.char1.inventory.find_slot(sword), 0)
        entry = self._sell_entry(sword.key)

        result = shop_service.execute_sell(self.char1, self.shopkeep, entry)

        self.assertTrue(result.success)
        self.assertEqual(result.sold_count, 1)
        self.assertEqual(sword.location, self.shopkeep)
        self.assertEqual(self.char1.inventory.find_slot(sword), -1)

    def test_a_refused_handover_is_not_paid_for(self):
        sword = ITEM_DB[STOCK_KEY].create(location=self.char1)
        entry = self._sell_entry(sword.key)

        with mock.patch.object(type(sword), "move_to", return_value=False):
            result = shop_service.execute_sell(self.char1, self.shopkeep, entry)

        self.assertEqual(result.sold_count, 0)
        self.assertEqual(result.total_price, 0)
        self.assertEqual(sword.location, self.char1)
        credits = shop_service.credits_count(self.char1)
        self.assertEqual(credits, STARTING_CREDITS)


class TestTradePublishesInventory(ShopTradeTestBase):
    """The snapshot the graphical inventory pane redraws from. The goods
    move through hooks that publish, but the credits never do."""

    def test_buying_publishes_a_snapshot(self):
        entry = self._buy_entry(PROTOTYPE_KEY)

        with mock.patch(
            "systems.statefeed.events.emit_inventory"
        ) as emit_inventory:
            shop_service.execute_buy(self.char1, self.shopkeep, entry)

        emit_inventory.assert_called_with(self.char1)

    def test_selling_publishes_a_snapshot(self):
        sword = ITEM_DB[STOCK_KEY].create(location=self.char1)
        entry = self._sell_entry(sword.key)

        with mock.patch(
            "systems.statefeed.events.emit_inventory"
        ) as emit_inventory:
            shop_service.execute_sell(self.char1, self.shopkeep, entry)

        emit_inventory.assert_called_with(self.char1)

    def test_a_raising_feed_does_not_lose_the_trade(self):
        entry = self._buy_entry(PROTOTYPE_KEY)

        with mock.patch(
            "systems.statefeed.events.emit_inventory",
            side_effect=RuntimeError("feed exploded"),
        ):
            result = shop_service.execute_buy(self.char1, self.shopkeep, entry)

        self.assertTrue(result.success)

    def test_selling_part_of_a_stack_publishes_though_nothing_moved(self):
        """The sell-side case the snapshot exists for. Draining part of a
        stack is a bare `obj.db.quantity` write and the payment is a bare
        `quantity` write on the credits stack -- neither is a move, so no
        hook of the seller's fires and this is the only publish in the
        transaction."""
        dust = ITEM_DB["rusty_metal_dust"].create(location=self.char1, quantity=5)
        entry = self._sell_entry(dust.key)

        with mock.patch(
            "systems.statefeed.events.emit_inventory"
        ) as emit_inventory:
            result = shop_service.execute_sell(self.char1, self.shopkeep, entry, 2)

        self.assertEqual(result.sold_count, 2)
        self.assertEqual(dust.quantity, 3)
        emit_inventory.assert_called_once_with(self.char1)

    def test_a_refused_purchase_publishes_the_refund(self):
        """Nothing reached the buyer and nothing left them, so no move hook
        ran -- but the credits stack was written twice, down for the charge
        and back up for the refund. Without this publish the pane would go on
        drawing the mid-transaction figure."""
        entry = self._buy_entry(PROTOTYPE_KEY)

        with mock.patch.object(InventoryHandler, "can_accept", return_value=False):
            with mock.patch(
                "systems.statefeed.events.emit_inventory"
            ) as emit_inventory:
                result = shop_service.execute_buy(self.char1, self.shopkeep, entry)

        self.assertFalse(result.success)
        emit_inventory.assert_called_once_with(self.char1)
