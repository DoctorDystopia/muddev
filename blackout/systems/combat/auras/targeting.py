"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/03/2026
Description: Spatial and friend/foe queries for damage auras — "which rooms are
             within N tiles of me, and which things in them may I pulse?"

Why this module exists
----------------------
This is the first Blackout feature that needs real geometry. `GridTile`
(typeclasses/rooms.py) inherits `XYZRoom` and therefore HAS coordinates, but
nothing in the game had ever read them: until now the only "nearby" primitive
in the codebase was `location.contents`, and combat was implicitly single-room
because `caller.search()` is room-scoped.

Keeping the query here rather than on the aura handler means the handler owns
cadence and damage, and this module owns "what is in range" — so a future
grenade, shout, or ground-targeted effect reuses the radius maths instead of
reinventing it.
"""

from evennia.contrib.grid.xyzgrid.xyzroom import (
    MAP_X_TAG_CATEGORY,
    MAP_Y_TAG_CATEGORY,
    MAP_Z_TAG_CATEGORY,
    XYZRoom,
)
from evennia.utils import logger

from .. import constants as const


# ─── Public constant definitions ───────────────────────────────────────────

# Metric names understood by _within_metric. Declared here so the constants
# module can carry the chosen value without importing this one.
DISTANCE_METRIC_EUCLIDEAN = "euclidean"
DISTANCE_METRIC_CHEBYSHEV = "chebyshev"


# ─── Radius query ──────────────────────────────────────────────────────────

def within_metric(dx: int, dy: int, radius: int) -> bool:
    """
    Purpose: Report whether a tile offset falls inside the configured radius.

    Public because the map overlay highlights tiles with this same predicate.
    Sharing it is the point: if the metric is ever retuned, what is drawn and
    what is pulsed move together instead of drifting apart.

    Entry:
        dx, dy - signed tile offsets from the origin.
        radius - non-negative radius in tiles.

    Exit/Returns:
        True iff the offset is in range under const.AURA_DISTANCE_METRIC.

    Module Globals:
        DISTANCE_METRIC_CHEBYSHEV read; const.AURA_DISTANCE_METRIC read.

    Methodology:
        Euclidean compares SQUARED distances so the test stays in integer
        arithmetic -- no math.sqrt, no float rounding deciding whether a tile
        on the exact boundary is in or out.

    Notes/References:
        An unrecognised metric falls back to euclidean rather than raising:
        this runs inside the tick loop, and a typo in a settings retune must
        not take combat down.

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    if const.AURA_DISTANCE_METRIC == DISTANCE_METRIC_CHEBYSHEV:
        return max(abs(dx), abs(dy)) <= radius

    return (dx * dx) + (dy * dy) <= (radius * radius)


def _coordinate_keys(center: int, radius: int) -> list:
    """
    Purpose: Build the exact list of coordinate tag values covering one axis.

    Entry:
        center - the origin's coordinate on this axis.
        radius - non-negative radius in tiles.

    Exit/Returns:
        Returns a list of strings, one per coordinate in [center-r, center+r].

    Module Globals:
        None.

    Methodology:
        Returns EXACT string values for an `__in` lookup, never a range bound.
        XYZ coordinates are stored as Evennia Tag keys, which are text columns,
        so a `db_tags__db_key__gte` range would compare lexicographically --
        "10" sorts before "9", and a radius spanning a digit boundary would
        silently return the wrong rooms. Enumerating the handful of exact keys
        sidesteps the collation question entirely.

    Notes/References:
        Negative coordinates stringify with their sign ("-3"), which matches how
        XYZRoom writes them (xyzroom.py parses back with `coord.lstrip("-")`).

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    keys = [str(value) for value in range(center - radius, center + radius + 1)]

    return keys


def rooms_within_radius(origin, radius: int) -> list:
    """
    Purpose: Return every grid room within `radius` tiles of `origin`, same Z.

    Entry:
        origin - the room to measure from. May be any room typeclass.
        radius - non-negative radius in tiles.

    Exit/Returns:
        Returns a list of room objects, always including `origin` itself. An
        off-grid origin returns [origin] rather than raising.

    Module Globals:
        MAP_*_TAG_CATEGORY read.

    Methodology:
        ONE database query, not (2r+1)^2 of them:

        1. Read origin.xyz. XYZRoom caches this into self._xyz after the first
           access, so repeat reads cost nothing.
        2. Query the bounding BOX with two `__in` lookups plus an exact Z.
           `XYZManager.filter_xyz` cannot express this -- it accepts only exact
           values or "*" -- so the query is built here in the same shape.
           The `.filter()` calls MUST stay separate: each one creates its own
           join against the tag table, whereas a single combined `.filter()`
           would demand one tag row match all three categories at once and
           always return nothing.
        3. Trim the box to the configured metric in Python.

        `filter_family()` is what makes GridTile (an XYZRoom SUBCLASS) match;
        a plain `.filter()` would match only exact XYZRoom rows and find none
        of the actual game world.

    Notes/References:
        Rooms can be deleted out from under a cached result by
        scripts/map_sync.py, so callers must re-resolve rather than hold
        these objects indefinitely.

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    if origin is None:
        return []

    if radius <= 0:
        return [origin]

    coordinates = getattr(origin, "xyz", None)
    if coordinates is None:
        # A plain Room, not a GridTile. Degrade to the caster's own room so an
        # aura still works in hand-built areas that were never on the grid.
        return [origin]

    x, y, z = coordinates

    if not isinstance(x, int) or not isinstance(y, int) or z is None:
        # xyzroom.py deliberately returns unconverted values when the
        # coordinate tags have not finished saving. Treat that as off-grid.
        return [origin]

    try:
        candidates = (
            XYZRoom.objects.filter_family()
            .filter(
                db_tags__db_key__in=_coordinate_keys(x, radius),
                db_tags__db_category=MAP_X_TAG_CATEGORY,
            )
            .filter(
                db_tags__db_key__in=_coordinate_keys(y, radius),
                db_tags__db_category=MAP_Y_TAG_CATEGORY,
            )
            .filter(
                db_tags__db_key__iexact=str(z),
                db_tags__db_category=MAP_Z_TAG_CATEGORY,
            )
            .distinct()
        )
        candidate_rooms = list(candidates)
    except Exception:
        logger.log_trace()
        return [origin]

    in_range = []

    for room in candidate_rooms:
        room_x, room_y, _room_z = room.xyz

        if not isinstance(room_x, int) or not isinstance(room_y, int):
            continue

        if within_metric(room_x - x, room_y - y, radius):
            in_range.append(room)

    if origin not in in_range:
        # The origin is always in its own radius. It can be missing if the
        # origin is off-grid but its neighbours are not.
        in_range.append(origin)

    return in_range


# ─── Friend / foe ──────────────────────────────────────────────────────────

def is_hostile_pulse_target(obj, caster) -> bool:
    """
    Purpose: Report whether an aura pulse may damage this object.

    Entry:
        obj    - any object found in a room's contents.
        caster - the entity running the aura, which must never target itself.

    Exit/Returns:
        True iff obj is a living hostile NPC other than the caster.

    Module Globals:
        None.

    Methodology:
        Blackout has no faction, aggression, or PvP flag -- the design vault
        leaves PvP explicitly undecided -- so hostility is inferred from the
        two signals that DO exist, and both must hold:

        1. `db.npc_key` is set. systems/spawning/respawn.py already treats this
           as canonical NPC identity precisely because every hostile shares one
           typeclass. Player Characters never carry it, so players are never
           pulsed and this cannot become accidental PvP.
        2. The object is a live CombatEntity. TalkativeNPC and ShopkeepNPC
           inherit DefaultObject only, so they have no `is_alive` at all --
           shopkeepers and quest givers standing in the radius are safe.

    Notes/References:
        Deliberately a predicate rather than an isinstance check, matching
        CmdAttack's `hasattr(target, "is_alive")` guard in commands/combat_cmds.py.

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    if obj is caster:
        return False

    if getattr(obj.db, "npc_key", None) is None:
        return False

    if not hasattr(obj, "is_alive"):
        return False

    return obj.is_alive()


def hostiles_in_rooms(rooms, caster) -> list:
    """
    Purpose: Collect every hostile eligible for a pulse standing in the given rooms.

    Entry:
        rooms  - iterable of room objects, typically from rooms_within_radius.
        caster - the entity running the aura.

    Exit/Returns:
        Returns a list of live hostile NPC objects. Empty when nothing is in
        range, which is the common case and not an error.

    Module Globals:
        None.

    Methodology:
        Flat scan of each room's contents through is_hostile_pulse_target. A room
        that has been deleted since the radius was cached raises on `.contents`,
        so each room is guarded individually -- one stale room must not cost the
        caster every other target on the tick.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    hostiles = []

    for room in rooms:
        try:
            contents = room.contents
        except Exception:
            logger.log_trace()
            continue

        for obj in contents:
            if is_hostile_pulse_target(obj, caster):
                hostiles.append(obj)

    return hostiles
