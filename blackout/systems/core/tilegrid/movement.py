"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: One step of a thing on the tile grid, from one tile to the next.

What replaces the exits
-----------------------
On an xyzgrid map, `north` is an exit object, and a step is a traversal of it.
A tile room has no exits, because the room at the next tile may not exist yet.
DESIGN-0011 section 6.1 moves the rule into data:

1. `TileGrid.check_step` reads the walk flags and the heights.
2. `TileRooms.ensure_room` gets the room at the next tile, or makes one.
3. `move_to` moves the thing, with every Evennia hook, as today.
4. `TileRooms.release` gives back the room behind, if it is empty now.

A telnet player keeps the same words. Phase 4 puts a command in front of this
routine. The command owns the message for each refusal, so this module holds
no player text.
"""

from . import constants as const


# ─── Public routines ─────────────────────────────────────────────────────────

def tile_of(rooms, room):
    """
    Return the (x, y) tile of a room of this tile world, or None for a room
    that is not on it.
    """
    coordinates = getattr(room, "xyz", None)

    if not coordinates or coordinates[2] != rooms.world_z:
        return None

    return (coordinates[0], coordinates[1])


def step(grid, rooms, mover, direction: str,
         walk_limit=const.WALK_LIMIT, transition=None, **move_kwargs) -> str:
    """
    Purpose: Move a thing one tile in a direction, if the tile grid allows it.

    Entry:
        grid        - a grid.TileGrid.
        rooms       - the rooms.TileRooms of the same world.
        mover       - an Evennia object that stands in a TileRoom.
        direction   - a key of const.DIRECTION_OFFSETS.
        walk_limit  - passed to TileGrid.check_step.
        transition  - `(x, y) -> (x, y) or None`. None means no transitions.
                      For a tile with a transition, it gives the target tile.
        move_kwargs - passed to `move_to`, for example quiet=True.

    Exit/Returns:
        const.STEP_OK if the mover moved. Otherwise the refusal from
        TileGrid.check_step, STEP_OFF_GRID if the mover is not on this grid,
        or STEP_MOVE_REFUSED if Evennia refused the move. STEP_BLOCKED if a
        transition points at a tile that holds no walker.

    Module Globals:
        const.DIRECTION_OFFSETS read.

    Methodology:
        1. Find the tile of the mover and the tile in the direction.
        2. Ask the grid whether the step is legal.
        3. If the next tile holds a transition, the target tile replaces it.
           The mover never stands on the transition tile, as on the xyzgrid.
        4. Get or make the room at the tile, and move the mover there.
        5. If Evennia refused the move, give the new room back.
        6. Give back the room behind, if nothing stands in it now.

    Notes/References:
        DESIGN-0011 section 6.1, steps 2 to 4.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    offset = const.DIRECTION_OFFSETS.get(direction)

    if offset is None:
        return const.STEP_NOT_ADJACENT

    source = mover.location
    start = tile_of(rooms, source)

    if start is None:
        return const.STEP_OFF_GRID

    end = (start[0] + offset[0], start[1] + offset[1])
    result = grid.check_step(start, end, walk_limit)

    if result != const.STEP_OK:
        return result

    jump = None

    if transition is not None:
        jump = transition(end[0], end[1])

    if jump is not None:
        landing_flags = grid.flags_at(jump[0], jump[1])

        if landing_flags & const.FLAGS_UNWALKABLE:
            return const.STEP_BLOCKED

        end = jump

    target = rooms.ensure_room(end[0], end[1])
    moved = mover.move_to(target, move_type="move", **move_kwargs)

    if not moved:
        rooms.release(target)
        return const.STEP_MOVE_REFUSED

    rooms.release(source)

    return const.STEP_OK


def place(rooms, thing, x: int, y: int, **move_kwargs) -> bool:
    """
    Purpose: Put a thing on a tile, from anywhere, and make the room if needed.

    Entry:
        rooms       - the rooms.TileRooms of the world.
        thing       - an Evennia object.
        (x, y)      - the tile. The caller checked that the thing may be there.
        move_kwargs - passed to `move_to`.

    Exit/Returns:
        True if the thing is now on the tile.

    Module Globals:
        None.

    Methodology:
        The room that the thing leaves goes back if it is a tile room of this
        world and it is empty now. The new room goes back if the move fails.

    Notes/References:
        A spawn, a teleport, and a login use this. `step` is for a walk.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    source = thing.location
    target = rooms.ensure_room(x, y)
    moved = thing.move_to(target, move_type="teleport", **move_kwargs)

    if not moved:
        rooms.release(target)
        return False

    if tile_of(rooms, source) is not None:
        rooms.release(source)

    return True
