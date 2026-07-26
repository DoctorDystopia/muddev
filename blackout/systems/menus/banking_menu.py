"""
Banking menu for Blackout.

Provides an EvMenu-based interface for depositing, withdrawing,
and browsing banked items. All storage logic is handled by
systems.banking.handler.BankHandler -- this module only manages
display formatting and navigation flow.
"""


from items.equipment.handler import EquipmentError
from items.equipment.constants import MAX_INVENTORY_SLOTS


TITLE_COLOR = "|w"
HIGHLIGHT_COLOR = "|y"
SUCCESS_COLOR = "|g"
ERROR_COLOR = "|r"
RESET_COLOR = "|n"
SEPARATOR = "-" * 60


def _format_item_line(item):
    weight = getattr(item.db, "weight", None)
    value = getattr(item.db, "value", None)
    tool_type = getattr(item.db, "tool_type", None)

    details = []
    if weight is not None:
        details.append(f"{weight}kg")
    if value is not None:
        details.append(f"{value} credits")
    if tool_type:
        tier = getattr(item.db, "tier", 0)
        details.append(f"T{tier} {tool_type}")

    suffix = f" [{', '.join(details)}]" if details else ""

    quantity = getattr(item, "quantity", None)
    if quantity and quantity > 1:
        suffix = f" (x{quantity}){suffix}"

    return suffix


def start(caller, **kwargs):
    stored = caller.bank.list_items()
    stored_count = len(stored)
    inv_count = caller.inventory.count_used()

    text = (
        f"{TITLE_COLOR}--- Bank Vault ---{RESET_COLOR}\n\n"
        f"{HIGHLIGHT_COLOR}Stored:{RESET_COLOR} {stored_count} item{'s' if stored_count != 1 else ''}\n"
        f"{HIGHLIGHT_COLOR}Carrying:{RESET_COLOR} {inv_count}/{MAX_INVENTORY_SLOTS} slot{'s' if inv_count != 1 else ''}"
    )

    options = [
        {"desc": "View storage", "goto": "node_storage"},
        {"desc": "Deposit items", "goto": "node_deposit_select"},
        {"desc": "Withdraw items", "goto": "node_withdraw_select"},
        {"desc": "Exit banking menu", "goto": "node_exit"},
    ]

    return text, options


def node_storage(caller, **kwargs):
    items = caller.bank.list_items()

    if not items:
        text = f"{HIGHLIGHT_COLOR}Your bank vault is empty.{RESET_COLOR}"
        options = (
            {"desc": "Deposit items", "goto": "node_deposit_select"},
            {"desc": "Back to menu", "goto": "start"},
        )

        return text, options

    text = f"{TITLE_COLOR}--- Bank Storage ---{RESET_COLOR}"
    options = []

    for item in items:
        suffix = _format_item_line(item)
        options.append(
            {
                "desc": f"{item.key}{suffix}",
                "goto": ("node_item_detail", {"item_id": item.id}),
            }
        )

    options.append({"desc": "Back to menu", "goto": "start"})

    return text, options


def node_item_detail(caller, **kwargs):
    item_id = kwargs.get("item_id")
    item_obj = caller.bank.get_item_by_id(item_id)

    if item_obj is None:
        text = f"{ERROR_COLOR}That item is no longer in your bank.{RESET_COLOR}"
        options = (
            {"desc": "Back to storage", "goto": "node_storage"},
            {"desc": "Back to menu", "goto": "start"},
        )
        return text, options

    item_desc = getattr(item_obj.db, "desc", None) or "No description."
    value = getattr(item_obj.db, "value", 0)
    weight = getattr(item_obj.db, "weight", 0.0)
    tradeable = getattr(item_obj.db, "tradeable", True)
    stackable = getattr(item_obj.db, "stackable", False)
    tool_type = getattr(item_obj.db, "tool_type", None)
    tier = getattr(item_obj.db, "tier", 0)
    req_level = getattr(item_obj.db, "req_level", 0)

    lines = [
        f"{TITLE_COLOR}--- {item_obj.key} ---{RESET_COLOR}",
        f"Description: {item_desc}",
        f"Value: {value} credits",
        f"Weight: {weight}kg",
        f"Tradeable: {HIGHLIGHT_COLOR}{'Yes' if tradeable else 'No'}{RESET_COLOR}",
        f"Stackable: {HIGHLIGHT_COLOR}{'Yes' if stackable else 'No'}{RESET_COLOR}",
    ]

    if tool_type:
        lines.append(f"Tool: {tool_type} (Tier {tier}, Req. Level {req_level})")

    text = "\n".join(lines)

    options = (
        {
            "desc": f"Withdraw {item_obj.key}",
            "goto": ("node_withdraw_quantity", {"item_id": item_obj.id}),
        },
        {"desc": "Back to storage", "goto": "node_storage"},
        {"desc": "Back to menu", "goto": "start"},
    )

    return text, options


def node_deposit_select(caller, **kwargs):
    caller.inventory.sync()
    inventory = list(caller.contents)

    if not inventory:
        text = f"{HIGHLIGHT_COLOR}You are not carrying anything.{RESET_COLOR}"
        options = (
            {"desc": "Back to menu", "goto": "start"},
        )

        return text, options

    text = f"{TITLE_COLOR}--- Deposit Items ---{RESET_COLOR}\nSelect an item to deposit."
    options = []

    for item in inventory:
        equipped = caller.equipment.is_equipped(item)
        suffix = _format_item_line(item)
        equipped_str = f" {SUCCESS_COLOR}[equipped]{RESET_COLOR}" if equipped else ""
        options.append(
            {
                "desc": f"{item.key}{suffix}{equipped_str}",
                "goto": ("node_deposit_quantity", {"item_id": item.id}),
            }
        )

    options.append({"desc": "Back to menu", "goto": "start"})

    return text, options


def node_deposit_quantity(caller, **kwargs):
    item_id = kwargs.get("item_id")
    item_obj = None

    for obj in caller.contents:
        if obj.id == item_id:
            item_obj = obj
            break

    if item_obj is None:
        text = f"{ERROR_COLOR}That item is no longer in your inventory.{RESET_COLOR}"
        options = (
            {"desc": "Back to deposit list", "goto": "node_deposit_select"},
            {"desc": "Back to menu", "goto": "start"},
        )
        return text, options

    is_stackable = getattr(item_obj, "is_stackable", False)
    max_qty = getattr(item_obj, "quantity", 1)

    if not is_stackable or max_qty <= 1:
        return _execute_deposit(caller, **{"item_id": item_id, "count": 1})

    text = (
        f"{TITLE_COLOR}--- Deposit {item_obj.key} ---{RESET_COLOR}\n"
        f"You have {max_qty}.\n\n"
        "How many to deposit?"
    )
    options = [
        {"desc": "1", "goto": (_execute_deposit, {"item_id": item_id, "count": 1})},
        {"desc": "X (custom)", "goto": ("node_deposit_custom_qty", {"item_id": item_id, "max_qty": max_qty})},
        {"desc": f"All ({max_qty})", "goto": (_execute_deposit, {"item_id": item_id, "count": "all"})},
        {"desc": "Cancel", "goto": "node_deposit_select"},
    ]

    return text, options


def node_deposit_custom_qty(caller, raw_string, **kwargs):
    item_id = kwargs.get("item_id")
    max_qty = kwargs.get("max_qty", 1)

    item_obj = None
    for obj in caller.contents:
        if obj.id == item_id:
            item_obj = obj
            break

    if item_obj is None:
        caller.msg(f"{ERROR_COLOR}That item is no longer in your inventory.{RESET_COLOR}")
        return "node_deposit_select"

    text = (
        f"{TITLE_COLOR}--- Deposit {item_obj.key} ---{RESET_COLOR}\n"
        f"You have {max_qty}.\n\n"
        f"{HIGHLIGHT_COLOR}How many to deposit?{RESET_COLOR}"
    )
    custom_options = (
        {"key": "_default", "goto": ("node_deposit_custom_qty", {"item_id": item_id, "max_qty": max_qty, "custom_qty_state": "awaiting"})},
    )

    if kwargs.get("custom_qty_state") != "awaiting":
        return text, custom_options

    try:
        count = int(raw_string.strip())
    except ValueError:
        caller.msg(f"{ERROR_COLOR}Invalid number. Enter a quantity between 1 and {max_qty}.{RESET_COLOR}")
        return text, custom_options

    if count < 1:
        caller.msg(f"{ERROR_COLOR}Quantity must be at least 1.{RESET_COLOR}")
        return text, custom_options

    count = min(count, max_qty)
    return _execute_deposit(caller, **{"item_id": item_id, "count": count})


def _execute_deposit(caller, **kwargs):
    item_id = kwargs.get("item_id")
    count = kwargs.get("count", 1)
    caller.inventory.sync()

    item_obj = None
    for obj in caller.contents:
        if obj.id == item_id:
            item_obj = obj
            break

    if item_obj is None:
        caller.msg(f"{ERROR_COLOR}That item is no longer available.{RESET_COLOR}")
        return "node_deposit_select"

    item_qty = getattr(item_obj, "quantity", 1)
    deposit_qty = item_qty if count == "all" else min(count, item_qty)

    result = caller.bank.deposit(item_obj, deposit_qty)
    if result is None:
        return "node_deposit_select"

    return "node_deposit_select"


def node_withdraw_select(caller, **kwargs):
    items = caller.bank.list_items()

    if not items:
        text = f"{HIGHLIGHT_COLOR}Your bank vault is empty.{RESET_COLOR}"
        options = (
            {"desc": "Back to menu", "goto": "start"},
        )

        return text, options

    text = f"{TITLE_COLOR}--- Withdraw Items ---{RESET_COLOR}\nSelect an item to withdraw."
    options = []

    for item in items:
        suffix = _format_item_line(item)
        options.append(
            {
                "desc": f"{item.key}{suffix}",
                "goto": ("node_withdraw_quantity", {"item_id": item.id}),
            }
        )

    options.append({"desc": "Back to menu", "goto": "start"})

    return text, options


def node_withdraw_quantity(caller, **kwargs):
    item_id = kwargs.get("item_id")
    item_obj = caller.bank.get_item_by_id(item_id)

    if item_obj is None:
        text = f"{ERROR_COLOR}That item is no longer in your bank.{RESET_COLOR}"
        options = (
            {"desc": "Back to withdraw list", "goto": "node_withdraw_select"},
            {"desc": "Back to menu", "goto": "start"},
        )
        return text, options

    is_stackable = getattr(item_obj, "is_stackable", False)
    max_qty = getattr(item_obj, "quantity", 1)

    if not is_stackable or max_qty <= 1:
        return _execute_withdraw(caller, **{"item_id": item_id, "count": 1})

    text = (
        f"{TITLE_COLOR}--- Withdraw {item_obj.key} ---{RESET_COLOR}\n"
        f"Bank has {max_qty}.\n\n"
        "How many to withdraw?"
    )
    options = [
        {"desc": "1", "goto": (_execute_withdraw, {"item_id": item_id, "count": 1})},
        {"desc": "X (custom)", "goto": ("node_withdraw_custom_qty", {"item_id": item_id, "max_qty": max_qty})},
        {"desc": f"All ({max_qty})", "goto": (_execute_withdraw, {"item_id": item_id, "count": "all"})},
        {"desc": "Cancel", "goto": "node_withdraw_select"},
    ]

    return text, options


def node_withdraw_custom_qty(caller, raw_string, **kwargs):
    item_id = kwargs.get("item_id")
    max_qty = kwargs.get("max_qty", 1)

    item_obj = caller.bank.get_item_by_id(item_id)
    if item_obj is None:
        caller.msg(f"{ERROR_COLOR}That item is no longer in your bank.{RESET_COLOR}")
        return "node_withdraw_select"

    text = (
        f"{TITLE_COLOR}--- Withdraw {item_obj.key} ---{RESET_COLOR}\n"
        f"Bank has {max_qty}.\n\n"
        f"{HIGHLIGHT_COLOR}How many to withdraw?{RESET_COLOR}"
    )
    custom_options = (
        {"key": "_default", "goto": ("node_withdraw_custom_qty", {"item_id": item_id, "max_qty": max_qty, "custom_qty_state": "awaiting"})},
    )

    if kwargs.get("custom_qty_state") != "awaiting":
        return text, custom_options

    try:
        count = int(raw_string.strip())
    except ValueError:
        caller.msg(f"{ERROR_COLOR}Invalid number. Enter a quantity between 1 and {max_qty}.{RESET_COLOR}")
        return text, custom_options

    if count < 1:
        caller.msg(f"{ERROR_COLOR}Quantity must be at least 1.{RESET_COLOR}")
        return text, custom_options

    count = min(count, max_qty)
    return _execute_withdraw(caller, **{"item_id": item_id, "count": count})


def _execute_withdraw(caller, **kwargs):
    item_id = kwargs.get("item_id")
    count = kwargs.get("count", 1)
    item_obj = caller.bank.get_item_by_id(item_id)

    if item_obj is None:
        caller.msg(f"{ERROR_COLOR}That item is no longer available.{RESET_COLOR}")
        return "node_withdraw_select"

    max_qty = getattr(item_obj, "quantity", 1)
    withdraw_qty = max_qty if count == "all" else min(count, max_qty)

    caller.inventory.sync()
    try:
        caller.equipment.validate_inventory_space()
    except EquipmentError as err:
        caller.msg(f"{ERROR_COLOR}{err}{RESET_COLOR}")
        return "node_withdraw_select"

    result = caller.bank.withdraw(item_obj.id, withdraw_qty)

    return "node_withdraw_select"


def node_exit(caller, **kwargs):
    text = "Closing banking menu."

    return text, None