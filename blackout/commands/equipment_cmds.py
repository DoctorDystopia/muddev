
"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Commands for equipment and inventory management via EvMenu.
"""



from commands.command import Command
from commands.constants import HELP_CATEGORY_GENERAL
from evennia import CmdSet


# Public constant definitions
EQUIPMENT_MODULE_PATH = "systems.menus.equipment_menu"



class CmdEquipment(Command):
    """
    Purpose: Opens the equipment management menu.

    Entry:
        self.caller is a valid Evennia Character object
        self.args is an optional string (unused)

    Exit/Returns:
        No conditions. Launches an EvMenu on the caller.

    Module Globals:
        EQUIPMENT_MODULE_PATH read

    Methodology:
        Starts EvMenu using the equipment_menu module.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key = "equip"
    aliases = ["equipment"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_GENERAL


    def func(self) -> None:
        """
        Purpose: Executes the equipment command, launching the menu.

        Entry:
            self.caller is a valid Evennia Character object

        Exit/Returns:
            No conditions

        Module Globals:
            EQUIPMENT_MODULE_PATH read

        Methodology:
            Starts the EvMenu with the equipment menu module.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        caller = self.caller

        from evennia.utils.evmenu import EvMenu

        EvMenu(
            caller,
            EQUIPMENT_MODULE_PATH,
            startnode="start",
        )



class EquipmentCmdSet(CmdSet):
    """
    Purpose: CmdSet containing equipment management commands.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        Adds CmdEquipment to the cmdset during creation.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key = "EquipmentCmdSet"


    def at_cmdset_creation(self) -> None:
        """
        Purpose: Populates the cmdset with equipment commands.

        Entry:
            No conditions

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Instantiates and adds CmdEquipment to this cmdset.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        equip_cmd = CmdEquipment()
        self.add(equip_cmd)
