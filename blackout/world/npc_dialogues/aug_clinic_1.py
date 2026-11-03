"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The dialogue of NPC_AUG_CLINIC_1, the recruiter of the
             Augmentation Clinic (DESIGN-0015, Phase 4). It gives the
             Augmentation intro quest and takes the report at its end.

             EVERY LINE HERE IS A PLACEHOLDER. Nick owns the lore and the
             names (10/30/2026). Each node says what happens in the beat, in
             a marked stage direction, and nothing more. The structure is
             the android's: one entry node that routes on the quest step,
             one node for each step, and a goodbye that closes the menu.

             Two closing options stand at the report, the truth and a cover
             story. Both complete the quest. Nick decides whether they
             differ.
"""

from systems.interface.menus.dialogue import menu_npc
from systems.gameplay.quests import constants as quest_constants
from systems.gameplay.quests.content.quest_augmentation_intro import (
    NPC_CLINIC_KEY,
    NPC_CLINIC_NAME,
    QUEST_KEY as INTRO_QUEST_KEY,
    STEP_GRAFT,
    STEP_RECRUIT,
    STEP_REPORT,
    STEP_TRAIL,
)
from systems.gameplay.quests.loader import GLOBAL_QUEST_REGISTRY
from systems.interface.ui.colors import (
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    dialog as _dialog,
    highlight as _hl,
    title as _line,
)
from systems.interface.statefeed import constants as feed_const

# Every line this module sends a player is something an NPC says, so the
# routing tag is bound one time here.
_MSG_DIALOGUE = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_DIALOGUE}


# Public constant definitions
NPC_NAME = NPC_CLINIC_NAME
NPC_DESC = "Placeholder. The recruiter of the Augmentation Clinic."
NPC_FAREWELL = "[Placeholder farewell of the Clinic recruiter.]"

# The talk target of the closing beat. The quest module names the first
# one, and this is the second, as the android has two.
_TALK_END_ARGUMENT = f"{NPC_CLINIC_KEY}_end"

# A marked stage direction. The player reads it in grey until Nick writes
# the line.
_STAGE_PREFIX = "|x[Placeholder: "
_STAGE_SUFFIX = "]|n"


def _stage(direction: str) -> str:
    """One stage direction, marked as a placeholder."""
    return f"{_STAGE_PREFIX}{direction}{_STAGE_SUFFIX}"


def _quest_status(caller: object) -> str:
    """The relationship of the caller to the intro quest, from the handler."""
    status = caller.quests.status(INTRO_QUEST_KEY)

    return status


def _advance(caller: object, action: str, argument: str) -> None:
    """Report a conversational beat to the quest engine. A dialogue node is
    the one caller that knows which quest it advances."""
    caller.quests.update_progress(INTRO_QUEST_KEY, action, argument)


def _objectives(caller: object) -> str:
    """The objective lines of the quest, indented under a heading."""
    lines = caller.quests.objective_lines(INTRO_QUEST_KEY)

    return "\n".join([_hl("Objectives:")] + [f"  {line}" for line in lines])


# ─── The entry node ──────────────────────────────────────────────────────────

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
        Dispatch on the quest STEP, through _STEP_NODES, as the android
        does. A completed quest gets the post-quest node. A quest not yet
        taken gets the offer.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    npc = menu_npc(caller)
    npc_name = NPC_NAME

    if npc:
        npc_name = npc.key

    status = _quest_status(caller)

    if status == quest_constants.STATUS_COMPLETED:
        return node_post_quest(caller)

    if status == quest_constants.STATUS_ACTIVE:
        step_node = _STEP_NODES.get(caller.quests.current_step_key(INTRO_QUEST_KEY))

        if step_node is not None:
            return step_node(caller)

    text = "\n".join([
        _line(npc_name),
        NPC_DESC,
        "",
        _stage(f"{NPC_NAME} greets the candidate and hints at a job."),
    ])

    options = (
        {"desc": "Placeholder: ask about the job.", "goto": "node_quest_offer"},
        {"desc": "Placeholder: leave.", "goto": "node_goodbye"},
    )

    return text, options


def node_quest_offer(caller: object, **kwargs) -> tuple:
    """The recruiter names the job, and the player accepts or declines."""
    blueprint = GLOBAL_QUEST_REGISTRY.get(INTRO_QUEST_KEY)

    if blueprint is None:
        text = _dialog(_stage("The quest is not registered."))
        options = ({"desc": "Never mind.", "goto": "node_goodbye"},)

        return text, options

    if not caller.quests.is_available(INTRO_QUEST_KEY):
        text = _dialog(_stage("The job is already taken."))
        options = ({"desc": "Right.", "goto": "start"},)

        return text, options

    text = "\n".join([
        _dialog(_stage(
            f"{NPC_NAME} explains that augments go missing from the Clinic, "
            "and asks the candidate to find out who takes them.")),
        "",
        _hl(f"Accept the quest '{blueprint.title}'?"),
    ])

    options = (
        {"desc": f"Accept: {blueprint.title}", "goto": _accept_quest},
        {"desc": "Not yet.", "goto": "node_goodbye"},
    )

    return text, options


def _accept_quest(caller: object, raw_string: str, **kwargs) -> str:
    """Accept the quest. A goto callable, so it may return a node name."""
    accepted = caller.quests.accept_quest(INTRO_QUEST_KEY)

    if accepted:
        caller.msg((f"{SUCCESS_COLOR}You take the job.{RESET_COLOR}", _MSG_DIALOGUE))
    else:
        caller.msg((f"{HIGHLIGHT_COLOR}You have already taken this quest.{RESET_COLOR}",
                    _MSG_DIALOGUE))

    return "node_step_recruit"


# ─── The step nodes ──────────────────────────────────────────────────────────

def node_step_recruit(caller: object, **kwargs) -> tuple:
    """The brief. This is where `talk:npc_aug_clinic_1` fires: the recruit
    step is satisfied by having had the conversation."""
    _advance(caller, quest_constants.ACTION_TALK, NPC_CLINIC_KEY)

    text = "\n".join([
        _dialog(_stage(
            f"{NPC_NAME} gives the brief: the trail of the missing augments "
            "points at the Public Hospital.")),
        "",
        _objectives(caller),
    ])

    options = ({"desc": "Placeholder: agree and go.", "goto": "node_goodbye"},)

    return text, options


def node_step_waiting(caller: object, **kwargs) -> tuple:
    """The recruiter waits for the report. No target fires here."""
    text = "\n".join([
        _dialog(_stage(f"{NPC_NAME} asks whether the candidate found the trail yet.")),
        "",
        _objectives(caller),
    ])

    options = ({"desc": "Placeholder: not yet.", "goto": "node_goodbye"},)

    return text, options


def node_step_report(caller: object, **kwargs) -> tuple:
    """
    Purpose: The report, with two closing options. Both complete the quest.

    Entry:
        caller is a Character on the report step.

    Exit/Returns:
        Returns (text, options) for the EvMenu node.

    Module Globals:
        None.

    Methodology:
        The firing is NOT on entry to this node. The last target completes
        the quest and runs the reward callback, and that must come after
        the player read the scene. Two options stand here, the truth and a
        cover story, so the structure holds the choice that the lore asks
        for. Nick decides what each one costs.

    Notes/References:
        The android's resolution node is the model.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    text = "\n".join([
        _dialog(_stage(f"{NPC_NAME} asks for the report.")),
    ])

    options = (
        {"desc": "Placeholder: tell the truth about the Hospital.",
         "goto": (_finish_quest, {"story": "truth"})},
        {"desc": "Placeholder: give a cover story.",
         "goto": (_finish_quest, {"story": "cover"})},
    )

    return text, options


def _finish_quest(caller: object, raw_string: str, **kwargs) -> str:
    """Satisfy the final target. kwargs["story"] names the option taken, and
    nothing reads it yet. The completion and the reward fire inside
    update_progress, before the closing node renders."""
    _advance(caller, quest_constants.ACTION_TALK, _TALK_END_ARGUMENT)

    return "node_post_quest"


def node_post_quest(caller: object, **kwargs) -> tuple:
    """What the recruiter says to a player who finished the quest."""
    text = _dialog(_stage(f"{NPC_NAME} thanks the candidate, and points at the Locus."))

    options = ({"desc": "Placeholder: leave.", "goto": "node_goodbye"},)

    return text, options


def node_goodbye(caller: object, **kwargs) -> tuple:
    """End the conversation. The None closes the menu, and CLOSING_TEXT
    carries the farewell."""
    return "", None


# Which node greets a player mid-quest, by the step they are on.
_STEP_NODES = {
    STEP_RECRUIT: node_step_recruit,
    STEP_TRAIL: node_step_waiting,
    STEP_GRAFT: node_step_waiting,
    STEP_REPORT: node_step_report,
}


# Spoken by BlackoutEvMenu.close_menu, however the conversation ends.
CLOSING_TEXT = _dialog(NPC_FAREWELL)
