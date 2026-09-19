"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: The shop pop-up: the shopkeeper's stock in one grid and the
             quantity row under it. Modelled on the OSRS shop interface.

             YOUR INVENTORY IS THE PANE, NOT A SECOND GRID. While the shop is
             open, carried_actions puts the Sell actions FIRST on each row of
             the inventory pane, and carried_detail gives the row its price.

             IT TRADES NOTHING. A stock slot carries `buy` lines and a carried
             slot carries `sell` lines, the commands on the shopkeeper's own
             cmdset. shop_service prices and executes both, as it does for the
             dialogue menu. So the pop-up, the menu and the typed commands pay
             the same price by construction.

             A PRICE IS DETAIL, NOT A LABEL. messages.format_trade gives the
             reason a context-menu label carries no price: the label is drawn
             before the trade. The slot's `detail` line shows the unit price,
             and every snapshot rebuilds it, so it cannot go stale for long.
"""

import time

from evennia.utils import logger

from systems.gameplay.shop import shop_service, stock
from systems.interface.statefeed import constants as feed_const
from typeclasses.npcs import BUY_COMMAND_KEY, SELL_COMMAND_KEY, VALUE_COMMAND_KEY
from world.item_database import ITEM_DB

from .base_popup import (
    BasePopup,
    definition_row,
    grid,
    item_row,
    quantity_actions,
)


# ─── Public constant definitions ─────────────────────────────────────────────

SHOP_POPUP_KEY: str = "shop"
SHOP_POPUP_TITLE: str = "Shop"

STOCK_GRID_KEY: str = "stock"
STOCK_GRID_TITLE: str = "Stock"

VERB_BUY_LABEL: str = "Buy"
VERB_SELL_LABEL: str = "Sell"
VERB_INSPECT_LABEL: str = feed_const.INVENTORY_ACTION_INSPECT[0]

# A stock slot names its ware by key for the reason BUY_TEMPLATE gives.
VALUE_TEMPLATE: str = f"{VALUE_COMMAND_KEY} {{name}}"

PROMPT_BUY: str = "Buy how many?"

# A stock slot names its ware by the BuyEntry key, which never collides, and
# which perform_buy matches before any name.
BUY_TEMPLATE: str = (
    f"{BUY_COMMAND_KEY} {{name}} {feed_const.ACTION_AMOUNT_PLACEHOLDER}")

# A carried slot names its item by slot number, the form the inventory pane's
# Sell actions use: this slot for one, the whole group for more.
SELL_TEMPLATE: str = (
    f"{SELL_COMMAND_KEY} {{slot}} {feed_const.ACTION_AMOUNT_PLACEHOLDER}")

PRICE_TEMPLATE: str = "{price} cr"
STATUS_TEMPLATE: str = "Your credits: {credits}"
OUT_OF_STOCK_DETAIL: str = "Out of stock"

# ndb attribute on the shopkeep: the time of the one scheduled restock
# refresh. See _watch_restock.
RESTOCK_WAKE_ATTR: str = "shop_restock_wake_at"


# ─── Private constant definitions ────────────────────────────────────────────

# An endless ware draws no count. The client hides a count below 2, as OSRS
# hides the count of a single item.
_ENDLESS_QUANTITY: int = 1


# ─── Private helper routines ─────────────────────────────────────────────────

def _inspect_action(entry) -> dict:
    """The Inspect action of one stock slot: `value <ware key>`.

    It goes LAST, so a left click still buys. The label is the inventory
    pane's own Inspect label, so the two panes name the verb one way.
    """
    command = VALUE_TEMPLATE.replace("{name}", entry.key)

    return {"label": VERB_INSPECT_LABEL, "command": command}


def _stock_row(entry, index: int, credits: int, mode) -> dict:
    """
    Purpose: Render one ware of the shop's stock.

    Entry:
        entry   - a shop_service.BuyEntry.
        index   - its position in the stock grid.
        credits - what the buyer holds.
        mode    - the active quantity mode.

    Exit/Returns:
        Returns one row dict.

    Module Globals:
        None.

    Methodology:
        1. Count what one click can reach: the stock, capped by what the
           buyer can afford. Endless stock is capped by credits alone.
        2. If the buyer can afford none, draw the slot dim, and keep the
           actions. A click then says "Insufficient credits", which teaches
           more than a slot that does nothing.
        3. Draw a physical ware from its object and a buy_list ware from its
           ItemDef, so both look like the item the player receives.
        4. Draw the count in the corner, as a stack: the units in stock for
           a finite ware, and no count for an endless ware. A finite ware at
           0 stays in its slot, dim, and says "Out of stock", as in OSRS.

    Notes/References:
        entry.count means the stock for a physical or finite ware and the
        affordable count for endless stock. See shop_service.get_buy_items.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    affordable = credits // entry.buy_price if entry.buy_price > 0 else 0
    units = min(entry.count, affordable)
    template = BUY_TEMPLATE.replace("{name}", entry.key)
    actions = quantity_actions(
        VERB_BUY_LABEL, template, mode, max(units, 1), PROMPT_BUY)
    actions.append(_inspect_action(entry))
    detail = PRICE_TEMPLATE.format(price=entry.buy_price)
    enabled = units > 0
    sold_out = entry.count <= 0

    if sold_out:
        detail = OUT_OF_STOCK_DETAIL

    if entry.content_items:
        return item_row(entry.content_items[0], index, entry.count, actions,
                        detail=detail, enabled=enabled)

    item_def = ITEM_DB[entry.key]
    shown = _ENDLESS_QUANTITY if entry.endless else entry.count

    return definition_row(item_def, index, shown, actions, name=entry.name,
                          detail=detail, enabled=enabled)


def _watch_restock(npc, now=None) -> None:
    """
    Purpose: Make sure one refresh is scheduled for the next restock.

    Entry:
        npc - the shopkeep that an open pop-up shows.
        now - the time to read at. None reads the wall clock.

    Exit/Returns:
        Returns nothing. Never raises.

    Module Globals:
        RESTOCK_WAKE_ATTR read and written.

    Methodology:
        1. Ask stock.next_restock_in. None means every ware is full.
        2. If a wake is already due at or before that moment, stop.
        3. Else schedule _restock_due, and record its time on the ndb.

    Notes/References:
        Each build calls this, and buffer.mark_stale does not merge delayed
        marks. The ndb record is what keeps it to one timer for each keeper.
        The chain stops when nobody looks: _restock_due marks no pop-up, so
        no build runs, and nothing schedules the next wake. The next open
        starts it again. A reload drops the timer and the record together.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    try:
        now = time.time() if now is None else now
        delay = stock.next_restock_in(npc, now=now)

        if delay is None:
            return

        due = now + delay
        pending = getattr(npc.ndb, RESTOCK_WAKE_ATTR, None)

        if pending is not None and now < pending <= due:
            return

        from twisted.internet import reactor

        setattr(npc.ndb, RESTOCK_WAKE_ATTR, due)
        reactor.callLater(delay, _restock_due, npc)
    except Exception:
        logger.log_trace()


def _restock_due(npc) -> None:
    """A restock fell due. Refresh every pop-up that shows this keeper."""
    from systems.interface.popups import service

    try:
        setattr(npc.ndb, RESTOCK_WAKE_ATTR, None)
        service.refresh_anchor_viewers(npc)
    except Exception:
        logger.log_trace()


def _stock_rows(npc, caller, mode) -> list:
    """Render one row for each ware, skipping one whose ItemDef is gone."""
    credits = shop_service.credits_count(caller)
    rows = []

    for entry in shop_service.get_buy_items(npc, caller):
        if not entry.content_items and entry.key not in ITEM_DB:
            continue

        rows.append(_stock_row(entry, len(rows), credits, mode))

    return rows


# ─── Public classes ──────────────────────────────────────────────────────────

class ShopPopup(BasePopup):
    """The shopkeeper's stock, anchored to the keeper. The pane sells."""

    key = SHOP_POPUP_KEY
    title = SHOP_POPUP_TITLE
    room_bound = True
    uses_quantity = True

    def title_for(self, caller, anchor) -> str:
        """The keeper's own name heads the shop, as OSRS names the store."""
        return str(getattr(anchor, "key", "") or self.title)

    def status(self, caller, anchor) -> str:
        """The buyer's credits."""
        credits = shop_service.credits_count(caller)

        return STATUS_TEMPLATE.format(credits=credits)

    def grids(self, caller, anchor, mode) -> list:
        """
        Purpose: Build the stock grid.

        Entry:
            caller - a Character with an inventory handler.
            anchor - the shopkeeper.
            mode   - the active quantity mode.

        Exit/Returns:
            Returns one grid dict.

        Module Globals:
            None.

        Methodology:
            Draw the stock with only its wares. The carried items are the
            inventory pane's, and carried_actions gives them Sell.

        Notes/References:
            The credits change on every trade, and a trade always moves an
            item on or off the character. So emit_inventory marks this pop-up
            stale after each one, and the prices and the dim slots follow.

        Author: Nick Hobar
        Creation date: 09/18/2026
        """
        stock_rows = _stock_rows(anchor, caller, mode)
        stock_grid = grid(STOCK_GRID_KEY, STOCK_GRID_TITLE, len(stock_rows), stock_rows)
        _watch_restock(anchor)

        return [stock_grid]

    def carried_actions(self, caller, anchor, item, slot_index, units, mode) -> list:
        """
        Purpose: Give one inventory-pane row its Sell actions.

        Entry:
            caller     - the selling Character.
            anchor     - the shopkeeper.
            item       - the carried object.
            slot_index - its 0-based slot in the carried grid.
            units      - the units of its whole group.
            mode       - the active quantity mode.

        Exit/Returns:
            Returns a list of action dicts, the active mode first. Empty for
            an item the shop will not buy.

        Module Globals:
            SELL_TEMPLATE, VERB_SELL_LABEL read.

        Methodology:
            shop_service.sell_entry_for decides what the shop buys, the test
            the sell list and the `sell` command use.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 09/18/2026
        """
        entry = shop_service.sell_entry_for(caller, anchor, item)

        if entry is None:
            return []

        template = SELL_TEMPLATE.replace("{slot}", str(slot_index + 1))
        actions = quantity_actions(
            VERB_SELL_LABEL, template, mode, units, feed_const.ACTION_PROMPT_SELL)

        return actions

    def carried_detail(self, caller, anchor, item) -> str:
        """The unit price the shop pays for one carried item, or ""."""
        entry = shop_service.sell_entry_for(caller, anchor, item)

        if entry is None:
            return ""

        return PRICE_TEMPLATE.format(price=entry.unit_price)
