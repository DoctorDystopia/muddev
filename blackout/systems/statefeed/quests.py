"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Turn a character's quest log into the plain values
             CharQuestsPayload carries.

             Kept out of serializers.py for the reason inventory.py gives:
             that module answers "what is this thing standing in the world",
             and every routine in it is built around an entity with a location
             and coordinates. This one answers "how far through this quest am
             I", which has no geometry in it at all.

             STRUCTURED, NOT RENDERED, and that is the whole design decision.
             `QuestHandler.objective_lines` already produces prose -- "[x] Cut
             poles 3/5" -- and shipping that would have been the smaller
             change. But an objective is DATA: a description, a count and a
             requirement. A client given the numbers can draw a progress bar,
             sort by completion and grey out what is done; a client given the
             sentence can only print it. The prose stays where it is, for the
             telnet screen, and both are built from the same handler reads in
             the same order -- the arrangement CombatPayload uses to mirror
             ActionResult.

             EVERY READ GOES THROUGH QuestHandler'S PUBLIC API. Not once does
             this module touch `db.active_quests`. CLAUDE.md is explicit that
             the attribute has exactly one owner and that three modules owning
             it is how the android's dialogue came to print "talk:tester:
             0/True" at players; this would have been the fourth.

             Imported LAZILY by events.emit_quests, for the same reason
             systems.summary is: reaching the quest loader pulls in every
             module under systems/quests/content/, and events.py is imported by
             typeclasses/mixins.py, which every Character and NPC pulls in at
             startup. A top-level import would drag the content walk into
             typeclass import time and couple the two systems' import order --
             which is the exact ring that left GLOBAL_QUEST_REGISTRY empty for
             a fortnight.
"""

from .payloads import CharQuestsPayload


# ─── Private helper routines ─────────────────────────────────────────────────

def _objective(handler, step, progress: dict, target_key: str,
               requirement) -> dict:
    """
    Purpose: One objective, as numbers rather than as a sentence.

    Entry:
        handler     - the character's QuestHandler.
        step        - the QuestStep the objective belongs to.
        progress    - handler.progress_for(quest_key) for that quest.
        target_key  - the compound target key.
        requirement - True for a one-shot objective, or a positive int.

    Exit/Returns:
        Returns {key, description, current, required, counted, done}.

    Module Globals:
        None.

    Methodology:
        `required` is normalised to 1 for a one-shot objective rather than
        left absent, so a client draws the same progress bar for both without
        a branch; `counted` is what says whether to render "3/5" or a tickbox.

        Whether the objective is SATISFIED is asked of the handler rather than
        recomputed. "1 of True" is exactly the comparison that has already been
        got wrong once in this codebase, and there is no reason for a second
        implementation of it to exist.

    Notes/References:
        Mirrors the branch in QuestHandler.objective_lines.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    current = progress.get(target_key, 0)
    counted = requirement is not True

    return {
        "key": target_key,
        "description": step.objective_text(target_key),
        "current": int(current),
        "required": int(requirement) if counted else 1,
        "counted": counted,
        "done": bool(handler._is_satisfied(current, requirement)),
    }


def _active_quest(handler, registry, quest_key: str):
    """
    Purpose: One in-progress quest, with its current step's objectives.

    Entry:
        handler   - the character's QuestHandler.
        registry  - GLOBAL_QUEST_REGISTRY.
        quest_key - a key from handler.active_keys().

    Exit/Returns:
        Returns the row dict, or None when nothing declares this quest or the
        handler reports no current step.

    Module Globals:
        None.

    Methodology:
        The CURRENT step only. Steps already finished are a history the handler
        does not keep, and steps ahead would spoil the quest.

        A quest key with no blueprint is SKIPPED rather than sent with an empty
        title. The loader tolerates a content module that failed to import, so
        a character can legitimately hold a key nothing declares any more -- and
        a row a client cannot label is worse than a row that is not there.

    Notes/References:
        QuestRegistry.load_errors is what makes a missing blueprint loud
        elsewhere; this path only has to not make it worse.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    blueprint = registry.get(quest_key)

    if blueprint is None:
        return None

    step = handler.current_step(quest_key)

    if step is None:
        return None

    progress = handler.progress_for(quest_key)
    objectives = []

    for target_key, requirement in step.targets.items():
        objectives.append(
            _objective(handler, step, progress, target_key, requirement))

    return {
        "key": quest_key,
        "title": blueprint.title,
        "step": step.key,
        "step_description": step.description,
        "objectives": objectives,
    }


# ─── Public interface ────────────────────────────────────────────────────────

def build_payload(observer) -> CharQuestsPayload:
    """
    Purpose: Build the observer's whole quest log as one snapshot.

    Entry:
        observer - the puppeted Character. One with no quest handler is a
                   supported no-op and yields empty lists.

    Exit/Returns:
        Returns a CharQuestsPayload.

    Module Globals:
        None. The blueprint registry is imported here rather than at module
        scope; see the module docstring.

    Methodology:
        A SNAPSHOT, for the reason CharItemsPayload gives at length: the
        mutation points are many -- accepting, every notify_quests fan-out, a
        step completing, a forced jump from the moderator tool -- and a delta
        protocol would rot at the first one anybody forgot. It is also small,
        a handful of quests with a handful of objectives each.

    Notes/References:
        Sent on CHANNEL_CHAR_QUESTS. See systems/statefeed/constants.py.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    from systems.quests.loader import GLOBAL_QUEST_REGISTRY

    handler = getattr(observer, "quests", None)

    if handler is None:
        return CharQuestsPayload()

    active = []

    for quest_key in handler.active_keys():
        row = _active_quest(handler, GLOBAL_QUEST_REGISTRY, quest_key)

        if row is not None:
            active.append(row)

    completed = []

    for quest_key in handler.completed_keys():
        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)

        if blueprint is None:
            continue

        completed.append({"key": quest_key, "title": blueprint.title})

    return CharQuestsPayload(active=active, completed=completed)
