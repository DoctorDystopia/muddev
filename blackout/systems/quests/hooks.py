"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: The one call every game system makes to report that a player did
             something a quest might be waiting for.
"""

from evennia.utils import logger

from systems.quests import constants



def notify_quests(character: object,
                  action: str,
                  argument: object = None,
                  amount: int = 1) -> None:
    """
    Purpose: Report a player action to whichever of their quests wants it.

    Entry:
        character is the actor -- a Character, or anything at all, including
            None. A caller must NOT pre-check that it holds a quest-bearing
            object.
        action is one of constants.QUEST_ACTIONS.
        argument identifies the specific target, or None.
        amount is the increment for a counted objective.

    Exit/Returns:
        No conditions. Never raises.

    Module Globals:
        constants.QUEST_ACTIONS read.

    Methodology:
        Three guards, in this order:

        1. The actor may have no quest handler. Every hostile NPC can land a
           killing blow and none of them carry quests, so the absence is
           normal rather than exceptional and is not logged.
        2. The action must be in the global vocabulary. A typo at a call site
           would otherwise match no target and simply do nothing, which is the
           silent failure this whole module exists to prevent -- so it is
           logged loudly and the call is dropped.
        3. Anything the handler raises is logged and swallowed. A quest bug
           must never abort the kill, craft or harvest that reported it; the
           progression hooks sit inside at_death and perform_craft, where an
           exception would take real game state with it.

    Notes/References:
        The vocabulary is documented in global_quest_actions.md.
        Callers pass the stable snake_case identifier -- db.npc_key, a recipe
        key, an ItemDef key -- never a display name. `self.key` on a spawned
        hostile is "Mutant Raider", which would produce the target
        "kill:Mutant Raider" and match nothing a blueprint could reasonably
        declare.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    quests = getattr(character, "quests", None)

    if quests is None:
        return

    if action not in constants.QUEST_ACTIONS:
        logger.log_err(
            f"notify_quests: '{action}' is not in QUEST_ACTIONS; "
            f"dropping progress for '{argument}'. "
            f"See systems/quests/global_quest_actions.md."
        )
        return

    try:
        quests.notify(action, argument, amount=amount)
    except Exception as exc:
        logger.log_err(
            f"notify_quests: {action}:{argument} failed for "
            f"{character}: {exc!r}"
        )
