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
from systems.core.tilegrid.world import get_world
from world import tile_text
from world.object_kinds import OBJECT_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_TRANSITION = tile_const.OBJECT_CATEGORY_TRANSITION


# ─── Private helper routines ─────────────────────────────────────────────────

def _chebyshev(start: tuple, goal: tuple) -> int:
    """Return the number of steps from start to goal on an open grid."""
    return max(abs(goal[0] - start[0]), abs(goal[1] - start[1]))


# ─── Public routines ─────────────────────────────────────────────────────────

def on_tile_world(obj) -> bool:
    """
    Return True if `obj` stands in a room of the tile world. Reads the Z tag
    only, so a server with no tile world loads nothing.
    """
    location = getattr(obj, "location", None)
    coordinates = getattr(location, "xyz", None)

    if not coordinates:
        return False

    return coordinates[2] == tile_const.WORLD_Z


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
        A STEP_* result of the tile grid constants.

    Module Globals:
        None.

    Methodology:
        `movement.step` with the world grid, the world rooms, and a
        transition lookup on this world.

    Notes/References:
        The walk limit is the default, `WALK_LIMIT` (handoff debt 4).

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    world = get_world()

    def _target(x, y):
        return transition_target(world, x, y)

    return movement.step(world.grid, world.rooms, mover, direction,
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
    world = get_world()
    here = tile_of(mover)

    if here is None:
        return False

    best = None
    best_distance = distance(here, goal)

    for name, (dx, dy) in tile_const.DIRECTION_OFFSETS.items():
        tile = (here[0] + dx, here[1] + dy)
        jump = transition_target(world, tile[0], tile[1])
        legal = world.grid.check_step(here, tile)

        if jump is not None or legal != tile_const.STEP_OK:
            continue

        tile_distance = distance(tile, goal)

        if tile_distance < best_distance:
            best = name
            best_distance = tile_distance

    if best is None:
        return False

    result = movement.step(world.grid, world.rooms, mover, best)

    return result == tile_const.STEP_OK


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
