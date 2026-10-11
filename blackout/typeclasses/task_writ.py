"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: TaskWrit, the item that opens the Exterminator task pop-up.
"""

from systems.gameplay.exterminator import constants as ext_const
from typeclasses.items import BaseItem



# The label of the inventory action. OSRS labels the same action on its
# enchanted gem "Check". TBD.
_CHECK_LABEL: str = "Check"



class TaskWrit(BaseItem):
    """
    Purpose: A carried item that shows the Exterminator task.

    Entry:
        Spawned from the "task_writ" ItemDef.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        The item holds no fact. The task lives on the character, through
        ExterminatorHandler. Thus, a lost writ loses nothing, and a new writ
        from a Preceptor shows the same task.

        The inventory action is the `task` command. CmdTask opens the task
        pop-up for a client that draws pop-ups, with this writ as its anchor.
        Every other client gets the task as text.

    Notes/References:
        DESIGN-0012, Phase 2. Nick, 10/06/2026: the task shows in a pop-up
        that opens from an item.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """

    # Read by systems/gameplay/exterminator/service.py, which must not import
    # a typeclass. A class attribute, so a writ in the database has it.
    is_task_writ = True

    def inventory_actions(self) -> list:
        """Give the `task` command as the first action of the inventory row."""
        return [{"command": ext_const.TASK_COMMAND_KEY, "label": _CHECK_LABEL}]
