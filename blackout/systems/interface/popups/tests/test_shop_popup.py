"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Cases for the shop pop-up and the `buy` and `trade` commands it
             rests on.

             THE LOAD-BEARING CASES send a slot's command through the real
             parser, with the real shopkeeper in the room, and count the
             credits and the items that moved. Prices come from shop_service,
             never from a literal, so a retune of the shop re-derives them.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.popups.tests.test_shop_popup
"""

from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from systems.gameplay.shop import shop_service
from systems.interface.popups import service
from systems.interface.popups.popup_defs import shop as shop_popup
from systems.interface.statefeed import buffer
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import inventory as items_feed
from systems.interface.statefeed import popup as popup_feed
from systems.interface.statefeed import subscriptions
from systems.interface.statefeed.serializers import interact_actions
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.npcs import BUY_COMMAND_KEY, TALK_COMMAND_KEY, TRADE_COMMAND_KEY
from typeclasses.npcs import VALUE_COMMAND_KEY
from typeclasses.npcs import SHOPKEEP_CMD_SET_KEY, ShopkeepCmdSet, ShopkeepNPC
from typeclasses.npcs import spawn_shopkeep
from world.item_database import ITEM_DB


# ─── Private constant definitions ────────────────────────────────────────────

# Enough to buy several of anything the oasis shop stocks.
_PURSE = 10_000

# How many of one ware a limited purse can pay for, in the clamp case.
_AFFORD_COUNT = 3


# ─── Private helper routines ─────────────────────────────────────────────────

class _ShopFixture(EvenniaCommandTest):
    """A shopkeeper in the room, credits in the bag, and a clean buffer."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.keeper = create_object(ShopkeepNPC, key="Shopkeeper", location=self.room1)
        buffer.reset()
        self.addCleanup(buffer.reset)

    def _pay(self, amount: int) -> None:
        ITEM_DB[shop_service.CREDITS_ITEM_KEY].create(
            location=self.char1, quantity=amount)
        self.char1.inventory.sync()

    def _credits(self) -> int:
        return shop_service.credits_count(self.char1)

    def _subscribe(self) -> None:
        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_CHAR_POPUP)

    def _open(self) -> None:
        self._subscribe()
        self._send(TRADE_COMMAND_KEY)

    def _send(self, command: str) -> None:
        self.char1.execute_cmd(command, session=self.session)

    def _grid(self, grid_key: str) -> dict:
        snapshot = popup_feed.build_payload(self.char1).to_dict()

        for grid in snapshot["grids"]:
            if grid["key"] == grid_key:
                return grid

        self.fail(f"no {grid_key} grid in the snapshot")

    def _first_ware(self):
        return shop_service.get_buy_items(self.keeper, self.char1)[0]

    def _count_named(self, name: str) -> int:
        wanted = name.lower()

        return sum(int(getattr(obj, "quantity", 1) or 1)
                   for obj in self.char1.contents if obj.key.lower() == wanted)

    def _text_of(self, command: str) -> str:
        with mock.patch.object(self.char1, "msg") as msg:
            self._send(command)

        lines = []

        for call in msg.call_args_list:
            text = call.kwargs.get("text", call.args[0] if call.args else None)

            if isinstance(text, tuple):
                lines.append(str(text[0]))

        return "\n".join(lines)


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestTradeOpensTheShop(_ShopFixture):
    """A client that draws pop-ups gets one. Every other client gets the menu."""

    def test_a_subscribed_session_gets_the_popup(self):
        self._open()

        self.assertTrue(service.is_open(self.char1))
        self.assertIsNone(self.char1.ndb._evmenu)

    def test_an_unsubscribed_session_gets_the_menu(self):
        self._send(TRADE_COMMAND_KEY)

        self.assertFalse(service.is_open(self.char1))
        self.assertIsNotNone(self.char1.ndb._evmenu)

    def test_a_right_click_on_the_keeper_offers_trade_then_talk(self):
        commands = [row["command"] for row in interact_actions(self.keeper, "")]

        self.assertEqual([TRADE_COMMAND_KEY, TALK_COMMAND_KEY], commands)

    def test_left_click_interact_verb_is_trade(self):
        from systems.interface.statefeed.serializers import interact_command

        self.assertEqual(TRADE_COMMAND_KEY, interact_command(self.keeper, ""))

    def test_the_shop_alias_opens_the_popup(self):
        self._subscribe()
        self._send("shop")

        self.assertTrue(service.is_open(self.char1))
        self.assertIsNone(self.char1.ndb._evmenu)

    def test_talking_to_the_keeper_and_trading_opens_the_popup(self):
        self._subscribe()
        self._send(TALK_COMMAND_KEY)

        self.assertIsNotNone(self.char1.ndb._evmenu)
        self.assertFalse(service.is_open(self.char1))

        # Option 1 is "Trade"
        self._send("1")

        self.assertTrue(service.is_open(self.char1))
        self.assertIsNone(self.char1.ndb._evmenu)

    def test_trading_from_talk_raises_no_menu_error(self):
        # The old goto callable returned ("", None). EvMenu raised on it
        # AFTER the pop-up opened, so the case above still passed.
        self._subscribe()
        self._send(TALK_COMMAND_KEY)

        said = self._text_of("1")

        self.assertNotIn("error", said.lower())
        self.assertTrue(service.is_open(self.char1))

    def test_the_stock_grid_shows_every_ware(self):
        self._pay(_PURSE)
        self._open()

        wares = shop_service.get_buy_items(self.keeper, self.char1)

        self.assertEqual(len(wares), self._grid(shop_popup.STOCK_GRID_KEY)["slots_total"])

    def test_a_ware_you_cannot_afford_is_dim(self):
        self._open()

        for row in self._grid(shop_popup.STOCK_GRID_KEY)["items"]:
            with self.subTest(ware=row["name"]):
                self.assertFalse(row["enabled"])


class TestBuyingThroughTheSlots(_ShopFixture):
    """A stock slot's command, sent through the parser, buys what it says."""

    def test_a_left_click_buys_one_at_the_shop_price(self):
        self._pay(_PURSE)
        self._open()
        ware = self._first_ware()
        row = self._grid(shop_popup.STOCK_GRID_KEY)["items"][0]
        before = self._credits()

        self._send(row["actions"][0]["command"])

        self.assertEqual(ware.buy_price, before - self._credits())
        self.assertEqual(1, self._count_named(ware.name))

    def test_buy_all_stops_at_what_the_purse_holds(self):
        ware = self._first_ware()
        self._pay(ware.buy_price * _AFFORD_COUNT)

        self._send(f"{BUY_COMMAND_KEY} {ware.key} all")

        self.assertEqual(_AFFORD_COUNT, self._count_named(ware.name))
        self.assertEqual(0, self._credits())

    def test_buy_more_than_you_can_pay_for_buys_what_you_can(self):
        ware = self._first_ware()
        self._pay(ware.buy_price * _AFFORD_COUNT)

        self._send(f"{BUY_COMMAND_KEY} {ware.key} {_AFFORD_COUNT + 5}")

        self.assertEqual(_AFFORD_COUNT, self._count_named(ware.name))

    def test_buy_by_name_works_for_a_telnet_player(self):
        self._pay(_PURSE)
        ware = self._first_ware()

        self._send(f"{BUY_COMMAND_KEY} {ware.name}")

        self.assertEqual(1, self._count_named(ware.name))

    def test_buying_nothing_the_shop_stocks_says_so(self):
        said = self._text_of(f"{BUY_COMMAND_KEY} moon rock")

        self.assertIn("no moon rock", said.lower())

    def test_buying_with_no_credits_is_refused(self):
        ware = self._first_ware()

        said = self._text_of(f"{BUY_COMMAND_KEY} {ware.key}")

        self.assertIn("credits", said.lower())
        self.assertEqual(0, self._count_named(ware.name))


class TestSellingThroughTheSlots(_ShopFixture):
    """An inventory-pane row's Sell command pays the shop's own price."""

    def _pane_rows(self) -> list:
        return items_feed.build_payload(self.char1).items

    def test_a_left_click_sells_at_the_price_the_slot_shows(self):
        self._pay(_PURSE)
        ware = self._first_ware()
        self._send(f"{BUY_COMMAND_KEY} {ware.key}")
        self._open()
        bought = [obj for obj in self.char1.contents
                  if obj.key.lower() == ware.name.lower()][0]
        price = shop_service.sell_entry_for(self.char1, self.keeper, bought).unit_price
        slot = self.char1.inventory.find_slot(bought)
        row = [row for row in self._pane_rows() if row["slot"] == slot][0]
        before = self._credits()

        self._send(row["actions"][0]["command"])

        self.assertEqual(price, self._credits() - before)
        self.assertIn(str(price), row["detail"])

    def test_what_the_shop_will_not_buy_offers_no_sell(self):
        self._pay(_PURSE)
        self._open()

        for row in self._pane_rows():
            item = [obj for obj in self.char1.contents if obj.id == row["id"]][0]

            if shop_service._is_sellable(item):
                continue

            with self.subTest(item=row["name"]):
                labels = [action["label"] for action in row["actions"]]
                sells = [label for label in labels
                         if label.startswith(shop_popup.VERB_SELL_LABEL)]
                self.assertEqual([], sells)
                self.assertNotIn("detail", row)


class TestInspectingAWare(_ShopFixture):
    """Every stock slot's Inspect says what the ware is, its price, its stock."""

    def _inspect_of(self, row: dict) -> dict:
        return row["actions"][-1]

    def test_every_slot_ends_with_inspect(self):
        self._open()

        for row in self._grid(shop_popup.STOCK_GRID_KEY)["items"]:
            with self.subTest(ware=row["name"]):
                self.assertEqual(shop_popup.VERB_INSPECT_LABEL,
                                 self._inspect_of(row)["label"])

    def test_a_left_click_still_buys(self):
        self._open()

        for row in self._grid(shop_popup.STOCK_GRID_KEY)["items"]:
            with self.subTest(ware=row["name"]):
                self.assertTrue(row["actions"][0]["command"].startswith(BUY_COMMAND_KEY))

    def test_inspect_names_the_ware_its_price_and_its_stock(self):
        self._open()

        for ware in shop_service.get_buy_items(self.keeper, self.char1):
            row = [row for row in self._grid(shop_popup.STOCK_GRID_KEY)["items"]
                   if row["asset"] == ware.key][0]

            with self.subTest(ware=ware.key):
                said = self._text_of(self._inspect_of(row)["command"])

                self.assertIn(ware.name.lower(), said.lower())
                self.assertIn(str(ware.buy_price), said)
                self.assertIn("stock", said.lower())

    def test_a_weapon_shows_its_combat_bonuses(self):
        from systems.gameplay.combat.combat_msg import (
            COMBAT_BONUSES_HEADING, format_combat_stat_bonuses)

        armed = [ware for ware in shop_service.get_buy_items(self.keeper, self.char1)
                 if format_combat_stat_bonuses(ITEM_DB[ware.key].combat_stat_bonuses)]

        if not armed:
            self.skipTest("the shop sells nothing with a combat bonus")

        said = self._text_of(f"{VALUE_COMMAND_KEY} {armed[0].key}")

        self.assertIn(COMBAT_BONUSES_HEADING, said)

    def test_value_by_name_works_for_a_telnet_player(self):
        ware = self._first_ware()

        said = self._text_of(f"{VALUE_COMMAND_KEY} {ware.name}")

        self.assertIn(str(ware.buy_price), said)

    def test_a_sold_out_ware_says_so(self):
        from systems.gameplay.shop import stock

        ware = self._first_ware()
        in_stock = stock.level(self.keeper, ware.key)

        if in_stock is None:
            self.skipTest("the first ware has endless stock")

        stock.take(self.keeper, ware.key, in_stock)
        said = self._text_of(f"{VALUE_COMMAND_KEY} {ware.key}")

        self.assertIn("out of stock", said.lower())

    def test_valuing_nothing_the_shop_stocks_says_so(self):
        said = self._text_of(f"{VALUE_COMMAND_KEY} moon rock")

        self.assertIn("no moon rock", said.lower())


class TestOneTradeCommand(EvenniaCommandTest):
    """A shopkeep carries one ShopkeepCmdSet, however often a rebuild runs."""

    character_typeclass = BlackoutCharacter

    def _copies(self, keeper) -> int:
        return sum(1 for cmdset in keeper.cmdset.all()
                   if cmdset.key == SHOPKEEP_CMD_SET_KEY)

    def test_a_spawned_keeper_has_one_copy(self):
        keeper = spawn_shopkeep(self.room1)

        self.assertEqual(1, self._copies(keeper))

    def test_a_second_rebuild_adds_no_copy(self):
        spawn_shopkeep(self.room1)
        keeper = spawn_shopkeep(self.room1)

        self.assertEqual(1, self._copies(keeper))

    def test_ensure_heals_a_keeper_with_extra_copies(self):
        keeper = create_object(ShopkeepNPC, key="Shopkeeper", location=self.room1)
        keeper.cmdset.add(ShopkeepCmdSet, persistent=True)
        keeper.cmdset.add(ShopkeepCmdSet, persistent=True)

        keeper.ensure_shop_cmdset()

        self.assertEqual(1, self._copies(keeper))
        path = f"{ShopkeepCmdSet.__module__}.{ShopkeepCmdSet.__name__}"
        self.assertEqual(1, keeper.cmdset_storage.count(path))

    def test_trade_names_one_command(self):
        spawn_shopkeep(self.room1)
        spawn_shopkeep(self.room1)

        with mock.patch.object(self.char1, "msg") as msg:
            self.char1.execute_cmd(TRADE_COMMAND_KEY, session=self.session)

        said = " ".join(str(call) for call in msg.call_args_list)
        self.assertNotIn("more than one match", said.lower())
        self.assertIsNotNone(self.char1.ndb._evmenu)


class TestItCloses(_ShopFixture):
    """Walking away from the keeper closes the shop."""

    def test_walking_away_closes_it(self):
        self._open()

        self.char1.move_to(self.room2, quiet=True)

        self.assertFalse(service.is_open(self.char1))
