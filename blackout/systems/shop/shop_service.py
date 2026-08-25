"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Shop service layer: pricing, stock lookup, and the buy/sell
             transactions behind the shopkeeper menu.
"""

from dataclasses import dataclass, field
from evennia.utils import logger

from typeclasses.items import CurrencyItem
from world.item_database import ITEM_DB
from world.shop_defs import SHOP_DB, ShopDef
from systems.stat_tracker import constants as stat_constants

_ITEM_NAME_TO_KEY = {defn.name.lower(): key for key, defn in ITEM_DB.items()}

# ITEM_DB key -- and matching currency tag key -- for the shop's currency.
# The display name lives on the ItemDef.
CREDITS_ITEM_KEY = "credits"

# Why a purchase delivered nothing. Both are shown to the player through
# npc_shopkeep._report_trade, which prefixes them with "Transaction failed".
_NO_ROOM_ERROR = "Your inventory is full."
_OUT_OF_STOCK_ERROR = "That is no longer in stock."


def _is_currency(item, currency_key: str = CREDITS_ITEM_KEY) -> bool:
    return item.is_typeclass(CurrencyItem, exact=False) and item.currency_key == currency_key


@dataclass
class BuyEntry:
    key: str = ""
    name: str = ""
    desc: str = ""
    buy_price: int = 0
    count: int = 1
    is_prototype: bool = True
    content_items: list = field(default_factory=list)


@dataclass
class SellEntry:
    items: list = field(default_factory=list)
    name: str = ""
    unit_price: int = 0
    count: int = 0
    is_stackable: bool = False


@dataclass
class BuyResult:
    success: bool = False
    bought_count: int = 0
    total_price: int = 0
    item_name: str = ""
    error: str = ""


@dataclass
class SellResult:
    success: bool = False
    sold_count: int = 0
    total_price: int = 0
    item_name: str = ""
    error: str = ""


def _get_shop_def(shopkeep) -> ShopDef | None:
    key = getattr(shopkeep.db, "shopdef_key", None)
    if key:
        return SHOP_DB.get(key)
    return None


def get_upsell_factor(shopkeep) -> float:
    shop_def = _get_shop_def(shopkeep)
    return shop_def.upsell_factor if shop_def else 1.5


def get_miser_factor(shopkeep) -> float:
    shop_def = _get_shop_def(shopkeep)
    return shop_def.miser_factor if shop_def else 0.5


def get_buy_list(shopkeep) -> list[str]:
    shop_def = _get_shop_def(shopkeep)
    return list(shop_def.buy_list) if shop_def else []


def get_greeting(shopkeep) -> str:
    shop_def = _get_shop_def(shopkeep)
    return shop_def.greeting if shop_def else '"Welcome."'


def get_farewell(shopkeep) -> str:
    shop_def = _get_shop_def(shopkeep)
    return shop_def.farewell if shop_def else '"Farewell."'


def credits_in(items) -> int:
    """Total currency held across an arbitrary iterable of item objects.

    Split out of credits_count so that a container which is not the buyer can
    be counted too -- the bank room's contents, for the summary screen's
    holdings panel. Every currency stack found is summed rather than the first
    one returned: a caller's own inventory merges credits into one stack, but
    nothing guarantees that for a container the shop never touches.
    """
    total = 0

    for item in items:
        if _is_currency(item):
            total += max(0, item.quantity)

    return total


def credits_count(caller) -> int:
    return credits_in(caller.contents)


def credits_deduct(caller, amount: int) -> bool:
    for item in caller.contents:
        if _is_currency(item):
            if item.quantity >= amount:
                item.quantity -= amount
                if item.quantity <= 0:
                    item.delete()
                return True
            return False
    return False


def credits_add(caller, amount: int) -> None:
    for item in caller.contents:
        if _is_currency(item):
            item.quantity += amount
            return
    # Route through ITEM_DB rather than create_object: the raw call skipped
    # the ("credits", "currency") tag, the desc and the value attribute, so
    # shop-issued credits were a different object from every other kind.
    ITEM_DB[CREDITS_ITEM_KEY].create(location=caller, quantity=amount)


def get_buy_items(shopkeep, caller=None) -> list[BuyEntry]:
    upsell = get_upsell_factor(shopkeep)
    credits = credits_count(caller) if caller else 0
    groups = {}
    group_order = []

    for key in get_buy_list(shopkeep):
        item_def = ITEM_DB.get(key)
        if item_def is None:
            continue
        buy_price = max(1, int(item_def.value * upsell))
        affordable = credits // buy_price if caller else 1
        count = max(1, affordable)
        if key not in groups:
            groups[key] = BuyEntry(
                key=key,
                name=item_def.name,
                desc=item_def.desc,
                buy_price=buy_price,
                count=0,
                is_prototype=True,
                content_items=[],
            )
            group_order.append(key)
        groups[key].count += count

    for obj in list(shopkeep.contents):
        if obj.is_typeclass(CurrencyItem, exact=False):
            continue
        value = obj.attributes.get("value", default=0)
        buy_price = max(1, int(value * upsell))
        key = _ITEM_NAME_TO_KEY.get(obj.key.lower(), obj.key.lower())
        if key not in groups:
            item_def = ITEM_DB.get(key)
            groups[key] = BuyEntry(
                key=key,
                name=obj.key,
                desc=item_def.desc if item_def else "",
                buy_price=buy_price,
                count=0,
                is_prototype=False,
                content_items=[],
            )
            group_order.append(key)
        groups[key].count += 1
        groups[key].content_items.append(obj)

    return [groups[k] for k in group_order]


def get_sell_items(caller, npc=None) -> list[SellEntry]:
    if npc is None and caller.ndb._evmenu:
        npc = caller.ndb._evmenu.npc
    miser_factor = get_miser_factor(npc) if npc else 0.5
    groups = {}
    group_order = []

    for obj in list(caller.contents):
        if obj.is_typeclass(CurrencyItem, exact=False):
            continue
        tradeable = obj.attributes.get("tradeable", default=True)
        if not tradeable:
            continue
        value = obj.attributes.get("value", default=0)
        if value <= 0:
            continue

        key = obj.key.lower()
        if key not in groups:
            unit_price = max(1, int(value * miser_factor))
            stackable = obj.attributes.get("stackable", default=False)
            groups[key] = SellEntry(
                items=[],
                name=obj.key,
                unit_price=unit_price,
                count=0,
                is_stackable=stackable,
            )
            group_order.append(key)

        entry = groups[key]
        entry.items.append(obj)
        stackable = obj.attributes.get("stackable", default=False)
        if stackable:
            qty = getattr(obj.db, "quantity", 1) or 1
            entry.count += qty
        else:
            entry.count += 1

    return [groups[k] for k in group_order]


def count_available(entry: SellEntry) -> int:
    count = 0
    for obj in list(entry.items):
        stackable = obj.attributes.get("stackable", default=False) if obj else False
        if stackable:
            qty = getattr(obj.db, "quantity", 1) if obj else 0
            count += max(0, qty)
        else:
            count += 1
    return count


def _publish_inventory(caller) -> None:
    """
    Purpose: Push one inventory snapshot once a trade has fully resolved.

    Entry:
        caller - the trading Character. Called after the goods and the
                 credits have both settled, on success and on failure.

    Exit/Returns:
        No return value. Never raises.

    Module Globals:
        None.

    Methodology:
        Moving goods publishes a snapshot of its own, because move_to runs
        Character.at_object_receive / at_object_leave. The CREDITS never do:
        credits_deduct and credits_add write `quantity` onto a surviving
        stack or call obj.delete(), and delete() assigns `self.location =
        None` directly rather than moving, so no hook fires. Selling part of
        a stack is the same story. One publish at the end of the transaction
        is what keeps the graphical grid honest about both halves of a trade
        -- and about a refunded purchase, where nothing moved at all.

    Notes/References:
        systems/crafting/crafting_service.py _publish_inventory documents the
        same asymmetry for the craft path.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    from evennia.utils import logger

    from systems.statefeed import events as feed

    try:
        feed.emit_inventory(caller)
    except Exception:
        logger.log_trace()


def _deliver_purchase(caller, obj) -> bool:
    """
    Purpose: Hand one bought object to the buyer.

    Entry:
        caller - the buying Character.
        obj    - the object being sold: detached, when it was just spawned
                 from a prototype, or still in the shopkeeper's contents when
                 it was pre-stocked.

    Exit/Returns:
        True once the object is carried. False when the move was refused, in
        which case the object has not moved and the buyer owes nothing.

    Module Globals:
        None.

    Methodology:
        move_to, not `obj.location = caller`. Direct assignment does not fire
        at_object_receive (CLAUDE.md gotcha 5), so a bought item landed in
        contents with no inventory slot, merged into no existing stack and
        published no state-feed snapshot -- the 3D client's pane sat stale
        until some unrelated movement repaired it. at_pre_object_receive
        never ran either, so a player at 32/32 could go on buying forever.

        Nothing is dropped on the shop floor when the move is refused. A
        craft has nowhere to put a rejected output but the ground; a purchase
        does -- the goods simply stay in stock and the credits go back, which
        is reversible and is what a shopkeeper would actually do.

    Notes/References:
        world/item_database.py ItemDef.create documents the same
        spawn-detached-then-move pattern and the same reason for it.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    carried = obj.move_to(caller, quiet=True, move_type="buy")
    return bool(carried)


def _buy_prototype(caller, item_def, buy_count: int) -> tuple[int, bool]:
    """
    Purpose: Spawn and deliver up to `buy_count` copies of a prototype ware.

    Entry:
        caller    - the buying Character.
        item_def  - the ItemDef named by the BuyEntry's key.
        buy_count - how many were asked for.

    Exit/Returns:
        (delivered, refused). `delivered` is how many the buyer now carries;
        `refused` is True when a copy would not fit, which ends the run. No
        undelivered copy survives -- one that cannot be handed over is
        deleted rather than left detached in the database forever.

    Module Globals:
        None.

    Methodology:
        Spawned detached and moved in a second step, with `home` pointed at
        the buyer so the copy is never homeless in between. ItemDef.create
        takes the same route for its own reason: at_object_receive reads
        `stackable` and `quantity` to decide on a merge, and an object
        spawned straight into a container runs that hook before the
        attributes exist.

    Notes/References: None.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    delivered = 0

    for _ in range(buy_count):
        obj = item_def.create(home=caller)
        carried = _deliver_purchase(caller, obj)

        if not carried:
            obj.delete()
            return delivered, True

        delivered += 1

    return delivered, False


def _buy_stock(caller, npc, entry: BuyEntry, buy_count: int) -> tuple[int, bool]:
    """
    Purpose: Hand over up to `buy_count` of a ware the shopkeeper physically
    holds.

    Entry:
        caller    - the buying Character.
        npc       - the shopkeeper whose contents the wares live in.
        entry     - the BuyEntry, whose content_items are those objects.
        buy_count - how many were asked for.

    Exit/Returns:
        (delivered, refused), read as in _buy_prototype. Delivered objects
        are dropped from entry.content_items, so a second pass over the same
        entry cannot sell the same object twice.

    Module Globals:
        None.

    Methodology:
        The location guard stays: get_buy_items may have been built before
        another shopper got here, so an object listed in the entry is not
        proof the shopkeeper still holds it. A missing object is skipped; a
        refusal ends the run, because the next copy would not fit either.

    Notes/References: None.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    delivered = 0

    for obj in list(entry.content_items):
        if delivered >= buy_count:
            break

        if obj is None or obj.location != npc:
            continue

        carried = _deliver_purchase(caller, obj)

        if not carried:
            return delivered, True

        entry.content_items.remove(obj)
        delivered += 1

    return delivered, False


def execute_buy(caller, npc, entry: BuyEntry, buy_count: int = 1) -> BuyResult:
    """
    Purpose: Charge for and hand over up to `buy_count` of one ware.

    Entry:
        caller    - the buying Character.
        npc       - the shopkeeper.
        entry     - the BuyEntry chosen from get_buy_items.
        buy_count - how many were asked for.

    Exit/Returns:
        A BuyResult. `total_price` is what was actually charged, which is the
        price of `bought_count` rather than of `buy_count`: anything not
        delivered is refunded before returning. A purchase that delivered
        nothing comes back success=False with every credit restored.

    Module Globals:
        _NO_ROOM_ERROR, _OUT_OF_STOCK_ERROR.

    Methodology:
        Pay first, refund the shortfall. Deducting the whole price up front
        keeps the affordability test in one place, and every exit below
        either delivers goods or hands credits back, so no refused delivery
        can leave the buyer out of pocket. That matters now in a way it did
        not before: delivery goes through move_to, which
        Character.at_pre_object_receive can veto at 32/32.

    Notes/References:
        systems/menus/npc_dialogues/npc_shopkeep.py _report_trade prints
        bought_count and total_price in one sentence, which is why the two
        have to describe the same goods.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    if not entry:
        return BuyResult(success=False, error="Item not found.")

    total_price = buy_count * entry.buy_price
    paid = credits_deduct(caller, total_price)

    if not paid:
        return BuyResult(success=False, error="Insufficient credits.")

    if entry.is_prototype:
        item_def = ITEM_DB.get(entry.key)

        if item_def is None:
            credits_add(caller, total_price)
            return BuyResult(success=False, error="Item definition missing.")

        bought, refused = _buy_prototype(caller, item_def, buy_count)
    else:
        bought, refused = _buy_stock(caller, npc, entry, buy_count)

    charged = bought * entry.buy_price
    refund = total_price - charged

    if refund > 0:
        credits_add(caller, refund)

    _publish_inventory(caller)

    if bought == 0:
        error = _NO_ROOM_ERROR if refused else _OUT_OF_STOCK_ERROR
        return BuyResult(success=False, error=error)

    stats = getattr(caller, "stats", None)
    if stats is not None and total_price:
        try:
            stats.increment(stat_constants.CREDITS_SPENT_STAT_KEY, amount=total_price)
        except Exception as exc:
            logger.log_err(f"shop_service.execute_buy CREDITS_SPENT_STAT_KEY stat update failed: {exc!r}")
            
    return BuyResult(
        success=True,
        bought_count=bought,
        total_price=charged,
        item_name=entry.name,
    )


def execute_sell(caller, npc, entry: SellEntry, sell_count: int = 1) -> SellResult:
    """
    Purpose: Take up to `sell_count` of one ware off the seller and pay for
    it.

    Entry:
        caller     - the selling Character.
        npc        - the shopkeeper, who receives whole objects.
        entry      - the SellEntry chosen from get_sell_items; its item list
                     and count are updated in place to match what is left.
        sell_count - how many were asked for.

    Exit/Returns:
        A SellResult carrying what was actually sold and what was paid for
        it. An object the shopkeeper refuses stays with the seller and is not
        paid for.

    Module Globals:
        None.

    Methodology:
        A whole object leaves through move_to, not `obj.location = npc`. That
        is the mirror image of the buy-side bug: direct assignment skips
        Character.at_object_leave, so the seller's inventory slot was never
        released and no snapshot was published -- the grid went on showing
        goods that now belonged to the shopkeeper, and the freed slot did not
        come back until the next real item movement.

        A part-sold STACK cannot use that route, because nothing leaves: the
        surviving object merely has a smaller `quantity`, and a drained one
        is deleted, which assigns location None rather than moving. Both are
        invisible to the hooks, which is why the closing snapshot is
        published from here rather than left to them.

    Notes/References:
        typeclasses/characters.py at_object_leave documents why the leave
        hook has to name the departing object when it publishes.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    if not entry or not entry.items:
        return SellResult(success=False, error="Items no longer available.")

    total_price = 0
    sold_count = 0
    remaining_items = []

    for obj in list(entry.items):
        if sold_count >= sell_count:
            remaining_items.append(obj)
            continue

        if obj is None or obj.location != caller:
            continue

        stackable = obj.attributes.get("stackable", default=False)
        if stackable:
            qty = getattr(obj.db, "quantity", 1) or 1
            if qty <= 0:
                continue
            to_sell = min(qty, sell_count - sold_count)
            new_qty = qty - to_sell
            if new_qty <= 0:
                obj.delete()
            else:
                obj.db.quantity = new_qty
                remaining_items.append(obj)
            total_price += to_sell * entry.unit_price
            sold_count += to_sell
        else:
            handed_over = obj.move_to(npc, quiet=True, move_type="sell")

            if not handed_over:
                remaining_items.append(obj)
                continue

            total_price += entry.unit_price
            sold_count += 1

    entry.items[:] = remaining_items
    entry.count = count_available(entry)

    credits_add(caller, total_price)

    _publish_inventory(caller)

    return SellResult(
        success=True,
        sold_count=sold_count,
        total_price=total_price,
        item_name=entry.name,
    )
