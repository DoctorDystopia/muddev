"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: The dialogue of every Preceptor.

             The options call systems/gameplay/exterminator/service.py, the
             same routines that `task new` and `task writ` call. An option
             cannot send those lines, because the open menu takes them.

             ONE MODULE FOR EVERY PRECEPTOR (10/09/2026). Atticus Quin and
             Atum Musa had one file each, and the only difference was two
             lines of text. The lines of each Preceptor are now one row of
             _LINES, keyed by npc key. A Preceptor with no row speaks the
             default lines, so a new Preceptor needs no edit here.

             All lines are TBD. Nick writes the voice of each Preceptor
             later. DESIGN-0012, Phase 2.
"""

from systems.gameplay.exterminator import service
from systems.interface.menus.dialogue import menu_npc, node_goodbye, npc_farewell
from systems.interface.ui.colors import dialog as _dialog, title as _line
from world.npc_database import npc_def_of



# This menu is bound to the room of the NPC. Walking away closes it.
ROOM_BOUND = True

_FALLBACK_NAME = "Preceptor"

# The keys of a row of _LINES.
_GREETING = "greeting"
_OPTION_TASK = "option_task"

# The lines of a Preceptor with no row of its own.
_DEFAULT_LINES = {
    _GREETING: '"You want work. Good. There is always work."',  # TBD line
    _OPTION_TASK: "I want a task.",                               # TBD line
}

# npc key -> the lines that differ from _DEFAULT_LINES.
_LINES = {
    "atticus_quin": {},
    "atum_musa": {
        _GREETING: '"Have you come to learn the truth of Extermination, '
                   'young one?"',                                 # TBD line
        _OPTION_TASK: "I want a task. Time to Exterminate!",      # TBD line
    },
}

_OPTION_WRIT = "I need a new Task Writ."   # TBD line
_OPTION_BACK = "Back."
_OPTION_GOODBYE = "Goodbye."



def _lines_of(npc: object) -> dict:
    """
    Purpose: Give the lines of one Preceptor.

    Entry:
        npc is the Preceptor of the menu, or None.

    Exit/Returns:
        Returns a dict with every key of _DEFAULT_LINES.

    Module Globals:
        _DEFAULT_LINES, _LINES read.

    Methodology:
        The row of the NPC overrides the defaults one key at a time, so a
        row gives only the lines that differ.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/09/2026
    """
    npc_def = npc_def_of(npc) if npc is not None else None
    npc_key = npc_def.key if npc_def is not None else ""
    lines = dict(_DEFAULT_LINES)
    lines.update(_LINES.get(npc_key, {}))

    return lines


def _goodbye_option() -> dict:
    """The option that ends the conversation."""
    return {"desc": _OPTION_GOODBYE, "goto": "node_goodbye"}


def start(caller: object, **kwargs) -> tuple:
    """
    Purpose: The first node. Shows the task of the player and the options.

    Entry:
        caller is a Character. The menu carries the NPC.

    Exit/Returns:
        Returns (text, options) for the EvMenu node.

    Module Globals:
        _OPTION_* read.

    Methodology:
        The task lines come from ExterminatorHandler.summary_lines, the same
        lines that `task` prints. The greeting and the task option come from
        the row of this Preceptor.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    npc = menu_npc(caller)
    npc_name = npc.key if npc is not None else _FALLBACK_NAME
    lines = _lines_of(npc)
    task_lines = caller.exterminator.summary_lines()

    text_lines = [_line(npc_name), "", _dialog(lines[_GREETING]), ""] + task_lines
    text = "\n".join(text_lines)

    options = [
        {"desc": lines[_OPTION_TASK], "goto": _take_task},
        {"desc": _OPTION_WRIT, "goto": _take_writ},
        _goodbye_option(),
    ]

    return text, options


def _take_task(caller: object, raw_string: str = "", **kwargs) -> tuple:
    """Take a task from this Preceptor, then show what happened."""
    npc = menu_npc(caller)
    lines = service.take_task(caller, npc)

    return "node_result", {"lines": lines}


def _take_writ(caller: object, raw_string: str = "", **kwargs) -> tuple:
    """Get a new Task Writ from this Preceptor, then show what happened."""
    npc = menu_npc(caller)
    line = service.give_writ(caller, npc)

    return "node_result", {"lines": [line]}


def node_result(caller: object, raw_string: str = "", **kwargs) -> tuple:
    """Show the lines of the last action, with a way back."""
    lines = kwargs.get("lines", [])
    text = "\n".join(lines)

    options = [
        {"desc": _OPTION_BACK, "goto": "start"},
        _goodbye_option(),
    ]

    return text, options



# Spoken by BlackoutEvMenu.close_menu, however the conversation ends.
CLOSING_TEXT = npc_farewell
