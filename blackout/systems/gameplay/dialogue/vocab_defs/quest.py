"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The `quest.*` names of the dialogue vocabulary (DESIGN-0017).

             Each name goes through the read API or a write of QuestHandler.
             Nothing here reads `db.active_quests`.

             A SCRIPT TYPES A KEY AS A LITERAL. A Python dialogue module
             imported the quest key and the step keys from the quest module.
             A script cannot import. Thus, each name here has an argument
             check. The content check runs it on each literal that a script
             wrote, and a key that names nothing fails a test.

             NO NAME GIVES A STATUS STRING. A script asks `quest.is_active`,
             not `quest.status(...) == "active"`. The status strings have
             one owner, the quest constants.
"""

from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue.vocabulary import action, query
from systems.gameplay.quests import constants as quest_constants
from systems.gameplay.quests.loader import GLOBAL_QUEST_REGISTRY
from systems.gameplay.quests.quests import normalize_target
from systems.interface.ui.colors import highlight


# ─── Private constant definitions ────────────────────────────────────────────

# The positions of the arguments that the checks read.
_QUEST_ARGUMENT: int = 0
_SECOND_ARGUMENT: int = 1


# ─── Private helper routines ─────────────────────────────────────────────────

def _check_quest_key(arguments: list) -> str | None:
    """The problem with the quest key of a call, or None."""
    quest_key = arguments[_QUEST_ARGUMENT]

    if quest_key is None:
        return None

    blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)

    if blueprint is None:
        return f"no quest has the key '{quest_key}'"

    return None


def _check_step_key(arguments: list) -> str | None:
    """The problem with the quest key or the step key of a call, or None."""
    quest_problem = _check_quest_key(arguments)
    quest_key = arguments[_QUEST_ARGUMENT]
    step_key = arguments[_SECOND_ARGUMENT]

    if quest_problem is not None or quest_key is None or step_key is None:
        return quest_problem

    blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)

    if step_key not in blueprint.step_keys:
        return f"the quest '{quest_key}' has no step '{step_key}'"

    return None


def _check_talk_target(arguments: list) -> str | None:
    """
    Purpose: Check that some step of the quest waits for this talk target.

    Entry:
        arguments is [quest key, talk target]. An entry is None if the
        script did not write a literal there.

    Exit/Returns:
        Returns the text of the problem, or None.

    Module Globals:
        GLOBAL_QUEST_REGISTRY read.

    Methodology:
        1. Check the quest key.
        2. Join the `talk` action and the target as the blueprint does.
        3. Look for that target key in the targets of each step.

    Notes/References:
        A talk target that no step waits for never advances a quest, and
        the quest engine gives no error for it.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    quest_problem = _check_quest_key(arguments)
    quest_key = arguments[_QUEST_ARGUMENT]
    target = arguments[_SECOND_ARGUMENT]

    if quest_problem is not None or quest_key is None or target is None:
        return quest_problem

    blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)
    target_key = normalize_target(quest_constants.ACTION_TALK, target)

    for step in blueprint.steps:
        if target_key in step.targets:
            return None

    return f"no step of the quest '{quest_key}' waits for the talk target '{target}'"


def _check_reported_target(arguments: list) -> str | None:
    """
    Purpose: Check that some step of the quest waits for this target.

    Entry:
        arguments is [quest key, action, target]. An entry is None if the
        script did not write a literal there.

    Exit/Returns:
        Returns the text of the problem, or None.

    Module Globals:
        GLOBAL_QUEST_REGISTRY read. quest_constants.QUEST_ACTIONS read.

    Methodology:
        1. Check the quest key.
        2. The action must be a verb of the quest vocabulary.
        3. Join the action and the target as the blueprint does, and look
           for that target key in the targets of each step.

    Notes/References:
        _check_talk_target is the same check for the `talk` action alone.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    quest_problem = _check_quest_key(arguments)
    quest_key, action_name, target = arguments

    if quest_problem is not None or None in (quest_key, action_name, target):
        return quest_problem

    if action_name not in quest_constants.QUEST_ACTIONS:
        return f"'{action_name}' is not a quest action"

    blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)
    target_key = normalize_target(action_name, target)

    for step in blueprint.steps:
        if target_key in step.targets:
            return None

    return f"no step of the quest '{quest_key}' waits for '{target_key}'"


# ─── The queries ─────────────────────────────────────────────────────────────

@query("quest.is_available", "True if the player can take the quest now.",
       argument_check=_check_quest_key)
def _is_available(context: object, quest_key: str) -> bool:
    available = context.caller.quests.is_available(quest_key)

    return available


@query("quest.is_active", "True while the player has the quest and it is not done.",
       argument_check=_check_quest_key)
def _is_active(context: object, quest_key: str) -> bool:
    active = context.caller.quests.is_active(quest_key)

    return active


@query("quest.is_complete", "True after the player completed the quest.",
       argument_check=_check_quest_key)
def _is_complete(context: object, quest_key: str) -> bool:
    complete = context.caller.quests.is_complete(quest_key)

    return complete


@query("quest.on_step", "True while the player is on this step of the quest.",
       argument_check=_check_step_key)
def _on_step(context: object, quest_key: str, step_key: str) -> bool:
    on_step = context.caller.quests.on_step(quest_key, step_key)

    return on_step


@query("quest.title", "The title of the quest.",
       argument_check=_check_quest_key)
def _title(context: object, quest_key: str) -> str:
    blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)

    return blueprint.title


@query("quest.objectives", "The objective lines of the quest, under a heading.",
       argument_check=_check_quest_key)
def _objectives(context: object, quest_key: str) -> str:
    lines = context.caller.quests.objective_lines(quest_key)
    heading = highlight(dialogue_const.OBJECTIVES_HEADING)
    indented = [f"{dialogue_const.OBJECTIVE_INDENT}{line}" for line in lines]
    block = "\n".join([heading] + indented)

    return block


@query("quest.accept_prompt", "The line that asks the player to take the quest, with its title.",
       argument_check=_check_quest_key)
def _accept_prompt(context: object, quest_key: str) -> str:
    blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)
    prompt = dialogue_const.ACCEPT_PROMPT_TEMPLATE.format(title=blueprint.title)

    return highlight(prompt)


@query("quest.reported", "True if the current step already has this target.",
       argument_check=_check_reported_target)
def _reported(context: object, quest_key: str, action_name: str, target: str) -> bool:
    progress = context.caller.quests.progress_for(quest_key)
    target_key = normalize_target(action_name, target)

    # A one-shot target holds True when it is done. A counted target holds
    # its count, and it is not done until the step advances.
    return progress.get(target_key) is True


# ─── The actions ─────────────────────────────────────────────────────────────

@action("quest.accept", "The player takes the quest.",
        argument_check=_check_quest_key)
def _accept(context: object, quest_key: str) -> bool:
    accepted = context.caller.quests.accept_quest(quest_key)

    return accepted


@action("quest.talk", "Report a talk target to one quest. The step that waits for it advances.",
        argument_check=_check_talk_target)
def _talk(context: object, quest_key: str, target: str) -> None:
    # A dialogue is the one caller that knows which quest it advances, so it
    # names the quest and does not go through notify_quests.
    context.caller.quests.update_progress(
        quest_key, quest_constants.ACTION_TALK, target)


@action("quest.report", "Report a target of any quest action to one quest, for example a chore.",
        argument_check=_check_reported_target)
def _report(context: object, quest_key: str, action_name: str, target: str) -> None:
    # A stand-in for a system that does not exist yet. When the system
    # exists, it calls notify_quests, and the script drops this line.
    context.caller.quests.update_progress(quest_key, action_name, target)
