"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Generic NPC dialogue nodes, shared by simple talking NPCs.
"""

from systems.ui.colors import (
    RESET_COLOR,
    TITLE_COLOR,
    dialog as _dialog,
)


# Public constant definitions

# Said by an NPC that names no parting line of its own.
DEFAULT_FAREWELL = '"Farewell."'

# Said by a conversation whose NPC could not be resolved at all.
UNKNOWN_NPC_FAREWELL = "Farewell."



def menu_npc(caller: object) -> object:
    """
    Purpose: Recover the NPC this conversation is with.

    Entry:
        caller is the Character in the menu.

    Exit/Returns:
        Returns the NPC object, or None if no menu is running.

    Module Globals:
        None

    Methodology:
        The NPC is handed to EvMenu as a plain keyword argument, and EvMenu
        assigns leftover keywords onto the menu INSTANCE rather than passing
        them down as node kwargs. Reading kwargs["npc"] inside a node
        therefore finds nothing; the menu on the caller is where it lives.

    Notes/References:
        Only startnode_input=(str, dict) reaches the start node as kwargs.

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    menu = caller.ndb._evmenu

    if menu is None:
        return None

    npc = getattr(menu, "npc", None)

    return npc


def resolve_farewell(npc: object) -> str:
    """
    Purpose: Decide WHAT an NPC says on parting. Not where, and not when.

    Entry:
        npc is the NPC object, or None.

    Exit/Returns:
        Returns the spoken line, unstyled.

    Module Globals:
        DEFAULT_FAREWELL read.
        UNKNOWN_NPC_FAREWELL read.

    Methodology:
        An NPC own db.farewell wins; otherwise the generic line. A menu whose
        NPC keeps its dialogue somewhere else -- the shopkeep, whose lines
        come from its shop definition -- overrides this by declaring its own
        CLOSING_TEXT, and still leaves the PRINTING to close_menu.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    if npc is None:
        return UNKNOWN_NPC_FAREWELL

    spoken = npc.db.farewell or DEFAULT_FAREWELL

    return spoken


def npc_farewell(caller: object, menu: object) -> str:
    """
    Purpose: The parting line for a generic NPC conversation.

    Entry:
        caller is the Character leaving the conversation.
        menu is the BlackoutEvMenu being closed.

    Exit/Returns:
        Returns the styled farewell.

    Module Globals:
        None

    Methodology:
        Reads the NPC off the closing menu rather than off the caller: the
        same object either way, but the menu is the one guaranteed to still
        be holding the reference at teardown.

    Notes/References:
        Wired in as this module CLOSING_TEXT below.

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    npc = getattr(menu, "npc", None)
    spoken = resolve_farewell(npc)
    styled = _dialog(spoken)

    return styled


# Spoken by BlackoutEvMenu.close_menu, however the conversation ends -- the
# "Goodbye" option, the q binding, or walking into another menu. This is the
# ONLY place an NPC says goodbye.
CLOSING_TEXT = npc_farewell


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
    npc = menu_npc(caller)

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
    Purpose: End the conversation in-fiction, by choosing to.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns ("", None). The None closes the menu; the empty text is the
        point -- see below.

    Module Globals:
        None

    Methodology:
        This node prints NOTHING. Closing the menu is what prints the
        farewell, via CLOSING_TEXT, so that choosing "Goodbye" and typing q
        produce the same parting line rather than two rival copies of it that
        can drift apart.

    Notes/References:
        The option survives because a conversation should be endable in
        character, not only by a menu key.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    return "", None
