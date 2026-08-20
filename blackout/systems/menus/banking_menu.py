"""
Banking menu for Blackout.

Provides an EvMenu-based interface for depositing, withdrawing,
and browsing banked items. All storage logic is handled by
systems.banking.handler.BankHandler -- this module only manages
display formatting and navigation flow.
"""


from dataclasses import dataclass
from typing import Callable

from items.equipment.handler import EquipmentError
from systems.banking import messages
from items.equipment.constants import MAX_INVENTORY_SLOTS
from systems.menus.base_menu import parse_quantity
from systems.ui.colors import (
    ERROR_COLOR,
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    TITLE_COLOR,
)


SEPARATOR = "-" * 60


def _format_item_details(item):
    """Bracketed stat suffix for one item, e.g. " [1.0kg, 5 credits, T1 axe]"."""
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

    if not details:
        return ""

    return f" [{', '.join(details)}]"


# ─── Item grouping ─────────────────────────────────────────────────────────
# A stackable item carries its own count, so ten credits are one menu row.
# A non-stackable one does not, so eleven scrap plates used to be eleven rows
# and eleven separate deposits. Grouping collapses interchangeable objects
# into a single row with a total, and the transfer flow below moves as many
# of the group's members as the player asks for.


@dataclass
class _ItemGroup:
    """Interchangeable objects presented to the player as one row.

    key      — the shared object key
    details  — shared stat suffix from _format_item_details
    extra    — shared decoration, e.g. " [equipped]"
    items    — the member objects, in listing order
    quantity — total units: a stack's size, or one per non-stackable object
    """

    key: str
    details: str
    extra: str
    items: list
    quantity: int

    @property
    def ids(self):
        """Member dbids, the form the menu passes through EvMenu kwargs."""
        return [obj.id for obj in self.items]

    @property
    def desc(self):
        """The option label, matching the "(xN)" convention used elsewhere."""
        count = f" (x{self.quantity})" if self.quantity > 1 else ""

        return f"{self.key}{count}{self.details}{self.extra}"


def _group_items(caller, items, decorate=None):
    """
    Purpose: Collapse a list of objects into display groups, so identical
             items occupy one row and can be transferred in bulk.

    Entry:
        items is a list of objects to display.
        decorate is an optional (caller, item) -> str label suffix.

    Exit/Returns:
        Returns a list of _ItemGroup in first-seen order.

    Module Globals:
        None

    Methodology:
        Group on what the player can actually see -- key, stat suffix and
        decoration. Two objects that render identically are interchangeable
        as far as the menu is concerned; anything that renders differently
        (a different tier, or one of them equipped) stays its own row.

    Notes/References:
        Stackables are grouped by the same rule, which also folds the rare
        case of two separate stacks of one key into a single row.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    groups = {}
    ordered = []

    for item in items:
        details = _format_item_details(item)
        extra = decorate(caller, item) if decorate else ""
        signature = (item.key, details, extra)
        group = groups.get(signature)

        if group is None:
            group = _ItemGroup(
                key=item.key,
                details=details,
                extra=extra,
                items=[],
                quantity=0,
            )
            groups[signature] = group
            ordered.append(group)

        group.items.append(item)
        group.quantity += getattr(item, "quantity", 1)

    return ordered


def _resolve_ids(kwargs):
    """Read the selected dbids out of EvMenu kwargs.

    Accepts the single-id form as well: menu state persisted before grouping
    existed still carries `item_id`, and the item-detail node has only ever
    needed one.
    """
    ids = kwargs.get("item_ids")

    if ids is not None:
        return list(ids)

    single = kwargs.get("item_id")

    if single is None:
        return []

    return [single]


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

    for group in _group_items(caller, items):
        options.append(
            {
                "desc": group.desc,
                "goto": ("node_item_detail", {"item_ids": group.ids}),
            }
        )

    options.append({"desc": "Back to menu", "goto": "start"})

    return text, options


def node_item_detail(caller, **kwargs):
    item_ids = _resolve_ids(kwargs)
    item_objs = _resolve_items(caller, WITHDRAW_FLOW, item_ids)

    if not item_objs:
        text = f"{ERROR_COLOR}That item is no longer in your bank.{RESET_COLOR}"
        options = (
            {"desc": "Back to storage", "goto": "node_storage"},
            {"desc": "Back to menu", "goto": "start"},
        )
        return text, options

    item_obj = item_objs[0]

    item_desc = getattr(item_obj.db, "desc", None) or "No description."
    value = getattr(item_obj.db, "value", 0)
    weight = getattr(item_obj.db, "weight", 0.0)
    tradeable = getattr(item_obj.db, "tradeable", True)
    stackable = getattr(item_obj.db, "stackable", False)
    tool_type = getattr(item_obj.db, "tool_type", None)
    tier = getattr(item_obj.db, "tier", 0)
    req_level = getattr(item_obj.db, "req_level", 0)

    stored = sum(getattr(obj, "quantity", 1) for obj in item_objs)

    lines = [
        f"{TITLE_COLOR}--- {item_obj.key} ---{RESET_COLOR}",
        f"Description: {item_desc}",
        f"Value: {value} credits",
        f"Weight: {weight}kg",
        f"Tradeable: {HIGHLIGHT_COLOR}{'Yes' if tradeable else 'No'}{RESET_COLOR}",
        f"Stackable: {HIGHLIGHT_COLOR}{'Yes' if stackable else 'No'}{RESET_COLOR}",
        f"Stored: {HIGHLIGHT_COLOR}{stored}{RESET_COLOR}",
    ]

    if tool_type:
        lines.append(f"Tool: {tool_type} (Tier {tier}, Req. Level {req_level})")

    text = "\n".join(lines)

    options = (
        {
            "desc": f"Withdraw {item_obj.key}",
            "goto": ("node_withdraw_quantity", {"item_ids": item_ids}),
        },
        {"desc": "Back to storage", "goto": "node_storage"},
        {"desc": "Back to menu", "goto": "start"},
    )

    return text, options


# ─── Transfer flows ────────────────────────────────────────────────────────
# Deposit and withdraw are the same four-node flow -- select an item, choose a
# quantity, optionally type a custom quantity, execute -- running in opposite
# directions. They were previously written out twice, ~150 near-identical
# lines that had to be kept in step by hand. The direction-specific parts are
# gathered into a _TransferFlow below and the shared machinery takes one as a
# parameter.
#
# The public node_* functions remain thin module-level wrappers because EvMenu
# resolves a "goto" string by looking up that name in this module.


@dataclass
class _TransferFlow:
    """One direction of a bank transfer (deposit or withdraw).

    verb         — lowercase action word used in prompts, and the verb
                   messages.format_transfer renders the outcome with, so it
                   must be one of that module's VERB_* constants
    title        — heading for the select node ("Deposit Items")
    stock_label  — how the available count is phrased ("You have")
    empty_text   — shown when the source side holds nothing
    gone_text    — shown when the chosen item vanished mid-flow
    *_node       — node names, for navigation and for re-entry
    find_item    — (caller, item_id) -> object or None
    list_items   — (caller) -> list of selectable objects
    execute      — (caller, items, quantity) -> None; moves `quantity` units
                   drawn from the group `items`. Raises EquipmentError if the
                   destination cannot accept them at all
    decorate     — (caller, item) -> extra label suffix, e.g. "[equipped]"
    execute_goto — filled in by _make_execute_goto after construction, which
                   needs the finished flow to close over
    """

    verb: str
    title: str
    stock_label: str
    empty_text: str
    gone_text: str
    select_node: str
    quantity_node: str
    custom_node: str
    find_item: Callable
    list_items: Callable
    execute: Callable
    decorate: Callable | None = None
    execute_goto: Callable | None = None


def _find_carried(caller, item_id):
    """Locate a carried object by dbid."""
    for obj in caller.contents:
        if obj.id == item_id:
            return obj
    return None


def _list_carried(caller):
    """Selectable items on the character, with the slot map resynced first."""
    caller.inventory.sync()
    return list(caller.contents)


def _equipped_marker(caller, item):
    """Label suffix marking an item as currently equipped."""
    if caller.equipment.is_equipped(item):
        return f" {SUCCESS_COLOR}[equipped]{RESET_COLOR}"
    return ""


def _do_deposit(caller, items, quantity):
    """Move `quantity` units drawn from `items` into the bank.

    Returns the handler's TransferResult; _perform_transfer renders it.
    """
    return caller.bank.deposit_many(items, quantity)


def _do_withdraw(caller, items, quantity):
    """Move `quantity` units drawn from `items` out of the bank, space permitting.

    Returns the handler's TransferResult; _perform_transfer renders it.
    """
    caller.inventory.sync()
    caller.equipment.validate_inventory_space()

    return caller.bank.withdraw_many(items, quantity)


DEPOSIT_FLOW = _TransferFlow(
    verb=messages.VERB_DEPOSIT,
    title="Deposit Items",
    stock_label="You have",
    empty_text="You are not carrying anything.",
    gone_text="That item is no longer in your inventory.",
    select_node="node_deposit_select",
    quantity_node="node_deposit_quantity",
    custom_node="node_deposit_custom_qty",
    find_item=_find_carried,
    list_items=_list_carried,
    execute=_do_deposit,
    decorate=_equipped_marker,
)

WITHDRAW_FLOW = _TransferFlow(
    verb=messages.VERB_WITHDRAW,
    title="Withdraw Items",
    stock_label="Bank has",
    empty_text="Your bank vault is empty.",
    gone_text="That item is no longer in your bank.",
    select_node="node_withdraw_select",
    quantity_node="node_withdraw_quantity",
    custom_node="node_withdraw_custom_qty",
    find_item=lambda caller, item_id: caller.bank.get_item_by_id(item_id),
    list_items=lambda caller: caller.bank.list_items(),
    execute=_do_withdraw,
)


def _select_node(caller, flow):
    """Render the item-picker for one transfer direction."""
    items = flow.list_items(caller)

    if not items:
        text = f"{HIGHLIGHT_COLOR}{flow.empty_text}{RESET_COLOR}"
        return text, ({"desc": "Back to menu", "goto": "start"},)

    text = (
        f"{TITLE_COLOR}--- {flow.title} ---{RESET_COLOR}\n"
        f"Select an item to {flow.verb}."
    )
    options = []

    for group in _group_items(caller, items, decorate=flow.decorate):
        options.append(
            {
                "desc": group.desc,
                "goto": (flow.quantity_node, {"item_ids": group.ids}),
            }
        )

    options.append({"desc": "Back to menu", "goto": "start"})

    return text, options


def _resolve_items(caller, flow, item_ids):
    """Re-resolve selected dbids to live objects, dropping any that moved."""
    resolved = []

    for item_id in item_ids:
        item_obj = flow.find_item(caller, item_id)
        if item_obj is not None:
            resolved.append(item_obj)

    return resolved


def _available_quantity(items):
    """Total transferable units held by a group: stack sizes, or one each."""
    return sum(getattr(obj, "quantity", 1) for obj in items)


def _quantity_prompt(flow, item_key, max_qty, highlight=False):
    """Build the shared 'how many?' prompt text."""
    question = f"How many to {flow.verb}?"
    if highlight:
        question = f"{HIGHLIGHT_COLOR}{question}{RESET_COLOR}"

    return (
        f"{TITLE_COLOR}--- {flow.verb.capitalize()} {item_key} ---{RESET_COLOR}\n"
        f"{flow.stock_label} {max_qty}.\n\n"
        f"{question}"
    )


def _quantity_node(caller, flow, **kwargs):
    """Offer 1 / custom / all when several units are available, else execute."""
    item_ids = _resolve_ids(kwargs)
    items = _resolve_items(caller, flow, item_ids)

    if not items:
        text = f"{ERROR_COLOR}{flow.gone_text}{RESET_COLOR}"
        options = (
            {"desc": f"Back to {flow.verb} list", "goto": flow.select_node},
            {"desc": "Back to menu", "goto": "start"},
        )
        return text, options

    # Units, not objects: a stack of ten and ten separate plates both offer
    # ten. This is what lets non-stackables reach the quantity prompt at all
    # -- the check used to read one object's `quantity`, which is always 1
    # for them, so they were transferred one at a time with no prompt.
    max_qty = _available_quantity(items)

    if max_qty <= 1:
        # Nothing to ask: transfer immediately and re-render the picker.
        # NOTE we must return a rendered (text, options) here, not a node
        # NAME -- EvMenu._execute_node treats a node's non-tuple return as
        # display text, so the old `return _execute_deposit(...)` printed the
        # literal string "node_deposit_select" at the player instead of
        # navigating anywhere.
        _perform_transfer(caller, flow, item_ids, 1)
        return _select_node(caller, flow)

    text = _quantity_prompt(flow, items[0].key, max_qty)
    options = [
        {"desc": "1", "goto": (flow.execute_goto, {"item_ids": item_ids, "count": 1})},
        {"desc": "X (custom)", "goto": (flow.custom_node, {"item_ids": item_ids, "max_qty": max_qty})},
        {"desc": f"All ({max_qty})", "goto": (flow.execute_goto, {"item_ids": item_ids, "count": "all"})},
        {"desc": "Cancel", "goto": flow.select_node},
    ]

    return text, options


def _custom_qty_node(caller, flow, raw_string, **kwargs):
    """Read a typed quantity via EvMenu's _default option, then execute.

    Two-pass: the first visit renders the prompt and arms a _default option
    that re-enters this node with custom_qty_state='awaiting'; the second
    visit parses raw_string.
    """
    item_ids = _resolve_ids(kwargs)
    max_qty = kwargs.get("max_qty", 1)

    items = _resolve_items(caller, flow, item_ids)
    if not items:
        caller.msg(f"{ERROR_COLOR}{flow.gone_text}{RESET_COLOR}")
        return _select_node(caller, flow)

    text = _quantity_prompt(flow, items[0].key, max_qty, highlight=True)
    custom_options = (
        {
            "key": "_default",
            "goto": (
                flow.custom_node,
                {"item_ids": item_ids, "max_qty": max_qty, "custom_qty_state": "awaiting"},
            ),
        },
    )

    if kwargs.get("custom_qty_state") != "awaiting":
        return text, custom_options

    count, parse_error = parse_quantity(raw_string, max_qty)

    if parse_error is not None:
        caller.msg(f"{ERROR_COLOR}{parse_error}{RESET_COLOR}")
        return text, custom_options

    _perform_transfer(caller, flow, item_ids, count)
    return _select_node(caller, flow)


def _perform_transfer(caller, flow, item_ids, count):
    """
    Purpose: Move `count` units of one item group in this flow's direction.

    Entry:
        item_ids is a list of dbids resolvable by flow.find_item, all holding
        the same kind of item.
        count is a positive int, or the string "all".

    Exit/Returns:
        None. Messages the caller with the outcome, successful or not.

    Module Globals:
        None

    Methodology:
        Re-resolve the group (members may have moved since the option was
        drawn), clamp the count to the units actually present, delegate to
        the flow's execute callable, then render the TransferResult it hands
        back. A partial transfer prints what moved AND why it stopped, which
        is the one place both halves are worth saying: the player picked a
        quantity from a menu and needs to know it was not honoured in full.

    Notes/References:
        Returns nothing on purpose. Callers differ in what they must hand
        back to EvMenu -- a node needs rendered (text, options), a goto
        callable needs a node name -- so neither is decided here.

        The handler no longer messages anyone; systems/banking/messages.py
        owns the wording, shared with the deposit/withdraw commands.

    Author: Nick Hobar
    Creation date: 07/31/2026
    """
    items = _resolve_items(caller, flow, item_ids)

    if not items:
        caller.msg(f"{ERROR_COLOR}That item is no longer available.{RESET_COLOR}")
        return

    max_qty = _available_quantity(items)
    quantity = max_qty if count == "all" else min(count, max_qty)

    try:
        result = flow.execute(caller, items, quantity)
    except EquipmentError as err:
        caller.msg(f"{ERROR_COLOR}{err}{RESET_COLOR}")
        return

    _report_transfer(caller, flow, result)


def _report_transfer(caller, flow, result) -> None:
    """Print the outcome of one transfer, tinting anything that went wrong.

    A partial success prints both lines: what landed, then the refusal that
    cut it short. A total failure prints only the refusal, because
    format_transfer already returns that as its whole message.
    """
    line = messages.format_transfer(result, flow.verb)

    if line and result.success:
        caller.msg(line)
    elif line:
        caller.msg(f"{ERROR_COLOR}{line}{RESET_COLOR}")

    if result.success and result.error:
        caller.msg(f"{ERROR_COLOR}{result.error}{RESET_COLOR}")


def _make_execute_goto(flow):
    """Build the EvMenu goto-callable that performs `flow` then returns its
    select node's NAME. Goto callables (unlike nodes) are expected to return
    a node name, so this is the one context where returning the string is
    correct."""
    def _goto(caller, raw_string, **kwargs):
        _perform_transfer(caller, flow, _resolve_ids(kwargs), kwargs.get("count", 1))
        return flow.select_node

    return _goto


# ─── EvMenu node entry points ──────────────────────────────────────────────
# Named wrappers so EvMenu's string-based "goto" can resolve them.


DEPOSIT_FLOW.execute_goto = _make_execute_goto(DEPOSIT_FLOW)
WITHDRAW_FLOW.execute_goto = _make_execute_goto(WITHDRAW_FLOW)


def node_deposit_select(caller, **kwargs):
    return _select_node(caller, DEPOSIT_FLOW)


def node_deposit_quantity(caller, **kwargs):
    return _quantity_node(caller, DEPOSIT_FLOW, **kwargs)


def node_deposit_custom_qty(caller, raw_string, **kwargs):
    return _custom_qty_node(caller, DEPOSIT_FLOW, raw_string, **kwargs)


def node_withdraw_select(caller, **kwargs):
    return _select_node(caller, WITHDRAW_FLOW)


def node_withdraw_quantity(caller, **kwargs):
    return _quantity_node(caller, WITHDRAW_FLOW, **kwargs)


def node_withdraw_custom_qty(caller, raw_string, **kwargs):
    return _custom_qty_node(caller, WITHDRAW_FLOW, raw_string, **kwargs)


def node_exit(caller, **kwargs):
    text = "Closing banking menu."

    return text, None