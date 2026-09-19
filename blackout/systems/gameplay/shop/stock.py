"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: The stock level of each ware a shopkeep sells, and its restock.
             Modelled on the OSRS shop: each ware has a maximum stock, a buy
             lowers the level, and the shop adds back one unit at each restock
             until the level is at the maximum again.

             ENDLESS STOCK IS THE ABSENCE OF A RULE. A buy_list ware with no
             WareStock in ShopDef.stock never runs out, and level() returns
             None for it. So one shop can mix finite and endless wares, and a
             shop with no stock rules is an endless shop.

             THE RESTOCK IS ARITHMETIC, NOT A TIMER. The shopkeep stores
             (level, stamp) only for a ware below its maximum. A read counts
             the restocks that fell due since the stamp. So no Script row, no
             ticker, and no work while nobody looks. A full shop stores
             nothing. The wall clock keeps running through a reload, so the
             stock also restocks while the server is down.

             A DEF CHANGE NEEDS NO MIGRATION. The maximum and the interval are
             read from the ShopDef at each read, never stored. The row holds
             only the fact that changes: how many units a buy took.
"""

import time

from world.shop_defs import WareStock, shop_def_for


# ─── Public constant definitions ─────────────────────────────────────────────

# db attribute on the shopkeep: {ware_key: (level, stamp)}, only for a ware
# below its maximum. `stamp` is the time the NEXT restock counts from.
STOCK_STATE_ATTR: str = "shop_stock"


# ─── Private helper routines ─────────────────────────────────────────────────

def _now(now) -> float:
    """The injected clock, or the wall clock."""
    if now is None:
        return time.time()

    return float(now)


def _state(npc) -> dict:
    """A plain copy of the stored stock state, {} when there is none."""
    stored = npc.attributes.get(STOCK_STATE_ATTR, default=None) or {}

    return {key: tuple(entry) for key, entry in dict(stored).items()}


def _settle(entry: tuple, ware: WareStock, now: float):
    """
    Purpose: Apply every restock that fell due since the stamp.

    Entry:
        entry - the stored (level, stamp).
        ware  - the WareStock rule of the ware.
        now   - the time to settle at.

    Exit/Returns:
        Returns (level, stamp) for a ware still below its maximum, or None
        when the ware is full again.

    Module Globals:
        None.

    Methodology:
        One unit for each whole interval since the stamp. The stamp moves
        forward by the same whole intervals, so a part interval is kept.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    level, stamp = entry
    restocks = int((now - stamp) // ware.restock_seconds)
    restocks = max(0, restocks)
    level = int(level) + restocks

    if level >= ware.max_stock:
        return None

    return level, stamp + restocks * ware.restock_seconds


# ─── Public routines ─────────────────────────────────────────────────────────

def ware_stock(npc, ware_key: str) -> WareStock | None:
    """The WareStock rule of one ware, or None for endless stock."""
    shop_def = shop_def_for(npc)

    if shop_def is None:
        return None

    return shop_def.stock.get(ware_key)


def level(npc, ware_key: str, now=None) -> int | None:
    """
    Purpose: Tell how many units of one ware the shop has now.

    Entry:
        npc      - the shopkeep.
        ware_key - the ITEM_DB key of the ware.
        now      - the time to read at. None reads the wall clock.

    Exit/Returns:
        Returns the level, an int from 0 to max_stock. Returns None for a
        ware with endless stock.

    Module Globals:
        None.

    Methodology:
        A ware with no stored entry is full. A stored entry is settled
        first. A read never writes, so a look at the shop costs no query.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    ware = ware_stock(npc, ware_key)

    if ware is None:
        return None

    entry = _state(npc).get(ware_key)

    if entry is None:
        return ware.max_stock

    settled = _settle(entry, ware, _now(now))

    if settled is None:
        return ware.max_stock

    return settled[0]


def take(npc, ware_key: str, units: int, now=None) -> None:
    """
    Purpose: Lower the stock of one ware after a buy.

    Entry:
        npc      - the shopkeep.
        ware_key - the ITEM_DB key of the ware.
        units    - how many units the buy delivered.
        now      - the time of the buy. None reads the wall clock.

    Exit/Returns:
        Returns nothing. Does nothing for an endless ware or for units <= 0.

    Module Globals:
        STOCK_STATE_ATTR written.

    Methodology:
        1. Settle the stored entry. A ware that is full again starts a new
           restock count at `now`.
        2. Store the lower level, never below 0.

    Notes/References:
        The caller clamps the buy to level() first. The floor at 0 is a guard
        for two buys that read the same level.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    ware = ware_stock(npc, ware_key)

    if ware is None or units <= 0:
        return

    now = _now(now)
    state = _state(npc)
    entry = state.get(ware_key)
    settled = _settle(entry, ware, now) if entry is not None else None

    if settled is None:
        settled = (ware.max_stock, now)

    current, stamp = settled
    state[ware_key] = (max(0, current - units), stamp)
    npc.attributes.add(STOCK_STATE_ATTR, state)


def next_restock_in(npc, now=None) -> float | None:
    """
    Purpose: Tell how long until the next unit comes back on any ware.

    Entry:
        npc - the shopkeep.
        now - the time to read at. None reads the wall clock.

    Exit/Returns:
        Returns seconds, more than 0, or None when every ware is full.

    Module Globals:
        None.

    Methodology:
        The smallest (stamp + interval - now) over the settled entries that
        are still below their maximum.

    Notes/References:
        The shop pop-up reads this to schedule its next refresh. See
        systems/interface/popups/popup_defs/shop.py.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    now = _now(now)
    soonest = None

    for ware_key, entry in _state(npc).items():
        ware = ware_stock(npc, ware_key)

        if ware is None:
            continue

        settled = _settle(entry, ware, now)

        if settled is None:
            continue

        due = settled[1] + ware.restock_seconds - now

        if soonest is None or due < soonest:
            soonest = due

    return soonest
