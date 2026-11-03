"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The dialogue of NPC_AUG_HOSPITAL_1, the contact at the Al
             Wasta Regional Public Hospital (DESIGN-0015, Phase 4). The
             trail of the missing augments ends here. The contact admits
             the thefts, gives the player one sample, and explains the
             graft.

             EVERY LINE HERE IS A PLACEHOLDER. Nick owns the lore and the
             names (10/30/2026). Each node says what happens in the beat, in
             a marked stage direction, and nothing more.
"""

from systems.interface.menus.dialogue import menu_npc
from systems.gameplay.quests import constants as quest_constants
from systems.gameplay.quests.content.quest_augmentation_intro import (
    NPC_HOSPITAL_KEY,
    NPC_HOSPITAL_NAME,
    QUEST_KEY as INTRO_QUEST_KEY,
    STEP_GRAFT,
    STEP_REPORT,
    STEP_TRAIL,
)
from systems.interface.ui.colors import (
    dialog as _dialog,
    highlight as _hl,
    title as _line,
)


# Public constant definitions
NPC_NAME = NPC_HOSPITAL_NAME
NPC_DESC = "Placeholder. The contact at the Public Hospital."
NPC_FAREWELL = "[Placeholder farewell of the Hospital contact.]"

# A marked stage direction. The player reads it in grey until Nick writes
# the line.
_STAGE_PREFIX = "|x[Placeholder: "
_STAGE_SUFFIX = "]|n"


def _stage(direction: str) -> str:
    """One stage direction, marked as a placeholder."""
    return f"{_STAGE_PREFIX}{direction}{_STAGE_SUFFIX}"


def _advance(caller: object, action: str, argument: str) -> None:
    """Report a conversational beat to the quest engine."""
    caller.quests.update_progress(INTRO_QUEST_KEY, action, argument)


def _objectives(caller: object) -> str:
    """The objective lines of the quest, indented under a heading."""
    lines = caller.quests.objective_lines(INTRO_QUEST_KEY)

    return "\n".join([_hl("Objectives:")] + [f"  {line}" for line in lines])


def start(caller: object, **kwargs) -> tuple:
    """
    Purpose: Entry node. Route to the beat that the player is owed.

    Entry:
        caller is a Character. kwargs["npc"] is the NPC object.

    Exit/Returns:
        Returns (text, options) for the EvMenu node.

    Module Globals:
        NPC_NAME, NPC_DESC read.

    Methodology:
        A player on the trail step gets the confession. A player on a later
        step gets the graft reminder. Everyone else gets a line that gives
        nothing away.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    npc = menu_npc(caller)
    npc_name = NPC_NAME

    if npc:
        npc_name = npc.key

    status = caller.quests.status(INTRO_QUEST_KEY)

    if status == quest_constants.STATUS_ACTIVE:
        step_node = _STEP_NODES.get(caller.quests.current_step_key(INTRO_QUEST_KEY))

        if step_node is not None:
            return step_node(caller)

    text = "\n".join([
        _line(npc_name),
        NPC_DESC,
        "",
        _stage(f"{NPC_NAME} is busy, and gives nothing away."),
    ])

    options = ({"desc": "Placeholder: leave.", "goto": "node_goodbye"},)

    return text, options


def node_step_trail(caller: object, **kwargs) -> tuple:
    """The confession. The contact admits the thefts, out of need, and
    offers the player one sample to try. The option fires the talk target,
    and the next step hands the sample over through its on_enter hook."""
    text = "\n".join([
        _dialog(_stage(
            f"{NPC_NAME} admits that the Hospital takes the augments, out "
            "of need, and asks the candidate to understand.")),
        "",
        _dialog(_stage(
            f"{NPC_NAME} offers one sample, and tells the candidate how a "
            "body takes a graft.")),
    ])

    options = (
        {"desc": "Placeholder: take the sample.", "goto": _take_sample},
        {"desc": "Placeholder: leave.", "goto": "node_goodbye"},
    )

    return text, options


def _take_sample(caller: object, raw_string: str, **kwargs) -> str:
    """Satisfy the trail target. The graft step opens, and its on_enter
    hook gives the sample."""
    _advance(caller, quest_constants.ACTION_TALK, NPC_HOSPITAL_KEY)

    return "node_step_graft"


def node_step_graft(caller: object, **kwargs) -> tuple:
    """The graft lesson. No target fires here: the graft command reports
    the graft through notify_quests."""
    text = "\n".join([
        _dialog(_stage(
            f"{NPC_NAME} explains the graft, and that a Locus takes one "
            "deeper.")),
        "",
        _objectives(caller),
    ])

    options = ({"desc": "Placeholder: try it.", "goto": "node_goodbye"},)

    return text, options


def node_step_report(caller: object, **kwargs) -> tuple:
    """The contact waits to hear what the candidate tells the Clinic."""
    text = _dialog(_stage(f"{NPC_NAME} asks what the candidate will tell the Clinic."))

    options = ({"desc": "Placeholder: leave.", "goto": "node_goodbye"},)

    return text, options


def node_goodbye(caller: object, **kwargs) -> tuple:
    """End the conversation. The None closes the menu."""
    return "", None


# Which node greets a player mid-quest, by the step they are on.
_STEP_NODES = {
    STEP_TRAIL: node_step_trail,
    STEP_GRAFT: node_step_graft,
    STEP_REPORT: node_step_report,
}


# Spoken by BlackoutEvMenu.close_menu, however the conversation ends.
CLOSING_TEXT = _dialog(NPC_FAREWELL)
