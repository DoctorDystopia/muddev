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
            caller.msg(f"{ERROR_COLOR}Slot {text} is empty.{RESET_COLOR}")
            return -1, None

        return index, item

    if text.isdigit():
        caller.msg(
            f"{ERROR_COLOR}You only have {SLOTS_TOTAL} inventory "
            f"slots.{RESET_COLOR}"
        )
        return -1, None

    found = caller.search(text, candidates=caller.contents)

    if found is None:
        return -1, None

    slot = caller.inventory.find_slot(found)

    return slot, found


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
            caller.msg(f"{ERROR_COLOR}You don't have an inventory.{RESET_COLOR}")
            return

        handler = caller.inventory
        handler.sync()

        title, grid_str = render_grid(handler)
        output = f"{TITLE_COLOR}--- {title} ---{RESET_COLOR}\n{grid_str}"
        caller.msg(text=(output, {"type": "inventory"}))
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
            caller.msg(f"{ERROR_COLOR}You don't have an inventory.{RESET_COLOR}")
            return

        parts = self.args.split()

        if len(parts) != SWAP_ARGUMENT_COUNT:
            caller.msg("Usage: swap <slot> <slot>")
            return

        first = parse_slot_number(parts[0])
        second = parse_slot_number(parts[1])

        if first < 0 or second < 0:
            caller.msg(
                f"{ERROR_COLOR}Both slots must be numbers between 1 and "
                f"{SLOTS_TOTAL}.{RESET_COLOR}"
            )
            return

        handler = caller.inventory
        handler.sync()

        try:
            changed = handler.move_slot(first, second)
        except InventoryError as swap_err:
            caller.msg(f"{ERROR_COLOR}{swap_err}{RESET_COLOR}")
            return

        if not changed:
            caller.msg("Nothing to move.")
            return

        caller.msg(
            f"{SUCCESS_COLOR}Swapped slots {parts[0]} and "
            f"{parts[1]}.{RESET_COLOR}"
        )
        feed.emit_inventory(caller)


class InventoryCmdSet(CmdSet):
    key = "InventoryCmdSet"

    def at_cmdset_creation(self):
        self.add(CmdInventory())
        self.add(CmdSwap())
