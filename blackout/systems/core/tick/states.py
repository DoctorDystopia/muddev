"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: The activity state machine every tickable handler advances
             through, as a (state, event) -> state table.

Why this is not called CombatState
----------------------------------
Combat is one activity that runs on the tick. Crafting a batch, working a
gathering node and pulsing an aura are the same shape: an actor commits to an
action, the action resolves, a cooldown runs, and eventually something ends it.
Naming the machine after the first system to need it is how a vocabulary stops
being reusable -- ``statefeed/events.py`` still exports ``emit_swing``, which
means a crossbow bolt and a mining swing both have to pretend to be sword
strokes to use it.

So the test applied to every name here is: **does it still read correctly for a
player mining a rock?** ``SWING_LANDED`` fails that test. ``ACTION_RESOLVED``
passes. ``ENGAGED`` fails (nobody is engaged with an ore vein); ``ACTIVE``
passes.

The word "combat" appears in the VALUES a system stores and the handlers that
own them, never in this machine.

What this replaces
------------------
"Is this entity in combat?" had five independent answers -- a persistent
``db.in_combat`` Attribute, whether a handler script existed, that script's
``db_is_active`` column, membership of the tick engine's rotation, and whether
``ndb.pending_action`` was None -- with nothing keeping them in agreement. The
repair code for their disagreement (a boot-time purge, an is_active filter on
every lookup, a delete-and-recreate branch) was the shape of the problem.

One field is authoritative now and the rest derive from it.

Reading the table
-----------------
``TRANSITIONS`` is exhaustive rather than clever: every legal pair is written
out, including the ones that could have been expressed as a wildcard. A
wildcard row is a branch in disguise, and the point of a table is that you can
read every legal move without simulating anything. A pair that is absent is
ILLEGAL, and ``next_state`` says so rather than guessing.
"""

from enum import Enum, auto

# ─── The states ─────────────────────────────────────────────────────────────


class ActivityState(Enum):
    """Where an actor is in the activity its handler is driving.

    IDLE        — the handler exists and is registered, but nothing is
                  pending. A combatant between fights; a gatherer standing at
                  a node they have not started working.
    ACTIVE      — an action is pending and will resolve on the next tick the
                  actor is free.
    RECOVERING  — mid-cooldown. One concept covering weapon speed, craft
                  seconds, gathering cadence and aura pulse interval, which
                  were four separate counters meaning the same thing.
    ENDING      — teardown is pending: the activity is over but the handler has
                  not been dismantled yet.
    TERMINATED  — the actor can no longer act at all. Death is the obvious
                  case; disconnection and forced removal are the others, which
                  is why this is not called DEAD.
    """

    IDLE = auto()
    ACTIVE = auto()
    RECOVERING = auto()
    ENDING = auto()
    TERMINATED = auto()


# ─── The events ─────────────────────────────────────────────────────────────


class ActivityEvent(Enum):
    """Something that happened to an activity.

    Named for what happened to the ACTIVITY, not for the fiction around it, so
    one vocabulary covers every system on the tick.

    ACTION_QUEUED         — an intention arrived. (Not ATTACK_QUEUED.)
    ACTION_RESOLVED       — the pending action ran to completion, whatever it
                            was. (Not SWING_LANDED: a mining swing, a craft
                            completing and an aura pulse are the same event.)
    COOLDOWN_EXPIRED      — the recovery period elapsed.
    TARGET_INVALID        — whatever the action was aimed at can no longer be
                            acted on: gone, dead, moved away, or its database
                            row deleted. ONE event for all four, which is what
                            collapses the six separate exit checks
                            ActionAttack.resolve used to carry.
    RESOURCES_EXHAUSTED   — the activity ran out of what it consumes: ore in
                            the vein, materials for the batch, ammunition.
    ACTIVITY_ABANDONED    — the actor chose to stop. Fleeing, cancelling a
                            craft, walking away from a node.
    ACTOR_INCAPACITATED   — the actor can no longer act: died, disconnected,
                            was teleported out, was stunned.
    """

    ACTION_QUEUED = auto()
    ACTION_RESOLVED = auto()
    COOLDOWN_EXPIRED = auto()
    TARGET_INVALID = auto()
    RESOURCES_EXHAUSTED = auto()
    ACTIVITY_ABANDONED = auto()
    ACTOR_INCAPACITATED = auto()


# ─── Public constant definitions ────────────────────────────────────────────

# The state every handler starts in.
INITIAL_STATE: ActivityState = ActivityState.IDLE

# States in which the actor counts as busy with its activity. This is the
# predicate `db.in_combat` used to be stored as: a combatant is in combat while
# swinging or between swings, and not while idle, ending or dead.
BUSY_STATES: frozenset = frozenset({
    ActivityState.ACTIVE,
    ActivityState.RECOVERING,
})

# States from which nothing further can happen. A handler reaching one of these
# is on its way out of the rotation.
FINAL_STATES: frozenset = frozenset({
    ActivityState.ENDING,
    ActivityState.TERMINATED,
})

# (state, event) -> next state. Written out in full; see the module header for
# why there are no wildcard rows.
TRANSITIONS: dict = {
    # Committing to an action. Queueing while already busy replaces the
    # pending action without disturbing the cooldown -- which is why
    # RECOVERING stays RECOVERING rather than jumping to ACTIVE.
    (ActivityState.IDLE, ActivityEvent.ACTION_QUEUED): ActivityState.ACTIVE,
    (ActivityState.ACTIVE, ActivityEvent.ACTION_QUEUED): ActivityState.ACTIVE,
    (ActivityState.RECOVERING, ActivityEvent.ACTION_QUEUED): ActivityState.RECOVERING,

    # The action ran. Whether a cooldown follows is the handler's business;
    # the machine's business is that the actor is no longer mid-action.
    (ActivityState.ACTIVE, ActivityEvent.ACTION_RESOLVED): ActivityState.RECOVERING,

    # Recovery elapsed.
    (ActivityState.RECOVERING, ActivityEvent.COOLDOWN_EXPIRED): ActivityState.ACTIVE,

    # Nothing left to act on, so the activity is over. ENDING rather than
    # IDLE because that is what Blackout actually does: a target vanishing
    # tears the handler down, and a craft batch that runs out of materials
    # halts and clears.
    #
    # IDLE is arguably the better GAME -- it would let a fighter re-target
    # without leaving combat -- but that is a rules change, not a modelling
    # decision, and this table describes the system as it is. Making that
    # change means changing these four rows and then deciding what tears an
    # idle handler down, which is why it is not smuggled in here.
    (ActivityState.ACTIVE, ActivityEvent.TARGET_INVALID): ActivityState.ENDING,
    (ActivityState.RECOVERING, ActivityEvent.TARGET_INVALID): ActivityState.ENDING,
    (ActivityState.ACTIVE, ActivityEvent.RESOURCES_EXHAUSTED): ActivityState.ENDING,
    (ActivityState.RECOVERING, ActivityEvent.RESOURCES_EXHAUSTED): ActivityState.ENDING,

    # The actor chose to stop.
    (ActivityState.IDLE, ActivityEvent.ACTIVITY_ABANDONED): ActivityState.ENDING,
    (ActivityState.ACTIVE, ActivityEvent.ACTIVITY_ABANDONED): ActivityState.ENDING,
    (ActivityState.RECOVERING, ActivityEvent.ACTIVITY_ABANDONED): ActivityState.ENDING,

    # The actor can no longer act. Legal from every non-final state, written
    # out rather than wildcarded.
    (ActivityState.IDLE, ActivityEvent.ACTOR_INCAPACITATED): ActivityState.TERMINATED,
    (ActivityState.ACTIVE, ActivityEvent.ACTOR_INCAPACITATED): ActivityState.TERMINATED,
    (ActivityState.RECOVERING, ActivityEvent.ACTOR_INCAPACITATED): ActivityState.TERMINATED,
    (ActivityState.ENDING, ActivityEvent.ACTOR_INCAPACITATED): ActivityState.TERMINATED,
}


# ─── Public routines ────────────────────────────────────────────────────────

def next_state(state: ActivityState, event: ActivityEvent):
    """
    Purpose: Look up where an event moves an activity, without applying it.

    Entry:
        state is the current ActivityState. event is an ActivityEvent.

    Exit/Returns:
        Returns the resulting ActivityState, or None when the pair is not in
        TRANSITIONS -- meaning the event cannot legally happen from here.

    Module Globals:
        TRANSITIONS read.

    Methodology:
        A dict lookup. The value of the table is that this routine has no
        branches at all, so adding an activity type or an event means adding
        rows rather than editing logic.

    Notes/References:
        Returning None rather than raising is deliberate: the caller decides
        whether an illegal transition is a bug worth logging or an ordinary
        race worth ignoring. TickableHandler.dispatch logs it.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    resulting = TRANSITIONS.get((state, event))

    return resulting


def is_busy(state: ActivityState) -> bool:
    """
    Purpose: Report whether an actor in this state is occupied by its activity.

    Entry:
        state is an ActivityState.

    Exit/Returns:
        True for ACTIVE and RECOVERING, False otherwise.

    Module Globals:
        BUSY_STATES read.

    Methodology:
        The one predicate `db.in_combat` is derived from, so the flag, the
        summary panel, the statefeed payload and `examine` are structurally
        incapable of disagreeing about it.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    busy = state in BUSY_STATES

    return busy


def is_final(state: ActivityState) -> bool:
    """Report whether a handler in this state is on its way out of the rotation."""
    final = state in FINAL_STATES

    return final
