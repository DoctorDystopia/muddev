"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The Grit pool of one character (DESIGN-0015, section 4.2).

             The maximum is the Augmentation level plus AUG_POOL_FLOOR, read
             at each call and never stored. The current value is one
             Attribute, GRIT_ATTR. This module is its one writer: `spend`,
             `restore`, and `sync_from_level`. Grit does not regenerate
             (Nick, 10/30/2026). An AugBot restores it in full, and a
             consumable restores a part of it (later).

             Each write reaches `emit_vitals`, the choke point of the
             `char_vitals` channel. The vitals bar of the client follows the
             pool as it follows HP. A move of the maximum is a forced send,
             for the reason the max_hp setter gives: nothing repeats it.
"""

from systems.interface.statefeed import events as feed

from . import constants as aug_const


# ─── Public routines ─────────────────────────────────────────────────────────

def level(obj) -> int:
    """
    Purpose: Read the Augmentation level of an entity. The rules module
             reads it for the bonus, and `maximum` reads it for the pool.

    Entry:
        obj is an Evennia object. It may have no skills handler.

    Exit/Returns:
        Returns the level as an int. 0 for an entity with no skills handler.

    Module Globals:
        None.

    Methodology:
        Read through the handler, not through skills/logic.py. Both the
        character handler and StatBlockSkills of an NPC give `get_level`, and
        the second never raises on a key the NPC does not declare. The
        skills constants are imported inside the routine. skills/logic.py
        imports this module for the level-up side effect.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    from systems.gameplay.progression.skills.constants import SKILL_KEY_AUGMENTATION

    skills = getattr(obj, "skills", None)

    if skills is None:
        return 0

    stored = skills.get_level(SKILL_KEY_AUGMENTATION)

    return int(stored)


# ─── Private helper routines ─────────────────────────────────────────────────

def _clamp(value: int, cap: int) -> int:
    """Hold a Grit value inside [GRIT_EMPTY, cap]."""
    if value < aug_const.GRIT_EMPTY:
        return aug_const.GRIT_EMPTY

    if value > cap:
        return cap

    return value


def _write(obj, value: int, force: bool) -> int:
    """
    Purpose: Store a Grit value and publish it. The one write of GRIT_ATTR.

    Entry:
        obj is an Evennia object with `db`.
        value is already clamped.
        force says whether the send passes the channel cap.

    Exit/Returns:
        Returns the stored value.

    Module Globals:
        None.

    Methodology:
        Write the Attribute, then call emit_vitals. The emitter reads the
        pool back through `current` and `maximum`.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    obj.attributes.add(aug_const.GRIT_ATTR, value)

    feed.emit_vitals(obj, force=force)

    return value


def maximum(obj) -> int:
    """
    Purpose: The most Grit an entity can hold: its Augmentation level plus
             the pool floor. Never stored.

    Entry:
        obj is an Evennia object. It may have no skills handler.

    Exit/Returns:
        Returns an int of at least AUG_POOL_FLOOR.

    Module Globals:
        aug_const.AUG_POOL_FLOOR read.

    Methodology:
        One addition. The level comes from `level`.

    Notes/References:
        DESIGN-0015 section 4.8: the pool is `AUG_POOL_FLOOR + level`.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    held_level = level(obj)

    return aug_const.AUG_POOL_FLOOR + held_level


def current(obj) -> int:
    """
    Purpose: The Grit an entity holds now.

    Entry:
        obj is an Evennia object. It may have no `db`, and it may have no
        GRIT_ATTR.

    Exit/Returns:
        Returns an int in [GRIT_EMPTY, maximum(obj)]. An entity with no
        GRIT_ATTR is full: it never spent any.

    Module Globals:
        aug_const.GRIT_ATTR read.

    Methodology:
        1. Read the Attribute. None means full.
        2. Clamp to the maximum of today. A level that moved since the last
           write cannot leave the reading over the cap.

    Notes/References:
        A read never writes. A character made before this module exists
        gets the full reading without a migration.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    cap = maximum(obj)
    attributes = getattr(obj, "attributes", None)

    if attributes is None:
        return cap

    stored = attributes.get(aug_const.GRIT_ATTR, default=None)

    if stored is None:
        return cap

    return _clamp(int(stored), cap)


def spend(obj, amount: int) -> int:
    """
    Purpose: Take Grit from an entity. The drain of Phase 2 calls this one
             point at a time.

    Entry:
        obj is an Evennia object with `db`.
        amount is an int of at least 0.

    Exit/Returns:
        Returns the Grit after the spend, clamped at GRIT_EMPTY.

    Module Globals:
        None.

    Methodology:
        Subtract, clamp, write. The send is not forced: the pool moves one
        point at a time, and the next point repairs a capped send.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    cap = maximum(obj)
    after = _clamp(current(obj) - amount, cap)

    return _write(obj, after, force=False)


def restore(obj, amount: int = None) -> int:
    """
    Purpose: Give Grit to an entity. The AugBot restores in full, and a
             consumable restores a part.

    Entry:
        obj is an Evennia object with `db`.
        amount is an int of at least 0, or None for a full restore.

    Exit/Returns:
        Returns the Grit after the restore, clamped at the maximum.

    Module Globals:
        None.

    Methodology:
        Add, clamp, write. A full restore writes the maximum.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    cap = maximum(obj)

    if amount is None:
        after = cap
    else:
        after = _clamp(current(obj) + amount, cap)

    return _write(obj, after, force=True)


def sync_from_level(obj) -> None:
    """
    Purpose: Follow a move of the Augmentation level. The level-up side
             effect that skills/logic.py registers, as Fortitude registers
             sync_max_hp_from_fortitude.

    Entry:
        obj is an Evennia object with `db`.

    Exit/Returns:
        No conditions. The stored Grit is clamped to the new maximum. A
        raised maximum does not fill the pool, and a lowered one cuts it.

    Module Globals:
        None.

    Methodology:
        Read the clamped current value and write it back with a forced
        send. The maximum is not stored, so the client learns the new cap
        from this send alone.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    after = current(obj)

    _write(obj, after, force=True)
