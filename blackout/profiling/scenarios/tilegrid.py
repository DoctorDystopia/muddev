"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The DESIGN-0011 Phase 1 spike: what a step costs when a room
             exists only where something stands.

The question
------------
DESIGN-0011 section 6.1 picks option B: one tile grid for the whole world, and
an Evennia room only at a tile that holds a thing. A step onto an empty tile
then needs a room at that tile. This module times that step three ways, beside
the xyzgrid step that the game takes today:

| Row | The room at the next tile |
|---|---|
| xyzgrid baseline | Already exists, as every xyzgrid tile does |
| no pool | Made new. The room behind is deleted |
| pooled | Taken from the pool. The room behind goes back to the pool |
| both tiles held | Already exists, because an item holds each tile |

Each pass is a round trip, east and back, so each pass is two steps and the
world ends each pass as it started. Divide a row by two for one step.

It also times the two reads that replace xyzgrid tables: the neighbourhood of a
tile (`TileRooms.rooms_near`, beside `_visible_rooms` in crowd.py) and a `goto`
path (`find_path`, beside the all-pairs table that section 5 measured).

Why the mover is a plain Object
-------------------------------
A step does not care what moves, and a Character has no session here to send
to. The baseline mover is a plain Object too, so the rows differ only in the
room model.

Where it stands
---------------
The tile rooms are on `WORLD_Z`, not on the fixture map, so no other scenario
walks them. The baseline mover stands in the far corner (12, 0) of the fixture.
Radius 3 around the centre covers 3..9, and the crowd stands at (0, 12).
"""

import random

from evennia.utils.create import create_object

from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.grid import Chunk, TileGrid
from systems.core.tilegrid.pathfind import find_path
from systems.core.tilegrid.rooms import TileRooms
from typeclasses.objects import Object

from .. import constants as const
from ..world_fixture import FIXTURE_WIDTH
from . import scenario


# ─── Private constant definitions ────────────────────────────────────────────

# Passes for a round trip. A pass is two steps.
_STEP_REPEAT = 50

# Passes for the reads, which are cheaper.
_READ_REPEAT = 200

# Passes for a path search.
_PATH_REPEAT = 20

# The tile that each stepping mover starts on, well inside chunk (0, 0).
_TILE_START = (30, 30)

# Where the baseline mover stands on the fixture map: the far corner on the
# y = 0 row, outside every radius-3 scenario.
_BASELINE_HOME = (FIXTURE_WIDTH - 1, 0)
_BASELINE_NEIGHBOUR = (FIXTURE_WIDTH - 2, 0)

# Live rooms for the neighbourhood read. A busy chunk: players, drops,
# facilities and NPC spawns, spread over the whole chunk.
_LIVE_ROOMS = 200

# The production statefeed radius, the same number crowd.py measures.
_NEIGHBOURHOOD_RADIUS = 10

# The share of tiles blocked in the path chunk, and the seed of the layout.
# A fixed seed gives the same maze on every run, so two runs compare.
_BLOCKED_SHARE = 0.2
_MAZE_SEED = 11

# The chunks of the long path case: a 3 x 3 block, which is the client's
# streaming block in DESIGN-0011 section 6.6.
_BLOCK_SIDE = 3


# ─── Private helper routines ─────────────────────────────────────────────────

def _open_grid(side: int = 1) -> TileGrid:
    """Return a grid of `side` x `side` open, flat chunks from (0, 0)."""
    grid = TileGrid()

    for cx in range(side):
        for cy in range(side):
            grid.add_chunk(Chunk(cx, cy))

    return grid


def _maze_grid(side: int, keep_open: tuple) -> TileGrid:
    """
    Return a grid with a seeded share of blocked tiles. The tiles in
    `keep_open` stay open, so the start and the goal can hold a player.
    """
    grid = _open_grid(side)
    rng = random.Random(_MAZE_SEED)
    size = tile_const.CHUNK_SIZE

    for cx in range(side):
        for cy in range(side):
            chunk = grid._chunks[(cx, cy)]

            for index in range(size * size):
                if rng.random() < _BLOCKED_SHARE:
                    chunk.flags[index] = tile_const.FLAG_BLOCKED

            for x, y in keep_open:
                if (x // size, y // size) == (cx, cy):
                    chunk.flags[(y % size) * size + (x % size)] = 0

    return grid


def _mover(rooms: TileRooms, key: str):
    """Return a new Object standing on _TILE_START in `rooms`."""
    mover = create_object(Object, key=key)
    movement.place(rooms, mover, *_TILE_START, quiet=True)

    return mover


def _round_trip(grid, rooms, mover):
    """Return the measured work: one step east and one step back."""
    def work():
        movement.step(grid, rooms, mover, "east", quiet=True)
        movement.step(grid, rooms, mover, "west", quiet=True)

    return work


# ─── Public routines ─────────────────────────────────────────────────────────

@scenario(name="tilegrid: xyzgrid step, round trip (baseline)",
          layer=const.LAYER_ENGINE,
          repeat=_STEP_REPEAT,
          notes="Two move_to calls between two existing GridTiles. What a "
                "step costs today, to read the three rows below against.")
def xyzgrid_step_baseline(world):
    """Measure a round trip between two xyzgrid tiles."""
    home = world.tiles[_BASELINE_HOME]
    neighbour = world.tiles[_BASELINE_NEIGHBOUR]
    mover = create_object(Object, key="baseline mover", location=home)

    def work():
        mover.move_to(neighbour, quiet=True, move_type="move")
        mover.move_to(home, quiet=True, move_type="move")

    return work


@scenario(name="tilegrid: step onto empty tile, no pool",
          layer=const.LAYER_ENGINE,
          repeat=_STEP_REPEAT,
          notes="Two steps. Each makes a new TileRoom and deletes the room "
                "behind. The cost of option B with no pool.")
def step_without_pool(world):
    """Measure a round trip that makes and deletes a room on each step."""
    grid = _open_grid()
    rooms = TileRooms(world_z=tile_const.WORLD_Z + "_nopool", pool_capacity=0)
    mover = _mover(rooms, "unpooled mover")

    return _round_trip(grid, rooms, mover)


@scenario(name="tilegrid: step onto empty tile, pooled",
          layer=const.LAYER_ENGINE,
          repeat=_STEP_REPEAT,
          notes="Two steps. Each moves a pooled room to the next tile by "
                "retagging it, and pools the room behind.")
def step_with_pool(world):
    """Measure a round trip that reuses pooled rooms."""
    grid = _open_grid()
    rooms = TileRooms(world_z=tile_const.WORLD_Z + "_pool")
    mover = _mover(rooms, "pooled mover")

    return _round_trip(grid, rooms, mover)


@scenario(name="tilegrid: step between held tiles",
          layer=const.LAYER_ENGINE,
          repeat=_STEP_REPEAT,
          notes="Two steps. An item holds each tile, so both rooms exist and "
                "neither is released. The floor under the two rows above.")
def step_between_held_tiles(world):
    """Measure a round trip where no room is made or given back."""
    grid = _open_grid()
    rooms = TileRooms(world_z=tile_const.WORLD_Z + "_held")
    mover = _mover(rooms, "held-tile mover")
    east = (_TILE_START[0] + 1, _TILE_START[1])

    for x, y in (_TILE_START, east):
        movement.place(rooms, create_object(Object, key="holder"), x, y,
                       quiet=True)

    return _round_trip(grid, rooms, mover)


@scenario(name="tilegrid: rooms_near radius 10, 200 live rooms",
          layer=const.LAYER_ENGINE,
          repeat=_READ_REPEAT,
          notes="The tile grid's neighbourhood read. A dict walk, no query. "
                "Compare with '_visible_rooms at production radius 10'.")
def rooms_near_production(world):
    """Measure the neighbourhood read over a busy chunk."""
    rooms = TileRooms(world_z=tile_const.WORLD_Z + "_near")
    rng = random.Random(_MAZE_SEED)
    size = tile_const.CHUNK_SIZE

    while rooms.live_count() < _LIVE_ROOMS:
        rooms.ensure_room(rng.randrange(size), rng.randrange(size))

    def work():
        rooms.rooms_near(_TILE_START[0], _TILE_START[1], _NEIGHBOURHOOD_RADIUS)

    return work


@scenario(name="tilegrid: A* across one chunk, 20% blocked",
          layer=const.LAYER_ENGINE,
          repeat=_PATH_REPEAT,
          notes="Corner to corner of a 64 x 64 chunk through a seeded maze. "
                "The xyzgrid holds a 320 MiB table for this instead.")
def path_across_chunk(world):
    """Measure one long goto path inside a chunk."""
    last = tile_const.CHUNK_SIZE - 1
    start, goal = (0, 0), (last, last)
    grid = _maze_grid(1, (start, goal))

    if find_path(grid, start, goal) is None:
        raise RuntimeError("the seeded maze has no path; change _MAZE_SEED")

    def work():
        find_path(grid, start, goal)

    return work


@scenario(name="tilegrid: A* across a 3 x 3 chunk block, 20% blocked",
          layer=const.LAYER_ENGINE,
          repeat=_PATH_REPEAT,
          notes="Corner to corner of 192 x 192 tiles, across chunk edges. "
                "The PATH_MAX_EXPANDED limit may stop it; see the notes row.")
def path_across_block(world):
    """Measure a path across the whole streaming block."""
    last = _BLOCK_SIDE * tile_const.CHUNK_SIZE - 1
    start, goal = (0, 0), (last, last)
    grid = _maze_grid(_BLOCK_SIDE, (start, goal))

    def work():
        find_path(grid, start, goal)

    return work


@scenario(name="tilegrid: A* to a walled-off goal (worst case)",
          layer=const.LAYER_ENGINE,
          repeat=_PATH_REPEAT,
          notes="The goal is boxed in, so the search expands every reachable "
                "tile up to PATH_MAX_EXPANDED and returns None.")
def path_to_unreachable(world):
    """Measure the search that a click on a sealed tile costs."""
    grid = _open_grid(_BLOCK_SIDE)
    goal = (100, 100)
    size = tile_const.CHUNK_SIZE

    for dx, dy in tile_const.DIRECTION_OFFSETS.values():
        x, y = goal[0] + dx, goal[1] + dy
        chunk = grid._chunks[(x // size, y // size)]
        chunk.flags[(y % size) * size + (x % size)] = tile_const.FLAG_BLOCKED

    def work():
        find_path(grid, (0, 0), goal)

    return work
