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

Line of sight
-------------
Since DESIGN-0011 Phase 6 (09/26/2026), a ranged attack needs sight too. A
wall or a Blocked tile on the line stops the shot (the vault,
Combat_System.md, "Line of sight"). Sight is a second question, beside the
distance: `can_strike` asks both. `systems/core/tilegrid/sight.py` walks the
line. in_reach alone still decides who is in a fight, so a wall between two
fighters does not end the fight.

What it deliberately does NOT do
--------------------------------
No cross-Z shots. A different Z is out of reach at any distance, and so is a
different map: two maps can both have a tile at (4, 6), and a shot that
crossed between them would be a shot through a wall of the worst kind.
"""

import math

from evennia.utils import logger

from systems.core.tilegrid.pathfind import find_path
from systems.core.tilegrid.sight import has_line_of_sight
from world import tile_travel

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

    return _planar_distance(here, there)


def _planar_distance(here, there) -> int:
    """
    The straight-line tiles between two (x, y, ...) points, rounded. The one
    measure that room_distance and the tile world chase both use.
    """
    dx = there[0] - here[0]
    dy = there[1] - here[1]
    distance = int(round(math.sqrt((dx * dx) + (dy * dy))))

    return distance


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


def has_sight(attacker, target) -> bool:
    """
    Purpose: Report whether a shot from `attacker` can pass to `target`.

    Entry:
        attacker, target - any two objects.

    Exit/Returns:
        True unless both stand on the tile world and a wall or a Blocked
        tile stops the line between them. Off the tile world there is no
        geometry to stop a shot, and in_reach already falls back to the
        same room there.

    Module Globals:
        None.

    Methodology:
        tilegrid.sight.has_line_of_sight between the two tiles. The rule is
        in the Obsidian vault, Combat_System.md, "Line of sight".

    Notes/References:
        Sight knows no distance. can_strike asks both questions.

    Author: Nick Hobar
    Creation date: 09/26/2026
    """
    here = tile_travel.tile_of(attacker)
    there = tile_travel.tile_of(target)

    if here is None or there is None:
        return True

    view = tile_travel.plane_view(attacker)

    # No shot crosses planes. in_reach refuses the different Z already.
    if tile_travel.plane_of(target) != view.plane:
        return False

    return has_line_of_sight(view.grid, here, there)


def can_strike(attacker, target, radius: int) -> bool:
    """
    Purpose: Report whether `attacker` may attack `target` from where it
             stands: in reach, and in sight for a ranged weapon.

    Entry:
        attacker - the acting combatant.
        target   - the candidate.
        radius   - the reach of the attacker in tiles, from reach_tiles.

    Exit/Returns:
        True if in_reach is True and, above melee reach, has_sight is True.

    Module Globals:
        const.MELEE_REACH_TILES read.

    Methodology:
        A melee weapon reaches only its own tile, so sight never stops it
        (the vault rule). The sight walk thus runs only for a ranged weapon.

    Notes/References:
        The attack command, the stall check, and the queue check ask this.
        The engagement check (get_sides) asks in_reach alone: a wall
        between two fighters does not end their fight.

    Author: Nick Hobar
    Creation date: 09/26/2026
    """
    if not in_reach(attacker, target, radius):
        return False

    if radius <= const.MELEE_REACH_TILES:
        return True

    return has_sight(attacker, target)


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


def _strikes_from(grid, tile: tuple, goal: tuple, radius: int) -> bool:
    """
    Return True if a weapon of this reach may strike `goal` from `tile`:
    in reach, and in sight above melee reach. can_strike, for two tiles.
    """
    if not within_metric(goal[0] - tile[0], goal[1] - tile[1], radius):
        return False

    if radius <= const.MELEE_REACH_TILES:
        return True

    return has_line_of_sight(grid, tile, goal)


def _first_tile_to_strike_from(grid, path: list, goal: tuple,
                               radius: int) -> tuple:
    """
    Return the first tile of `path` from which the weapon may strike `goal`.
    The path ends at the goal, and a tile strikes itself at any radius.
    """
    for tile in path:
        if _strikes_from(grid, tile, goal, radius):
            return tile

    return goal


def nearest_tile_in_reach(attacker, target, radius: int):
    """
    Purpose: Return the tile where `attacker` stops to strike `target`, or
             None when no walk can help.

    Entry:
        attacker - the combatant that wants to close.
        target   - the thing it wants to act on.
        radius   - the reach of the attacker in tiles, from reach_tiles.

    Exit/Returns:
        Returns an (x, y) tile of the tile world. Returns None when either
        one stands off the tile world. None means "no walk can help", which
        is a refusal and not a dead end.

    Module Globals:
        None.

    Methodology:
        1. An attacker that can strike now stays on its own tile.
        2. Search a shortest walk to the tile of the TARGET with A*. `goto`
           makes the same search.
        3. Return the first tile of that walk from which the weapon can
           strike: in reach, and in sight for a ranged weapon. can_strike
           asks the same two questions on arrival. Thus, the walk cannot
           end one tile short of its own rule.

        A radius of zero returns the tile of the target, because no other
        tile is in reach. Every melee weapon thus walks onto its target.

        The walk goes around a wall, because the path does. A bow walks
        until the wall no longer stands between the two (the vault rule,
        Combat_System.md, "Line of sight").

        When no path exists, the answer is the tile of the target. Then
        `goto` tells the player that it finds no way there.

    Notes/References:
        Handoff debt 16. The version before DESIGN-0011 Phase 4b picked the
        nearest LIVE ROOM of the ring. On the tile world most tiles have no
        room, so the archer walked onto the tile of the target.

        Another tile of the ring can be one step nearer than the tile that
        this returns, when the walk goes diagonally. The walk still ends
        where the weapon can strike.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    here = tile_travel.tile_of(attacker)
    there = tile_travel.tile_of(target)

    if here is None or there is None:
        return None

    view = tile_travel.plane_view(attacker)

    # A target on another plane is a climb away, not a walk.
    if tile_travel.plane_of(target) != view.plane:
        return None

    grid = view.grid

    if _strikes_from(grid, here, there, radius):
        return here

    path = find_path(grid, here, there)

    if path is None:
        return there

    return _first_tile_to_strike_from(grid, path, there, radius)


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


def _step_on_tile_world(mover, destination_room) -> bool:
    """
    The tile world branch of step_toward_room. A tile room has no exits, so
    the eight neighbour tiles take their place. The rule stays the same:
    greedy, strictly closer, by the same measure. Never raises.
    """
    there = _room_coordinates(destination_room)
    here = _room_coordinates(mover.location)

    if there is _OFF_GRID or here is _OFF_GRID or here[2] != there[2]:
        return False

    try:
        moved = tile_travel.step_toward(
            mover, (int(there[0]), int(there[1])), _planar_distance)
    except Exception:
        logger.log_trace()
        return False

    return moved


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

    if tile_travel.on_tile_world(mover):
        return _step_on_tile_world(mover, destination_room)

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
