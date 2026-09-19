"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Cases for shop stock: the level of each ware, the restock, the
             endless ware, and what the shop pop-up draws from them.

             Every level, maximum and interval is read from the ShopDef, never
             typed here, so a retune of the oasis shop re-derives them. Every
             clock is injected, so no case waits or reads the wall clock.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.gameplay.shop.tests.test_stock
"""

from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest, EvenniaTestCase

from systems.gameplay.shop import shop_service, stock
from systems.interface.popups import service
from systems.interface.popups.popup_defs import shop as shop_popup
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.npcs import ShopkeepNPC
from world.item_database import ITEM_DB
from world.shop_defs import SHOP_DB, ShopDef, WareStock


# ─── Private constant definitions ────────────────────────────────────────────

_SHOP_KEY = "oasis_shop"

# A shop with no stock rules, for the endless cases.
_ENDLESS_SHOP_KEY = "test_endless_shop"

# Enough to buy every unit of any ware the oasis shop stocks.
_PURSE = 100_000

# An arbitrary start time for the injected clock.
_T0 = 1_000_000.0


# ─── Private helper routines ─────────────────────────────────────────────────

def _finite_ware() -> tuple:
    """The first (key, WareStock) of the oasis shop with room to count."""
    for key, ware in SHOP_DB[_SHOP_KEY].stock.items():
        if ware.max_stock >= 2:
            return key, ware

    raise AssertionError("the oasis shop has no finite ware of 2 or more")


def _endless_shop() -> ShopDef:
    """A shop that sells the oasis wares with no stock rules."""
    return ShopDef(key=_ENDLESS_SHOP_KEY,
                   buy_list=list(SHOP_DB[_SHOP_KEY].buy_list))


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestStockDefinitions(EvenniaTestCase):
    """Every stock rule names a ware its shop sells, and is usable."""

    def test_every_stocked_ware_is_in_its_buy_list(self):
        for shop_def in SHOP_DB.values():
            for ware_key in shop_def.stock:
                with self.subTest(shop=shop_def.key, ware=ware_key):
                    self.assertIn(ware_key, shop_def.buy_list)

    def test_every_rule_is_well_formed(self):
        for shop_def in SHOP_DB.values():
            for ware_key, ware in shop_def.stock.items():
                with self.subTest(shop=shop_def.key, ware=ware_key):
                    self.assertIn(ware_key, ITEM_DB)
                    self.assertGreaterEqual(ware.max_stock, 0)
                    self.assertGreater(ware.restock_seconds, 0)


class TestStockLevel(EvenniaTestCase):
    """The arithmetic of one ware: take, restock, floor, full."""

    def setUp(self):
        super().setUp()
        self.keeper = create_object(ShopkeepNPC, key="Shopkeeper")
        self.key, self.ware = _finite_ware()

    def test_an_untouched_ware_is_full(self):
        self.assertEqual(self.ware.max_stock, stock.level(self.keeper, self.key, now=_T0))

    def test_a_take_lowers_the_level(self):
        stock.take(self.keeper, self.key, 2, now=_T0)

        self.assertEqual(self.ware.max_stock - 2,
                         stock.level(self.keeper, self.key, now=_T0))

    def test_the_level_never_goes_below_zero(self):
        stock.take(self.keeper, self.key, self.ware.max_stock + 5, now=_T0)

        self.assertEqual(0, stock.level(self.keeper, self.key, now=_T0))

    def test_one_unit_comes_back_each_interval(self):
        stock.take(self.keeper, self.key, 2, now=_T0)
        one_later = _T0 + self.ware.restock_seconds
        almost = one_later - 1

        self.assertEqual(self.ware.max_stock - 2,
                         stock.level(self.keeper, self.key, now=almost))
        self.assertEqual(self.ware.max_stock - 1,
                         stock.level(self.keeper, self.key, now=one_later))

    def test_the_restock_stops_at_the_maximum(self):
        stock.take(self.keeper, self.key, 1, now=_T0)
        much_later = _T0 + self.ware.restock_seconds * 50

        self.assertEqual(self.ware.max_stock,
                         stock.level(self.keeper, self.key, now=much_later))
        self.assertIsNone(stock.next_restock_in(self.keeper, now=much_later))

    def test_a_part_interval_is_kept_across_a_take(self):
        # A second buy half way through an interval must not restart it.
        half = self.ware.restock_seconds / 2
        stock.take(self.keeper, self.key, 2, now=_T0)
        stock.take(self.keeper, self.key, 0, now=_T0 + half)
        stock.take(self.keeper, self.key, 1, now=_T0 + half)

        due = _T0 + self.ware.restock_seconds

        self.assertEqual(self.ware.max_stock - 2,
                         stock.level(self.keeper, self.key, now=due))

    def test_next_restock_counts_down(self):
        self.assertIsNone(stock.next_restock_in(self.keeper, now=_T0))

        stock.take(self.keeper, self.key, 1, now=_T0)
        half = self.ware.restock_seconds / 2

        self.assertEqual(self.ware.restock_seconds,
                         stock.next_restock_in(self.keeper, now=_T0))
        self.assertEqual(half, stock.next_restock_in(self.keeper, now=_T0 + half))

    def test_a_full_shop_stores_nothing(self):
        stock.level(self.keeper, self.key, now=_T0)

        self.assertIsNone(self.keeper.attributes.get(stock.STOCK_STATE_ATTR))


class TestEndlessStock(EvenniaTestCase):
    """A ware with no WareStock never runs out, in any shop."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(SHOP_DB, {_ENDLESS_SHOP_KEY: _endless_shop()})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.keeper = create_object(ShopkeepNPC, key="Shopkeeper")
        self.keeper.db.shopdef_key = _ENDLESS_SHOP_KEY

    def test_an_endless_ware_has_no_level(self):
        for ware_key in SHOP_DB[_ENDLESS_SHOP_KEY].buy_list:
            with self.subTest(ware=ware_key):
                self.assertIsNone(stock.level(self.keeper, ware_key))

    def test_a_take_on_an_endless_ware_stores_nothing(self):
        ware_key = SHOP_DB[_ENDLESS_SHOP_KEY].buy_list[0]

        stock.take(self.keeper, ware_key, 5)

        self.assertIsNone(self.keeper.attributes.get(stock.STOCK_STATE_ATTR))

    def test_an_endless_entry_is_marked_endless(self):
        for entry in shop_service.get_buy_items(self.keeper):
            with self.subTest(ware=entry.key):
                self.assertTrue(entry.endless)


class _BuyFixture(EvenniaCommandTest):
    """The oasis shopkeeper in the room, and a buyer with a full purse."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.keeper = create_object(ShopkeepNPC, key="Shopkeeper", location=self.room1)
        self.keeper.db.shopdef_key = _SHOP_KEY
        self.key, self.ware = _finite_ware()
        ITEM_DB[shop_service.CREDITS_ITEM_KEY].create(
            location=self.char1, quantity=_PURSE)

    def _entry(self):
        for entry in shop_service.get_buy_items(self.keeper, self.char1):
            if entry.key == self.key:
                return entry

        self.fail(f"no {self.key} in the shop")

    def _row(self) -> dict:
        rows = shop_popup._stock_rows(self.keeper, self.char1, 1)

        for row in rows:
            if row["asset"] == self.key:
                return row

        self.fail(f"no {self.key} row in the stock grid")


class TestBuyingLowersTheStock(_BuyFixture):
    """A buy through execute_buy takes from the stock, and stops at 0."""

    def test_a_buy_lowers_the_stock(self):
        shop_service.execute_buy(self.char1, self.keeper, self._entry(), 1)

        self.assertEqual(self.ware.max_stock - 1, stock.level(self.keeper, self.key))

    def test_a_buy_past_the_stock_delivers_only_the_stock(self):
        result = shop_service.execute_buy(
            self.char1, self.keeper, self._entry(), self.ware.max_stock + 3)

        self.assertEqual(self.ware.max_stock, result.bought_count)
        self.assertEqual(self.ware.max_stock * self._entry().buy_price,
                         result.total_price)

    def test_a_sold_out_ware_refuses_and_refunds(self):
        stock.take(self.keeper, self.key, self.ware.max_stock)
        before = shop_service.credits_count(self.char1)

        result = shop_service.execute_buy(self.char1, self.keeper, self._entry(), 1)

        self.assertFalse(result.success)
        self.assertIn("stock", result.error.lower())
        self.assertEqual(before, shop_service.credits_count(self.char1))

    def test_a_held_unit_sells_before_the_stock(self):
        held = ITEM_DB[self.key].create(location=self.keeper)

        shop_service.execute_buy(self.char1, self.keeper, self._entry(), 1)

        self.assertEqual(self.char1, held.location)
        self.assertEqual(self.ware.max_stock, stock.level(self.keeper, self.key))

    def test_the_entry_counts_stock_and_held_units(self):
        ITEM_DB[self.key].create(location=self.keeper)

        self.assertEqual(self.ware.max_stock + 1, self._entry().count)


class TestThePopupDrawsTheStock(_BuyFixture):
    """The stock slot draws the level as a stack count."""

    def test_a_full_ware_shows_its_stock(self):
        self.assertEqual(self.ware.max_stock, self._row()["quantity"])

    def test_a_buy_lowers_the_shown_count(self):
        shop_service.execute_buy(self.char1, self.keeper, self._entry(), 1)

        self.assertEqual(self.ware.max_stock - 1, self._row()["quantity"])

    def test_a_sold_out_ware_stays_dim_and_says_so(self):
        stock.take(self.keeper, self.key, self.ware.max_stock)
        row = self._row()

        self.assertEqual(0, row["quantity"])
        self.assertFalse(row["enabled"])
        self.assertEqual(shop_popup.OUT_OF_STOCK_DETAIL, row["detail"])

    def test_an_endless_ware_shows_no_count(self):
        endless = _endless_shop()

        with mock.patch.dict(SHOP_DB, {_ENDLESS_SHOP_KEY: endless}):
            self.keeper.db.shopdef_key = _ENDLESS_SHOP_KEY
            row = self._row()

        self.assertEqual(shop_popup._ENDLESS_QUANTITY, row["quantity"])


class TestOtherViewersFollowTheStock(_BuyFixture):
    """A buy by one player refreshes every other open pop-up on the keeper."""

    def test_a_buy_marks_the_other_viewer(self):
        service.open_popup(self.char2, shop_popup.SHOP_POPUP_KEY, self.keeper)

        with mock.patch(
                "systems.interface.statefeed.events.refresh_popup") as refresh:
            shop_service.execute_buy(self.char1, self.keeper, self._entry(), 1)

        refresh.assert_any_call(self.char2)

    def test_a_viewer_of_another_anchor_is_not_marked(self):
        other = create_object(ShopkeepNPC, key="Other", location=self.room1)
        service.open_popup(self.char2, shop_popup.SHOP_POPUP_KEY, other)

        with mock.patch(
                "systems.interface.statefeed.events.refresh_popup") as refresh:
            service.refresh_anchor_viewers(self.keeper)

        refresh.assert_not_called()


class TestTheRestockClock(_BuyFixture):
    """One timer for each keeper, and none when the shop is full."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch("twisted.internet.reactor.callLater")
        self.call_later = patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_full_shop_schedules_nothing(self):
        shop_popup._watch_restock(self.keeper, now=_T0)

        self.call_later.assert_not_called()

    def test_repeated_builds_schedule_one_wake(self):
        stock.take(self.keeper, self.key, 1, now=_T0)

        shop_popup._watch_restock(self.keeper, now=_T0)
        shop_popup._watch_restock(self.keeper, now=_T0 + 1)

        self.assertEqual(1, self.call_later.call_count)

    def test_the_wake_refreshes_the_viewers(self):
        with mock.patch.object(service, "refresh_anchor_viewers") as refresh:
            shop_popup._restock_due(self.keeper)

        refresh.assert_called_once_with(self.keeper)
