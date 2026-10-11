"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: The work that a Preceptor does for a player: find a Preceptor
             in the room, give a task, and give a Task Writ.

             Two callers share it: the `task` command and the Preceptor
             dialogue. A dialogue option cannot send `task new`, because an
             open EvMenu takes every line that the player sends. Thus, both
             call these routines, and the two cannot act differently.
             DESIGN-0012, Phase 2.
"""

from systems.gameplay.exterminator import constants
from systems.gameplay.exterminator.preceptors import PRECEPTOR_DB



# The attribute that marks an object as a Preceptor NPC. PreceptorNPC in
# typeclasses/npcs.py reads it from the NpcDef of the NPC.
PRECEPTOR_KEY_ATTR: str = "preceptor_key"

# The class attribute that marks an item as a Task Writ. TaskWrit in
# typeclasses/task_writ.py declares it. A flag, not an isinstance check, so
# this module does not import a typeclass.
TASK_WRIT_FLAG_ATTR: str = "is_task_writ"

MSG_BAG_FULL: str = "Your bag is full. Make room for the {item} first."



def carried_writ(caller):
    """Give the first Task Writ that the caller carries, or None."""
    for item in caller.contents:
        if getattr(item, TASK_WRIT_FLAG_ATTR, False):
            return item

    return None


def preceptor_here(caller, name: str = ""):
    """
    Purpose: Find a Preceptor NPC in the room of the caller.

    Entry:
        caller is a Character. name is "" or the start of a Preceptor name.

    Exit/Returns:
        Returns the first Preceptor NPC that matches, or None.

    Module Globals:
        PRECEPTOR_KEY_ATTR, PRECEPTOR_DB read.

    Methodology:
        A Preceptor NPC is an object that gives a preceptor_key
        that names a row of PRECEPTOR_DB. With a name, match the start of
        the object key, with no case.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    location = getattr(caller, "location", None)

    if location is None:
        return None

    wanted = name.strip().lower()

    for obj in location.contents:
        preceptor_key = getattr(obj, PRECEPTOR_KEY_ATTR, "")

        if preceptor_key not in PRECEPTOR_DB:
            continue

        if wanted and not obj.key.lower().startswith(wanted):
            continue

        return obj

    return None


def give_writ(caller, preceptor_npc) -> str:
    """
    Purpose: Give the caller a free Task Writ, if the caller has none.

    Entry:
        caller is a Character. preceptor_npc is the Preceptor that gives it.

    Exit/Returns:
        Returns the line for the caller.

    Module Globals:
        ITEM_DB read.

    Methodology:
        1. If the caller carries a writ, give MSG_WRIT_ALREADY.
        2. Make the writ, and move it into the bag.
        3. If the bag refused it, delete it and say that the bag is full.

    Notes/References:
        ItemDef.create builds the item detached, then moves it. A refused
        move leaves it with no location. ITEM_DB is imported inside, because
        world/item_defs/exterminator.py imports this package.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    from world.item_database import ITEM_DB

    item_def = ITEM_DB[constants.TASK_WRIT_ITEM_KEY]
    held = carried_writ(caller)

    if held is not None:
        return constants.MSG_WRIT_ALREADY.format(item=item_def.name)

    writ = item_def.create(location=caller, home=caller)

    if writ.location != caller:
        writ.delete()
        return MSG_BAG_FULL.format(item=item_def.name)

    return constants.MSG_WRIT_GIVEN.format(preceptor=preceptor_npc.key, item=item_def.name)


def take_task(caller, preceptor_npc, rng=None) -> list:
    """
    Purpose: Take a task from a Preceptor NPC, and a writ if none is held.

    Entry:
        caller is a Character. preceptor_npc is a Preceptor NPC.
        rng is a random.Random, or None for the default.

    Exit/Returns:
        Returns the lines for the caller, in order.

    Module Globals:
        None.

    Methodology:
        1. Ask the handler to assign a task.
        2. If it did, and the caller has no writ, give one.

    Notes/References:
        Nick, 10/06/2026: a Preceptor gives the writ free.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    preceptor_key = getattr(preceptor_npc, PRECEPTOR_KEY_ATTR, "")
    assigned, message = caller.exterminator.assign(preceptor_key, rng=rng)
    lines = [message]
    held = carried_writ(caller)

    if assigned and held is None:
        writ_line = give_writ(caller, preceptor_npc)
        lines.append(writ_line)

    return lines
