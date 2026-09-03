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
from systems.statefeed import constants as feed_const

# Every line perform_sell sends a player is a completed or refused trade, so
# the routing tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. A
# trade RESULT is commerce, not dialogue -- what the shopkeeper says in their
# own voice is what carries MESSAGE_TYPE_DIALOGUE. See MESSAGE_TYPES in
# systems/statefeed/constants.py.
_MSG_COMMERCE = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_COMMERCE}

_ITEM_NAME_TO_KEY = {defn.name.lower(): key for key, defn in ITEM_DB.items()}

# ITEM_DB key -- and matching currency tag key -- for the shop's currency.
# The display name lives on the ItemDef.
CREDITS_ITEM_KEY = "credits"

# Why a purchase delivered nothing. Both are shown to the player through
# messages.format_trade, which prefixes them with "Transaction failed".
_NO_ROOM_ERROR = "Your inventory is full."
_OUT_OF_STOCK_ERROR = "That is no longer in stock."

# Pricing for a shopkeeper carrying no ShopDef. Named rather than typed at each
# of the three call sites, because a shop that lost its def and one that
# declares these numbers must price identically -- and 0.5 appearing twice is
# how the two would drift.
_DEFAULT_UPSELL_FACTOR = 1.5
_DEFAULT_MISER_FACTOR = 0.5

# Smallest sale that is a sale. Named for the same reason base_menu.MIN_QUANTITY
# is: zero and negatives are refused rather than silently clamped up, because
# selling one thing after asking for zero is surprising.
_MIN_SELL_COUNT = 1


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
    return shop_def.upsell_factor if shop_def else _DEFAULT_UPSELL_FACTOR


def get_miser_factor(shopkeep) -> float:
    shop_def = _get_shop_def(shopkeep)
    return shop_def.miser_factor if shop_def else _DEFAULT_MISER_FACTOR


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


def _is_sellable(obj) -> bool:
    """
    Purpose: Report whether the shop will buy one object at all.

    Entry:
        obj - a carried object.

    Exit/Returns:
        True when the shop would take it, False otherwise.

    Module Globals:
        None.

    Methodology:
        Extracted from the filter that used to sit inline in get_sell_items,
        rather than copied, because there are now two readers of this fact:
        the shop's own sell list, and the per-slot Sell action the state feed
        offers a graphical client. Copied, the two would eventually disagree
        about what the shop buys, and the pane would offer a sale the
        shopkeeper refuses.

        Currency is excluded first because selling credits for credits is the
        one case that is nonsense rather than merely unprofitable.

    Notes/References:
        systems/statefeed/tests/test_inventory.py asserts the payload's Sell
        action against THIS routine rather than against a list of item keys,
        so content added tomorrow is covered without an edit.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    if obj is None:
        return False

    if obj.is_typeclass(CurrencyItem, exact=False):
        return False

    tradeable = obj.attributes.get("tradeable", default=True)

    if not tradeable:
        return False

    value = obj.attributes.get("value", default=0)

    return value > 0


def sell_entry_for(caller, npc, item) -> SellEntry | None:
    """
    Purpose: Build a SellEntry describing ONE object, so a sale can name a
             single inventory slot.

    Entry:
        caller - the selling Character. Present for symmetry with
                 get_sell_items and so a future per-player price has somewhere
                 to read from; unused today.
        npc    - the shopkeeper, whose miser factor sets the price.
        item   - the carried object being offered.

    Exit/Returns:
        Returns a SellEntry whose `items` list holds only `item`, or None when
        _is_sellable refuses it.

    Module Globals:
        None.

    Methodology:
        This is the whole reason `sell 7` sells slot 7 rather than every
        chunk in the bag. get_sell_items groups by key, which is right for a
        menu the player reads and wrong for a slot the player clicked --
        eight identical rusty metal chunks are a real inventory, and the pane
        knows which one it means.

        Priced by the same miser factor the grouped entry uses, read through
        get_miser_factor rather than recomputed, so a slot sale and a menu
        sale of the same object pay the same.

    Notes/References:
        execute_sell already takes an explicit `items` list, so nothing in
        the transaction needed changing to support this.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    return _sell_entry_over(caller, npc, [item])


def _sell_entry_over(caller, npc, items) -> SellEntry | None:
    """Build a SellEntry over an explicit, already-ordered list of objects.

    The shared half of sell_entry_for and sell_entry_for_group. Priced from
    the FIRST member, which is why the caller's ordering matters: the group
    forms are slot-ascending, so the price quoted is the price of the copy the
    sale starts with.
    """
    if not items:
        return None

    head = items[0]

    if not _is_sellable(head):
        return None

    miser_factor = get_miser_factor(npc) if npc else _DEFAULT_MISER_FACTOR
    value = head.attributes.get("value", default=0)
    unit_price = max(1, int(value * miser_factor))
    stackable = head.attributes.get("stackable", default=False)

    entry = SellEntry(
        items=list(items),
        name=head.key,
        unit_price=unit_price,
        count=0,
        is_stackable=stackable,
    )
    entry.count = count_available(entry)

    return entry


def sell_entry_for_group(caller, npc, item) -> SellEntry | None:
    """
    Purpose: Build a SellEntry over every carried copy of one item, lowest
             slot first.

    Entry:
        caller - the selling Character.
        npc    - the shopkeeper, whose miser factor sets the price.
        item   - a carried object naming the group.

    Exit/Returns:
        Returns a SellEntry whose `items` are slot-ascending, or None when the
        shop refuses the item.

    Module Globals:
        None.

    Methodology:
        THIS IS WHAT MAKES 1 / X / ALL MEAN ANYTHING FOR A NON-STACKABLE.
        Eight rusty metal chunks are eight objects in eight slots, so a stack
        size of one is the wrong bound for "how many can I sell" -- the answer
        is eight, and it is spread across the grid.

        Slot-ascending, because execute_sell walks `items` in order and stops
        at the count. That ordering IS the "lowest number first" rule: sell
        three of eight and the three lowest-numbered copies go.

    Notes/References:
        commands/inventory_cmds.carried_group owns the ordering and the
        grouping rule, shared with the deposit side so the two verbs cannot
        come to disagree about what "all of them" means.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    from commands.inventory_cmds import carried_group

    return _sell_entry_over(caller, npc, carried_group(caller, item))


def _entry_for_request(caller, npc, item, count):
    """
    Purpose: Choose between the one-slot entry and the whole-group entry.

    Entry:
        count - an int, QUANTITY_ALL_KEYWORD, or None for an omitted quantity.

    Exit/Returns:
        Returns a SellEntry. Never None: the caller has already established
        that the shop will buy this item.

    Module Globals:
        _MIN_SELL_COUNT read.

    Methodology:
        THE CLICKED SLOT WINS FOR ONE, THE GROUP WINS FOR MORE.

        An omitted quantity and an explicit 1 both mean "what is in that
        slot" -- one object for a non-stackable, the whole stack for a
        stackable. That is the rule slot addressing exists for: right-clicking
        the eighth chunk and choosing Sell 1 must sell the eighth, not the
        first, which was a live bug until 08/17/2026.

        Anything larger, and `all`, reach the whole group from the lowest slot
        up. A player asking for three of eight is not naming three slots, and
        the only ordering they can predict is the one `inventory` prints.

    Notes/References:
        The asymmetry is deliberate and was chosen over two alternatives: a
        group that always starts at the lowest (which reinstates the 08/17
        bug for Sell 1) and one that climbs from the clicked slot (consistent,
        but makes "sell 3" mean different objects depending on which copy was
        right-clicked).

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    from systems.menus.base_menu import QUANTITY_ALL_KEYWORD

    single = count is None or count == _MIN_SELL_COUNT

    if single and count != QUANTITY_ALL_KEYWORD:
        return sell_entry_for(caller, npc, item)

    return sell_entry_for_group(caller, npc, item)


def _requested_count(count, available: int) -> int:
    """Turn a parsed quantity into the number of units to move.

    None means "whatever the chosen entry holds", which is the whole slot for
    the single form. QUANTITY_ALL_KEYWORD means the same for the group form.
    An integer is clamped down, never up: asking for more than is there is a
    reasonable way to say "all of it", whereas asking for zero is not a
    quantity at all and is refused by the caller.
    """
    from systems.menus.base_menu import QUANTITY_ALL_KEYWORD

    if count is None or count == QUANTITY_ALL_KEYWORD:
        return available

    return min(count, available)


def get_sell_items(caller, npc=None) -> list[SellEntry]:
    if npc is None and caller.ndb._evmenu:
        npc = caller.ndb._evmenu.npc
    miser_factor = get_miser_factor(npc) if npc else _DEFAULT_MISER_FACTOR
    groups = {}
    group_order = []

    for obj in list(caller.contents):
        if not _is_sellable(obj):
            continue

        value = obj.attributes.get("value", default=0)
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


def perform_sell(caller, npc, args: str) -> bool:
    """
    Purpose: Parse, execute and report one slot- or name-addressed sale.

    Entry:
        caller - the selling Character.
        npc    - the shopkeeper being sold to.
        args   - the raw argument, e.g. "7", "7 3", "7 all", "rusty spear 2".

    Exit/Returns:
        Returns True when anything was sold. Messages the caller on every
        exit, successful or not, so no caller needs a second refusal line.

    Module Globals:
        _MSG_COMMERCE read.

    Methodology:
        THIS ROUTINE EXISTS BECAUSE THERE ARE TWO WAYS IN. EvMenuCmdSet is
        `mergetype="Replace"` with `no_objs=True`, so while the shopkeep menu
        is open NOTHING reaches the command parser -- not even a command
        hosted on the shopkeep itself. A graphical client that opened the menu
        by clicking the merchant and then right-clicked an item would have hit
        "Invalid choice". So `sell` is reachable two ways, from one routine:
        CmdSell on the shopkeep's cmdset, and a `_default` option on the
        menu's sell node. Both parse and report identically because neither
        of them parses or reports.

        Resolution is resolve_carried_item, which is slot-first and messages
        its own failures -- the same route `equip` and `drop` take, and the
        reason `sell 7` sells slot 7 rather than the lowest-numbered copy of
        whatever is in it.

        An omitted quantity means the whole stack, matching what None has
        always meant to the banking transfers. A quantity above the stack is
        clamped rather than refused, which is parse_quantity's rule too:
        asking for more than is there is a reasonable way to say "all of it".

    Notes/References:
        No confirmation step, and that is a deliberate difference from the
        menu. The menu confirms because it targets a name GROUP -- "sell rusty
        metal chunk" can mean eight objects the player never counted. A slot
        bounds the blast radius to one stack, and the report names the price.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    from commands.inventory_cmds import resolve_carried_item, split_item_and_count

    from . import messages

    item_text, count = split_item_and_count(args.strip())

    if not item_text:
        caller.msg((messages.NOTHING_NAMED, _MSG_COMMERCE))
        return False

    _index, item = resolve_carried_item(caller, item_text)

    if item is None:
        return False

    if not _is_sellable(item):
        line = messages.format_not_wanted(str(npc.key), str(item.key))
        caller.msg((line, _MSG_COMMERCE))
        return False

    entry = _entry_for_request(caller, npc, item, count)
    available = count_available(entry)

    if available < _MIN_SELL_COUNT:
        caller.msg((messages.NOTHING_TO_SELL, _MSG_COMMERCE))
        return False

    sell_count = _requested_count(count, available)

    if sell_count < _MIN_SELL_COUNT:
        caller.msg((messages.NOTHING_TO_SELL, _MSG_COMMERCE))
        return False

    result = execute_sell(caller, npc, entry, sell_count)
    line = messages.format_trade(result, messages.VERB_SOLD, result.sold_count)
    caller.msg((line, _MSG_COMMERCE))

    return result.success
