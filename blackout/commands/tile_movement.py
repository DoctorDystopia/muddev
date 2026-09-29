"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Movement on the tile world: the eight direction commands, `run`,
             `climb`, `tiletp`, and the `goto` walk.

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
Since 09/29/2026 no command here moves a player. A direction command and
`goto` each start a walk, and the tick moves every walker
(`systems/gameplay/movement/walk.py`). A direction command is one tick of
movement: one tile, or two tiles with run on. The `goto` command runs A* on
the tile grid and walks the path. `BlackoutGotoCmd` in `commands/movement_cmds.py` calls
`run_goto`.
"""

import re

from evennia.commands.command import Command

from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.pathfind import find_path
from systems.core.tilegrid.world import get_world
from systems.gameplay.movement import constants as walk_const
from systems.gameplay.movement import walk
from systems.interface.statefeed import constants as feed_const
from world import tile_travel


# ─── Private constant definitions ────────────────────────────────────────────

_MSG_WHERE = "Where do you want to go?"
_MSG_STOPPED = "You stop walking."
_MSG_UNKNOWN = "You know of no place called '{text}' here."
_MSG_NO_PATH = "You cannot find a way there."
_MSG_SET_OFF = "You set off toward {place}."

# `goto (x,y)`, with or without the brackets and the spaces.
_COORDINATE_RE = re.compile(r"^\(?\s*(-?\d+)\s*,\s*(-?\d+)\s*\)?$")


# ─── Direction commands ──────────────────────────────────────────────────────

class _CmdTileDirection(Command):
    """
    Walk in a direction on the tile world.

    Usage:
        north, n, northeast, ne, ... northwest, nw

    One command is one tick of movement: one tile, or two tiles when you
    run. Hold the key in the client to keep walking.
    """

    direction = ""
    locks = "cmd:all()"
    help_category = "Movement"
    auto_help = False

    def func(self):
        """Start one tick of movement, or say why not."""
        caller = self.caller

        if not tile_travel.on_tile_world(caller):
            caller.msg(walk_const.MSG_NO_WAY)
            return

        walk.start_direction(caller, self.direction, self.session)


def _direction_command(name: str):
    """Return a direction command class for one direction name."""
    alias = tile_const.DIRECTION_ALIASES[name]
    class_name = "CmdTile" + name.capitalize()
    attributes = {"key": name, "aliases": [alias], "direction": name}

    return type(class_name, (_CmdTileDirection,), attributes)


# One class for each direction, from the direction table.
TILE_DIRECTION_COMMANDS: tuple = tuple(
    _direction_command(name) for name in tile_const.DIRECTION_OFFSETS)


# ─── Run ─────────────────────────────────────────────────────────────────────

class CmdRun(Command):
    """
    Turn run on or off.

    Usage:
        run         - turn run on if it is off, and off if it is on
        run on
        run off

    When you run, you move two tiles each tick, not one. This applies to
    `goto`, to a click on the map, and to the direction commands.
    """

    key = feed_const.COMMAND_RUN_TOGGLE
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        """Set run from the argument, or turn it the other way."""
        caller = self.caller
        word = self.args.strip().lower()

        if not word:
            running = not walk.is_running(caller)
        elif word in walk_const.RUN_WORDS_ON:
            running = True
        elif word in walk_const.RUN_WORDS_OFF:
            running = False
        else:
            caller.msg(walk_const.MSG_RUN_USAGE)
            return

        walk.set_running(caller, running)
        caller.msg(walk_const.MSG_RUN_ON if running else walk_const.MSG_RUN_OFF)


# ─── Climbing ────────────────────────────────────────────────────────────────

_MSG_CLIMBED = "You climb {way}."
_CLIMB_MESSAGES: dict = {
    tile_travel.CLIMB_NOTHING: "There is nothing to climb here.",
    tile_travel.CLIMB_WHICH_WAY: "Climb up or climb down?",
    tile_travel.CLIMB_NOT_THAT_WAY: "It does not go that way.",
    tile_travel.CLIMB_BLOCKED: "The way is blocked.",
}


class CmdClimb(Command):
    """
    Climb a ladder or a staircase on your tile.

    Usage:
        climb up
        climb down
        climb          - when it goes one way only

    You land on the same spot, one floor up or down.
    """

    key = "climb"
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        """Stop any walk, climb, and say how it went."""
        caller = self.caller
        direction = self.args.strip().lower()
        walk.stop(caller)
        result, way = tile_travel.climb(caller, direction)

        if result == tile_travel.CLIMB_OK:
            caller.msg(_MSG_CLIMBED.format(way=way))
            return

        message = _CLIMB_MESSAGES.get(result, "")

        if message:
            caller.msg(message)


# ─── The staff teleport ──────────────────────────────────────────────────────

_MSG_TELEPORT_USAGE = ("Usage: tiletp <x>,<y>[,<plane>]. Plane 0 holds chunks "
                       "{chunks}.")
_MSG_NO_PLANE = "There is no plane {plane}. The planes are 0 to {top}."
_MSG_NOT_LOADED = "No chunk holds tile ({x}, {y}) on plane {plane}."
_MSG_NOT_WALKABLE = "Tile ({x}, {y}) on plane {plane} is blocked or water."
_MSG_TELEPORT_FAILED = "The move to tile ({x}, {y}) failed."

# `tiletp x,y` or `tiletp x,y,plane`, with or without the brackets.
_TELEPORT_RE = re.compile(
    r"^\(?\s*(-?\d+)\s*,\s*(-?\d+)\s*(?:,\s*(\d+)\s*)?\)?$")


class CmdTileTeleport(Command):
    """
    Teleport to a tile of the tile world.

    Usage:
        tiletp <x>,<y>
        tiletp <x>,<y>,<plane>

    Staff jump to any open tile with this command. The plane is 0, the
    ground, when you give none. `tiletp` with no tile lists the chunks.
    """

    key = "tiletp"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        """Check the plane and the tile, then place the caller on it."""
        caller = self.caller
        world = get_world()
        match = _TELEPORT_RE.match(self.args.strip())

        if not match:
            chunks = ", ".join(str(key) for key in world.chunk_keys())
            caller.msg(_MSG_TELEPORT_USAGE.format(chunks=chunks or "none"))
            return

        x, y = int(match.group(1)), int(match.group(2))
        plane = int(match.group(3) or tile_const.GROUND_PLANE)

        if plane > tile_const.PLANE_MAX:
            caller.msg(_MSG_NO_PLANE.format(plane=plane,
                                            top=tile_const.PLANE_MAX))
            return

        view = world.plane(plane)
        refusal = _landing_refusal(view, x, y)

        if refusal:
            caller.msg(refusal)
            return

        walk.stop(caller)
        placed = movement.place(view.rooms, caller, x, y)

        if not placed:
            caller.msg(_MSG_TELEPORT_FAILED.format(x=x, y=y))


def _landing_refusal(view, x: int, y: int) -> str:
    """Return why a walker cannot land on a tile of a plane, or ""."""
    if not view.has_tile(x, y):
        return _MSG_NOT_LOADED.format(x=x, y=y, plane=view.plane)

    if view.grid.flags_at(x, y) & tile_const.FLAGS_UNWALKABLE:
        return _MSG_NOT_WALKABLE.format(x=x, y=y, plane=view.plane)

    return ""


# ─── The walk ────────────────────────────────────────────────────────────────

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


def run_goto(caller, text: str, follow_up: str = "", session=None) -> None:
    """
    Purpose: Do `goto` for a character on the tile world.

    Entry:
        caller    - a character on the tile world.
        text      - the target: "(x, y)" or a place name. "" stops a walk.
        follow_up - the line to run on arrival, or "".
        session   - the session of the command.

    Exit/Returns:
        None. The tick moves the walk: one tile a tick, or two with run on.

    Module Globals:
        None.

    Methodology:
        1. An empty target stops the walk, or asks where to go.
        2. Resolve the target, then search a path with A*.
        3. A walker on the goal arrives at once, so the follow-up runs now.
        4. Else start the walk. A new `goto` replaces an old walk.

    Notes/References:
        `BlackoutGotoCmd.func` calls this. `walk.start_path` owns the rest.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    if not text.strip():
        stopped = walk.stop(caller)
        caller.msg(_MSG_STOPPED if stopped else _MSG_WHERE)
        return

    view = tile_travel.plane_view(caller)
    here = tile_travel.tile_of(caller)

    if view is None or here is None:
        caller.msg(_MSG_NO_PATH)
        return

    # The walk stays on the plane of the caller. A name on another plane is
    # not found, and a climb is its own command.
    goal, place = _resolve(view, text, here)

    if goal is None:
        caller.msg(_MSG_UNKNOWN.format(text=text.strip()))
        return

    path = find_path(view.grid, here, goal)

    if path is None:
        caller.msg(_MSG_NO_PATH)
        return

    # A walk of one tile is a click on the next tile: a step, with no words.
    if len(path) > 1:
        caller.msg(_MSG_SET_OFF.format(place=place))

    walk.start_path(caller, path, goal, follow_up, session)
