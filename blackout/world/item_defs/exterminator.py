"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: ItemDef entries for the Exterminator skill.

             The Task Writ opens the task pop-up. A Preceptor gives one free.
             A player can drop or destroy it, and a Preceptor gives a new
             one (Nick, 10/06/2026). The name and the text are TBD.
             DESIGN-0012, Phase 2.
"""

from systems.gameplay.exterminator.constants import TASK_WRIT_ITEM_KEY
from world.item_database import ItemDef



_TASK_WRIT_DESC = (
    "A strip of parchment under a wax seal. The ink rewrites itself to show "
    "your task."
)  # TBD text



ITEMS = {
    TASK_WRIT_ITEM_KEY: ItemDef(
        key=TASK_WRIT_ITEM_KEY,
        name="Task Writ",  # TBD name
        typeclass="typeclasses.task_writ.TaskWrit",
        desc=_TASK_WRIT_DESC,
        # Free from any Preceptor, so it has no value and no trade.
        value=0,
        weight=0.0,
        tradeable=False,
        stackable=False,
    ),
}
