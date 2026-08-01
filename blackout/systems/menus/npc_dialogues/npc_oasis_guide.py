"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Dialogue nodes for the oasis guide NPC, including its quest
             offer and progress branches.
"""

from systems.quests.loader import GLOBAL_QUEST_REGISTRY


# Public constant definitions
NPC_NAME = "Lone Android"
NPC_DESC = (
    "A solitary synthetic figure stands motionless at the edge of a small, "
    "impossibly green oasis. Its photoreceptors gleam faintly as it watches "
    "you approach, one mechanical hand resting on a rusted irrigation pipe."
)
OASIS_QUEST_KEY = "oasis"

from systems.ui.colors import (
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    dialog as _dialog,
    highlight as _hl,
    title as _line,
)




def _quest_status(caller: object) -> str:
    """
    Purpose: Determines the caller's relationship to the oasis quest.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns "not_started", "active", or "completed".

    Module Globals:
        OASIS_QUEST_KEY read

    Methodology:
        Checks the caller's active and completed quest lists.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    active_quests = caller.db.active_quests or {}
    completed_quests = caller.db.completed_quests or []

    if OASIS_QUEST_KEY in completed_quests:
        status = "completed"
    elif OASIS_QUEST_KEY in active_quests:
        status = "active"
    else:
        status = "not_started"

    return status



def start(caller: object, **kwargs) -> tuple:
    """
    Purpose: Entry node for the Lone Android NPC at the oasis.

    Entry:
        caller is a valid Evennia Character object
        kwargs["npc"] is the NPC object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        NPC_NAME read
        NPC_DESC read
        OASIS_QUEST_KEY read

    Methodology:
        Checks the caller's quest status to tailor dialogue options.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    npc = kwargs.get("npc")
    npc_name = NPC_NAME

    if npc:
        npc_name = npc.key

    quest_status = _quest_status(caller)

    greeting = _dialog(
        '"Another soul stumbled out of the dunes. '
        "You look half-dead. The wastes don't forgive.\""
    )

    text_lines = [
        _line(npc_name),
        NPC_DESC,
        "",
        greeting,
    ]
    text = "\n".join(text_lines)

    options_list = [
        {
            "desc": "Who are you? What is this place?",
            "goto": "node_who_are_you",
        },
    ]

    if quest_status == "not_started":
        options_list.append({
            "desc": "I could use some help. Do you have work?",
            "goto": "node_quest_offer",
        })
    elif quest_status == "active":
        options_list.append({
            "desc": "I'm back. What should I do next?",
            "goto": "node_quest_progress",
        })
    else:
        options_list.append({
            "desc": "The oasis looks good. Thanks again.",
            "goto": "node_post_quest",
        })

    options_list.append({
        "desc": "Goodbye for now.",
        "goto": "node_goodbye",
    })

    options_tuple = tuple(options_list)

    return text, options_tuple



def node_who_are_you(caller: object, **kwargs) -> tuple:
    """
    Purpose: NPC explains its identity and the oasis.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        Provides lore about the android's past as a farm hand
        and the oasis as a remnant of the old world.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    dialog = _dialog(
        '"I was... I AM a farm hand. '
        "Before the Blackout, I tended crops in the Nile Delta. "
        "Now this oasis is all that remains of that life. "
        "The Hegemony does not care about a single android "
        "or the patch of green it keeps alive. So I stay. "
        "I do what I was made to do.\""
    )
    text = dialog

    options = (
        {"desc": "That's admirable. Can I help?", "goto": "node_quest_offer"},
        {"desc": "Fascinating. Tell me more about yourself.", "goto": "node_android_lore"},
        {"desc": "I should go.", "goto": "node_goodbye"},
    )

    return text, options



def node_android_lore(caller: object, **kwargs) -> tuple:
    """
    Purpose: NPC shares deeper lore about itself and the world.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        Provides world-building dialogue about the android observations
        of the Hegemony and the wastes.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    dialog = _dialog(
        '"I have been here since the collapse. '
        "I have watched the Hegemony drones scan the horizon. "
        "They are looking for something. Or someone. "
        "I do not know which. But the sky burns brighter every night, "
        "and the Nexus grows. Out there, in the city of Neo Cairo, "
        "they say the Illusive Man plans to connect everyone to a "
        "new network. I do not trust it. Nothing is free.\""
    )
    text = dialog

    options = (
        {"desc": "How can I help you protect this place?", "goto": "node_quest_offer"},
        {"desc": "Interesting. I will keep that in mind.", "goto": "node_goodbye"},
    )

    return text, options



def node_quest_offer(caller: object, **kwargs) -> tuple:
    """
    Purpose: NPC offers the starter quest to the caller.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        OASIS_QUEST_KEY read

    Methodology:
        Checks if the quest is available. If so, presents
        acceptance options. Calls QuestHandler.accept_quest
        on confirmation.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    quest_blueprint = GLOBAL_QUEST_REGISTRY.get(OASIS_QUEST_KEY)
    blueprint_is_valid = quest_blueprint is not None

    if not blueprint_is_valid:
        dialog = _dialog(
            '"I have nothing for you right now. '
            "Check back later.\""
        )
        text = dialog
        options = (
            {"desc": "I understand.", "goto": "start"},
        )

        return text, options

    quest_status = _quest_status(caller)

    if quest_status == "completed":
        dialog = _dialog(
            '"You have already done so much for this '
            "oasis. Thank you, friend.\""
        )
        text = dialog
        options = (
            {"desc": "I am glad I could help.", "goto": "start"},
        )

        return text, options

    if quest_status == "active":
        dialog = _dialog(
            '"You already know what needs to be done. '
            "The oasis will not sustain itself.\""
        )
        text = dialog
        options = (
            {"desc": "Right. I will get to it.", "goto": "start"},
        )

        return text, options

    dialog = _dialog(
        '"Help me keep this place alive. The irrigation '
        "pipes are clogged with sand, the soil is thin, and the desert "
        "is always hungry. If you can manage the basics of tending the "
        "land, I can teach you to survive out here.\""
    )
    accept_prompt = _hl(f"Accept the quest '{quest_blueprint.title}'?")
    text = f"{dialog}\n\n{accept_prompt}"

    options = (
        {
            "desc": f"Accept: {quest_blueprint.title}",
            "goto": "_accept_oasis_quest",
        },
        {"desc": "Not right now. Maybe later.", "goto": "start"},
    )

    return text, options



def _accept_oasis_quest(caller: object,
                        raw_string: str,
                        **kwargs) -> str:
    """
    Purpose: Accepts the oasis quest and returns to the dialogue.

    Entry:
        caller is a valid Evennia Character object
        raw_string is the raw input from the user (unused)

    Exit/Returns:
        Returns the string "start" to return to the main dialogue node.

    Module Globals:
        SUCCESS_COLOR read
        OASIS_QUEST_KEY read

    Methodology:
        Calls caller.quests.accept_quest(OASIS_QUEST_KEY). On success,
        sends a confirmation message. On failure, sends an error.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    accepted = caller.quests.accept_quest(OASIS_QUEST_KEY)

    if accepted:
        caller.msg(f"{SUCCESS_COLOR}You agree to help the android.{RESET_COLOR}")
    else:
        caller.msg(f"{HIGHLIGHT_COLOR}You have already taken this quest.{RESET_COLOR}")

    return_node = "start"

    return return_node



def node_quest_progress(caller: object, **kwargs) -> tuple:
    """
    Purpose: Shows current quest progress when player checks in.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        OASIS_QUEST_KEY read

    Methodology:
        Retrieves the active quest data and displays current
        step description.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    active_quests = caller.db.active_quests or {}
    quest_data = active_quests.get(OASIS_QUEST_KEY)

    if quest_data is None:
        text = _dialog(
            '"I do not recall giving you a task.\"'
        )
        options = (
            {"desc": "My mistake.", "goto": "start"},
        )

        return text, options

    blueprint = GLOBAL_QUEST_REGISTRY.get(OASIS_QUEST_KEY)
    step_index = quest_data.get("step_index", 0)

    if blueprint and step_index < len(blueprint.steps):
        current_step = blueprint.steps[step_index]
        step_desc = current_step.description
        progress_data = quest_data.get("progress_data", {})
        progress_parts = []

        for target_key, target_value in current_step.targets.items():
            current_value = progress_data.get(target_key, 0)
            progress_parts.append(f"{target_key}: {current_value}/{target_value}")

        progress_string = ", ".join(progress_parts)

        dialog = _dialog(
            '"You are making progress. Keep at it.\"'
        )
        step_line = _hl(f"Current Step: {step_desc}")
        progress_line = _hl(f"Progress: {progress_string}")
        text = f"{dialog}\n\n{step_line}\n{progress_line}"
    else:
        text = _dialog(
            '"You have done well.\"'
        )

    options = (
        {"desc": "Back to conversation.", "goto": "start"},
    )

    return text, options



def node_post_quest(caller: object, **kwargs) -> tuple:
    """
    Purpose: Dialogue after the oasis quest is completed.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        None

    Methodology:
        Provides post-completion dialogue with hints about
        where to go next (Neo Cairo).

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    dialog = _dialog(
        '"The oasis breathes easier because of you. '
        "I have repaired the irrigation lines and the soil is "
        "rich again. If you seek greater purpose, follow the "
        "power lines east to Neo Cairo. The city does not sleep, "
        "but it may have answers you need.\""
    )
    text = dialog

    options = (
        {"desc": "Thank you. I will head to Neo Cairo.", "goto": "node_goodbye"},
        {"desc": "I will stay here a while longer.", "goto": "start"},
    )

    return text, options



def node_goodbye(caller: object, **kwargs) -> tuple:
    """
    Purpose: Exit node for the oasis NPC conversation.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, None) to exit the menu.

    Module Globals:
        None

    Methodology:
        Shows a farewell and returns None to close the menu.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    text = _dialog('"May the oasis find you again.\"')

    return text, None
