"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: The concrete NPC combat behaviours.

A behaviour is a plain function taking the combatant's BlackoutCombatHandler
and returning either an action dict (the same shape the player commands pass to
queue_action) or None for "do nothing this tick". It decides; it never resolves,
never messages, and never mutates handler state. That keeps every behaviour
callable directly from a test with no tick engine running.
"""

from .constants import AI_BEHAVIOR_AGGRESSIVE_MELEE, LAST_ATTACKER_ID_ATTR
from .registry import register_behavior


def _last_attacker(npc):
    """
    Purpose: Resolve the entity that last damaged `npc`.

    Entry:
        npc - the NPC whose ndb carries LAST_ATTACKER_ID_ATTR.

    Exit/Returns:
        The attacker object, or None when there is no recorded attacker or its
        row no longer exists.

    Module Globals:
        LAST_ATTACKER_ID_ATTR read.

    Methodology:
        CombatEntity.at_damage records an id, not an object reference, so this
        resolves it back through the same _object_by_id helper the combat
        actions use. A deleted row resolves to None rather than raising.

    Notes/References:
        This is the seam a threat table drops into. Swapping "last attacker"
        for "highest accumulated damage" means changing what at_damage records
        and what this function reads -- the behaviour below, and the controller
        that calls it, do not change at all. See
        docs/2026-08-23-DESIGN-0003 §3.2.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    attacker_id = getattr(npc.ndb, LAST_ATTACKER_ID_ATTR, None)

    if attacker_id is None:
        return None

    # Imported here rather than at module scope: systems.combat.combat imports
    # this package's registry for the controller seam, so a top-level import
    # back into combat.py would close the cycle.
    from systems.combat.combat import _object_by_id

    attacker = _object_by_id(attacker_id)

    return attacker


def _can_be_fought(npc, target) -> bool:
    """
    Purpose: Decide whether `target` is a legal thing for `npc` to swing at.

    Entry:
        npc    - the attacking NPC.
        target - the candidate, already resolved to an object.

    Exit/Returns:
        True if the target can be acted on and is in the same room.

    Module Globals:
        None.

    Methodology:
        "Can this be acted on at all" is combat.target_unusable's question, not
        this module's -- it covers a None, a deleted row whose pk is gone, a
        non-Combatant and a corpse, and open-coding a subset here is how those
        four checks drifted apart the first time.

        The room check is the part that genuinely belongs to the AI. It is a
        decision not to chase, not a rule about whether an action can resolve.
        Without it the NPC would queue at a target that is no longer present,
        spend a tick starting a fight that check_stop_combat tears down on the
        next one, and re-queue on the tick after that, forever.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    # Imported here for the same cycle reason as _last_attacker's import.
    from systems.combat.combat import target_unusable

    if target_unusable(target):
        return False

    if target.location is None or target.location is not npc.location:
        return False

    return True


@register_behavior(AI_BEHAVIOR_AGGRESSIVE_MELEE)
def aggressive_melee(handler):
    """
    Purpose: Retaliate against whatever last hit us, and keep doing so.

    Entry:
        handler - the NPC's BlackoutCombatHandler. Consulted only when it has
                  no pending action.

    Exit/Returns:
        An {"kind": "attack", "target": ...} action dict, or None to stay idle
        this tick.

    Module Globals:
        None.

    Methodology:
        Purely reactive: an NPC running this behaviour never opens a fight, it
        only answers one. Unprovoked aggression is a separate trigger and a
        separate decision (phase 4), because the combat handler this behaviour
        hangs off only exists once combat has already started.

        Returning None on an unreachable attacker rather than clearing the
        recorded id is deliberate. A player who steps out of the room and back
        in gets attacked again, which is the behaviour a monster should have;
        the fight itself is ended by check_stop_combat either way.

    Notes/References:
        ActionAttack.next_action returns itself, so ONE queued attack
        self-sustains at the weapon's attack_speed cadence. This behaviour
        therefore fires once per fight in the normal case, not once per tick --
        the controller only consults it when pending_action is None.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    npc = handler.obj

    if npc is None:
        return None

    target = _last_attacker(npc)

    if not _can_be_fought(npc, target):
        return None

    return {"kind": "attack", "target": target}
