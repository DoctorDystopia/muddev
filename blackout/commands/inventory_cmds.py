"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: Command for rendering the 32-slot inventory grid.
"""

from commands.command import Command
from evennia.commands.cmdset import CmdSet
from items.inventory.display import render_grid
from systems.ui.colors import (
    ERROR_COLOR,
    RESET_COLOR,
    TITLE_COLOR,
)



class CmdInventory(Command):
    key = "inventory"
    aliases = ["inv", "i"]
    locks = "cmd:all()"
    help_category = "General"

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


class InventoryCmdSet(CmdSet):
    key = "InventoryCmdSet"

    def at_cmdset_creation(self):
        self.add(CmdInventory())
