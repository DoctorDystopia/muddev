from commands.command import Command
from evennia.commands.cmdset import CmdSet
from items.inventory.display import render_grid

HIGHLIGHT_COLOR = "|y"
TITLE_COLOR = "|w"
RESET_COLOR = "|n"
ERROR_COLOR = "|r"


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
