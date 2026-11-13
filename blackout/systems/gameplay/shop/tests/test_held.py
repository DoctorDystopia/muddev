"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/03/2026
Description: Cases for the held units of a shopkeep: the decay to the base
             stock, the hold of a sold stack, the buy of part of a held
             stack, and the pop-up wake for a decay step.

             Every key, maximum and step is read from SHOP_DB and ITEM_DB,
             never typed here. Thus a retune of the oasis shop re-derives
             them. Every decay clock is injected, so no case waits.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.gameplay.shop.tests.test_held
"""

import time
import unittest
from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from items import stacking
from systems.gameplay.shop import held, shop_service, stock
from systems.interface.popups.popup_defs import shop as shop_popup
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.npcs import ShopkeepNPC
from world.item_database import ITEM_DB
from world.shop_defs import SHOP_DB, ShopDef


# ─── Private constant definitions ────────────────────────────────────────────

_SHOP_KEY = "oasis_shop"

# A shop with no stock rules, for the endless case.
_ENDLESS_SHOP_KEY = "test_endless_held_shop"

# An arbitrary start time for the injected clock.
_T0 = 1_000_000.0

# Enough to buy any held stack in these cases.
_PURSE = 100_000

# The units of a test stack, and the units that a part sale or buy moves.
_STACK_UNITS = 5
_PART_UNITS = 2


# ─── Private helper routines ─────────────────────────────────────────────────

def _step() -> float:
    """The decay step of the oasis shop."""
    return SHOP_DB[_SHOP_KEY].decay_seconds


def _finite_ware() -> tuple:
    """The first (key, WareStock) of the oasis shop with room to count."""
    for key, ware in SHOP_DB[_SHOP_KEY].stock.items():
        if ware.max_stock >= 2:
            return key, ware

    raise AssertionError("the oasis shop has no finite ware of 2 or more")


def _item_not_sold(stackable: bool) -> str:
    """
    The first ITEM_DB key that the oasis shop does not sell, that a player
    can sell, and whose display name names no other item.
    """
    buy_list = set(SHOP_DB[_SHOP_KEY].buy_list)
    names = [defn.name.lower() for defn in ITEM_DB.values()]

    for key, defn in sorted(ITEM_DB.items()):
        unique = names.count(defn.name.lower()) == 1
        sellable = defn.tradeable and defn.value > 0
        fits = defn.stackable == stackable and key not in buy_list

        if unique and sellable and fits and key != shop_service.CREDITS_ITEM_KEY:
            return key

    raise AssertionError(f"no sellable item outside the shop, stackable={stackable}")


def _held_units(keeper, item_key: str) -> int:
    """The units of one item that the keeper holds."""
    objs = [obj for obj in held.held_objects(keeper)
            if held.held_key(obj) == item_key]

    return stacking.available_units(objs)


def _oasis_keeper(location=None):
    """A shopkeep of the oasis shop."""
    keeper = create_object(ShopkeepNPC, key="Shopkeeper", location=location)
    keeper.db.shopdef_key = _SHOP_KEY

    return keeper


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestTheDecayDefinitions(unittest.TestCase):
    """Every shop has a decay step that a clock can count."""

    def test_every_decay_step_is_positive(self):
        for shop_def in SHOP_DB.values():
            with self.subTest(shop=shop_def.key):
                self.assertGreater(shop_def.decay_seconds, 0)


class TestTheBaseStock(EvenniaTestCase):
    """max_stock for a finite ware, 0 for every other item."""

    def setUp(self):
        super().setUp()
        self.keeper = _oasis_keeper()

    def test_a_finite_ware_has_its_max_stock(self):
        key, ware = _finite_ware()

        self.assertEqual(ware.max_stock, held.base_stock(self.keeper, key))

    def test_an_item_not_sold_has_no_base(self):
        key = _item_not_sold(stackable=False)

        self.assertEqual(0, held.base_stock(self.keeper, key))

    def test_an_endless_ware_has_no_base(self):
        endless = ShopDef(key=_ENDLESS_SHOP_KEY,
                          buy_list=list(SHOP_DB[_SHOP_KEY].buy_list))

        with mock.patch.dict(SHOP_DB, {_ENDLESS_SHOP_KEY: endless}):
            self.keeper.db.shopdef_key = _ENDLESS_SHOP_KEY

            for ware_key in endless.buy_list:
                with self.subTest(ware=ware_key):
                    self.assertEqual(0, held.base_stock(self.keeper, ware_key))


class TestAnItemNotSoldDecaysToNothing(EvenniaTestCase):
    """One unit for each step, down to zero, then nothing is stored."""

    def setUp(self):
        super().setUp()
        self.keeper = _oasis_keeper()
        self.key = _item_not_sold(stackable=False)

        for _ in range(3):
            ITEM_DB[self.key].create(location=self.keeper)

    def test_the_first_settle_starts_the_clock(self):
        removed = held.settle(self.keeper, now=_T0)

        self.assertEqual(0, removed)
        self.assertEqual({self.key: _T0},
                         self.keeper.attributes.get(held.DECAY_STATE_ATTR))

    def test_one_unit_goes_at_each_step(self):
        held.settle(self.keeper, now=_T0)

        held.settle(self.keeper, now=_T0 + _step() - 1)
        self.assertEqual(3, _held_units(self.keeper, self.key))

        held.settle(self.keeper, now=_T0 + _step())
        self.assertEqual(2, _held_units(self.keeper, self.key))

    def test_the_decay_ends_at_nothing(self):
        held.settle(self.keeper, now=_T0)
        held.settle(self.keeper, now=_T0 + _step() * 50)

        self.assertEqual(0, _held_units(self.keeper, self.key))
        self.assertIsNone(self.keeper.attributes.get(held.DECAY_STATE_ATTR))

    def test_a_part_step_is_kept(self):
        held.settle(self.keeper, now=_T0)
        held.settle(self.keeper, now=_T0 + _step() * 1.5)
        held.settle(self.keeper, now=_T0 + _step() * 2)

        self.assertEqual(1, _held_units(self.keeper, self.key))

    def test_next_decay_counts_down(self):
        self.assertIsNone(held.next_decay_in(self.keeper, now=_T0))

        held.settle(self.keeper, now=_T0)
        half = _step() / 2

        self.assertEqual(_step(), held.next_decay_in(self.keeper, now=_T0))
        self.assertEqual(half, held.next_decay_in(self.keeper, now=_T0 + half))


class TestAHeldStackDecaysByUnit(EvenniaTestCase):
    """A step takes one unit off a stack, not the whole stack."""

    def test_two_steps_take_two_units(self):
        keeper = _oasis_keeper()
        key = _item_not_sold(stackable=True)
        stack = ITEM_DB[key].create(location=keeper, quantity=_STACK_UNITS)

        held.settle(keeper, now=_T0)
        held.settle(keeper, now=_T0 + _step() * 2)

        self.assertEqual(_STACK_UNITS - 2, stack.quantity)


class TestAWareDecaysToItsMaxStock(EvenniaTestCase):
    """The level plus the held units moves back to max_stock."""

    def setUp(self):
        super().setUp()
        self.keeper = _oasis_keeper()
        self.key, self.ware = _finite_ware()

    def test_the_held_units_of_a_full_ware_decay_to_nothing(self):
        for _ in range(2):
            ITEM_DB[self.key].create(location=self.keeper)

        held.settle(self.keeper, now=_T0)
        held.settle(self.keeper, now=_T0 + _step() * 50)

        self.assertEqual(0, _held_units(self.keeper, self.key))

    def test_held_units_that_fill_a_short_ware_stay(self):
        stock.take(self.keeper, self.key, 2, now=_T0)
        ITEM_DB[self.key].create(location=self.keeper)
        objs = held.held_objects(self.keeper)

        held.settle(self.keeper, now=_T0)

        self.assertEqual(-1, held.surplus(self.keeper, self.key, objs, now=_T0))
        self.assertEqual(1, _held_units(self.keeper, self.key))
        self.assertIsNone(self.keeper.attributes.get(held.DECAY_STATE_ATTR))


class TestALookSettles(EvenniaTestCase):
    """Each reader of the stock comes through get_buy_items, which settles."""

    def test_get_buy_items_settles_first(self):
        keeper = _oasis_keeper()

        with mock.patch.object(held, "settle") as settle:
            shop_service.get_buy_items(keeper)

        settle.assert_called_once_with(keeper)


class _TradeFixture(EvenniaTest):
    """The oasis shopkeep in the room, and a player with a full purse."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.keeper = _oasis_keeper(location=self.room1)
        self.key = _item_not_sold(stackable=True)
        ITEM_DB[shop_service.CREDITS_ITEM_KEY].create(
            location=self.char1, quantity=_PURSE)

    def _sell(self, stack, units: int):
        entry = shop_service.sell_entry_for(self.char1, self.keeper, stack)

        return shop_service.execute_sell(self.char1, self.keeper, entry, units)

    def _buy_entry(self):
        for entry in shop_service.get_buy_items(self.keeper, self.char1):
            if entry.key == self.key:
                return entry

        self.fail(f"no {self.key} in the shop")


class TestASoldStackIsHeld(_TradeFixture):
    """The units of a sold stack go to the shopkeep, not to nothing."""

    def test_a_part_sale_holds_the_sold_units(self):
        stack = ITEM_DB[self.key].create(location=self.char1, quantity=_STACK_UNITS)

        self._sell(stack, _PART_UNITS)

        self.assertEqual(_STACK_UNITS - _PART_UNITS, stack.quantity)
        self.assertEqual(_PART_UNITS, _held_units(self.keeper, self.key))

    def test_two_sales_make_one_held_stack(self):
        first = ITEM_DB[self.key].create(location=self.char1, quantity=_STACK_UNITS)
        self._sell(first, _PART_UNITS)
        self._sell(first, _STACK_UNITS - _PART_UNITS)
        stacks = [obj for obj in held.held_objects(self.keeper)
                  if held.held_key(obj) == self.key]

        self.assertEqual(1, len(stacks))
        self.assertEqual(_STACK_UNITS, stacks[0].quantity)

    def test_a_sale_starts_the_clock(self):
        stack = ITEM_DB[self.key].create(location=self.char1, quantity=_STACK_UNITS)

        self._sell(stack, _PART_UNITS)
        stamps = self.keeper.attributes.get(held.DECAY_STATE_ATTR)

        self.assertIn(self.key, stamps)

    def test_an_old_stamp_does_not_remove_the_new_units(self):
        ITEM_DB[self.key].create(location=self.keeper, quantity=1)
        long_ago = time.time() - _step() * 100
        self.keeper.attributes.add(held.DECAY_STATE_ATTR, {self.key: long_ago})
        stack = ITEM_DB[self.key].create(location=self.char1, quantity=_STACK_UNITS)

        self._sell(stack, _STACK_UNITS)

        self.assertEqual(_STACK_UNITS, _held_units(self.keeper, self.key))


class TestBuyingAHeldStack(_TradeFixture):
    """A held stack sells by the unit."""

    def setUp(self):
        super().setUp()
        self.held_stack = ITEM_DB[self.key].create(
            location=self.keeper, quantity=_STACK_UNITS)

    def _carried_units(self) -> int:
        objs = [obj for obj in self.char1.contents
                if held.held_key(obj) == self.key]

        return stacking.available_units(objs)

    def test_the_entry_counts_units(self):
        self.assertEqual(_STACK_UNITS, self._buy_entry().count)

    def test_a_part_buy_splits_the_held_stack(self):
        entry = self._buy_entry()

        result = shop_service.execute_buy(self.char1, self.keeper, entry, _PART_UNITS)

        self.assertEqual(_PART_UNITS, result.bought_count)
        self.assertEqual(_PART_UNITS * entry.buy_price, result.total_price)
        self.assertEqual(_PART_UNITS, self._carried_units())
        self.assertEqual(_STACK_UNITS - _PART_UNITS,
                         _held_units(self.keeper, self.key))

    def test_a_whole_buy_takes_the_held_stack(self):
        entry = self._buy_entry()

        result = shop_service.execute_buy(self.char1, self.keeper, entry, _STACK_UNITS)

        self.assertEqual(_STACK_UNITS, result.bought_count)
        self.assertEqual(_STACK_UNITS, self._carried_units())
        self.assertEqual(0, _held_units(self.keeper, self.key))


class TestThePopupWakesForADecay(EvenniaTestCase):
    """A surplus alone schedules a wake at the next decay step."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch("twisted.internet.reactor.callLater")
        self.call_later = patcher.start()
        self.addCleanup(patcher.stop)
        self.keeper = _oasis_keeper()

    def test_a_surplus_schedules_one_wake(self):
        key = _item_not_sold(stackable=False)
        ITEM_DB[key].create(location=self.keeper)
        held.settle(self.keeper, now=_T0)

        shop_popup._watch_stock(self.keeper, now=_T0)

        self.call_later.assert_called_once()
        self.assertEqual(_step(), self.call_later.call_args[0][0])

    def test_no_surplus_schedules_nothing(self):
        shop_popup._watch_stock(self.keeper, now=_T0)

        self.call_later.assert_not_called()
