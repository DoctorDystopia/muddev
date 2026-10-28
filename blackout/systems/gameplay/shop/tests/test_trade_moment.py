"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/27/2026
Description: Tests for the moment that a shop trade sends. execute_buy
             sends MOMENT_SHOP_BUY and execute_sell sends MOMENT_SHOP_SELL,
             to the trader only, and only when goods moved. The client plays
             the sound of the moment (godot/audio/cues.json).

Run with:
    evennia test --settings test_settings.py systems.gameplay.shop
"""


from unittest import mock

from items.inventory.handler import InventoryHandler
from systems.gameplay.shop import shop_service
from systems.gameplay.shop.tests.test_trade_delivery import (
    PROTOTYPE_KEY,
    STOCK_KEY,
    ShopTradeTestBase,
)
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed_events
from world.item_database import ITEM_DB


class TestTradeMoment(ShopTradeTestBase):
    """A trade that moved goods sends its moment one time."""

    def _buy(self):
        """Buy one ware and give the result and the mock of emit_moment."""
        entry = self._buy_entry(PROTOTYPE_KEY)

        with mock.patch.object(feed_events, "emit_moment") as emitted:
            result = shop_service.execute_buy(self.char1, self.shopkeep, entry)

        return result, emitted

    def _sell(self, entry, count=1):
        """Sell from one entry and give the result and the mock."""
        with mock.patch.object(feed_events, "emit_moment") as emitted:
            result = shop_service.execute_sell(
                self.char1, self.shopkeep, entry, count)

        return result, emitted

    def test_a_buy_sends_the_buy_moment_to_the_buyer(self):
        result, emitted = self._buy()

        self.assertTrue(result.success)
        emitted.assert_called_once_with(self.char1, feed_const.MOMENT_SHOP_BUY)

    def test_a_refused_buy_sends_nothing(self):
        """No room, no goods, and thus no sound."""
        with mock.patch.object(InventoryHandler, "can_accept",
                               return_value=False):
            result, emitted = self._buy()

        self.assertFalse(result.success)
        emitted.assert_not_called()

    def test_a_sell_sends_the_sell_moment_to_the_seller(self):
        sword = ITEM_DB[STOCK_KEY].create(location=self.char1)

        result, emitted = self._sell(self._sell_entry(sword.key))

        self.assertEqual(result.sold_count, 1)
        emitted.assert_called_once_with(self.char1, feed_const.MOMENT_SHOP_SELL)

    def test_a_sell_of_part_of_a_stack_sends_one_moment(self):
        """One trade is one sound, whatever the count."""
        dust = ITEM_DB["rusty_metal_dust"].create(
            location=self.char1, quantity=5)

        result, emitted = self._sell(self._sell_entry(dust.key), 2)

        self.assertEqual(result.sold_count, 2)
        emitted.assert_called_once_with(self.char1, feed_const.MOMENT_SHOP_SELL)

    def test_a_refused_handover_sends_nothing(self):
        sword = ITEM_DB[STOCK_KEY].create(location=self.char1)
        entry = self._sell_entry(sword.key)

        with mock.patch.object(type(sword), "move_to", return_value=False):
            result, emitted = self._sell(entry)

        self.assertEqual(result.sold_count, 0)
        emitted.assert_not_called()
