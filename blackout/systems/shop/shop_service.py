"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Shop service layer: pricing, stock lookup, and the buy/sell
             transactions behind the shopkeeper menu.
"""

from dataclasses import dataclass, field

from typeclasses.items import CurrencyItem
from world.item_database import ITEM_DB
from world.shop_defs import SHOP_DB, ShopDef

_ITEM_NAME_TO_KEY = {defn.name.lower(): key for key, defn in ITEM_DB.items()}

# ITEM_DB key -- and matching currency tag key -- for the shop's currency.
# The display name lives on the ItemDef.
CREDITS_ITEM_KEY = "credits"


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


def execute_buy(caller, npc, entry: BuyEntry, buy_count: int = 1) -> BuyResult:
    if not entry:
        return BuyResult(success=False, error="Item not found.")

    total_price = buy_count * entry.buy_price
    if not credits_deduct(caller, total_price):
        return BuyResult(success=False, error="Insufficient credits.")

    bought = 0
    if entry.is_prototype:
        item_def = ITEM_DB.get(entry.key)
        if item_def is None:
            credits_add(caller, total_price)
            return BuyResult(success=False, error="Item definition missing.")
        for _ in range(buy_count):
            item_def.create(location=caller)
            bought += 1
    else:
        for obj in list(entry.content_items):
            if bought >= buy_count:
                break
            if obj.location == npc:
                obj.location = caller
                bought += 1

    return BuyResult(
        success=True,
        bought_count=bought,
        total_price=total_price,
        item_name=entry.name,
    )


def execute_sell(caller, npc, entry: SellEntry, sell_count: int = 1) -> SellResult:
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
            obj.location = npc
            total_price += entry.unit_price
            sold_count += 1

    entry.items[:] = remaining_items
    entry.count = count_available(entry)

    credits_add(caller, total_price)

    return SellResult(
        success=True,
        sold_count=sold_count,
        total_price=total_price,
        item_name=entry.name,
    )
