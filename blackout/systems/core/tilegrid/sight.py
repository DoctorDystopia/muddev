"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/26/2026
Description: Line of sight on the tile grid: may a shot pass from one tile to
             another?

The rule
--------
The Obsidian vault, 03_Systems/Combat_System.md, "Line of sight" (Nick,
09/26/2026). It is the OSRS rule:

- A wall on a tile edge that the line crosses stops the shot.
- A Blocked tile that the line enters stops the shot. The tile of the target
  does not count: the target stands on it.
- Water does not stop a shot. Height does not stop a shot.

The walk
--------
The walk of OSRS (RuneLite `WorldArea.hasLineOfSightTo`). The line goes from
the centre of the start tile to the centre of the end tile. The walk takes one
step on the longer axis at a time. At each step it enters the next tile on
that axis. Then, if the line crossed into the next row on the shorter axis,
it enters that tile too. Each entry crosses one tile edge, so the walk reads
walls with the same edge tables as the step rule.

The line is fixed point, with SIGHT_FIXED_POINT_BITS bits of fraction. Integers
give one answer on every machine, as heights do (DESIGN-0011 section 6.4).

A diagonal line crosses as an L: the longer axis first, then the shorter.
Only that leg is read, as in OSRS. Thus, sight is not always the same in both
directions past a corner. The walk rule for a step is stricter: no corner
cutting.
"""

from . import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

_BITS = const.SIGHT_FIXED_POINT_BITS

# One half of a tile in fixed point: the line starts at the tile centre.
_HALF = 1 << (_BITS - 1)


# ─── Private helper routines ─────────────────────────────────────────────────

def _x_major(major: int, minor: int) -> tuple:
    """Return the tile for a walk whose longer axis is x."""
    return (major, minor)


def _y_major(major: int, minor: int) -> tuple:
    """Return the tile for a walk whose longer axis is y."""
    return (minor, major)


def _can_pass(grid, start: tuple, end: tuple, goal: tuple) -> bool:
    """
    Return True if a shot may cross the edge from `start` into `end`, two
    tiles that share an edge. The goal tile is never Blocked to a shot.
    """
    offset = (end[0] - start[0], end[1] - start[1])
    leaving = grid.flags_at(start[0], start[1])
    entering = grid.flags_at(end[0], end[1])

    if leaving & const.EDGE_WALL_LEAVING[offset]:
        return False

    if entering & const.EDGE_WALL_ENTERING[offset]:
        return False

    if end != goal and entering & const.FLAGS_BLOCK_SIGHT:
        return False

    return True


def _walk(grid, start: tuple, goal: tuple, major_delta: int,
          minor_delta: int, to_tile) -> bool:
    """
    Walk the line from `start` to `goal`, one step on the longer axis at a
    time. `to_tile(major, minor)` turns axis values into an (x, y) tile.
    Return False at the first edge that a shot may not cross.
    """
    major_step = 1 if major_delta > 0 else -1
    major_length = abs(major_delta)
    slope = (abs(minor_delta) << _BITS) // major_length

    if minor_delta < 0:
        slope = -slope

    major, minor_start = (start if to_tile is _x_major
                          else (start[1], start[0]))
    minor_fixed = (minor_start << _BITS) + _HALF

    if minor_delta < 0:
        minor_fixed -= 1

    previous = start

    for _step in range(major_length):
        major += major_step
        tile = to_tile(major, minor_fixed >> _BITS)

        if not _can_pass(grid, previous, tile, goal):
            return False

        minor_fixed += slope
        turned = to_tile(major, minor_fixed >> _BITS)

        if turned != tile:
            if not _can_pass(grid, tile, turned, goal):
                return False

            tile = turned

        previous = tile

    return True


# ─── Public routines ─────────────────────────────────────────────────────────

def has_line_of_sight(grid, start: tuple, goal: tuple) -> bool:
    """
    Purpose: Say whether a shot may pass from tile `start` to tile `goal`.

    Entry:
        grid        - a grid.TileGrid.
        start, goal - (x, y) global tile coordinates.

    Exit/Returns:
        True if no wall and no Blocked tile stops the line. True if the two
        tiles are the same tile.

    Module Globals:
        None.

    Methodology:
        The module docstring, "The walk". The axis with the larger change is
        the longer axis. On a tie, y is the longer axis, as in OSRS.

    Notes/References:
        `systems/gameplay/combat/reach.py` asks this for a ranged attack.
        Reach and sight are two questions: this one knows no distance.

    Author: Nick Hobar
    Creation date: 09/26/2026
    """
    if start == goal:
        return True

    dx = goal[0] - start[0]
    dy = goal[1] - start[1]

    if abs(dx) > abs(dy):
        return _walk(grid, start, goal, dx, dy, _x_major)

    return _walk(grid, start, goal, dy, dx, _y_major)
