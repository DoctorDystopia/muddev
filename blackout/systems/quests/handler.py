"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: QuestHandler -- one character's progress through the quests
             declared in systems/quests/content/.

Split out of quests.py so that module can be imported by content/ without
dragging the loader in behind it. See the note at the head of quests.py for
the import ring that split closes, and systems/progression/skills/ for the
same handler.py / registry.py separation.
"""

from evennia.utils import logger

from systems.quests import constants
from systems.quests.loader import GLOBAL_QUEST_REGISTRY
from systems.quests.quests import normalize_target



class QuestHandler:
    """
    Purpose: One character's relationship to every quest -- what is active,
             how far along it is, and what has been finished.

    Entry:
        obj is the Character this handler belongs to.

    Exit/Returns:
        No conditions.

    Module Globals:
        GLOBAL_QUEST_REGISTRY read.

    Methodology:
        State persists in obj.db.active_quests (a dict keyed by quest key) and
        obj.db.completed_quests (a list). Those two attributes are read
        directly by nothing outside this class: the read API below exists so
        that dialogue nodes, the quest command and the summary panel ask the
        handler rather than re-deriving quest state from raw dicts, which is
        how three modules ended up owning the same fact.

    Notes/References:
        Reached as `character.quests`, a lazy_property built by
        typeclasses/characters.py.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """

    def __init__(self, obj: object) -> None:
        self.obj = obj

        if not self.obj.db.active_quests:
            self.obj.db.active_quests = {}

        if not self.obj.db.completed_quests:
            self.obj.db.completed_quests = []


    # ─── Read API ───────────────────────────────────────────────────────────

    def active_keys(self) -> list:
        """The keys of every quest currently in progress."""
        active = self.obj.db.active_quests or {}
        return list(active.keys())


    def completed_keys(self) -> list:
        """The keys of every quest this character has finished."""
        completed = self.obj.db.completed_quests or []
        return list(completed)


    def status(self, quest_key: str) -> str:
        """
        Purpose: This character's relationship to one quest.

        Entry:
            quest_key is a quest identifier.

        Exit/Returns:
            Returns STATUS_COMPLETED, STATUS_ACTIVE or STATUS_NOT_STARTED.

        Module Globals:
            constants.STATUS_* read.

        Methodology:
            Completion is checked first: a repeatable quest re-accepted after
            completion would appear in both lists, and "in progress" is the
            more useful answer only once such quests exist. Until then the
            order is arbitrary but must be decided in exactly one place.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        if quest_key in self.completed_keys():
            return constants.STATUS_COMPLETED

        if quest_key in self.active_keys():
            return constants.STATUS_ACTIVE

        return constants.STATUS_NOT_STARTED


    def is_active(self, quest_key: str) -> bool:
        """True while the character is partway through this quest."""
        return self.status(quest_key) == constants.STATUS_ACTIVE


    def is_complete(self, quest_key: str) -> bool:
        """True once the character has finished this quest."""
        return self.status(quest_key) == constants.STATUS_COMPLETED


    def is_available(self, quest_key: str) -> bool:
        """
        Purpose: Whether this character could accept this quest right now.

        Entry:
            quest_key is a quest identifier.

        Exit/Returns:
            Returns True only if the quest exists, is untouched, and every
            prerequisite quest is complete.

        Module Globals:
            GLOBAL_QUEST_REGISTRY read.

        Methodology:
            Separated from accept_quest so a dialogue node can decide whether
            to OFFER a quest without attempting to start one and interpreting
            the failure.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)

        if blueprint is None:
            return False

        if self.status(quest_key) != constants.STATUS_NOT_STARTED:
            return False

        completed = self.completed_keys()
        unmet = [key for key in blueprint.prerequisites if key not in completed]

        return not unmet


    def current_step(self, quest_key: str) -> object:
        """
        Purpose: The QuestStep the character is working on.

        Entry:
            quest_key is a quest identifier.

        Exit/Returns:
            Returns a QuestStep, or None if the quest is not active or its
            stored index no longer addresses a step.

        Module Globals:
            GLOBAL_QUEST_REGISTRY read.
            constants.FIELD_STEP_INDEX read.

        Methodology:
            The bounds check is not paranoia: a saved character carries a step
            index from whatever the blueprint looked like when they accepted
            it, and shortening a quest in a content edit leaves live players
            pointing past the end.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)
        active = self.obj.db.active_quests or {}
        quest_data = active.get(quest_key)

        if blueprint is None or quest_data is None:
            return None

        step_index = quest_data.get(constants.FIELD_STEP_INDEX, 0)

        if step_index < 0 or step_index >= len(blueprint.steps):
            return None

        return blueprint.steps[step_index]


    def current_step_key(self, quest_key: str) -> str:
        """
        Purpose: Name the active phase, for dialogue nodes to gate on.

        Entry:
            quest_key is a quest identifier.

        Exit/Returns:
            Returns the step key, or None if the quest is not active.

        Module Globals:
            None

        Methodology:
            Nodes gate on the key rather than the index so that inserting a
            step into a quest does not silently re-point every node after it.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        step = self.current_step(quest_key)

        if step is None:
            return None

        return step.key


    def on_step(self, quest_key: str, step_key: str) -> bool:
        """True when this quest is active AND sitting on the named step."""
        return self.current_step_key(quest_key) == step_key


    def progress_for(self, quest_key: str) -> dict:
        """
        Purpose: The raw counters for the active step.

        Entry:
            quest_key is a quest identifier.

        Exit/Returns:
            Returns a plain-dict COPY, empty if the quest is not active.

        Module Globals:
            constants.FIELD_PROGRESS read.

        Methodology:
            Copied rather than handed out live. The stored value is one of
            Evennia's _SaverDict wrappers, and a caller that mutated it would
            be writing to the database through what reads as a getter.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        active = self.obj.db.active_quests or {}
        quest_data = active.get(quest_key)

        if quest_data is None:
            return {}

        progress = quest_data.get(constants.FIELD_PROGRESS, {})

        return dict(progress)


    def objective_lines(self, quest_key: str) -> list:
        """
        Purpose: Render the active step's objectives for display.

        Entry:
            quest_key is a quest identifier.

        Exit/Returns:
            Returns a list of formatted strings, empty if the quest is not
            active.

        Module Globals:
            constants.MSG_OBJECTIVE_* read.
            constants.OBJECTIVE_DONE_MARK, OBJECTIVE_TODO_MARK read.

        Methodology:
            A boolean objective renders as a tickbox and a counted one as a
            fraction, because "1/True" is not a sentence -- which is what the
            android's progress node used to print at players.

        Notes/References:
            Consumed by commands/quest_cmds.py and the oasis dialogue.

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        step = self.current_step(quest_key)

        if step is None:
            return []

        progress = self.progress_for(quest_key)
        lines = []

        for target_key, requirement in step.targets.items():
            current = progress.get(target_key, 0)
            description = step.objective_text(target_key)
            satisfied = self._is_satisfied(current, requirement)
            mark = (constants.OBJECTIVE_DONE_MARK if satisfied
                    else constants.OBJECTIVE_TODO_MARK)

            if requirement is True:
                line = constants.MSG_OBJECTIVE_BOOLEAN.format(
                    mark=mark, description=description)
            else:
                line = constants.MSG_OBJECTIVE_COUNTED.format(
                    mark=mark, description=description,
                    current=int(current), required=int(requirement))

            lines.append(line)

        return lines


    # ─── Lifecycle ──────────────────────────────────────────────────────────

    def accept_quest(self, quest_key: str) -> bool:
        """
        Purpose: Begin a quest for this character.

        Entry:
            quest_key is a quest identifier.

        Exit/Returns:
            Returns True if the quest was started, False otherwise. Messages
            the character on an unknown key.

        Module Globals:
            GLOBAL_QUEST_REGISTRY read.
            constants.MSG_QUEST_UNKNOWN, MSG_QUEST_ACCEPTED read.
            constants.FIELD_STEP_INDEX, FIELD_PROGRESS written.

        Methodology:
            Seeds the progress dict from the FIRST step's targets only. The
            dict is re-seeded at each step boundary, and update_progress
            ignores any target absent from it -- which is what makes an action
            belonging to a later step harmless when performed early.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)

        if blueprint is None:
            self.obj.msg(constants.MSG_QUEST_UNKNOWN.format(quest_key=quest_key))
            return False

        if not self.is_available(quest_key):
            return False

        first_step = blueprint.steps[0]
        self.obj.db.active_quests[quest_key] = {
            constants.FIELD_STEP_INDEX: 0,
            constants.FIELD_PROGRESS: {key: 0 for key in first_step.targets},
        }

        self.obj.msg(constants.MSG_QUEST_ACCEPTED.format(
            title=blueprint.title, description=blueprint.description))

        self._fire_step_hook(first_step, "on_enter")

        return True


    def abandon_quest(self, quest_key: str) -> bool:
        """
        Purpose: Drop an in-progress quest, discarding its progress.

        Entry:
            quest_key is a quest identifier.

        Exit/Returns:
            Returns True if a quest was dropped, False if none was active.

        Module Globals:
            constants.MSG_QUEST_ABANDONED read.

        Methodology:
            Does not touch the completed list, so abandoning is a return to
            the not-started state and the quest may be taken again. No reward
            hook fires.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        if not self.is_active(quest_key):
            return False

        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)
        title = getattr(blueprint, "title", None) or quest_key

        del self.obj.db.active_quests[quest_key]
        self.obj.msg(constants.MSG_QUEST_ABANDONED.format(title=title))

        return True


    # ─── Direct writes ──────────────────────────────────────────────────────
    #
    # Not how a character plays a quest -- accept_quest and notify are. These
    # are the write path a staff tool, a test fixture or a content migration
    # needs, and they exist HERE rather than in the caller because
    # db.active_quests has exactly one owner. The same reasoning that put
    # skills.logic.set_level beside add_xp.

    def force_complete_quest(self, quest_key: str) -> bool:
        """
        Purpose: Mark a quest finished regardless of how far along it is.

        Entry:
            quest_key is a quest identifier. The quest may be active or never
            started; both end in the completed state.

        Exit/Returns:
            Returns True if the quest was completed, False on an unknown key
            or one already complete.

        Module Globals:
            GLOBAL_QUEST_REGISTRY read.

        Methodology:
            Delegates to _complete_quest, so the completion record, the
            announcement and the reward callback are the SAME code the honest
            route runs. Rewards do pay out: the main reason to force a
            completion is to exercise the reward path, and a "completion" that
            skipped it would test the one thing that is not being tested.

            Intermediate steps' on_complete hooks do NOT fire. A hook that
            spawns an encounter or teaches a skill is written to run when its
            step is genuinely finished; firing four of them in a row because
            someone skipped to the end is a worse lie than skipping them.

        Notes/References:
            Silent on an already-complete quest rather than completing it
            twice, which would re-pay the rewards.

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)

        if blueprint is None:
            return False

        if self.is_complete(quest_key):
            return False

        self._complete_quest(blueprint)

        return True


    def force_step(self, quest_key: str, step_key: str) -> bool:
        """
        Purpose: Move an active quest to a named step, forward or back.

        Entry:
            quest_key names an ACTIVE quest. step_key names a step of that
            quest's blueprint.

        Exit/Returns:
            Returns True if the character now sits on that step, False if the
            quest is not active or the blueprint has no such step.

        Module Globals:
            GLOBAL_QUEST_REGISTRY read.
            constants.FIELD_STEP_INDEX, FIELD_PROGRESS written.
            constants.MSG_STEP_SET read.

        Methodology:
            Re-seeds progress from the destination step's targets, exactly as
            accept_quest and _check_step_completion do. Carrying the old
            counters across would leave a target from the previous step
            sitting in the dict, where _step_is_satisfied would read it as a
            requirement that does not exist.

            The destination's on_enter DOES fire, because it is what makes the
            step playable -- a step whose on_enter teaches the skill its
            objective needs is unreachable without it. Steps jumped OVER fire
            nothing.

            Requires the quest to be active rather than accepting it first.
            "Start this quest" and "put them on step three" are two decisions,
            and a method that silently made the first while being asked for
            the second would re-run the opening step's on_enter as a side
            effect nobody asked for.

        Notes/References:
            Jumping BACKWARD is supported and is the more useful direction:
            it is how a step gets replayed without resetting the whole quest.

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)

        if blueprint is None or not self.is_active(quest_key):
            return False

        step_index = blueprint.step_index_of(step_key)

        if step_index < 0:
            return False

        target_step = blueprint.steps[step_index]
        active_data = self.obj.db.active_quests[quest_key]
        active_data[constants.FIELD_STEP_INDEX] = step_index
        active_data[constants.FIELD_PROGRESS] = {
            key: 0 for key in target_step.targets
        }
        self.obj.db.active_quests[quest_key] = active_data

        self.obj.msg(constants.MSG_STEP_SET.format(
            description=target_step.description))

        self._fire_step_hook(target_step, "on_enter")

        return True


    def reset_quest(self, quest_key: str) -> bool:
        """
        Purpose: Return a quest to the not-started state, from anywhere.

        Entry:
            quest_key is a quest identifier.

        Exit/Returns:
            Returns True if anything was cleared, False if the character had
            no record of this quest either way.

        Module Globals:
            constants.MSG_QUEST_RESET read.
            GLOBAL_QUEST_REGISTRY read.

        Methodology:
            Clears BOTH lists. That is the difference from abandon_quest,
            which drops progress but leaves a completion record standing --
            so abandoning a finished quest does nothing at all, and a tester
            who wanted to play it again is stuck. Reset is the one that makes
            a quest takeable a second time.

            No reward is clawed back. Whatever the completion paid out is an
            item or an XP total now, and hunting it down from here would mean
            this method knowing what every rewards_callback in the game does.

        Notes/References:
            Announced to the character. A quest silently vanishing from their
            journal is indistinguishable from a bug, and they will report it
            as one.

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        was_active = quest_key in self.active_keys()
        was_complete = quest_key in self.completed_keys()

        if not was_active and not was_complete:
            return False

        if was_active:
            del self.obj.db.active_quests[quest_key]

        if was_complete:
            self.obj.db.completed_quests.remove(quest_key)

        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)
        title = getattr(blueprint, "title", None) or quest_key
        self.obj.msg(constants.MSG_QUEST_RESET.format(title=title))

        return True


    # ─── Progression ────────────────────────────────────────────────────────

    def notify(self, action: str, argument: object = None, amount: int = 1) -> None:
        """
        Purpose: Report that the character did something, to every quest that
                 might care.

        Entry:
            action is one of constants.QUEST_ACTIONS.
            argument identifies the specific target, or None.
            amount is the increment for a counted objective.

        Exit/Returns:
            No conditions.

        Module Globals:
            None

        Methodology:
            The fan-out entry point every progression hook should call. Game
            systems know what the player did, not which quest wanted it, and
            asking them to know is how the at_death hook came to pass the
            literal quest key "*" -- which matched no blueprint, so no kill
            objective in the game could ever advance.

            Iterates a SNAPSHOT of the active keys: satisfying the last step
            of a quest deletes it from the dict being walked.

        Notes/References:
            The action vocabulary is documented in global_quest_actions.md.

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        for quest_key in self.active_keys():
            self.update_progress(quest_key, action, argument, amount=amount)


    def update_progress(self,
                        quest_key: str,
                        action: str,
                        argument: object = None,
                        amount: int = 1) -> None:
        """
        Purpose: Advance one named quest's counters for one action.

        Entry:
            quest_key names an active quest.
            action and argument together name a target of its current step.
            amount is the increment for a counted objective.

        Exit/Returns:
            No conditions. Silently ignores an action the current step does
            not want.

        Module Globals:
            GLOBAL_QUEST_REGISTRY read.
            constants.FIELD_PROGRESS written.

        Methodology:
            A boolean target is latched True; a counted one accumulates and is
            clamped at its requirement so a display never reads "4/3". The
            membership test is against the PROGRESS dict rather than the step's
            targets, because progress is re-seeded per step and is therefore
            the authoritative statement of what is being watched right now.

        Notes/References:
            Prefer notify() from game systems; this is for a caller that
            genuinely knows which quest it is advancing.

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)

        if blueprint is None or not self.is_active(quest_key):
            return

        active_data = self.obj.db.active_quests[quest_key]
        progress = active_data[constants.FIELD_PROGRESS]
        target_key = normalize_target(action, argument)

        if target_key not in progress:
            return

        current_step = self.current_step(quest_key)
        requirement = current_step.targets[target_key]

        if requirement is True:
            progress[target_key] = True
        else:
            raised = progress[target_key] + amount
            progress[target_key] = min(raised, requirement)

        self.obj.db.active_quests[quest_key] = active_data
        self._check_step_completion(blueprint)


    def _check_step_completion(self, blueprint: object) -> None:
        """
        Purpose: Advance the quest if the active step's objectives are all met.

        Entry:
            blueprint is the QuestBlueprint of an active quest.

        Exit/Returns:
            No conditions.

        Module Globals:
            constants.FIELD_STEP_INDEX, FIELD_PROGRESS written.
            constants.MSG_STEP_ADVANCED read.

        Methodology:
            Fires the completed step's on_complete hook, then either seeds the
            next step and fires its on_enter, or completes the quest. The two
            hooks bracket the transition so a step can teach a skill on entry
            and spawn an encounter on exit without either being expressed as a
            branch in this method.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        quest_key = blueprint.key
        current_step = self.current_step(quest_key)

        if current_step is None or not self._step_is_satisfied(current_step, quest_key):
            return

        self._fire_step_hook(current_step, "on_complete")

        active_data = self.obj.db.active_quests[quest_key]
        next_index = active_data[constants.FIELD_STEP_INDEX] + 1

        if next_index >= len(blueprint.steps):
            self._complete_quest(blueprint)
            return

        next_step = blueprint.steps[next_index]
        active_data[constants.FIELD_STEP_INDEX] = next_index
        active_data[constants.FIELD_PROGRESS] = {
            key: 0 for key in next_step.targets
        }
        self.obj.db.active_quests[quest_key] = active_data

        self.obj.msg(constants.MSG_STEP_ADVANCED.format(
            description=next_step.description))

        self._fire_step_hook(next_step, "on_enter")


    def _step_is_satisfied(self, step: object, quest_key: str) -> bool:
        """
        Purpose: Whether every objective of one step is met.

        Entry:
            step is a QuestStep. quest_key names the active quest.

        Exit/Returns:
            Returns True only if all targets are satisfied.

        Module Globals:
            None

        Methodology:
            A target missing from progress reads as 0, which fails both
            comparisons -- an unseeded objective must never count as done.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        progress = self.progress_for(quest_key)

        for target_key, requirement in step.targets.items():
            current = progress.get(target_key, 0)

            if not self._is_satisfied(current, requirement):
                return False

        return True


    @staticmethod
    def _is_satisfied(current: object, requirement: object) -> bool:
        """
        Purpose: Compare one counter against one requirement.

        Entry:
            current is the stored value, requirement is True or a positive int.

        Exit/Returns:
            Returns True if the objective is met.

        Module Globals:
            None

        Methodology:
            The boolean case is tested with `is True` rather than `==`. Python
            makes True == 1, so a counted objective standing at 1 would satisfy
            a boolean requirement and vice versa if this used equality -- the
            two shapes must not be interchangeable by accident.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        if requirement is True:
            return current is True

        return current >= requirement


    def _fire_step_hook(self, step: object, hook_name: str) -> None:
        """
        Purpose: Run a step's on_enter or on_complete callback.

        Entry:
            step is a QuestStep. hook_name is "on_enter" or "on_complete".

        Exit/Returns:
            No conditions.

        Module Globals:
            None

        Methodology:
            A raising hook is logged and swallowed. Content callbacks teach
            skills and spawn encounters, and a bad one must not leave the
            player's quest wedged mid-transition with the step already marked
            done -- losing the encounter is recoverable, losing the quest is
            not.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        hook = getattr(step, hook_name, None)

        if hook is None:
            return

        try:
            hook(self.obj, step)
        except Exception as exc:
            logger.log_err(
                f"QuestHandler: step '{step.key}' {hook_name} failed: {exc!r}")


    def _complete_quest(self, blueprint: object) -> None:
        """
        Purpose: Retire a finished quest and pay out its rewards.

        Entry:
            blueprint is the QuestBlueprint whose final step was just met.

        Exit/Returns:
            No conditions.

        Module Globals:
            constants.MSG_QUEST_COMPLETE read.

        Methodology:
            Moves the key from active to completed, announces, then fires the
            reward callback LAST -- a reward that raises must not also cost the
            player the completion record, which is what decides whether the
            quest can be replayed and what later quests gate on.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        quest_key = blueprint.key

        if quest_key in self.obj.db.active_quests:
            del self.obj.db.active_quests[quest_key]

        if quest_key not in self.obj.db.completed_quests:
            self.obj.db.completed_quests.append(quest_key)

        self.obj.msg(constants.MSG_QUEST_COMPLETE.format(title=blueprint.title))

        if blueprint.rewards_callback is None:
            return

        try:
            blueprint.rewards_callback(self.obj)
        except Exception as exc:
            logger.log_err(
                f"QuestHandler: rewards for '{quest_key}' failed: {exc!r}")
