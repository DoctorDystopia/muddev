"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: How a walker travels on the tile world: one step, a transition,
             and a search for a named tile.

             `systems/core/tilegrid/` knows the step rule and the rooms, but
             no content. This module adds the content: the target of each
             transition kind (`world/object_kinds.py`) and the room names of
             `world/tile_text.py`. The commands in `commands/tile_movement.py`
             call it. It holds no player text: a command picks the message
             for each step result.
"""

from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.planes import plane_of_z
from systems.core.tilegrid.world import get_world
from world import tile_text
from world.object_kinds import OBJECT_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_TRANSITION = tile_const.OBJECT_CATEGORY_TRANSITION
_CLIMB = tile_const.OBJECT_CATEGORY_CLIMB


# ─── Public constant definitions ─────────────────────────────────────────────

# The results of `climb`. The command picks the words for each one.
CLIMB_OK: str = "climbed"
CLIMB_NOTHING: str = "nothing_to_climb"
CLIMB_WHICH_WAY: str = "which_way"
CLIMB_NOT_THAT_WAY: str = "not_that_way"
CLIMB_BLOCKED: str = "landing_blocked"
CLIMB_MOVE_REFUSED: str = "move_refused"


# ─── Private helper routines ─────────────────────────────────────────────────

def _chebyshev(start: tuple, goal: tuple) -> int:
    """Return the number of steps from start to goal on an open grid."""
    return max(abs(goal[0] - start[0]), abs(goal[1] - start[1]))


# ─── Public routines ─────────────────────────────────────────────────────────

def plane_of(obj):
    """
    Return the plane that `obj` stands on, or None off the tile world. Reads
    the Z tag only, so a server with no tile world loads nothing.
    """
    location = getattr(obj, "location", None)
    coordinates = getattr(location, "xyz", None)

    if not coordinates:
        return None

    return plane_of_z(coordinates[2])


def on_tile_world(obj) -> bool:
    """Return True if `obj` stands in a room of the tile world, any plane."""
    return plane_of(obj) is not None


def plane_view(obj):
    """
    Return the TilePlane that `obj` stands on, or None off the tile world.
    A routine that acts for a walker reads the grid and the rooms of this
    plane, never those of the world, which are plane 0.
    """
    plane = plane_of(obj)

    if plane is None:
        return None

    return get_world().plane(plane)


def tile_of(obj):
    """Return the (x, y) tile that `obj` stands on, or None off the world."""
    if not on_tile_world(obj):
        return None

    x, y, _z = obj.location.xyz

    return (int(x), int(y))


def transition_target(world, x: int, y: int):
    """Return the target tile of the first transition on a tile, or None."""
    for key in world.kinds_at(x, y):
        kind = OBJECT_KINDS.get(key)

        if kind is not None and kind.category == _TRANSITION:
            return tuple(kind.target)

    return None


def step(mover, direction: str) -> str:
    """
    Purpose: Move a walker one tile on the tile world, through a transition
             if the next tile holds one.

    Entry:
        mover     - an object on the tile world.
        direction - a key of DIRECTION_OFFSETS.

    Exit/Returns:
        A STEP_* result of the tile grid constants. STEP_OFF_GRID off the
        tile world.

    Module Globals:
        None.

    Methodology:
        `movement.step` with the grid and the rooms of the plane of the
        mover, and a transition lookup on that plane. A transition lands on
        its target tile of the same plane.

    Notes/References:
        The walk limit is the default, `WALK_LIMIT` (the vault rule).

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    view = plane_view(mover)

    if view is None:
        return tile_const.STEP_OFF_GRID

    def _target(x, y):
        return transition_target(view, x, y)

    return movement.step(view.grid, view.rooms, mover, direction,
                         transition=_target)


def stride(mover, directions: list) -> tuple:
    """
    Move a walker along one or more hops in one move, through a transition
    if a hop lands on one. Return (result, hops) of `movement.stride`, or
    (STEP_OFF_GRID, 0) off the tile world. A run takes two hops a tick.
    """
    view = plane_view(mover)

    if view is None:
        return (tile_const.STEP_OFF_GRID, 0)

    def _target(x, y):
        return transition_target(view, x, y)

    return movement.stride(view.grid, view.rooms, mover, directions,
                           transition=_target)


def step_toward(mover, goal: tuple, distance) -> bool:
    """
    Purpose: Move a walker one tile toward a goal tile, greedily, as an NPC
             chase does.

    Entry:
        mover    - an object on the tile world.
        goal     - the (x, y) tile to walk toward.
        distance - `(tile, tile) -> int`, the measure of the caller.

    Exit/Returns:
        True if the mover moved. False if no legal step brings it strictly
        closer, or if the move failed.

    Module Globals:
        None.

    Methodology:
        Try the eight neighbours in the fixed order of DIRECTION_OFFSETS.
        Keep the legal step that is strictly closest. A tile with a
        transition is never a step for an NPC: a chase must not teleport.

    Notes/References:
        `systems/gameplay/combat/reach.py:step_toward_room` calls this on the
        tile world. It keeps the same greedy rule as on the xyzgrid.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    view = plane_view(mover)
    here = tile_of(mover)

    if view is None or here is None:
        return False

    best = None
    best_distance = distance(here, goal)

    for name, (dx, dy) in tile_const.DIRECTION_OFFSETS.items():
        tile = (here[0] + dx, here[1] + dy)
        jump = transition_target(view, tile[0], tile[1])
        legal = view.grid.check_step(here, tile)

        if jump is not None or legal != tile_const.STEP_OK:
            continue

        tile_distance = distance(tile, goal)

        if tile_distance < best_distance:
            best = name
            best_distance = tile_distance

    if best is None:
        return False

    result = movement.step(view.grid, view.rooms, mover, best)

    return result == tile_const.STEP_OK


def climb_directions(view, tile: tuple) -> list:
    """
    Return the climb directions of the climb objects on a tile of a plane,
    in the order of CLIMB_PLANE_STEPS, with no repeat. [] for no climb.
    """
    found = set()

    for key in view.kinds_at(tile[0], tile[1]):
        kind = OBJECT_KINDS.get(key)

        if kind is not None and kind.category == _CLIMB:
            found.update(kind.climbs)

    return [way for way in tile_const.CLIMB_PLANE_STEPS if way in found]


def _climb_way(ways: list, direction: str):
    """
    Return (direction, None) for a climb that may go, or (None, result) for
    a refusal. An empty direction picks the only way, if there is one.
    """
    if not ways:
        return (None, CLIMB_NOTHING)

    if not direction:
        if len(ways) > 1:
            return (None, CLIMB_WHICH_WAY)

        return (ways[0], None)

    if direction not in ways:
        return (None, CLIMB_NOT_THAT_WAY)

    return (direction, None)


def _landing(tile: tuple, plane: int):
    """Return the TilePlane where a climb to `plane` lands, or None."""
    if not tile_const.GROUND_PLANE <= plane <= tile_const.PLANE_MAX:
        return None

    landing = get_world().plane(plane)

    if not landing.has_tile(*tile):
        return None

    if landing.grid.flags_at(*tile) & tile_const.FLAGS_UNWALKABLE:
        return None

    return landing


def climb(mover, direction: str = "") -> tuple:
    """
    Purpose: Move a walker up or down one plane, by the climb object on its
             tile.

    Entry:
        mover     - an object on the tile world.
        direction - CLIMB_UP, CLIMB_DOWN, or "" for the only way there is.

    Exit/Returns:
        (result, direction): a CLIMB_* result of this module, and the
        direction that the climb took, or "" when it did not go.

    Module Globals:
        const.CLIMB_PLANE_STEPS read.

    Methodology:
        1. Read the climb directions of the tile.
        2. Pick the direction, or refuse.
        3. The landing is the same tile, one plane up or down. It must be a
           loaded tile that a walker may stand on.
        4. Place the mover there, and give back the room behind.

    Notes/References:
        The vault rule of Phase 7: stand on the tile, land on the same tile
        (Nick, 09/26/2026). `commands/tile_movement.py:CmdClimb` calls this.
        `movement.place` gives back only a room of the landing plane, so
        this gives back the room of the old plane itself.

    Author: Nick Hobar
    Creation date: 09/26/2026
    """
    view = plane_view(mover)
    tile = tile_of(mover)

    if view is None or tile is None:
        return (CLIMB_NOTHING, "")

    way, refusal = _climb_way(climb_directions(view, tile), direction)

    if refusal:
        return (refusal, "")

    landing = _landing(tile, view.plane + tile_const.CLIMB_PLANE_STEPS[way])

    if landing is None:
        return (CLIMB_BLOCKED, "")

    source = mover.location

    if not movement.place(landing.rooms, mover, tile[0], tile[1]):
        return (CLIMB_MOVE_REFUSED, "")

    view.rooms.release(source)

    return (CLIMB_OK, way)


def open_directions(world, tile: tuple) -> list:
    """
    Return the direction names of each legal step from a tile, in the order
    of DIRECTION_OFFSETS. A telnet player reads them as the Exits line.
    """
    names = []

    for name, (dx, dy) in tile_const.DIRECTION_OFFSETS.items():
        end = (tile[0] + dx, tile[1] + dy)
        result = world.grid.check_step(tile, end)

        if result == tile_const.STEP_OK:
            names.append(name)

    return names


def direction_between(start: tuple, end: tuple):
    """Return the direction name of a one-tile step, or None."""
    offset = (end[0] - start[0], end[1] - start[1])

    for name, direction_offset in tile_const.DIRECTION_OFFSETS.items():
        if direction_offset == offset:
            return name

    return None


def tiles_named(world, text: str, near: tuple) -> list:
    """
    Purpose: Find the tiles whose room name matches a typed name.

    Entry:
        world - a TileWorld.
        text  - what the player typed, for example "bank".
        near  - the tile of the player. The nearest match comes first.

    Exit/Returns:
        A list of (x, y), nearest first. An exact name match beats a prefix
        match at any distance.

    Module Globals:
        None.

    Methodology:
        Only a tile with a placed object has its own name. The search thus
        reads the placed objects, not every tile.

    Notes/References:
        `goto <name>` calls this. The xyzgrid `goto` searches the room keys of
        its map in the same way.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    wanted = text.strip().lower()
    exact = []
    prefix = []

    for _kind, x, y, _rotation in world.placed_objects():
        name = tile_text.tile_name(world.kinds_at(x, y), None).lower()

        if not name or (x, y) in exact or (x, y) in prefix:
            continue

        if name == wanted:
            exact.append((x, y))
        elif name.startswith(wanted):
            prefix.append((x, y))

    def _distance(tile):
        return _chebyshev(near, tile)

    return sorted(exact, key=_distance) + sorted(prefix, key=_distance)
