"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: The static half of the quest engine -- QuestStep and
             QuestBlueprint, the shapes a content module declares.

This module must NOT import systems.quests.loader. The loader builds its
registry singleton at import time by importing every module under content/,
and every one of those imports QuestBlueprint and QuestStep from here. An
import of the loader at this module's scope closes that ring: quests ->
loader -> content -> quests, where the third hop finds a half-initialized
module with no QuestBlueprint defined yet.

That was not hypothetical. It was the live state of the game -- typeclasses/
characters.py imports the handler first, which pulled quests.py in first,
which meant every content module raised ImportError inside the loader's
`except Exception`, and GLOBAL_QUEST_REGISTRY held zero quests. Player-facing
symptom: the oasis quest could not be accepted, because as far as the server
was concerned it did not exist.

The character-facing half lives in handler.py, which may import the loader
freely because nothing under content/ imports it back.
"""

from systems.quests import constants



def normalize_target(action: str, argument: object = None) -> str:
    """
    Purpose: Join an action and its argument into one compound target key.

    Entry:
        action is a string from constants.QUEST_ACTIONS.
        argument is the specific identifier, or None for a bare action.

    Exit/Returns:
        Returns "action:argument", or just "action" when argument is None.

    Module Globals:
        constants.TARGET_SEPARATOR read.

    Methodology:
        The one place the separator is applied. Blueprints declare targets in
        this form and progression hooks fire the two halves separately, so a
        second copy of this join would be a second chance for the two spellings
        to drift and for an objective to silently never match.

    Notes/References:
        The vocabulary itself is documented in global_quest_actions.md.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    if argument is None:
        return str(action)

    joined = f"{action}{constants.TARGET_SEPARATOR}{argument}"

    return joined


def split_target(target_key: str) -> tuple:
    """
    Purpose: Recover the action half of a compound target key.

    Entry:
        target_key is a string, with or without a separator.

    Exit/Returns:
        Returns (action, argument). argument is None when the key carries no
        separator.

    Module Globals:
        constants.TARGET_SEPARATOR read.

    Methodology:
        Splits once from the left, so an argument may itself contain the
        separator without corrupting the action.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    parts = str(target_key).split(constants.TARGET_SEPARATOR, 1)
    action = parts[0]
    argument = parts[1] if len(parts) > 1 else None

    return action, argument



class QuestStep:
    """
    Purpose: One phase of a quest -- what must happen, and what happens when
             it does.

    Entry:
        key is a short identifier unique within its blueprint.
        description is the player-facing summary of the phase.
        targets maps compound target keys to a requirement: True for a
            one-shot objective, or a positive int for a counted one.
        objectives optionally maps those same keys to player-facing objective
            text; a key with no entry falls back to the raw target key.
        on_enter and on_complete are optional callables taking (character,
            step).

    Exit/Returns:
        No conditions. Raises ValueError on a malformed target.

    Module Globals:
        constants.QUEST_ACTIONS read.

    Methodology:
        Validation happens here, at construction, rather than at fire time.
        Content modules are imported by the quest loader at server start and
        by the quest test suite, so a target naming an undocumented action --
        the "interract" typo that would otherwise simply never fire -- fails
        loudly the moment the module is read instead of quietly costing a
        player their quest.

    Notes/References:
        The previous implementation accepted tuple keys and normalized them
        with f"{k[0]}:{k[1]}". No blueprint ever used that form, and it
        silently mangled any tuple that was not exactly two elements long, so
        it is gone -- declare targets as strings.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """

    def __init__(self,
                 key: str,
                 description: str,
                 targets: dict = None,
                 objectives: dict = None,
                 on_enter: object = None,
                 on_complete: object = None) -> None:
        self.key = key
        self.description = description
        self.targets = self._validate_targets(targets or {})
        self.objectives = self._validate_objectives(objectives or {})
        self.on_enter = on_enter
        self.on_complete = on_complete


    def _validate_targets(self, targets: dict) -> dict:
        """
        Purpose: Reject a target whose action is not in the global vocabulary.

        Entry:
            targets maps compound key strings to bool or positive int.

        Exit/Returns:
            Returns the validated dict. Raises ValueError naming both the step
            and the offending key.

        Module Globals:
            constants.QUEST_ACTIONS read.

        Methodology:
            Checks the action half against the vocabulary and the requirement
            against the two shapes _check_step_completion knows how to compare.
            A requirement of False or 0 would be satisfied before the player
            did anything, so both are refused.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        validated = {}

        for target_key, requirement in targets.items():
            action, _argument = split_target(target_key)

            if action not in constants.QUEST_ACTIONS:
                raise ValueError(
                    f"QuestStep '{self.key}': target '{target_key}' names "
                    f"action '{action}', which is not in QUEST_ACTIONS. "
                    f"See systems/quests/global_quest_actions.md."
                )

            if requirement is not True and not isinstance(requirement, int):
                raise ValueError(
                    f"QuestStep '{self.key}': target '{target_key}' requires "
                    f"{requirement!r}; expected True or a positive int."
                )

            if requirement is not True and requirement < 1:
                raise ValueError(
                    f"QuestStep '{self.key}': target '{target_key}' requires "
                    f"{requirement!r}, which is already satisfied."
                )

            validated[str(target_key)] = requirement

        return validated


    def _validate_objectives(self, objectives: dict) -> dict:
        """
        Purpose: Reject objective text describing a target that does not exist.

        Entry:
            objectives maps compound key strings to display strings.
            self.targets is already populated.

        Exit/Returns:
            Returns the validated dict. Raises ValueError on an orphan key.

        Module Globals:
            None

        Methodology:
            An objective line keyed to a misspelled target would render nothing
            and leave the real target showing its raw key -- visible, but easy
            to read as a missing description rather than a typo. Naming it here
            makes the cause obvious.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        for target_key in objectives:
            if target_key not in self.targets:
                raise ValueError(
                    f"QuestStep '{self.key}': objective text for "
                    f"'{target_key}', which is not one of its targets."
                )

        return dict(objectives)


    def objective_text(self, target_key: str) -> str:
        """
        Purpose: The player-facing name of one objective.

        Entry:
            target_key is one of this step's targets.

        Exit/Returns:
            Returns the authored text, or the raw target key as a fallback.

        Module Globals:
            constants.UNDESCRIBED_OBJECTIVE read.

        Methodology:
            The fallback is deliberately the raw key rather than a generic
            placeholder: an undescribed objective should still tell a player
            (and a builder) exactly what the game is waiting for.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        authored = self.objectives.get(target_key)

        if authored:
            return authored

        fallback = constants.UNDESCRIBED_OBJECTIVE.format(target_key=target_key)

        return fallback



class QuestBlueprint:
    """
    Purpose: The static definition of one quest -- its steps, its text and its
             reward hook. Shared by every character; holds no player state.

    Entry:
        key is the unique registry identifier.
        title and description are player-facing.
        steps is an ordered list of QuestStep.
        rewards_callback is an optional callable taking (character).
        prerequisites is an optional list of quest keys that must be completed
            before this quest may be accepted.

    Exit/Returns:
        No conditions. Raises ValueError on an empty or duplicate-keyed step
        list.

    Module Globals:
        None

    Methodology:
        Step keys are validated for uniqueness because dialogue nodes gate
        themselves on the current step KEY rather than its index -- inserting a
        step must not silently re-point every node after it, and two steps
        sharing a key would make that gate ambiguous.

    Notes/References:
        Discovered by systems/quests/loader.py through the module-level QUESTS
        list in each content module.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """

    def __init__(self,
                 key: str,
                 title: str,
                 description: str,
                 steps: list,
                 rewards_callback: object = None,
                 prerequisites: list = None) -> None:
        self.key = key
        self.title = title
        self.description = description
        self.steps = self._validate_steps(steps)
        self.rewards_callback = rewards_callback
        self.prerequisites = list(prerequisites or [])


    def _validate_steps(self, steps: list) -> list:
        """
        Purpose: Refuse a step list that cannot be progressed through.

        Entry:
            steps is a list of QuestStep.

        Exit/Returns:
            Returns the list unchanged. Raises ValueError otherwise.

        Module Globals:
            None

        Methodology:
            A quest with no steps would complete on acceptance; a step with no
            targets would complete the instant the step was entered and cascade
            through the rest. Both are content bugs that look like engine bugs
            when they surface in play.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        if not steps:
            raise ValueError(f"QuestBlueprint '{self.key}' declares no steps.")

        seen_keys = set()

        for step in steps:
            if not step.targets:
                raise ValueError(
                    f"QuestBlueprint '{self.key}': step '{step.key}' declares "
                    f"no targets and would complete immediately."
                )

            if step.key in seen_keys:
                raise ValueError(
                    f"QuestBlueprint '{self.key}': duplicate step key "
                    f"'{step.key}'."
                )

            seen_keys.add(step.key)

        return list(steps)


    @property
    def step_keys(self) -> list:
        """The ordered step keys, for gating dialogue and for tests."""
        return [step.key for step in self.steps]


    def step_index_of(self, step_key: str) -> int:
        """
        Purpose: Locate a step by key.

        Entry:
            step_key is a step identifier.

        Exit/Returns:
            Returns the zero-based index, or -1 if this blueprint has no such
            step.

        Module Globals:
            None

        Methodology:
            Linear scan. Quests have a handful of steps; an index would cost
            more to keep correct than it saves.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        for index, step in enumerate(self.steps):
            if step.key == step_key:
                return index

        return -1
