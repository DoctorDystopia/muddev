"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: A dialogue script as an EvMenu (DESIGN-0017). One beat of the
             dialogue runner is one node: its text, and one option for each
             response.

             PRESENTATION ONLY. The rules are in
             `systems/gameplay/dialogue/`. This module starts a Conversation,
             keeps it on the menu, and gives each beat to EvMenu. Thus, a
             script gets the same look, the same key footer, and the same
             pop-up in the Godot client as each other menu.

             A FAULT CLOSES THE CONVERSATION. A script that the server
             cannot run gives the player one plain line and a log entry. It
             never gives the player a traceback.
"""

from evennia.utils import logger

from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue import loader
from systems.gameplay.dialogue.runner import Beat, Conversation, DialogueContext
from systems.gameplay.dialogue.script import DialogueScriptError
from systems.interface.menus.base_menu import (
    MENU_UNAVAILABLE_MSG,
    start_blackout_menu,
)
from systems.interface.menus.dialogue import npc_farewell
from systems.interface.statefeed import constants as feed_const


# ─── Public constant definitions ─────────────────────────────────────────────

# The python path of this module. The launcher gives it to EvMenu.
MENU_MODULE_PATH: str = "systems.interface.menus.dialogue_script"

# The node that shows each beat after the first one.
NODE_BEAT: str = "node_beat"

# The keyword of the option that carries the index of a response.
RESPONSE_KWARG: str = "response"


# ─── Private constant definitions ────────────────────────────────────────────

_MSG_DIALOGUE = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_DIALOGUE}


# ─── Private helper routines ─────────────────────────────────────────────────

def _conversation_of(caller: object) -> Conversation | None:
    """The Conversation of the menu that the caller has open, or None."""
    menu = caller.ndb._evmenu

    if menu is None:
        return None

    return getattr(menu, "conversation", None)


def _as_node(beat: Beat) -> tuple:
    """
    Purpose: Give one beat to EvMenu as a node.

    Entry:
        beat is what the runner made.

    Exit/Returns:
        Returns (text, options). options is None for a beat that ends the
        conversation, and EvMenu then closes the menu.

    Module Globals:
        NODE_BEAT, RESPONSE_KWARG read.

    Methodology:
        Each option goes to the same node, and carries only the index of its
        response. The Conversation on the menu holds the rest.

    Notes/References:
        A node returns (text, options). Only a goto callable returns a node
        name (CLAUDE.md, Evennia gotcha 3).

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    if beat.is_ending():
        return beat.text, None

    options = []

    for index, response in enumerate(beat.responses):
        options.append({
            "desc": response.label,
            "goto": (NODE_BEAT, {RESPONSE_KWARG: index}),
        })

    return beat.text, tuple(options)


def _fault_node(caller: object, error: Exception) -> tuple:
    """Log a script fault, and close the conversation with one plain line."""
    logger.log_err(f"{dialogue_const.LOG_TAG} {error} (talker: {caller})")

    return MENU_UNAVAILABLE_MSG, None


def _script_farewell(caller: object, menu: object) -> str:
    """
    Purpose: The parting line of a conversation from a dialogue script.

    Entry:
        caller is the Character that leaves. menu is the closing menu.

    Exit/Returns:
        Returns the styled farewell.

    Module Globals:
        None.

    Methodology:
        1. If the script has a farewell cue, return its text.
        2. Else, or on a fault, return the generic farewell of the NPC.

    Notes/References:
        BlackoutEvMenu.close_menu calls it, however the conversation ends.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    conversation = getattr(menu, "conversation", None)

    if conversation is not None:
        try:
            parting = conversation.farewell()
        except DialogueScriptError as error:
            logger.log_err(f"{dialogue_const.LOG_TAG} {error} (talker: {caller})")
            parting = None

        if parting:
            return parting

    generic = npc_farewell(caller, menu)

    return generic


# Spoken by BlackoutEvMenu.close_menu, however the conversation ends.
CLOSING_TEXT = _script_farewell


# ─── The nodes ───────────────────────────────────────────────────────────────

def start(caller: object, raw_string: str = "", **kwargs) -> tuple:
    """
    Purpose: The entry node. Show the first beat of the conversation.

    Entry:
        caller is a Character. The menu holds a Conversation.

    Exit/Returns:
        Returns (text, options) for the EvMenu node.

    Module Globals:
        None.

    Methodology:
        Open the conversation at its start cue. The script routes from
        there on the state of the player.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    conversation = _conversation_of(caller)

    if conversation is None:
        return MENU_UNAVAILABLE_MSG, None

    try:
        beat = conversation.open()
    except DialogueScriptError as error:
        return _fault_node(caller, error)

    return _as_node(beat)


def node_beat(caller: object, raw_string: str = "", **kwargs) -> tuple:
    """
    Purpose: Show the beat that follows the response that the player gave.

    Entry:
        kwargs[RESPONSE_KWARG] is the index of the response.

    Exit/Returns:
        Returns (text, options) for the EvMenu node.

    Module Globals:
        RESPONSE_KWARG read.

    Methodology:
        Give the index to the conversation. Each `do` line under the
        response runs there, before the next beat shows.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    conversation = _conversation_of(caller)
    index = kwargs.get(RESPONSE_KWARG)

    if conversation is None or index is None:
        return MENU_UNAVAILABLE_MSG, None

    try:
        beat = conversation.choose(index)
    except DialogueScriptError as error:
        return _fault_node(caller, error)

    return _as_node(beat)


# ─── Public routines ─────────────────────────────────────────────────────────

def open_script(caller: object, npc: object, script_key: str) -> object:
    """
    Purpose: Start a conversation from a dialogue script.

    Entry:
        caller is the Character that talks. npc is the NPC, or None.
        script_key names a compiled script.

    Exit/Returns:
        Returns the menu, or None if the script does not load. The caller
        then gets one plain line, and the log gets the reason.

    Module Globals:
        MENU_MODULE_PATH read.

    Methodology:
        1. Load the script. The loader refuses a script with a problem.
        2. Make the Conversation.
        3. Start the menu through start_blackout_menu, as each menu does.
           EvMenu puts the two keywords on the menu instance.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    try:
        script = loader.get_script(script_key)
    except DialogueScriptError as error:
        logger.log_err(f"{dialogue_const.LOG_TAG} {error} (talker: {caller})")
        caller.msg((MENU_UNAVAILABLE_MSG, _MSG_DIALOGUE))

        return None

    context = DialogueContext(caller=caller, npc=npc)
    conversation = Conversation(script, context)
    menu = start_blackout_menu(
        caller,
        MENU_MODULE_PATH,
        startnode="start",
        npc=npc,
        conversation=conversation,
    )

    return menu
