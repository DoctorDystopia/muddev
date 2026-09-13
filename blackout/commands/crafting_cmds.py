"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/12/2026
Description: Crafting commands that belong to the PLAYER rather than to a
             facility.

             `toggle craft confirm` lived in CraftCmdSet until 09/12/2026, and
             CraftCmdSet hangs on each workbench -- so the preference could
             only be set while standing next to one. That was invisible to a
             telnet player, who types it at the anvil, and fatal to the Godot
             Options pane, whose button is pressed from anywhere and was
             answered "Command not found" everywhere but a crafting room. A
             preference stored on the character is reached through the
             character. `craft` stays on the facility, because it IS the
             facility's verb.
"""

from commands.command import Command
from commands.constants import HELP_CATEGORY_CRAFTING
from evennia import CmdSet
from systems.interface.statefeed import constants as feed_const

# Every line this module sends a player is crafting, so the routing tag is
# bound once here rather than repeated at every call site.
_MSG_CRAFTING = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_CRAFTING}

_MSG_TOGGLED: str = "Crafting confirmation turned {status}."
_STATUS_ON: str = "ON"
_STATUS_OFF: str = "OFF"

# Unset means on. The crafting menu's _confirm_required reads the same
# attribute with the same default.
_DEFAULT_CRAFT_CONFIRM: bool = True


class CmdToggleCraftConfirm(Command):
    """
    Toggle the crafting confirmation prompt on or off.

    Usage:
        toggle craft confirm

    When confirmation is OFF, selecting a recipe in the crafting menu
    will skip the confirmation step and craft immediately.
    """

    key = "toggle craft confirm"
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_CRAFTING


    def func(self) -> None:
        """
        Purpose: Flip the caller's crafting confirmation preference.

        Entry:
            self.caller is a character.

        Exit/Returns:
            No conditions. Messages the caller with the new state.

        Module Globals:
            _MSG_CRAFTING, _MSG_TOGGLED, _STATUS_ON, _STATUS_OFF and
            _DEFAULT_CRAFT_CONFIRM read.

        Methodology:
            An unset preference resolves to the default before it is flipped,
            so the first toggle turns confirmation OFF, matching what the
            crafting menu was already doing for that player.

        Notes/References:
            Read by _confirm_required in systems/interface/menus/crafting_menu.py.

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        caller = self.caller
        current = caller.db.craft_confirm

        if current is None:
            current = _DEFAULT_CRAFT_CONFIRM

        caller.db.craft_confirm = not current
        status = _STATUS_ON if caller.db.craft_confirm else _STATUS_OFF
        caller.msg((_MSG_TOGGLED.format(status=status), _MSG_CRAFTING))


class CraftingCmdSet(CmdSet):
    """
    Purpose: Crafting commands that do not need a facility.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        Hangs on the CHARACTER. See the module docstring for why the confirm
        toggle cannot live on the workbench.

    Notes/References:
        `craft` itself stays in CraftCmdSet in typeclasses/crafting_facilities.py.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    key = "CraftingCmdSet"


    def at_cmdset_creation(self) -> None:
        """
        Purpose: Populate the cmdset.

        Entry:
            No conditions.

        Exit/Returns:
            No conditions.

        Module Globals:
            None.

        Methodology:
            One add.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/12/2026
        """
        self.add(CmdToggleCraftConfirm())
