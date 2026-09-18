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



from .constants import (
    AI_BEHAVIOR_AGGRESSIVE_MELEE,
    AI_BEHAVIOR_CHASING_MELEE,
    LAST_ATTACKER_ID_ATTR,
    LEASH_DISTANCE_TILES,
    LEASH_ORIGIN_ATTR,
)
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

    # Imported here rather than at module scope: systems.gameplay.combat.combat imports
    # this package's registry for the controller seam, so a top-level import
    # back into combat.py would close the cycle.
    from systems.gameplay.combat.combat import _object_by_id

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
    from systems.gameplay.combat.combat import target_unusable

    unusable = target_unusable(target)

    if unusable:
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

    can_be_fought = _can_be_fought(npc, target)

    if not can_be_fought:
        return None

    action = {"kind": "attack", "target": target}

    return action



def _leash_origin(npc):
    """The tile this NPC is leashed to, recording it on the first call.

    Recorded lazily, when a chase starts, rather than stamped at spawn. An
    NPC that has never chased anything needs no leash, and "where I was when
    this began" is the tile a chase should return to -- which is not
    necessarily where the spawner put it.
    """
    origin = getattr(npc.db, LEASH_ORIGIN_ATTR, None)

    if origin is not None and getattr(origin, "pk", None) is not None:
        return origin

    room = npc.location

    if room is None:
        return None

    setattr(npc.db, LEASH_ORIGIN_ATTR, room)

    return room



def _release_leash(npc) -> None:
    """Forget the chase origin. The next chase records a new one."""
    setattr(npc.db, LEASH_ORIGIN_ATTR, None)



def _beyond_leash(npc, target) -> bool:
    """Whether the target has drawn this NPC past its leash.

    Measured from the LEASH ORIGIN to the target, not from the NPC to the
    target. Measuring from the NPC would make the leash a maximum chase
    distance that resets with every step, which is not a leash at all.

    A distance of None -- a different map, a different Z, an off-grid room --
    counts as beyond. Nothing the NPC can walk would close it.
    """
    from systems.gameplay.combat import reach

    origin = _leash_origin(npc)

    if origin is None:
        return False

    distance = reach.room_distance(origin, getattr(target, "location", None))

    if distance is None:
        return True

    return distance > LEASH_DISTANCE_TILES



def _go_home(npc) -> None:
    """Walk one step back toward the leash origin, and release it on arrival.

    One step per tick, through the same greedy chooser the chase uses, so an
    NPC returning home walks the map rather than teleporting across it.
    """
    from systems.gameplay.combat import reach

    origin = getattr(npc.db, LEASH_ORIGIN_ATTR, None)

    if origin is None or getattr(origin, "pk", None) is None:
        return

    if npc.location is origin:
        _release_leash(npc)

        return

    # step_toward_room, not step_toward: the destination is a ROOM, and a
    # room has no `.location` for step_toward to read. Passing one there
    # reports a dead end and the leashed NPC never moves.
    reach.step_toward_room(npc, origin)



@register_behavior(AI_BEHAVIOR_CHASING_MELEE)
def chasing_melee(handler):
    """
    Purpose: Retaliate, and close the distance when the attacker is out of
             reach.

    Entry:
        handler - the NPC's BlackoutCombatHandler. Consulted when it has no
                  pending action, AND on every tick its pending action is
                  stalled -- which is the tick a chase step belongs on.

    Exit/Returns:
        An attack action dict when the attacker is reachable, an approach
        action dict when it is not, or None.

    Module Globals:
        LEASH_DISTANCE_TILES read through _beyond_leash.

    Methodology:
        THIS IS WHAT KEEPS THE PROJECTILE NUMBERS HONEST. Without it a player
        shoots a melee NPC from seven tiles and takes no damage ever, and
        every balance figure for a bow is a fiction.

        It is aggressive_melee plus one branch, and the branch returns
        another ACTION rather than moving the NPC itself. Movement that
        bypassed queue_action would land at whatever point in the tick
        rotation this behaviour happened to be consulted, which is exactly
        the advantage over players the engine's INPUT phase removes.

        The leash is checked BEFORE the step, never after. An NPC that
        stepped first and then discovered it had gone too far would end one
        tile further out every time.

    Notes/References:
        Reuses _last_attacker and _can_be_fought from aggressive_melee. The
        two behaviours answer the same question about WHO; they differ only
        on what to do when that answer is out of range.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    npc = handler.obj

    if npc is None:
        return None

    target = _last_attacker(npc)

    if target is None:
        _go_home(npc)

        return None

    from systems.gameplay.combat.combat import target_unusable

    if target_unusable(target):
        _go_home(npc)

        return None

    if _can_be_fought(npc, target):
        # In the same room, which is every melee weapon's reach. Attacking
        # releases the leash: the NPC is where it needs to be, and the next
        # chase should measure from here.
        _release_leash(npc)

        return {"kind": "attack", "target": target}

    if _beyond_leash(npc, target):
        _go_home(npc)

        return None

    return {"kind": "approach", "target": target}
