from evennia.utils.evmenu import list_node

from systems.menus.base_menu import (
    TITLE_COLOR,
    SPEECH_COLOR,
    HIGHLIGHT_COLOR,
    SUCCESS_COLOR,
    ERROR_COLOR,
    RESET_COLOR,
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


def _dialog(text: str) -> str:
    return f"{SPEECH_COLOR}{text}{RESET_COLOR}"


def _hl(text: str) -> str:
    return f"{HIGHLIGHT_COLOR}{text}{RESET_COLOR}"


def _line(text: str) -> str:
    return f"{TITLE_COLOR}{text}{RESET_COLOR}"


def _get_npc(caller):
    return caller.ndb._evmenu.npc if caller.ndb._evmenu else None


# -------------------------------------------------------------
# Buy items
# -------------------------------------------------------------


def _buy_option_generator(caller):
    npc = _get_npc(caller)
    entries = get_buy_items(npc, caller)
    result = []
    for entry in entries:
        if entry.count > 1:
            result.append(
                f"|w{entry.name}|n (x{entry.count}) [|y{entry.buy_price}|n each]"
            )
        else:
            result.append(
                f"|w{entry.name}|n [|y{entry.buy_price}|n]"
            )
    return result


def _select_ware_to_buy(caller, selection, **kwargs):
    npc = kwargs.get("npc", _get_npc(caller))
    entries = get_buy_items(npc, caller)
    for entry in entries:
        display_single = f"|w{entry.name}|n [|y{entry.buy_price}|n]"
        display_multi = (
            f"|w{entry.name}|n (x{entry.count}) [|y{entry.buy_price}|n each]"
        )
        if display_single == selection or display_multi == selection:
            kwargs["buy_entry"] = entry
            return ("node_buy_quantity", kwargs)
    caller.msg(f"{ERROR_COLOR}That item is no longer available.{RESET_COLOR}")
    return (None, kwargs)


@list_node(_buy_option_generator, select=_select_ware_to_buy, pagesize=20)
def node_buy(caller, raw_string, **kwargs):
    credits = credits_count(caller)
    text = (
        f'{_dialog("Here is what I have for sale.")}\n\n'
        f"{_hl(f'Your credits: {credits}')}"
    )
    extra_options = [{"key": ("[b]ack", "b", "back"), "desc": "Back", "goto": "start"}]
    return text, extra_options


def _parse_custom_buy_quantity(caller, raw_string, **kwargs):
    entry = kwargs.get("buy_entry")
    if not entry:
        caller.msg(f"{ERROR_COLOR}Item not found.{RESET_COLOR}")
        return ("node_buy", kwargs)

    credits = credits_count(caller)
    max_affordable = credits // entry.buy_price if entry.buy_price > 0 else 0
    total_available = min(entry.count, max_affordable)

    try:
        qty = int(raw_string.strip())
    except (ValueError, TypeError):
        caller.msg(f"{ERROR_COLOR}Enter a number 1-{total_available}, or 'all'.{RESET_COLOR}")
        return (None, kwargs)

    qty = max(1, min(qty, total_available))
    kwargs["buy_count"] = qty
    return ("node_confirm_buy", kwargs)


def node_buy_quantity(caller, raw_string, **kwargs) -> tuple:
    entry = kwargs.get("buy_entry")
    if not entry:
        return _dialog('"I do not see that item."'), [{"desc": "Back", "goto": "node_buy"}]

    credits = credits_count(caller)
    max_affordable = credits // entry.buy_price if entry.buy_price > 0 else 0
    total_available = min(entry.count, max_affordable)

    if total_available <= 0:
        return (
            _dialog('"You cannot afford that."'),
            [{"desc": "Back", "goto": "node_buy"}],
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
                "desc": f"Confirm purchase ({total_price} credits)",
                "goto": (_confirm_buy, {"buy_entry": entry, "buy_count": 1}),
            })
        else:
            text_parts.append("")
            text_parts.append(f"{ERROR_COLOR}Not enough credits!{RESET_COLOR}")
            text = "\n".join(text_parts)
        options.append({"desc": "Cancel", "goto": "node_buy"})
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
        {"key": "1", "desc": "Buy 1", "goto": (_pick_buy_quantity, {"buy_entry": entry, "buy_count": 1})},
        {"key": ("a", "all"), "desc": f"Buy {total_available} for {_hl(str(total_available * entry.buy_price))} credits", "goto": (_pick_buy_quantity, {"buy_entry": entry, "buy_count": total_available})},
        {"key": "_default", "goto": (_parse_custom_buy_quantity, {"buy_entry": entry})},
        {"desc": "Cancel", "goto": "node_buy"},
    ]

    return text, options


def _pick_buy_quantity(caller, raw_string, **kwargs) -> str:
    return ("node_confirm_buy", kwargs)


def node_confirm_buy(caller, raw_string, **kwargs) -> tuple:
    npc = kwargs.get("npc", _get_npc(caller))
    entry = kwargs.get("buy_entry")
    buy_count = kwargs.get("buy_count", 1)

    if not entry:
        return _dialog('"That item is no longer available."'), [{"desc": "Back", "goto": "node_buy"}]

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
            "desc": f"Confirm purchase ({total_price} credits)",
            "goto": (_confirm_buy, {"buy_entry": entry, "buy_count": buy_count}),
        })
    else:
        text_parts.append("")
        text_parts.append(f"{ERROR_COLOR}Not enough credits!{RESET_COLOR}")
        text = "\n".join(text_parts)

    if entry.count > 1 or entry.is_prototype:
        options.append({"desc": "Change quantity", "goto": "node_buy_quantity"})
    options.append({"desc": "Cancel", "goto": "node_buy"})

    return text, options


def _confirm_buy(caller, raw_string, **kwargs) -> str:
    npc = kwargs.get("npc", _get_npc(caller))
    entry = kwargs.get("buy_entry")
    buy_count = kwargs.get("buy_count", 1)
    result = execute_buy(caller, npc, entry, buy_count)
    if result.success:
        caller.msg(
            f"{SUCCESS_COLOR}You bought {result.bought_count} {result.item_name} "
            f"for {result.total_price} credits.{RESET_COLOR}"
        )
    else:
        caller.msg(f"{ERROR_COLOR}Transaction failed — {result.error}{RESET_COLOR}")
    return "node_buy"


# -------------------------------------------------------------
# Sell items
# -------------------------------------------------------------


def _sell_option_generator(caller):
    npc = _get_npc(caller)
    entries = get_sell_items(caller, npc)
    result = []
    for entry in entries:
        if entry.count > 1:
            result.append(
                f"|w{entry.name}|n (x{entry.count}) [|y{entry.unit_price}|n each]"
            )
        else:
            result.append(
                f"|w{entry.name}|n [|y{entry.unit_price}|n]"
            )
    return result


def _find_entry_by_display(entries, selection):
    for entry in entries:
        display_single = f"|w{entry.name}|n [|y{entry.unit_price}|n]"
        display_multi = (
            f"|w{entry.name}|n (x{entry.count}) [|y{entry.unit_price}|n each]"
        )
        if display_single == selection or display_multi == selection:
            return entry
    return None


def _select_ware_to_sell(caller, selection, **kwargs):
    npc = kwargs.get("npc", _get_npc(caller))
    entries = get_sell_items(caller, npc)
    entry = _find_entry_by_display(entries, selection)
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
    extra_options = [{"key": ("[b]ack", "b", "back"), "desc": "Back", "goto": "start"}]
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

    try:
        qty = int(raw_string.strip())
    except (ValueError, TypeError):
        caller.msg(f"{ERROR_COLOR}Enter a number 1-{available}, or 'all'.{RESET_COLOR}")
        return (None, kwargs)

    qty = max(1, min(qty, available))
    kwargs["sell_count"] = qty
    kwargs["actual_count"] = qty
    return ("node_confirm_sell", kwargs)


def node_sell_quantity(caller, raw_string, **kwargs) -> tuple:
    entry = kwargs.get("sell_group")
    if not entry:
        return _dialog('"I do not see that item."'), [{"desc": "Back", "goto": "node_sell"}]

    available = max(0, count_available(entry))
    if available <= 0:
        return _dialog('"That item is no longer available."'), [{"desc": "Back", "goto": "node_sell"}]

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
                "desc": f"Confirm sale ({total_price} credits)",
                "goto": (_confirm_sell, {
                    "sell_group": entry,
                    "sell_count": 1,
                }),
            },
        ]
        options.append({"desc": "Cancel", "goto": "node_sell"})
        return text, options

    text_parts = [
        _line(entry.name),
        "",
        _hl(f"Unit price: {entry.unit_price} credits each"),
        _hl(f"You have: {available}"),
    ]
    text = "\n".join(text_parts)

    options = [
        {"key": "1", "desc": "Sell 1", "goto": (_pick_sell_quantity, {"sell_group": entry, "sell_count": 1})},
        {"key": ("a", "all"), "desc": f"Sell all {available} for {_hl(str(available * entry.unit_price))} credits", "goto": (_pick_sell_quantity, {"sell_group": entry, "sell_count": available})},
        {"key": "_default", "goto": (_parse_custom_sell_quantity, {"sell_group": entry})},
        {"desc": "Cancel", "goto": "node_sell"},
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
    sell_count = kwargs.get("sell_count", 1)
    actual_count = kwargs.get("actual_count", 1)

    if not entry:
        return _dialog('"I do not see that item."'), [{"desc": "Back", "goto": "node_sell"}]

    available = max(0, count_available(entry))
    if available <= 0:
        return _dialog('"That item is no longer available."'), [{"desc": "Back", "goto": "node_sell"}]

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
            "desc": f"Confirm sale ({total_price} credits)",
            "goto": (_confirm_sell, {
                "sell_group": entry,
                "sell_count": actual_count,
            }),
        },
    ]

    if entry.count > 1:
        options.append({"desc": "Change quantity", "goto": "node_sell_quantity"})
    options.append({"desc": "Cancel", "goto": "node_sell"})

    return text, options


def _confirm_sell(caller, raw_string, **kwargs) -> str:
    npc = kwargs.get("npc", _get_npc(caller))
    entry = kwargs.get("sell_group")
    sell_count = kwargs.get("sell_count", 1)
    result = execute_sell(caller, npc, entry, sell_count)
    if result.success:
        caller.msg(
            f"{SUCCESS_COLOR}You sold {result.sold_count} {result.item_name} "
            f"for {result.total_price} credits.{RESET_COLOR}"
        )
    else:
        caller.msg(f"{ERROR_COLOR}Transaction failed — {result.error}{RESET_COLOR}")
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
    npc = kwargs.get("npc", _get_npc(caller))
    farewell = _dialog(getattr(npc.db, "farewell", None) or get_farewell(npc))
    return farewell, None
