"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Movement on the tile world: the eight direction commands, and the
             walk behind `goto`.

Why commands, not exits
-----------------------
An xyzgrid tile moved a player through exit objects, one for each direction.
A tile room has no exits, because the room at the next tile may not exist
yet (DESIGN-0011 section 6.1). These commands take the place of the exits.
They sit in the character cmdset. A room with an exit object (a room that a
builder digs) still works: an exit cmdset has a higher priority.

The words are the words of the old exits: `north`, `n`, and so on. The Godot
client and a telnet player send the same line.

The walk
--------
`goto` on the tile world runs A* on the tile grid, then types one direction
command each tick, through `execute_cmd`. Every lock and every refusal of a
typed step thus applies to a walk too. A walk stops when a step does not land
on the next tile of the path, for example after a transition or a refusal.
`BlackoutGotoCmd` in `commands/movement_cmds.py` calls `run_goto`.
"""

import re
from dataclasses import dataclass, field

from evennia.commands.command import Command
from evennia.utils.utils import delay

from systems.core.tick.constants import TICK_SECONDS
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.pathfind import find_path
from systems.core.tilegrid.world import get_world
from world import tile_travel


# ─── Private constant definitions ────────────────────────────────────────────

_MSG_NO_WAY = "You cannot go that way."

# The message for each refused step. A result with no row says nothing:
# Evennia already told the player why it refused the move.
_STEP_MESSAGES: dict = {
    tile_const.STEP_NOT_ADJACENT: _MSG_NO_WAY,
    tile_const.STEP_OFF_GRID: _MSG_NO_WAY,
    tile_const.STEP_BLOCKED: "Something blocks the way.",
    tile_const.STEP_WALL: "A wall blocks the way.",
    tile_const.STEP_CORNER: "You cannot cut that corner.",
    tile_const.STEP_TOO_STEEP: "It is too steep to climb.",
}

_MSG_WHERE = "Where do you want to go?"
_MSG_STOPPED = "You stop walking."
_MSG_UNKNOWN = "You know of no place called '{text}' here."
_MSG_NO_PATH = "You cannot find a way there."
_MSG_SET_OFF = "You set off toward {place}."
_MSG_ARRIVED = "Target reached."
_MSG_WALK_BROKEN = "Your walk stops."

# `goto (x,y)`, with or without the brackets and the spaces.
_COORDINATE_RE = re.compile(r"^\(?\s*(-?\d+)\s*,\s*(-?\d+)\s*\)?$")


# ─── Private classes ─────────────────────────────────────────────────────────

@dataclass
class _TileWalk:
    """One walk: the tiles still to step on, and the line to run at the end."""

    path: list
    goal: tuple
    follow_up: str = ""
    task: object = field(default=None, repr=False)


# ─── Direction commands ──────────────────────────────────────────────────────

class _CmdTileDirection(Command):
    """
    Walk one tile in a direction on the tile world.

    Usage:
        north, n, northeast, ne, ... northwest, nw
    """

    direction = ""
    locks = "cmd:all()"
    help_category = "Movement"
    auto_help = False

    def func(self):
        """Take one step, or say why not."""
        caller = self.caller

        if not tile_travel.on_tile_world(caller):
            caller.msg(_MSG_NO_WAY)
            return

        result = tile_travel.step(caller, self.direction)
        message = _STEP_MESSAGES.get(result, "")

        if result != tile_const.STEP_OK and message:
            caller.msg(message)


def _direction_command(name: str):
    """Return a direction command class for one direction name."""
    alias = tile_const.DIRECTION_ALIASES[name]
    class_name = "CmdTile" + name.capitalize()
    attributes = {"key": name, "aliases": [alias], "direction": name}

    return type(class_name, (_CmdTileDirection,), attributes)


# One class for each direction, from the direction table.
TILE_DIRECTION_COMMANDS: tuple = tuple(
    _direction_command(name) for name in tile_const.DIRECTION_OFFSETS)


# ─── The staff teleport ──────────────────────────────────────────────────────

_MSG_TELEPORT_USAGE = "Usage: tiletp <x>,<y>. The tile world holds chunks {chunks}."
_MSG_NOT_LOADED = "No chunk holds tile ({x}, {y})."
_MSG_NOT_WALKABLE = "Tile ({x}, {y}) is blocked or water."
_MSG_TELEPORT_FAILED = "The move to tile ({x}, {y}) failed."


class CmdTileTeleport(Command):
    """
    Teleport to a tile of the tile world.

    Usage:
        tiletp <x>,<y>

    Staff jump to any open tile with this command. `tiletp` with no tile
    lists the chunks.
    """

    key = "tiletp"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        """Check the tile, then place the caller on it."""
        caller = self.caller
        world = get_world()
        match = _COORDINATE_RE.match(self.args.strip())

        if not match:
            chunks = ", ".join(str(key) for key in world.chunk_keys())
            caller.msg(_MSG_TELEPORT_USAGE.format(chunks=chunks or "none"))
            return

        x, y = int(match.group(1)), int(match.group(2))

        if not world.has_tile(x, y):
            caller.msg(_MSG_NOT_LOADED.format(x=x, y=y))
            return

        flags = world.grid.flags_at(x, y)

        if flags & tile_const.FLAGS_UNWALKABLE:
            caller.msg(_MSG_NOT_WALKABLE.format(x=x, y=y))
            return

        _stop(caller)
        placed = movement.place(world.rooms, caller, x, y)

        if not placed:
            caller.msg(_MSG_TELEPORT_FAILED.format(x=x, y=y))


# ─── The walk ────────────────────────────────────────────────────────────────

def _stop(caller) -> bool:
    """Cancel the walk of a character. Return True if one was running."""
    walk = caller.ndb.tile_walk

    if walk is None:
        return False

    if walk.task is not None and walk.task.active():
        walk.task.cancel()

    caller.ndb.tile_walk = None

    return True


def _resolve(world, text: str, here: tuple):
    """Return (goal tile, place name) for a typed target, or (None, "")."""
    match = _COORDINATE_RE.match(text.strip())

    if match:
        goal = (int(match.group(1)), int(match.group(2)))

        return goal, "(%d, %d)" % goal

    tiles = tile_travel.tiles_named(world, text, here)

    if not tiles:
        return None, ""

    return tiles[0], text.strip()


def _arrive(caller, walk, session) -> None:
    """End a walk at its goal, and run its follow-up line."""
    caller.ndb.tile_walk = None
    caller.msg(_MSG_ARRIVED)

    if walk.follow_up:
        caller.execute_cmd(walk.follow_up, session=session)


def _walk_step(caller, session) -> None:
    """
    Purpose: Take the next step of a walk, then book the step after it.

    Entry:
        caller  - the walking character.
        session - the session that started the walk.

    Exit/Returns:
        None.

    Module Globals:
        TICK_SECONDS read.

    Methodology:
        1. Stop if the walk is gone or the path does not start next to the
           walker.
        2. Type the direction command.
        3. Stop if the walker did not land on the next tile.
        4. Arrive at the end of the path. Else book the next step one tick
           later.

    Notes/References:
        The module docstring, "The walk".

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    walk = caller.ndb.tile_walk

    if walk is None or not walk.path:
        return

    here = tile_travel.tile_of(caller)
    next_tile = walk.path[0]
    direction = tile_travel.direction_between(here, next_tile) if here else None

    if direction is None:
        caller.ndb.tile_walk = None
        caller.msg(_MSG_WALK_BROKEN)
        return

    caller.execute_cmd(direction, session=session)
    landed = tile_travel.tile_of(caller)

    if landed != next_tile:
        caller.ndb.tile_walk = None
        return

    walk.path.pop(0)

    if not walk.path:
        _arrive(caller, walk, session)
        return

    walk.task = delay(TICK_SECONDS, _walk_step, caller, session)


def run_goto(caller, text: str, follow_up: str = "", session=None) -> None:
    """
    Purpose: Do `goto` for a character on the tile world.

    Entry:
        caller    - a character on the tile world.
        text      - the target: "(x, y)" or a place name. "" stops a walk.
        follow_up - the line to run on arrival, or "".
        session   - the session of the command.

    Exit/Returns:
        None. The walk runs in steps, one tick apart.

    Module Globals:
        None.

    Methodology:
        1. An empty target stops the walk, or asks where to go.
        2. Resolve the target, then search a path with A*.
        3. A walker on the goal arrives at once, so the follow-up runs now.
        4. Else start the walk. A new `goto` replaces an old walk.

    Notes/References:
        `BlackoutGotoCmd.func` calls this.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    if not text.strip():
        stopped = _stop(caller)
        caller.msg(_MSG_STOPPED if stopped else _MSG_WHERE)
        return

    world = get_world()
    here = tile_travel.tile_of(caller)
    goal, place = _resolve(world, text, here)

    if goal is None:
        caller.msg(_MSG_UNKNOWN.format(text=text.strip()))
        return

    path = find_path(world.grid, here, goal)

    if path is None:
        caller.msg(_MSG_NO_PATH)
        return

    _stop(caller)
    walk = _TileWalk(path=path, goal=goal, follow_up=follow_up)

    if not path:
        _arrive(caller, walk, session)
        return

    caller.ndb.tile_walk = walk
    caller.msg(_MSG_SET_OFF.format(place=place))
    _walk_step(caller, session)
