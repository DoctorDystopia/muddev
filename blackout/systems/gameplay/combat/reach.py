"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/17/2026
Description: Reach — can this attacker act on that target, and how far away is
             it? The one place combat answers a question about distance.

Why this module exists
----------------------
Combat was implicitly single-tile. Three places said so, in three different
ways: `_validate_attack` compared two `location` references, `get_sides`
scanned `location.contents`, and `check_stop_combat` filtered on
`c.location is location`. Each was correct while every weapon reached exactly
one tile, and each would have needed its own fix the moment one did not.

They now ask this module instead. The rule that a melee weapon reaches only
its own tile did not go away -- it became a NUMBER, `max_range = 0`, which is
what every melee ItemDef and bare hands carry. So melee behaviour is
unchanged, and it is unchanged because the data says so rather than because
three routines happen to agree.

What it reuses, and why nothing here is new
-------------------------------------------
The geometry is `auras/targeting.within_metric` and the room lookup is
`statefeed/neighbourhood.visible_rooms`. Both already existed for the aura
system, and the neighbourhood memo is the only reason a per-tick radius query
is affordable at all: it is a cache over a bounding-box tag join, keyed by
(room, radius) and invalidated when a tile is built or demolished.

What it deliberately does NOT do
--------------------------------
No line of sight. A wall does not block an arrow yet, and adding that means
walking the exits between two tiles, which is a different question from
"how far apart are they".

No cross-Z shots. A different Z is out of reach at any distance, and so is a
different map: two maps can both have a tile at (4, 6), and a shot that
crossed between them would be a shot through a wall of the worst kind.
"""

import math

from evennia.utils import logger

from . import constants as const
from .auras.targeting import within_metric


# ─── Private constant definitions ────────────────────────────────────────────

# Returned by _coordinates for anything not standing on a grid tile. Named
# rather than written as None at four call sites, because "off the grid" and
# "no answer" are the same value and only one of them is an error.
_OFF_GRID = None


# ─── Private helper routines ─────────────────────────────────────────────────

def _room_coordinates(room):
    """Return (x, y, z) for a room, or _OFF_GRID.

    A plain Room, a room mid-creation whose coordinate tags have not saved,
    and None all read as off-grid rather than raising -- this runs on the
    0.6s tick.
    """
    if room is None:
        return _OFF_GRID

    coordinates = getattr(room, "xyz", None)

    if coordinates is None:
        return _OFF_GRID

    x, y, z = coordinates

    if not isinstance(x, int) or not isinstance(y, int) or z is None:
        # xyzroom.py returns unconverted values while the tags are still
        # saving. Treat that as off-grid, exactly as targeting.py does.
        return _OFF_GRID

    return (x, y, z)


def _coordinates(obj):
    """Return (x, y, z) for the tile `obj` stands on, or _OFF_GRID.

    Reads the LOCATION's coordinates, not the object's: a character has no
    xyz of its own, the room it is in does.
    """
    if obj is None:
        return _OFF_GRID

    return _room_coordinates(getattr(obj, "location", None))


# ─── Public routines ─────────────────────────────────────────────────────────

def style_range_bonus(style) -> int:
    """Return the tiles a combat style adds to its weapon's range.

    Snipe declares 2. Every other style declares nothing and reads 0.
    """
    if not style:
        return 0

    bonus = style.get(const.STYLE_RANGE_BONUS_KEY, 0)

    return int(bonus or 0)


def reach_tiles(weapon_data) -> int:
    """
    Purpose: Return how far the attacker described by `weapon_data` reaches.

    Entry:
        weapon_data - a combat_profile() snapshot: the dict carrying
                      max_range and active_combat_style. May be None or {}.

    Exit/Returns:
        Returns a non-negative integer number of tiles. Zero means the same
        tile, which is melee and bare hands.

    Module Globals:
        const.MELEE_REACH_TILES read.

    Methodology:
        The weapon's own max_range plus the active style's range_bonus. Both
        are data on the ItemDef and its style table, so a new weapon reaches
        further by declaring a number, never by an edit here.

        Floored at MELEE_REACH_TILES rather than trusted: a negative
        range_bonus would otherwise make a bounding-box query with a negative
        radius, and the answer to that is not a smaller box.

    Notes/References:
        Reads the SNAPSHOT rather than the weapon object. The combat handler
        rebuilds that snapshot on every equip and on entering combat, so a
        bow swapped mid-fight changes the reach on the same tick it changes
        the damage.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    if not weapon_data:
        return const.MELEE_REACH_TILES

    base = int(weapon_data.get("max_range", const.MELEE_REACH_TILES) or 0)
    bonus = style_range_bonus(weapon_data.get("active_combat_style"))

    return max(const.MELEE_REACH_TILES, base + bonus)


def room_distance(origin, destination):
    """
    Purpose: Return the distance in tiles between two ROOMS.

    Entry:
        origin, destination - any two rooms. Either may be off the grid.

    Exit/Returns:
        Returns an integer number of tiles, or None when the two cannot be
        compared.

    Module Globals:
        None.

    Methodology:
        The same straight-line measure tile_distance makes, but between
        tiles rather than between the things standing on them. The chase
        behaviour needs this one: it compares the exits of a room, and an
        exit leads to a room, not to a combatant.

    Notes/References:
        tile_distance is written in terms of this, so the two can never
        disagree about how far apart two tiles are.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    here = _room_coordinates(origin)
    there = _room_coordinates(destination)

    if here is _OFF_GRID or there is _OFF_GRID:
        return None

    if here[2] != there[2]:
        return None

    dx = there[0] - here[0]
    dy = there[1] - here[1]

    return int(round(math.sqrt((dx * dx) + (dy * dy))))


def tile_distance(attacker, target):
    """
    Purpose: Return the distance in tiles between two combatants.

    Entry:
        attacker, target - any two objects. Either may be off the grid.

    Exit/Returns:
        Returns an integer number of tiles, or None when the two cannot be
        compared: a different Z, a different map, or either one off the grid.
        None is not zero. A caller that treats it as a distance would report
        two combatants on separate maps as standing on the same tile.

    Module Globals:
        None.

    Methodology:
        Straight-line distance, rounded to the nearest whole tile. This is
        the number a REFUSAL MESSAGE quotes, not the number a reach check
        uses -- in_reach compares squared distances through within_metric and
        never rounds, so a target on the exact boundary cannot be in range by
        one test and out by the other.

    Notes/References:
        The Z and map guard is the same one in_reach applies. It lives in
        both because this routine is also called on its own, to report how
        far away something is.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    return room_distance(
        getattr(attacker, "location", None),
        getattr(target, "location", None),
    )


def in_reach(attacker, target, radius: int) -> bool:
    """
    Purpose: Report whether `attacker` may act on `target` from where it stands.

    Entry:
        attacker - the acting combatant.
        target   - the candidate.
        radius   - the attacker's reach in tiles, from reach_tiles.

    Exit/Returns:
        True iff the two are on the same map and Z, and within `radius`
        tiles under the configured metric.

    Module Globals:
        const.REACH_DISTANCE_METRIC read through within_metric.

    Methodology:
        A radius of 0 is answered by comparing LOCATIONS, not coordinates.
        That keeps melee working in hand-built areas that were never put on
        the grid, where both combatants read as off-grid and no coordinate
        comparison is possible -- which is every room in the test suite's
        default fixtures.

        Above 0, the coordinate comparison is authoritative and an off-grid
        combatant is out of reach. A bow cannot shoot across a map boundary,
        and it cannot shoot from a room the grid does not place.

    Notes/References:
        Squared arithmetic through within_metric, so a tile on the exact
        boundary is decided by integers and not by float rounding.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    if attacker is None or target is None:
        return False

    location = getattr(attacker, "location", None)

    if location is None:
        return False

    if radius <= const.MELEE_REACH_TILES:
        return getattr(target, "location", None) is location

    here = _coordinates(attacker)
    there = _coordinates(target)

    if here is _OFF_GRID or there is _OFF_GRID:
        # Fall back to the same-tile answer. An off-grid combatant has no
        # distance, and reporting one would be inventing geometry.
        return getattr(target, "location", None) is location

    if here[2] != there[2]:
        return False

    return within_metric(there[0] - here[0], there[1] - here[1], radius)


def rooms_in_reach(attacker, radius: int) -> list:
    """
    Purpose: Return every room an attacker with this reach can act into.

    Entry:
        attacker - the acting combatant.
        radius   - its reach in tiles.

    Exit/Returns:
        Returns a list of rooms, always including the attacker's own. Returns
        [] when the attacker has no location.

    Module Globals:
        None.

    Methodology:
        Delegates to statefeed.neighbourhood, which memoises the bounding-box
        query by (room, radius) and drops the whole cache when any tile is
        built or demolished. That memo is what makes this affordable on the
        0.6s tick: uncached, the query measured 1.778 ms.

        A radius of 0 short-circuits before the memo is consulted. Melee is
        the overwhelming majority of calls and it needs no query at all.

    Notes/References:
        The import is deferred. This module is reached from combat.py, which
        is imported at typeclass load time, and the statefeed package is not
        safe to pull in that early.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    location = getattr(attacker, "location", None)

    if location is None:
        return []

    if radius <= const.MELEE_REACH_TILES:
        return [location]

    from systems.interface.statefeed import neighbourhood

    try:
        rooms = neighbourhood.visible_rooms(location, radius)
    except Exception:
        logger.log_trace()
        return [location]

    if location not in rooms:
        rooms.append(location)

    return rooms


def combatants_in_reach(attacker, radius: int) -> list:
    """
    Purpose: Return every object standing within the attacker's reach.

    Entry:
        attacker - the acting combatant, excluded from the result.
        radius   - its reach in tiles.

    Exit/Returns:
        Returns a list of objects. Empty is the normal answer for a lone
        combatant, not an error.

    Module Globals:
        None.

    Methodology:
        Walks the rooms from rooms_in_reach and trims each room's contents
        with in_reach. The room list is a bounding BOX; the trim is what
        makes the covered area a circle, the same two-step
        targeting.rooms_within_radius uses.

        A room deleted since the neighbourhood was cached raises on
        `.contents`, so each room is guarded on its own -- one stale room
        must not cost the attacker every other candidate on the tick.

    Notes/References:
        Returns objects, not combatants. Deciding what is a legal target is
        the caller's question and the answers differ: get_sides wants whoever
        is in the fight, an aura wants whoever is hostile.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    found = []

    for room in rooms_in_reach(attacker, radius):
        try:
            contents = room.contents
        except Exception:
            logger.log_trace()
            continue

        for obj in contents:
            if obj is attacker:
                continue

            if in_reach(attacker, obj, radius):
                found.append(obj)

    return found


def nearest_tile_in_reach(attacker, target, radius: int):
    """
    Purpose: Return the tile closest to `attacker` from which it could reach
             `target`, or None when there is none.

    Entry:
        attacker - the combatant that wants to close.
        target   - the thing it wants to act on.
        radius   - the attacker's reach in tiles, from reach_tiles.

    Exit/Returns:
        Returns a room, or None when the two share no geometry: a different
        map, a different Z, or either one off the grid. None means "no walk
        would help", which is a refusal and not a dead end.

    Module Globals:
        None.

    Methodology:
        Asked of the TARGET, not of the attacker. rooms_in_reach(target,
        radius) is every tile from which the target is `radius` tiles away or
        less, which is exactly the set of places this weapon could shoot it
        from. The metric is symmetric, so the ring is the same one in_reach
        will test on arrival -- the walk cannot end one tile short of its own
        rule.

        A radius of zero returns the target's own tile, because that is the
        only member of the ring. Every melee weapon therefore walks exactly
        where it walked before this routine existed.

    Notes/References:
        Ties are broken by iteration order, which is the neighbourhood's.
        Two tiles equally near are equally good: both are a step on the way,
        and choosing between them is a pathfinding question that `goto`
        already owns.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    here = getattr(attacker, "location", None)

    if here is None:
        return None

    best = None
    best_distance = None

    for room in rooms_in_reach(target, radius):
        distance = room_distance(here, room)

        if distance is None:
            continue

        if best_distance is None or distance < best_distance:
            best = room
            best_distance = distance

    return best


def search_candidates(attacker, radius: int):
    """
    Purpose: The candidate list a target search must cover for this reach.

    Entry:
        attacker - the searching combatant.
        radius   - its reach in tiles.

    Exit/Returns:
        Returns None for a melee reach, which tells Object.search to use its
        own default (the room's contents plus the searcher's). Returns an
        explicit list when the reach is wider.

    Module Globals:
        const.MELEE_REACH_TILES read.

    Methodology:
        None IS THE ANSWER FOR A RADIUS OF ZERO, not a failure. Evennia's
        default candidate set is already exactly the right one for a same-tile
        weapon, and rebuilding it here would be a second owner of what
        "nearby" means.

        The wider list keeps the searcher's own contents, so `attack` still
        resolves the name of something being carried the way it always did,
        and the refusal for that case stays the reach refusal rather than a
        "you see no such thing".

    Notes/References:
        `attack` is the only caller, and it asks for the ENGAGEMENT radius
        rather than its weapon's: it walks to what it cannot reach, so its
        search has to cover everything it can walk to. A click on a distant
        entity in the Godot client sends the same typed command, so the client
        needs no idea that this list exists.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    if radius <= const.MELEE_REACH_TILES:
        return None

    candidates = list(getattr(attacker, "contents", ()))
    candidates.extend(combatants_in_reach(attacker, radius))

    return candidates


def step_toward(mover, target) -> bool:
    """Move `mover` one tile toward whatever tile `target` is standing on.

    A thin wrapper over step_toward_room, for the common case of chasing
    something rather than walking to a place. The two are separate because a
    ROOM has no `.location`: passing one here would read its destination as
    None and report a dead end, which is how a leashed NPC stayed exactly
    where it stood.
    """
    return step_toward_room(mover, getattr(target, "location", None))


def step_toward_room(mover, destination_room) -> bool:
    """
    Purpose: Move `mover` one tile along whichever exit brings it closest to
             `destination_room`.

    Entry:
        mover            - the object taking the step. Must have a location
                           with exits.
        destination_room - the tile it is walking toward.

    Exit/Returns:
        Returns True when the move happened, False otherwise: no location, no
        exit that improves the distance, a dead end, or a refused move.

    Module Globals:
        None.

    Methodology:
        Greedy, one tile at a time, and deliberately NOT a path search. The
        step is recomputed from scratch every tick against the target's
        CURRENT tile, so a chase corrects itself as the quarry turns -- which
        a path computed once would not. The cost of the greedy choice is a
        dead end, and a dead end already has an answer: the fight ends
        through the grace.

        Moves through move_to, never through a location assignment. Every
        hook has to fire -- the room's arrival feed, the departure delta, and
        whatever a tile does to what stands on it. CLAUDE.md records what
        skipping them costs.

        Strictly closer, not "no further". An exit that leaves the distance
        unchanged is refused, because taking it would let two NPCs walk a
        circuit around a wall forever.

    Notes/References:
        Never raises. This runs inside an action on the 0.6s tick, and a
        malformed exit must not be able to end a fight.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    room = getattr(mover, "location", None)

    if room is None or destination_room is None:
        return False

    best_exit = None
    best_distance = room_distance(room, destination_room)

    if best_distance is None:
        return False

    try:
        exits = room.exits
    except Exception:
        logger.log_trace()
        return False

    for exit_obj in exits:
        destination = getattr(exit_obj, "destination", None)

        if destination is None:
            continue

        distance = room_distance(destination, destination_room)

        if distance is None:
            continue

        if distance < best_distance:
            best_exit = exit_obj
            best_distance = distance

    if best_exit is None:
        return False

    try:
        moved = mover.move_to(best_exit.destination, move_type="traverse")
    except Exception:
        logger.log_trace()
        return False

    return bool(moved)
