"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: CraftingFacility base typeclass and the craft command attached
             to facilities.
"""

from evennia import Command, CmdSet
from evennia import DefaultObject
from evennia.utils.evmenu import EvMenu

from commands.constants import HELP_CATEGORY_CRAFTING
from typeclasses.objects import ObjectParent


CRAFT_COMMAND_KEY = "craft"
CRAFT_COMMAND_LOCKS = "cmd:all()"
CRAFT_CMD_SET_KEY = "crafting_facility_cmdset"
CRAFT_CMD_SET_PRIORITY = 10
CRAFT_MENU_MODULE_PATH = "systems.menus.crafting_menu"


class CmdCraft(Command):
    """
    Purpose: Opens the crafting menu at this crafting facility.

    Entry:
        self.caller is a valid Evennia Character object
        self.obj is the crafting facility object

    Exit/Returns:
        No conditions. Launches an EvMenu on the caller.

    Module Globals:
        CRAFT_MENU_MODULE_PATH read

    Methodology:
        Launches the crafting EvMenu. Passes the facility
        object as a kwarg for potential facility-specific logic.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key = CRAFT_COMMAND_KEY
    locks = CRAFT_COMMAND_LOCKS
    help_category = HELP_CATEGORY_CRAFTING


    def func(self) -> None:
        """
        Purpose: Executes the craft command, opening the crafting menu.

        Entry:
            self.caller is a valid Character
            self.obj is the crafting facility Object

        Exit/Returns:
            No conditions

        Module Globals:
            CRAFT_MENU_MODULE_PATH read

        Methodology:
            Starts EvMenu using the shared crafting menu module.
            Passes facility=self.obj to the start node via startnode_input --
            EvMenu's own **kwargs only become attributes on the menu
            instance, they are not forwarded to the start node.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        caller = self.caller
        facility = self.obj

        caller.msg(f"(You approach the {facility.key}.)")

        EvMenu(
            caller,
            CRAFT_MENU_MODULE_PATH,
            startnode="start",
            startnode_input=("", {"facility": facility}),
        )



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
        caller = self.caller
        current = caller.db.craft_confirm
        if current is None:
            current = True
        caller.db.craft_confirm = not current
        status = "ON" if caller.db.craft_confirm else "OFF"
        caller.msg(f"Crafting confirmation turned {status}.")



class CraftCmdSet(CmdSet):
    """
    Purpose: Stores the craft command for crafting facilities.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        CRAFT_CMD_SET_KEY read
        CRAFT_CMD_SET_PRIORITY read

    Methodology:
        Adds CmdCraft to the cmdset during creation.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key = CRAFT_CMD_SET_KEY
    priority = CRAFT_CMD_SET_PRIORITY


    def at_cmdset_creation(self) -> None:
        """
        Purpose: Populates the cmdset with the craft command.

        Entry:
            No conditions

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Instantiates and adds CmdCraft to this cmdset.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        craft_command = CmdCraft()
        self.add(craft_command)
        toggle_command = CmdToggleCraftConfirm()
        self.add(toggle_command)



class CraftingFacility(ObjectParent, DefaultObject):
    """
    Purpose: A workbench or facility where players can craft items.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        At creation, adds the CraftCmdSet persistently.
        Optionally stores a list of recipe categories or
        specific recipes available at this facility.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """


    def at_object_creation(self) -> None:
        """
        Purpose: Called once when the crafting facility is first created.

        Entry:
            No conditions

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Calls parent creation. Adds CraftCmdSet persistently.
            Sets a default description.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        parent_class = super()
        parent_class.at_object_creation()

        self.cmdset.add_default(CraftCmdSet, persistent=True)

        self.db.desc = "A sturdy workbench covered in tools and scrap."
