"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/03/2026
Description: The held units of a shopkeep, and their decay. A held unit is a
             unit that a player sold to the shop. Modelled on the OSRS shop:
             the stock of each item moves back to its base, one unit at each
             decay step.

             THE BASE OF AN ITEM. For a ware with a WareStock, the base is
             max_stock. The level plus the held units then decays down to
             it. For every other item the base is 0, so its held units decay
             to nothing. That covers an item that the shop does not sell. It
             also covers an endless ware, because endless stock makes each
             held unit a surplus. Nick chose the OSRS rule on 11/03/2026.

             THE DECAY IS ARITHMETIC, NOT A TIMER, as the restock in stock.py
             is. The shopkeep stores a stamp only for an item with a surplus.
             A settle counts the steps that fell due since the stamp, and it
             deletes that many units. So no Script row runs, and nothing
             works while nobody looks. Until 11/03/2026, a daily
             ShopkeepCleanup script cut the holdings to 20 objects.

             A LOOK AND A SALE SETTLE. get_buy_items settles before it reads
             the contents, so each reader sees the settled shop. A sale
             settles before and after it holds the units. The first settle
             stops an old stamp from removing the new units at once. The
             second settle starts the clock at the sale.

             ONE HELD STACK FOR EACH ITEM. hold_units adds sold units to the
             held stack. With no held stack, it puts a new stack there.
             Until 11/03/2026, a sold stack went to nothing at the sale.
"""

import time

from evennia.utils import logger

from items import stacking
from typeclasses.items import CurrencyItem
from world.item_database import ITEM_DB
from world.shop_defs import DEFAULT_DECAY_SECONDS, shop_def_for

from systems.gameplay.shop import stock


# ─── Public constant definitions ─────────────────────────────────────────────

# db attribute on the shopkeep: {item_key: stamp}, only for an item with a
# surplus. `stamp` is the time the NEXT decay step counts from.
DECAY_STATE_ATTR: str = "shop_decay"


# ─── Private constant definitions ────────────────────────────────────────────

# The base stock of an item with no WareStock: the held units decay to this.
_NO_BASE: int = 0

# The level of an item with no WareStock, for the surplus sum.
_NO_LEVEL: int = 0

# The display name of each ItemDef -> its ITEM_DB key. A held object carries
# its display name as its key.
_ITEM_NAME_TO_KEY: dict = {
    defn.name.lower(): key for key, defn in ITEM_DB.items()
}


# ─── Private helper routines ─────────────────────────────────────────────────

def _now(now) -> float:
    """The injected clock, or the wall clock."""
    if now is None:
        return time.time()

    return float(now)


def _row_id(obj) -> int:
    """The database id of an object, for the oldest-first order."""
    row_id = getattr(obj, "id", None) or 0

    return row_id


def _decay_seconds(npc) -> float:
    """The decay step of the shop of this shopkeep, or the default."""
    shop_def = shop_def_for(npc)

    if shop_def is None:
        return DEFAULT_DECAY_SECONDS

    return shop_def.decay_seconds


def _stamps(npc) -> dict:
    """A plain copy of the stored stamps, {} when there is none."""
    stored = npc.attributes.get(DECAY_STATE_ATTR, default=None) or {}
    stamps = {key: float(stamp) for key, stamp in dict(stored).items()}

    return stamps


def _write_stamps(npc, stamps: dict, stored: dict) -> None:
    """Store the stamps, only when they changed. No stamp removes the row."""
    if stamps == stored:
        return

    if stamps:
        npc.attributes.add(DECAY_STATE_ATTR, stamps)
        return

    npc.attributes.remove(DECAY_STATE_ATTR)


def _groups(npc) -> dict:
    """The held objects of the shopkeep by item key, oldest first in each."""
    groups = {}

    for obj in held_objects(npc):
        item_key = held_key(obj)
        groups.setdefault(item_key, []).append(obj)

    return groups


def _remove_units(objs: list, units: int) -> None:
    """Delete `units` units, from the oldest object first. reduce_units
    deletes a drained stack and a single object."""
    left = units

    for obj in objs:
        if left <= 0:
            break

        have = stacking.quantity_of(obj)
        take = min(have, left)
        stacking.reduce_units(obj, take)
        left -= take


def _settle_item(npc, item_key: str, objs: list, stamp, now: float,
                 seconds: float) -> tuple:
    """
    Purpose: Apply every decay step of one item that fell due since its
             stamp.

    Entry:
        npc      - the shopkeep.
        item_key - the ITEM_DB key of the item.
        objs     - the held objects of the item, oldest first.
        stamp    - the stored stamp of the item, or None.
        now      - the time to settle at.
        seconds  - the decay step of the shop.

    Exit/Returns:
        Returns (removed, stamp). `removed` is the units deleted. `stamp` is
        the new stamp, or None when no surplus is left.

    Module Globals:
        None.

    Methodology:
        1. No surplus: drop the stamp.
        2. A surplus with no stamp: start the clock at `now`.
        3. Else delete one unit for each whole step, up to the surplus. The
           stamp moves forward by the same whole steps, so a part step is
           kept.

    Notes/References:
        The surplus is read at `now`. A restock that raised the level
        between two settles counts in full. That is close enough, because
        both clocks move one unit at each step.

    Author: Nick Hobar
    Creation date: 11/03/2026
    """
    excess = surplus(npc, item_key, objs, now=now)

    if excess <= 0:
        return 0, None

    if stamp is None:
        return 0, now

    steps = int((now - stamp) // seconds)
    steps = max(0, steps)
    removed = min(steps, excess)
    _remove_units(objs, removed)

    if removed >= excess:
        return removed, None

    return removed, stamp + steps * seconds


# ─── Public routines ─────────────────────────────────────────────────────────

def held_key(obj) -> str:
    """The ITEM_DB key of a held object. Its display name maps to the key.
    An object with no ItemDef falls back to its own key, in lower case."""
    name = obj.key.lower()
    item_key = _ITEM_NAME_TO_KEY.get(name, name)

    return item_key


def held_objects(npc) -> list:
    """
    Purpose: List the objects that a shopkeep holds for sale.

    Entry:
        npc - the shopkeep.

    Exit/Returns:
        Returns a list of objects, oldest database row first. Currency is
        not a held unit, so the list leaves it out.

    Module Globals:
        None.

    Methodology:
        The id order is the creation order. It is the order that a buy
        hands over and that the decay removes.

    Notes/References:
        shop_service.get_buy_items reads the same list, so the decay and the
        stock grid count the same objects.

    Author: Nick Hobar
    Creation date: 11/03/2026
    """
    held = [obj for obj in npc.contents
            if not obj.is_typeclass(CurrencyItem, exact=False)]
    held.sort(key=_row_id)

    return held


def base_stock(npc, item_key: str) -> int:
    """The base stock of one item: max_stock for a ware with a WareStock,
    else 0. The held units decay while the stock is above it."""
    ware = stock.ware_stock(npc, item_key)

    if ware is None:
        return _NO_BASE

    return ware.max_stock


def surplus(npc, item_key: str, objs: list, now=None) -> int:
    """
    Purpose: Tell how many units of one item are above its base stock.

    Entry:
        npc      - the shopkeep.
        item_key - the ITEM_DB key of the item.
        objs     - the held objects of the item.
        now      - the time to read the level at. None reads the wall clock.

    Exit/Returns:
        Returns the level plus the held units minus the base. A result of 0
        or less means that nothing decays.

    Module Globals:
        _NO_LEVEL read.

    Methodology:
        A ware with no WareStock has no level, so only its held units
        count, against a base of 0.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/03/2026
    """
    level = stock.level(npc, item_key, now=now)

    if level is None:
        level = _NO_LEVEL

    held = stacking.available_units(objs)
    base = base_stock(npc, item_key)

    return level + held - base


def settle(npc, now=None) -> int:
    """
    Purpose: Apply every decay step that fell due on one shopkeep.

    Entry:
        npc - the shopkeep.
        now - the time to settle at. None reads the wall clock.

    Exit/Returns:
        Returns the units deleted. The stored stamps then name only the
        items that still have a surplus.

    Module Globals:
        DECAY_STATE_ATTR read and written.

    Methodology:
        Settle each item that the shopkeep holds. A stamp of an item that
        the shopkeep no longer holds falls away, because no group names it.
        The row is written only when a stamp changed.

    Notes/References:
        This publishes nothing. A settle runs inside a pop-up build, and a
        mark from there would start a second build. The pop-up wake of each
        viewer comes at the same step. See popup_defs/shop.py.

    Author: Nick Hobar
    Creation date: 11/03/2026
    """
    now = _now(now)
    stored = _stamps(npc)
    seconds = _decay_seconds(npc)
    stamps = {}
    removed = 0

    for item_key, objs in _groups(npc).items():
        old = stored.get(item_key)
        gone, stamp = _settle_item(npc, item_key, objs, old, now, seconds)
        removed += gone

        if stamp is not None:
            stamps[item_key] = stamp

    _write_stamps(npc, stamps, stored)

    return removed


def next_decay_in(npc, now=None) -> float | None:
    """
    Purpose: Tell how long until the next decay step on any item.

    Entry:
        npc - the shopkeep.
        now - the time to read at. None reads the wall clock.

    Exit/Returns:
        Returns seconds, 0 or more, or None when no item has a surplus.

    Module Globals:
        None.

    Methodology:
        The smallest (stamp + step - now) over the stored stamps. A settle
        must run first, so that each stamp names a real surplus.

    Notes/References:
        The shop pop-up reads this beside stock.next_restock_in to schedule
        its next refresh.

    Author: Nick Hobar
    Creation date: 11/03/2026
    """
    now = _now(now)
    seconds = _decay_seconds(npc)
    soonest = None

    for stamp in _stamps(npc).values():
        due = max(0.0, stamp + seconds - now)

        if soonest is None or due < soonest:
            soonest = due

    return soonest


def hold_units(npc, obj, units: int) -> None:
    """
    Purpose: Put `units` of a sold stack on the shopkeep.

    Entry:
        npc   - the shopkeep.
        obj   - the stack of the seller, with `units` or more units.
        units - how many units the sale takes.

    Exit/Returns:
        Returns nothing. The stack of the seller does not change here. The
        caller reduces it after this call.

    Module Globals:
        None.

    Methodology:
        1. If the shopkeep holds a stack of the same item, add the units.
        2. Else build a detached copy with the units, and move it to the
           shopkeep.
        The copy reads the attributes of the seller's stack, so this call
        must come before the stack loses the units.

    Notes/References:
        A refused move deletes the copy and logs it. The units then go to
        nothing, which is the old rule. The sale still pays.

    Author: Nick Hobar
    Creation date: 11/03/2026
    """
    if units <= 0:
        return

    existing = stacking.find_mergeable(held_objects(npc), obj)

    if existing is not None:
        stacking.add_units(existing, units)
        return

    copy = stacking.detached_copy(obj, units)
    copy.home = npc
    moved = copy.move_to(npc, quiet=True, move_type="sell")

    if moved:
        return

    logger.log_err(f"shop held.hold_units: {npc} refused {units} x {obj.key}")
    copy.delete()
