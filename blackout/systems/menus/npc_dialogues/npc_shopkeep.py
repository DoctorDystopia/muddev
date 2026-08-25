"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Dialogue nodes for shopkeeper NPCs: the buy and sell flows.
"""

from evennia.utils.evmenu import list_node

from systems.menus.base_menu import back_option, cancel_option, parse_quantity
from systems.menus.constants import (
    CONFIRM_NO_KEYS,
    CONFIRM_YES_KEYS,
    QUANTITY_ALL_KEYS,
    QUANTITY_CUSTOM_KEYS,
    QUANTITY_ONE_KEYS,
)
from systems.menus.dialogue import resolve_farewell

from systems.ui.colors import (
    ERROR_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    dialog as _dialog,
    highlight as _hl,
    title as _line,
)
from systems.shop.shop_service import (
    get_buy_items,
    get_sell_items,
    execute_buy,
    execute_sell,
    credits_count,
    count_available,
    get_greeting,
    get_farewell,
)


def _get_npc(caller):
    return caller.ndb._evmenu.npc if caller.ndb._evmenu else None


# -------------------------------------------------------------
# Ware listing
# -------------------------------------------------------------
# The listed label and the string matched on selection MUST be produced by the
# same code. list_node hands the chosen label back verbatim, so if a generator
# and its matcher ever drift apart -- and there were four copies across buy and
# sell, in two formats -- selection silently stops matching and every item
# reports "no longer available". _ware_label is now the single producer.

BUY_PRICE_ATTR = "buy_price"
SELL_PRICE_ATTR = "unit_price"


def _ware_label(entry, price_attr):
    """Render one shop entry's selectable label."""
    price = getattr(entry, price_attr)

    if entry.count > 1:
        return f"|w{entry.name}|n (x{entry.count}) [|y{price}|n each]"

    return f"|w{entry.name}|n [|y{price}|n]"


def _ware_labels(entries, price_attr):
    """Render labels for a whole ware list, in order."""
    return [_ware_label(entry, price_attr) for entry in entries]


def _find_entry_by_display(entries, selection, price_attr):
    """Reverse _ware_label: map a chosen label back to its entry."""
    for entry in entries:
        if _ware_label(entry, price_attr) == selection:
            return entry

    return None


# -------------------------------------------------------------
# Buy items
# -------------------------------------------------------------


def _buy_option_generator(caller):
    npc = _get_npc(caller)
    entries = get_buy_items(npc, caller)
    return _ware_labels(entries, BUY_PRICE_ATTR)


def _select_ware_to_buy(caller, selection, **kwargs):
    npc = kwargs.get("npc", _get_npc(caller))
    entries = get_buy_items(npc, caller)
    entry = _find_entry_by_display(entries, selection, BUY_PRICE_ATTR)

    if entry is None:
        caller.msg(f"{ERROR_COLOR}That item is no longer available.{RESET_COLOR}")
        return (None, kwargs)

    kwargs["buy_entry"] = entry
    return ("node_buy_quantity", kwargs)


@list_node(_buy_option_generator, select=_select_ware_to_buy, pagesize=20)
def node_buy(caller, raw_string, **kwargs):
    credits = credits_count(caller)
    text = (
        f'{_dialog("Here is what I have for sale.")}\n\n'
        f"{_hl(f'Your credits: {credits}')}"
    )
    extra_options = [back_option("Back", "start")]
    return text, extra_options


def _parse_custom_buy_quantity(caller, raw_string, **kwargs):
    entry = kwargs.get("buy_entry")
    if not entry:
        caller.msg(f"{ERROR_COLOR}Item not found.{RESET_COLOR}")
        return ("node_buy", kwargs)

    credits = credits_count(caller)
    max_affordable = credits // entry.buy_price if entry.buy_price > 0 else 0
    total_available = min(entry.count, max_affordable)

    qty, parse_error = parse_quantity(raw_string, total_available)

    if parse_error is not None:
        caller.msg(f"{ERROR_COLOR}{parse_error}{RESET_COLOR}")
        return (None, kwargs)

    kwargs["buy_count"] = qty
    return ("node_confirm_buy", kwargs)


def node_buy_quantity(caller, raw_string, **kwargs) -> tuple:
    entry = kwargs.get("buy_entry")
    if not entry:
        return _dialog('"I do not see that item."'), [back_option("Back", "node_buy")]

    credits = credits_count(caller)
    max_affordable = credits // entry.buy_price if entry.buy_price > 0 else 0
    total_available = min(entry.count, max_affordable)

    if total_available <= 0:
        return (
            _dialog('"You cannot afford that."'),
            [back_option("Back", "node_buy")],
        )

    if total_available == 1:
        total_price = entry.buy_price
        credits = credits_count(caller)
        text_parts = [
            _line(entry.name),
            entry.desc or "No description.",
            "",
            _hl(f"Buying: 1"),
            _hl(f"Total: {SUCCESS_COLOR}{total_price}{RESET_COLOR} credits"),
            _hl(f"Your credits: {credits}"),
        ]
        text = "\n".join(text_parts)
        options = []
        if credits >= total_price:
            options.append({
                "key": CONFIRM_YES_KEYS,
                "desc": f"Confirm purchase ({total_price} credits)",
                "goto": (_confirm_buy, {"buy_entry": entry, "buy_count": 1}),
            })
        else:
            text_parts.append("")
            text_parts.append(f"{ERROR_COLOR}Not enough credits!{RESET_COLOR}")
            text = "\n".join(text_parts)
        options.append(
            {"key": CONFIRM_NO_KEYS, "desc": "Cancel", "goto": "node_buy"}
        )
        return text, options

    text_parts = [
        _line(entry.name),
        entry.desc or "No description.",
        "",
        _hl(f"Price: {entry.buy_price} credits each"),
        _hl(f"Can afford: {total_available}"),
    ]
    text = "\n".join(text_parts)

    options = [
        {
            "key": QUANTITY_ONE_KEYS,
            "desc": "Buy 1",
            "goto": (_pick_buy_quantity, {"buy_entry": entry, "buy_count": 1}),
        },
        {
            "key": QUANTITY_CUSTOM_KEYS,
            "desc": "Buy X (custom)",
            "goto": ("node_buy_custom_qty", {"buy_entry": entry}),
        },
        {
            "key": QUANTITY_ALL_KEYS,
            "desc": (
                f"Buy all {total_available} for "
                f"{_hl(str(total_available * entry.buy_price))} credits"
            ),
            "goto": (_pick_buy_quantity, {"buy_entry": entry, "buy_count": total_available}),
        },
        cancel_option("node_buy"),
    ]

    return text, options


def node_buy_custom_qty(caller, raw_string, **kwargs) -> tuple:
    """Prompt for a typed quantity, reached via the "Buy X (custom)" option.

    Mirrors banking_menu's custom-quantity nodes: this node only renders the
    prompt and arms a hidden _default option; typing a number fires the
    _parse_custom_buy_quantity goto callable, which parses raw_string and
    hands off to node_confirm_buy.
    """
    entry = kwargs.get("buy_entry")
    if not entry:
        return _dialog('"That item is no longer available."'), [back_option("Back", "node_buy")]

    credits = credits_count(caller)
    max_affordable = credits // entry.buy_price if entry.buy_price > 0 else 0
    total_available = min(entry.count, max_affordable)

    text_parts = [
        _line(entry.name),
        _hl(f"Price: {entry.buy_price} credits each"),
        _hl(f"Can afford: {total_available}"),
        "",
        _hl("How many would you like to buy?"),
    ]
    text = "\n".join(text_parts)

    options = [
        {"key": "_default", "goto": (_parse_custom_buy_quantity, {"buy_entry": entry})},
        cancel_option(("node_buy_quantity", {"buy_entry": entry})),
    ]

    return text, options


def _pick_buy_quantity(caller, raw_string, **kwargs) -> str:
    return ("node_confirm_buy", kwargs)


def node_confirm_buy(caller, raw_string, **kwargs) -> tuple:
    entry = kwargs.get("buy_entry")
    buy_count = kwargs.get("buy_count", 1)

    if not entry:
        return _dialog('"That item is no longer available."'), [back_option("Back", "node_buy")]

    total_price = buy_count * entry.buy_price
    credits = credits_count(caller)

    text_parts = [
        _line(entry.name),
        entry.desc or "No description.",
        "",
        _hl(f"Buying: {buy_count}"),
        _hl(f"Total: {SUCCESS_COLOR}{total_price}{RESET_COLOR} credits"),
        _hl(f"Your credits: {credits}"),
    ]
    text = "\n".join(text_parts)

    options = []
    if credits >= total_price:
        options.append({
            "key": CONFIRM_YES_KEYS,
            "desc": f"Confirm purchase ({total_price} credits)",
            "goto": (_confirm_buy, {"buy_entry": entry, "buy_count": buy_count}),
        })
    else:
        text_parts.append("")
        text_parts.append(f"{ERROR_COLOR}Not enough credits!{RESET_COLOR}")
        text = "\n".join(text_parts)

    if entry.count > 1 or entry.is_prototype:
        options.append({
            "key": QUANTITY_CUSTOM_KEYS,
            "desc": "Change quantity",
            "goto": ("node_buy_quantity", {"buy_entry": entry}),
        })
    options.append(
        {"key": CONFIRM_NO_KEYS, "desc": "Cancel", "goto": "node_buy"}
    )

    return text, options


def _report_trade(caller, result, verb, count):
    """Message the caller with the outcome of a completed trade."""
    if result.success:
        caller.msg(
            f"{SUCCESS_COLOR}You {verb} {count} {result.item_name} "
            f"for {result.total_price} credits.{RESET_COLOR}"
        )
        return

    caller.msg(f"{ERROR_COLOR}Transaction failed — {result.error}{RESET_COLOR}")


def _confirm_buy(caller, raw_string, **kwargs) -> str:
    npc = kwargs.get("npc", _get_npc(caller))
    entry = kwargs.get("buy_entry")
    buy_count = kwargs.get("buy_count", 1)

    result = execute_buy(caller, npc, entry, buy_count)
    _report_trade(caller, result, "bought", result.bought_count)

    return "node_buy"


# -------------------------------------------------------------
# Sell items
# -------------------------------------------------------------


def _sell_option_generator(caller):
    npc = _get_npc(caller)
    entries = get_sell_items(caller, npc)
    return _ware_labels(entries, SELL_PRICE_ATTR)


def _select_ware_to_sell(caller, selection, **kwargs):
    npc = kwargs.get("npc", _get_npc(caller))
    entries = get_sell_items(caller, npc)
    entry = _find_entry_by_display(entries, selection, SELL_PRICE_ATTR)
    if entry is None:
        caller.msg(f"{ERROR_COLOR}That item is no longer available.{RESET_COLOR}")
        return (None, kwargs)
    kwargs["sell_group"] = entry
    return ("node_sell_quantity", kwargs)


@list_node(_sell_option_generator, select=_select_ware_to_sell, pagesize=20)
def node_sell(caller, raw_string, **kwargs):
    credits = credits_count(caller)
    text = (
        f'{_dialog("Let me see what you have.")}\n\n'
        f"{_hl(f'Your credits: {credits}')}"
    )
    extra_options = [back_option("Back", "start")]
    return text, extra_options


def _parse_custom_sell_quantity(caller, raw_string, **kwargs):
    entry = kwargs.get("sell_group")
    if not entry:
        caller.msg(f"{ERROR_COLOR}Item not found.{RESET_COLOR}")
        return ("node_sell", kwargs)

    available = max(0, count_available(entry))
    if available <= 0:
        caller.msg(f"{ERROR_COLOR}No more of that item available.{RESET_COLOR}")
        return ("node_sell", kwargs)

    qty, parse_error = parse_quantity(raw_string, available)

    if parse_error is not None:
        caller.msg(f"{ERROR_COLOR}{parse_error}{RESET_COLOR}")
        return (None, kwargs)

    kwargs["sell_count"] = qty
    kwargs["actual_count"] = qty
    return ("node_confirm_sell", kwargs)


def node_sell_quantity(caller, raw_string, **kwargs) -> tuple:
    entry = kwargs.get("sell_group")
    if not entry:
        return _dialog('"I do not see that item."'), [back_option("Back", "node_sell")]

    available = max(0, count_available(entry))
    if available <= 0:
        return _dialog('"That item is no longer available."'), [back_option("Back", "node_sell")]

    if available == 1:
        total_price = entry.unit_price
        text_parts = [
            _line(entry.name),
            "",
            _hl(f"Selling: 1"),
            _hl(f"Total: {SUCCESS_COLOR}{total_price}{RESET_COLOR} credits"),
        ]
        text = "\n".join(text_parts)
        options = [
            {
                "key": CONFIRM_YES_KEYS,
                "desc": f"Confirm sale ({total_price} credits)",
                "goto": (_confirm_sell, {
                    "sell_group": entry,
                    "sell_count": 1,
                }),
            },
        ]
        options.append(
            {"key": CONFIRM_NO_KEYS, "desc": "Cancel", "goto": "node_sell"}
        )
        return text, options

    text_parts = [
        _line(entry.name),
        "",
        _hl(f"Unit price: {entry.unit_price} credits each"),
        _hl(f"You have: {available}"),
    ]
    text = "\n".join(text_parts)

    options = [
        {
            "key": QUANTITY_ONE_KEYS,
            "desc": "Sell 1",
            "goto": (_pick_sell_quantity, {"sell_group": entry, "sell_count": 1}),
        },
        {
            "key": QUANTITY_CUSTOM_KEYS,
            "desc": "Sell X (custom)",
            "goto": ("node_sell_custom_qty", {"sell_group": entry}),
        },
        {
            "key": QUANTITY_ALL_KEYS,
            "desc": (
                f"Sell all {available} for "
                f"{_hl(str(available * entry.unit_price))} credits"
            ),
            "goto": (_pick_sell_quantity, {"sell_group": entry, "sell_count": available}),
        },
        cancel_option("node_sell"),
    ]

    return text, options


def node_sell_custom_qty(caller, raw_string, **kwargs) -> tuple:
    """Prompt for a typed quantity, reached via the "Sell X (custom)" option.

    Mirrors banking_menu's custom-quantity nodes: this node only renders the
    prompt and arms a hidden _default option; typing a number fires the
    _parse_custom_sell_quantity goto callable, which parses raw_string and
    hands off to node_confirm_sell.
    """
    entry = kwargs.get("sell_group")
    if not entry:
        return _dialog('"That item is no longer available."'), [back_option("Back", "node_sell")]

    available = max(0, count_available(entry))
    if available <= 0:
        return _dialog('"That item is no longer available."'), [back_option("Back", "node_sell")]

    text_parts = [
        _line(entry.name),
        _hl(f"Unit price: {entry.unit_price} credits each"),
        _hl(f"You have: {available}"),
        "",
        _hl("How many would you like to sell?"),
    ]
    text = "\n".join(text_parts)

    options = [
        {"key": "_default", "goto": (_parse_custom_sell_quantity, {"sell_group": entry})},
        cancel_option(("node_sell_quantity", {"sell_group": entry})),
    ]

    return text, options


def _pick_sell_quantity(caller, raw_string, **kwargs) -> str:
    entry = kwargs.get("sell_group")
    sell_count = kwargs.get("sell_count", 1)
    available = max(0, count_available(entry))
    kwargs["actual_count"] = min(sell_count, available)
    return "node_confirm_sell", kwargs


def node_confirm_sell(caller, raw_string, **kwargs) -> tuple:
    entry = kwargs.get("sell_group")
    actual_count = kwargs.get("actual_count", 1)

    if not entry:
        return _dialog('"I do not see that item."'), [back_option("Back", "node_sell")]

    available = max(0, count_available(entry))
    if available <= 0:
        return _dialog('"That item is no longer available."'), [back_option("Back", "node_sell")]

    actual_count = min(actual_count, available)
    total_price = actual_count * entry.unit_price

    text_parts = [
        _line(entry.name),
        "",
        _hl(f"Selling: {actual_count}"),
        _hl(f"Total: {SUCCESS_COLOR}{total_price}{RESET_COLOR} credits"),
    ]
    text = "\n".join(text_parts)

    options = [
        {
            "key": CONFIRM_YES_KEYS,
            "desc": f"Confirm sale ({total_price} credits)",
            "goto": (_confirm_sell, {
                "sell_group": entry,
                "sell_count": actual_count,
            }),
        },
    ]

    if entry.count > 1:
        options.append({
            "key": QUANTITY_CUSTOM_KEYS,
            "desc": "Change quantity",
            "goto": ("node_sell_quantity", {"sell_group": entry}),
        })
    options.append(
        {"key": CONFIRM_NO_KEYS, "desc": "Cancel", "goto": "node_sell"}
    )

    return text, options


def _confirm_sell(caller, raw_string, **kwargs) -> str:
    npc = kwargs.get("npc", _get_npc(caller))
    entry = kwargs.get("sell_group")
    sell_count = kwargs.get("sell_count", 1)

    result = execute_sell(caller, npc, entry, sell_count)
    _report_trade(caller, result, "sold", result.sold_count)

    return "node_sell"


# -------------------------------------------------------------
# Menu entry / exit
# -------------------------------------------------------------


def start(caller, **kwargs) -> tuple:
    npc = kwargs.get("npc", _get_npc(caller))
    npc_name = npc.key if npc else "Shopkeeper"
    greeting = _dialog(getattr(npc.db, "greeting", None) or get_greeting(npc))
    credits = credits_count(caller)

    text_lines = [
        _line(npc_name),
        npc.db.desc or "A shopkeeper.",
        "",
        greeting,
        "",
        _hl(f"Your credits: {credits}"),
    ]
    text = "\n".join(text_lines)

    options = [
        {"desc": "Buy items", "goto": "node_buy"},
        {"desc": "Sell items", "goto": "node_sell"},
        {"desc": "Goodbye", "goto": "node_goodbye"},
    ]

    return text, options


def node_goodbye(caller, **kwargs) -> tuple:
    """End the trade in-fiction. Prints nothing: closing the menu is what
    speaks, so that "Goodbye" and q part with the same words."""
    return "", None


def _shop_farewell(caller: object, menu: object) -> str:
    """
    Purpose: Decide what a shopkeep says on parting.

    Entry:
        caller is the Character leaving.
        menu is the BlackoutEvMenu being closed; it carries the NPC.

    Exit/Returns:
        Returns the styled farewell line.

    Module Globals:
        None

    Methodology:
        A shopkeep keeps its dialogue in its shop definition rather than on
        the object, so this overrides the generic source in dialogue.py --
        but only the SOURCE. The printing still happens once, in
        BlackoutEvMenu.close_menu.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    npc = getattr(menu, "npc", None)

    if npc is None:
        return _dialog(resolve_farewell(None))

    spoken = npc.db.farewell or get_farewell(npc)
    styled = _dialog(spoken)

    return styled


# Spoken by BlackoutEvMenu.close_menu, however the conversation ends.
CLOSING_TEXT = _shop_farewell
