"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: Commands for rendering and rearranging the 32-slot inventory grid.
"""

from commands.command import Command
from commands.constants import HELP_CATEGORY_GENERAL
from evennia.commands.cmdset import CmdSet
from items.inventory.display import render_grid
from items.inventory.handler import SLOTS_TOTAL, InventoryError
from systems.statefeed import events as feed
from systems.ui.colors import (
    ERROR_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    TITLE_COLOR,
)
from systems.statefeed import constants as feed_const

# Every line this module sends a player is about your inventory, so the
# routing tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_INVENTORY = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_INVENTORY}


# ─── Public constant definitions ─────────────────────────────────────────────

# How many arguments `swap` takes. Named so the arity check is not a literal.
SWAP_ARGUMENT_COUNT: int = 2


# ─── Public routines ─────────────────────────────────────────────────────────

def parse_slot_number(text: str) -> int:
    """
    Purpose: Turn a player-typed slot number into a grid index.

    Entry:
        text - a raw argument, already stripped.

    Exit/Returns:
        Returns the 0-BASED grid index, or -1 when `text` is not a slot number
        at all (it may still be an item name -- that is the caller's problem,
        not an error here).

    Module Globals:
        SLOTS_TOTAL read.

    Methodology:
        Players count slots from 1, because that is what `inventory` prints --
        display.format_slot_cell renders `slot_idx + 1`. Every command that
        takes a slot therefore takes a 1-based one, and this is the single
        place the conversion happens.

        An out-of-range number returns -1 rather than raising, so a caller can
        report "slot 99 is outside your inventory" with the same message it
        uses for a name that matched nothing.

    Notes/References:
        systems/statefeed/inventory.py performs the same +1 when it builds the
        action commands the 3D pane sends, so what the pane sends and what a
        player types are the same string.

    Author: Nick Hobar
    Creation date: 08/15/2026
    """
    if not text.isdigit():
        return -1

    number = int(text)

    if number < 1 or number > SLOTS_TOTAL:
        return -1

    return number - 1


def resolve_carried_item(caller, text: str):
    """
    Purpose: Resolve "7" or "rusty scrap spear" to something the player is
    carrying.

    Entry:
        caller - the puppeted Character.
        text   - a raw argument, already stripped and non-empty.

    Exit/Returns:
        Returns an (index, item) pair. On failure returns (-1, None), having
        already messaged the caller.

    Module Globals:
        None.

    Methodology:
        A slot number is tried FIRST and is the unambiguous form. This is the
        detail that makes the graphical client honest: two stacks of rusty
        scrap metal are a real thing, so a pane sending `equip rusty scrap
        metal` would be sending a command whose target it cannot predict. A
        slot index is exactly what the pane has, and telnet players get the
        shorter path as a side effect.

        Name lookup falls through to caller.search over contents only.
        Equipped items are held at location=None by EquipmentHandler.equip, so
        they are correctly invisible to this -- `equip` on something already
        worn should fail to find it rather than half-succeed.

    Notes/References:
        caller.search messages the caller itself on no-match and multi-match,
        which is why this returns without a message in that branch.

    Author: Nick Hobar
    Creation date: 08/15/2026
    """
    index = parse_slot_number(text)

    if index >= 0:
        item = caller.inventory.get_slot_content(index)

        if item is None:
            caller.msg(
                (f"{ERROR_COLOR}Slot {text} is empty.{RESET_COLOR}", _MSG_INVENTORY))
            return -1, None

        return index, item

    if text.isdigit():
        caller.msg(
            (f"{ERROR_COLOR}You only have {SLOTS_TOTAL} inventory "
            f"slots.{RESET_COLOR}", _MSG_INVENTORY)
        )
        return -1, None

    found = caller.search(text, candidates=caller.contents)

    if found is None:
        return -1, None

    slot = caller.inventory.find_slot(found)

    return slot, found


def split_item_and_count(args: str) -> tuple:
    """
    Purpose: Split "<item> [quantity|all]" into its two halves, so a
             multi-word item key survives a trailing number.

    Entry:
        args - a raw argument string, already stripped. May be empty.

    Exit/Returns:
        Returns an (item_text, count) pair. `count` is an int, the string
        QUANTITY_ALL_KEYWORD for an explicit "all", or None for an omitted
        quantity. `item_text` is "" for empty input, which every caller reports
        in its own words.

    Module Globals:
        QUANTITY_ALL_KEYWORD read.

    Methodology:
        A trailing integer is the quantity and everything before it is the
        name, so "rusty scrap metal 5" parses correctly. A trailing "all" is
        spelled out by players often enough to accept explicitly.

        "ALL" AND AN OMITTED QUANTITY ARE NO LONGER THE SAME ANSWER, and the
        distinction is why the count is three-valued. An omitted quantity means
        "what is in that slot" -- one object for a non-stackable, the whole
        stack for a stackable. `all` means "every unit of this you are
        carrying", which for eight separate rusty metal chunks is eight
        objects in seven other slots. A caller that wants the old
        "as many as there are" reading maps QUANTITY_ALL_KEYWORD to None
        itself; `withdraw` does, because a vault has no slots to distinguish.

        The single-token case is left whole on purpose: "7" is a slot number
        and not a quantity, which is what lets `deposit 7` and `sell 7` mean
        slot seven rather than seven of nothing.

    Notes/References:
        This lived as _split_name_and_count in typeclasses/bank_nodes.py until
        09/02/2026, when `sell` needed the identical split. It belongs beside
        resolve_carried_item, which is what the name half is fed to -- one
        owner for how a player names an item and a quantity, rather than one
        copy per commanding system.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    from systems.menus.base_menu import QUANTITY_ALL_KEYWORD

    parts = args.split()
    count = None

    if len(parts) > 1 and parts[-1].isdigit():
        count = int(parts[-1])
        parts = parts[:-1]
    elif len(parts) > 1 and parts[-1].lower() == QUANTITY_ALL_KEYWORD:
        count = QUANTITY_ALL_KEYWORD
        parts = parts[:-1]

    item_text = " ".join(parts)

    return item_text, count


def carried_group(caller, item) -> list:
    """
    Purpose: List every carried object a player would call the same thing as
             `item`, in slot order.

    Entry:
        caller - the puppeted Character.
        item   - a carried object naming the group.

    Exit/Returns:
        Returns a list of objects, LOWEST SLOT FIRST, always containing `item`
        itself. Returns [item] when the character has no inventory handler.

    Module Globals:
        None.

    Methodology:
        SLOT ORDER IS THE WHOLE POINT. Eight separate rusty metal chunks are
        eight objects in eight slots, and "sell three of them" has to name
        three particular ones. Ascending slot order is the only ordering the
        player can see and predict -- it is what `inventory` prints -- so a
        group verb consumes from the lowest number up and the same command
        twice does the same thing.

        Read from InventoryHandler.all_items rather than caller.contents,
        because contents comes back in database order and carries no slot at
        all. Equipped objects are held at location=None and are correctly
        absent: a group verb reached from a carried slot must not silently
        strip what the player is wearing.

        Grouped on the lowercased key alone, matching what
        shop_service.get_sell_items and bank_nodes._find_carried_group already
        do. Two objects a player would name identically are interchangeable to
        every one of those readers, and a fourth rule here would be a fourth
        answer to one question.

    Notes/References:
        `item` itself is guaranteed present even when the handler has not yet
        slotted it, so a caller can always act on at least what was clicked.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    handler = getattr(caller, "inventory", None)

    if handler is None:
        return [item]

    wanted = str(item.key).lower()
    group = []

    for _slot_index, carried in handler.all_items():
        if carried is not None and str(carried.key).lower() == wanted:
            group.append(carried)

    if item not in group:
        group.append(item)

    return group


def group_units(caller, item) -> int:
    """
    Purpose: Count every unit of `item` the character is carrying, across all
             its slots.

    Entry:
        caller - the puppeted Character.
        item   - a carried object naming the group.

    Exit/Returns:
        Returns the total: a stack's size for a stackable, one per object for
        a non-stackable, summed over the whole group.

    Module Globals:
        None.

    Methodology:
        THIS IS NOT THE ROW'S `quantity`, and conflating the two is the trap.
        A row's quantity is what the pane draws in the corner of that frame,
        and for one of eight chunks it is 1 -- printing 8 on all eight cells
        would say the player has sixty-four. This is what a group VERB can
        reach, which is the bound a "how many?" prompt needs.

    Notes/References:
        Reads the same group carried_group builds, so what the prompt offers
        and what the command consumes cannot disagree.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    total = 0

    for member in carried_group(caller, item):
        total += max(0, int(getattr(member, "quantity", 1) or 1))

    return total


# ─── Public routines / Classes ───────────────────────────────────────────────

class CmdInventory(Command):
    """
    show what you are carrying

    Usage:
      inventory

    Displays your 32 carry slots as a grid. Slot numbers shown here are the
    ones `swap`, `equip` and `unequip` accept.
    """

    key = "inventory"
    aliases = ["inv", "i"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_GENERAL

    def func(self):
        caller = self.caller
        if not hasattr(caller, "inventory"):
            caller.msg(
                (f"{ERROR_COLOR}You don't have an inventory.{RESET_COLOR}",
                 _MSG_INVENTORY))
            return

        handler = caller.inventory
        handler.sync()

        title, grid_str = render_grid(handler)
        output = f"{TITLE_COLOR}--- {title} ---{RESET_COLOR}\n{grid_str}"
        caller.msg((output, _MSG_INVENTORY))
        feed.emit_inventory(caller)


class CmdSwap(Command):
    """
    rearrange your inventory

    Usage:
      swap <slot> <slot>

    Exchanges the contents of two inventory slots, using the numbers shown by
    `inventory`. Either slot may be empty. This is also what the 3D inventory
    pane sends when you drag one item onto another.

    Example:
      swap 3 17
    """

    key = "swap"
    aliases = ["arrange"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_GENERAL

    def func(self):
        caller = self.caller

        if not hasattr(caller, "inventory"):
            caller.msg(
                (f"{ERROR_COLOR}You don't have an inventory.{RESET_COLOR}",
                 _MSG_INVENTORY))
            return

        parts = self.args.split()

        if len(parts) != SWAP_ARGUMENT_COUNT:
            caller.msg(("Usage: swap <slot> <slot>", _MSG_INVENTORY))
            return

        first = parse_slot_number(parts[0])
        second = parse_slot_number(parts[1])

        if first < 0 or second < 0:
            caller.msg(
                (f"{ERROR_COLOR}Both slots must be numbers between 1 and "
                f"{SLOTS_TOTAL}.{RESET_COLOR}", _MSG_INVENTORY)
            )
            return

        handler = caller.inventory
        handler.sync()

        try:
            changed = handler.move_slot(first, second)
        except InventoryError as swap_err:
            caller.msg((f"{ERROR_COLOR}{swap_err}{RESET_COLOR}", _MSG_INVENTORY))
            return

        if not changed:
            caller.msg(("Nothing to move.", _MSG_INVENTORY))
            return

        caller.msg(
            (f"{SUCCESS_COLOR}Swapped slots {parts[0]} and "
            f"{parts[1]}.{RESET_COLOR}", _MSG_INVENTORY)
        )
        feed.emit_inventory(caller)


class InventoryCmdSet(CmdSet):
    key = "InventoryCmdSet"

    def at_cmdset_creation(self):
        self.add(CmdInventory())
        self.add(CmdSwap())
