
# Public constant definitions
TITLE_COLOR = "|w"
HIGHLIGHT_COLOR = "|y"
RESET_COLOR = "|n"



def start(caller: object, **kwargs) -> tuple:
    """
    Purpose: Generic start node for NPC dialogue menus.

    Entry:
        caller is a valid Evennia Character object
        kwargs["npc"] is the NPC object being spoken to

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        TITLE_COLOR read
        RESET_COLOR read

    Methodology:
        Retrieves the NPC from kwargs. Generates a greeting
        using the NPC's description or a default message.
        Subclasses should override or provide their own start node.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    npc = kwargs.get("npc")

    if npc:
        npc_desc = npc.db.desc or "An NPC."
        greeting = npc.db.greeting or f'"Greetings, traveler."'
        text = (
            f"{TITLE_COLOR}{npc.key}{RESET_COLOR}\n"
            f"{npc_desc}\n\n"
            f"{greeting}"
        )
    else:
        text = f"{TITLE_COLOR}Unknown NPC{RESET_COLOR}\nSomeone stands before you."

    options = (
        {"desc": "Goodbye.", "goto": "node_goodbye"},
    )

    return text, options



def node_goodbye(caller: object, **kwargs) -> tuple:
    """
    Purpose: Exit node for NPC conversations.

    Entry:
        caller is a valid Evennia Character object
        kwargs["npc"] is the NPC object

    Exit/Returns:
        Returns a tuple of (text, None) to exit the menu.

    Module Globals:
        None

    Methodology:
        Shows a farewell message and returns None options
        to close the menu.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    npc = kwargs.get("npc")

    if npc:
        farewell = npc.db.farewell or f'"Farewell."'
        text = farewell
    else:
        text = "Farewell."

    return text, None
