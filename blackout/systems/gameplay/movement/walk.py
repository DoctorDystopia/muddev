"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/29/2026
Description: The walk of a character on the tile world, and the run toggle.
             Every step of a player moves here, on the tick.

One walk, two sources
---------------------
A walk is a list of tiles to step on. Two commands make one:

1. `goto` searches a path with A*, and the walk follows it to the goal.
2. A direction command (`north`, `n`, ...) makes a walk of ONE tick of
   movement in a straight line: one tile, or two tiles when the character
   runs.

The tick moves every walker at PHASE_START. A held movement key and a click
thus move at the same speed: one tile a tick, or two tiles a tick with run
on. A direction command replaces a `goto` walk, and a `goto` replaces a
direction walk. The newest command wins, as in OSRS.

A held key
----------
The Godot client sends the direction of a held key two times a tick. Each
command makes a new walk from the current tile, so a walk never holds more
than one tick of movement. When the player lets go of the key, the client
stops the sends. The walker then moves at most one tick more. A tap is one
tick of movement. No "stop" command exists, so a lost key-up message cannot
make a walk that never ends.

The run and the tile skip
-------------------------
A run takes two tiles a tick, in ONE `move_to` (`movement.stride`). The
middle tile gets no room, no `at_object_receive`, and no quest visit: the
tile skip of OSRS. A path with an odd number of tiles ends with one tile at
walk speed. A path of one tile is one tile, with run on or off, so a click on
the next tile never overshoots.

A hop onto a transition ends the stride at the transition target, and it
ends the walk.

The walk feed
-------------
`set_walk` is the one writer of the walk, and it sends `blackout_walk` when
the feed must change. A `goto` walk shows the destination marker. A direction
walk shows none, so the feed sends nothing for a held key.
"""

from dataclasses import dataclass, field

from evennia.utils import logger

from systems.core.tick.engine import PHASE_START, register_phase_hook
from systems.core.tilegrid import constants as tile_const
from systems.interface.statefeed import events as feed
from world import tile_travel

from . import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

# The message for each refused step. A result with no row says nothing:
# Evennia already told the player why it refused the move.
_STEP_MESSAGES: dict = {
    tile_const.STEP_NOT_ADJACENT: const.MSG_NO_WAY,
    tile_const.STEP_OFF_GRID: const.MSG_NO_WAY,
    tile_const.STEP_BLOCKED: const.MSG_BLOCKED,
    tile_const.STEP_WALL: const.MSG_WALL,
    tile_const.STEP_CORNER: const.MSG_CORNER,
    tile_const.STEP_TOO_STEEP: const.MSG_TOO_STEEP,
}


# ─── Module globals ──────────────────────────────────────────────────────────

# Every character with a walk, by id. `set_walk` keeps it current. The tick
# reads it, so a server with no walker does no work on the tick.
_WALKERS: dict = {}


# ─── Public classes ──────────────────────────────────────────────────────────

@dataclass
class TileWalk:
    """
    One walk: the tiles still to step on, the goal, and the line to run at
    the end. `shown` is False for a direction walk: the minimap draws no
    destination marker for a held key. `announce` is False for a walk of
    one tile: a click on the next tile is a step, and it says nothing.
    """

    path: list
    goal: tuple
    follow_up: str = ""
    shown: bool = True
    announce: bool = True
    session: object = field(default=None, repr=False)


# ─── The run toggle ──────────────────────────────────────────────────────────

def is_running(character) -> bool:
    """Return True if the character has run on."""
    return bool(character.attributes.get(const.RUN_ATTR, default=False))


def set_running(character, running: bool) -> None:
    """Turn run on or off, and send the walk feed, which carries it."""
    character.attributes.add(const.RUN_ATTR, bool(running))
    feed.emit_walk(character)


def tiles_per_tick(character) -> int:
    """Return how many tiles the character moves each tick."""
    if is_running(character):
        return const.RUN_TILES_PER_TICK

    return const.WALK_TILES_PER_TICK


# ─── The walk ────────────────────────────────────────────────────────────────

def current(character):
    """Return the walk of the character, or None."""
    return getattr(character.ndb, const.WALK_NDB_ATTR)


def _shown(walk) -> bool:
    """Return True if the feed shows this walk."""
    return walk is not None and walk.shown


def set_walk(character, walk) -> None:
    """
    Set the walk of a character, or None. The one writer of the walk, so the
    tick and the feed follow every start, arrival, stop, and break. The feed
    goes out only if the old walk or the new walk shows on it.
    """
    old = current(character)
    setattr(character.ndb, const.WALK_NDB_ATTR, walk)

    if walk is None:
        _WALKERS.pop(character.id, None)
    else:
        _WALKERS[character.id] = character

    if _shown(old) or _shown(walk):
        feed.emit_walk(character)


def stop(character) -> bool:
    """Cancel the walk of a character. Return True if one was running."""
    if current(character) is None:
        return False

    set_walk(character, None)

    return True


def refuse(character, tile, direction: str, result: str) -> None:
    """
    Tell the character why a step did not go. A refusal of the same step
    from the same tile says nothing again, because a held key sends the step
    two times a tick. A step that goes clears the record.
    """
    refusal = (tile, direction)

    if getattr(character.ndb, const.REFUSAL_NDB_ATTR) == refusal:
        return

    setattr(character.ndb, const.REFUSAL_NDB_ATTR, refusal)
    message = _STEP_MESSAGES.get(result, "")

    if message:
        character.msg(message)


def _line(view, start: tuple, direction: str, count: int) -> tuple:
    """
    Return (tiles, result): up to `count` legal tiles in a straight line from
    `start`, and the refusal of the first hop that does not go, or STEP_OK.
    The line ends on a transition tile, because the transition moves the
    walker somewhere else.
    """
    offset = tile_const.DIRECTION_OFFSETS[direction]
    tiles = []
    at = start

    for _hop in range(count):
        end = (at[0] + offset[0], at[1] + offset[1])
        result = view.grid.check_step(at, end)

        if result != tile_const.STEP_OK:
            return (tiles, result)

        tiles.append(end)

        if tile_travel.transition_target(view, end[0], end[1]) is not None:
            break

        at = end

    return (tiles, tile_const.STEP_OK)


def start_direction(character, direction: str, session=None) -> str:
    """
    Purpose: Start one tick of movement in a direction: the walk behind a
             direction command.

    Entry:
        character - a character on the tile world.
        direction - a key of DIRECTION_OFFSETS.
        session   - the session of the command.

    Exit/Returns:
        STEP_OK if the walk starts. Else the refusal of the first hop. A
        refusal leaves the current walk as it is.

    Module Globals:
        None.

    Methodology:
        1. Make the line of tiles for one tick: one, or two with run on.
        2. A refused first hop tells the player why, and starts nothing.
        3. Else the line replaces the current walk. The tick moves it.

    Notes/References:
        The module docstring, "A held key".

    Author: Nick Hobar
    Creation date: 09/29/2026
    """
    view = tile_travel.plane_view(character)
    here = tile_travel.tile_of(character)

    if view is None or here is None:
        return tile_const.STEP_OFF_GRID

    tiles, result = _line(view, here, direction, tiles_per_tick(character))

    if not tiles:
        refuse(character, here, direction, result)
        return result

    walk = TileWalk(path=tiles, goal=tiles[-1], shown=False, session=session)
    set_walk(character, walk)

    return tile_const.STEP_OK


def start_path(character, path: list, goal: tuple, follow_up: str = "",
               session=None) -> None:
    """
    Start a walk along a path from A*. An empty path arrives at once, so the
    follow-up runs now. The first step goes on the next tick.
    """
    walk = TileWalk(path=list(path), goal=tuple(goal), follow_up=follow_up,
                    announce=len(path) > 1, session=session)

    if not walk.path:
        _arrive(character, walk)
        return

    set_walk(character, walk)


def _arrive(character, walk) -> None:
    """End a walk at its goal, and run its follow-up line."""
    set_walk(character, None)

    if walk.shown and walk.announce:
        character.msg(const.MSG_ARRIVED)

    if walk.follow_up:
        character.execute_cmd(walk.follow_up, session=walk.session)


def _hops(here, tiles: list) -> list:
    """
    Return the direction of each one-tile hop from `here` along `tiles`. The
    list stops at the first tile that is not next to the one before it.
    """
    directions = []
    at = here

    for tile in tiles:
        direction = tile_travel.direction_between(at, tile) if at else None

        if direction is None:
            break

        directions.append(direction)
        at = tile

    return directions


def advance(character) -> None:
    """
    Purpose: Move one walker for one tick.

    Entry:
        character - a character with a walk.

    Exit/Returns:
        None.

    Module Globals:
        None.

    Methodology:
        1. Take the next tiles of the path: one, or two with run on.
        2. Stop if the path does not start next to the walker.
        3. Move along them in one stride. A refused first hop stops the
           walk, and the player reads why.
        4. Stop if the walker did not land on the path, for example after a
           transition.
        5. Drop the tiles walked. An empty path arrives.

    Notes/References:
        The module docstring, "The run and the tile skip".

    Author: Nick Hobar
    Creation date: 09/29/2026
    """
    walk = current(character)

    if walk is None or not walk.path:
        _WALKERS.pop(character.id, None)
        return

    here = tile_travel.tile_of(character)
    directions = _hops(here, walk.path[:tiles_per_tick(character)])

    if not directions:
        set_walk(character, None)
        character.msg(const.MSG_WALK_BROKEN)
        return

    result, hops = tile_travel.stride(character, directions)

    if hops == 0:
        set_walk(character, None)
        refuse(character, here, directions[0], result)
        return

    setattr(character.ndb, const.REFUSAL_NDB_ATTR, None)

    if tile_travel.tile_of(character) != walk.path[hops - 1]:
        set_walk(character, None)
        return

    del walk.path[:hops]

    if not walk.path:
        _arrive(character, walk)


def advance_all() -> None:
    """
    Move every walker for one tick. The PHASE_START hook of the tick. A
    walker that raises loses its walk, and the other walkers still move.
    """
    for character_id, character in list(_WALKERS.items()):
        try:
            advance(character)
        except Exception:
            logger.log_trace("walk of #%s failed" % character_id)
            _WALKERS.pop(character_id, None)
            setattr(character.ndb, const.WALK_NDB_ATTR, None)


def walker_count() -> int:
    """Return the number of characters with a walk."""
    return len(_WALKERS)


def forget_all() -> None:
    """Drop every walker. For a test teardown only."""
    _WALKERS.clear()


register_phase_hook(PHASE_START, advance_all)
