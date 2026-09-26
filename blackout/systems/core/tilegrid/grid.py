"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The tile grid in memory: corner heights, floor types, and walk
             flags for each loaded chunk, and the one rule that says whether a
             step between two tiles is legal.

Why flat lists of ints
----------------------
A step check and a path search read a few flags for each tile they touch, and
the search touches thousands. A Python list index is the cheapest read that
Python has. A NumPy array is slower for one element at a time, and the search
reads one element at a time. A 64 x 64 chunk is 12,417 ints in three lists.

Why heights are integers
------------------------
DESIGN-0011 section 6.4. The Python server and the GDScript client must get
the same slope and the same tile height. Two float pipelines give two answers.

The tile height
---------------
The height of a tile, for gameplay, is the LOWEST of its four corners. This is
the one function that says so. The client uses the same rule (Phase 5).

Coordinates are global
----------------------
A chunk is a unit of storage, not a wall. Tile (x, y) is in chunk
(x // CHUNK_SIZE, y // CHUNK_SIZE), and floor division puts a negative x in the
right chunk too. Y grows to the north.
"""

from dataclasses import dataclass, field

from . import constants as const


# ─── Private helper routines ─────────────────────────────────────────────────

def _filled(count: int, value: int) -> list:
    """Return a new list of `count` copies of `value`."""
    return [value] * count


# ─── Public routines / Classes ───────────────────────────────────────────────

@dataclass
class Chunk:
    """
    One 64 x 64 part of the tile grid, as three flat lists.

    `heights` holds CORNERS_PER_SIDE rows of CORNERS_PER_SIDE corners, row 0 at
    the south edge. `floors` and `flags` hold CHUNK_SIZE rows of CHUNK_SIZE
    tiles. The index of local tile (lx, ly) is `ly * CHUNK_SIZE + lx`.

    A chunk holds its own north and east edge corners, so a tile never reads
    a neighbour chunk. The same corner thus sits in two chunks. The editor
    (Phase 3) must write the same value to both.
    """

    cx: int
    cy: int
    heights: list = field(default_factory=lambda: _filled(
        const.CORNERS_PER_SIDE * const.CORNERS_PER_SIDE, const.DEFAULT_HEIGHT))
    floors: list = field(default_factory=lambda: _filled(
        const.CHUNK_SIZE * const.CHUNK_SIZE, const.DEFAULT_FLOOR))
    flags: list = field(default_factory=lambda: _filled(
        const.CHUNK_SIZE * const.CHUNK_SIZE, const.FLAG_NONE))

    def __post_init__(self):
        """Refuse a chunk whose lists do not have the chunk shape."""
        corner_count = const.CORNERS_PER_SIDE * const.CORNERS_PER_SIDE
        tile_count = const.CHUNK_SIZE * const.CHUNK_SIZE

        if len(self.heights) != corner_count:
            raise ValueError("a chunk needs %d corner heights, not %d"
                             % (corner_count, len(self.heights)))

        if len(self.floors) != tile_count or len(self.flags) != tile_count:
            raise ValueError("a chunk needs %d floors and %d flags"
                             % (tile_count, tile_count))


class TileGrid:
    """
    Every loaded chunk, looked up by global tile coordinates.

    The grid holds no Evennia object. `rooms.TileRooms` owns the rooms. Thus,
    this class is testable with no database, and the path search runs on it
    with no query.
    """

    def __init__(self):
        self._chunks = {}

    def add_chunk(self, chunk: Chunk) -> None:
        """Load one chunk. A chunk at the same coordinates is replaced."""
        self._chunks[(chunk.cx, chunk.cy)] = chunk

    def chunk_count(self) -> int:
        """Return how many chunks are loaded."""
        return len(self._chunks)

    def has_tile(self, x: int, y: int) -> bool:
        """Return True if a loaded chunk holds tile (x, y)."""
        chunk_key = (x // const.CHUNK_SIZE, y // const.CHUNK_SIZE)

        return chunk_key in self._chunks

    def flags_at(self, x: int, y: int) -> int:
        """
        Purpose: Return the walk flags of one tile.

        Entry:
            (x, y) - global tile coordinates.

        Exit/Returns:
            The flag bits of the tile. A tile off the loaded grid returns
            FLAG_BLOCKED, so no caller can walk off the edge of the world.

        Module Globals:
            const.CHUNK_SIZE read.

        Notes/References:
            The path search calls this for each neighbour of each tile it
            expands. Keep it to one dict read and one list read.

        Author: Nick Hobar
        Creation date: 09/24/2026
        """
        size = const.CHUNK_SIZE
        chunk = self._chunks.get((x // size, y // size))

        if chunk is None:
            return const.FLAG_BLOCKED

        index = (y % size) * size + (x % size)

        return chunk.flags[index]

    def corner_heights(self, x: int, y: int) -> tuple:
        """
        Purpose: Return the four corner heights of one tile.

        Entry:
            (x, y) - global tile coordinates of a loaded tile.

        Exit/Returns:
            (southwest, southeast, northwest, northeast), in height steps.

        Module Globals:
            const.CHUNK_SIZE, const.CORNERS_PER_SIDE read.

        Notes/References:
            Raises KeyError for a tile off the loaded grid. A height of the
            void has no honest value.

        Author: Nick Hobar
        Creation date: 09/24/2026
        """
        size = const.CHUNK_SIZE
        side = const.CORNERS_PER_SIDE
        chunk = self._chunks[(x // size, y // size)]
        south = (y % size) * side + (x % size)
        north = south + side
        heights = chunk.heights

        return (heights[south], heights[south + 1],
                heights[north], heights[north + 1])

    def tile_height(self, x: int, y: int) -> int:
        """Return the gameplay height of a tile: its lowest corner."""
        corners = self.corner_heights(x, y)
        lowest = min(corners)

        return lowest

    def floor_at(self, x: int, y: int) -> int:
        """Return the floor type index of one loaded tile."""
        size = const.CHUNK_SIZE
        chunk = self._chunks[(x // size, y // size)]

        return chunk.floors[(y % size) * size + (x % size)]

    def check_step(self, start: tuple, end: tuple,
                   walk_limit=const.WALK_LIMIT) -> str:
        """
        Purpose: Say whether one step from `start` to `end` is legal, and why
                 not if it is not.

        Entry:
            start, end - (x, y) global tile coordinates.
            walk_limit - the largest height change of one step, or None for
                         no height rule.

        Exit/Returns:
            One of the const.STEP_* results. STEP_OK means the step is legal.

        Module Globals:
            const.STEP_*, const.FLAGS_UNWALKABLE read.

        Methodology:
            1. Refuse a step that is not to one of the eight neighbours.
            2. Refuse a tile off the grid, blocked, or water.
            3. Refuse a cardinal step across a wall on either side.
            4. Refuse a diagonal step if either cardinal step around the corner
               is refused. This is the OSRS rule: no corner cutting.
            5. Refuse a height change above the walk limit.

        Notes/References:
            DESIGN-0011 section 6.1, step 2.

        Author: Nick Hobar
        Creation date: 09/24/2026
        """
        dx = end[0] - start[0]
        dy = end[1] - start[1]

        if (dx, dy) == (0, 0) or abs(dx) > 1 or abs(dy) > 1:
            return const.STEP_NOT_ADJACENT

        result = self._check_entry(end)

        if result != const.STEP_OK:
            return result

        if dx != 0 and dy != 0:
            result = self._check_corner(start, dx, dy)
        else:
            result = self._check_edge(start, end, (dx, dy))

        if result != const.STEP_OK:
            return result

        return self._check_slope(start, end, walk_limit)

    def _check_entry(self, end: tuple) -> str:
        """Refuse a target tile that holds no player."""
        if not self.has_tile(end[0], end[1]):
            return const.STEP_OFF_GRID

        target_flags = self.flags_at(end[0], end[1])

        if target_flags & const.FLAGS_UNWALKABLE:
            return const.STEP_BLOCKED

        return const.STEP_OK

    def _check_edge(self, start: tuple, end: tuple, offset: tuple) -> str:
        """Refuse a cardinal step across a wall on either side of the edge."""
        leaving = self.flags_at(start[0], start[1])
        entering = self.flags_at(end[0], end[1])

        if leaving & const.EDGE_WALL_LEAVING[offset]:
            return const.STEP_WALL

        if entering & const.EDGE_WALL_ENTERING[offset]:
            return const.STEP_WALL

        return const.STEP_OK

    def _check_corner(self, start: tuple, dx: int, dy: int) -> str:
        """
        Refuse a diagonal step unless both L-shaped legs are legal. A leg goes
        from the start to a side tile, then from the side tile to the target.
        """
        end = (start[0] + dx, start[1] + dy)
        across = (start[0] + dx, start[1])
        along = (start[0], start[1] + dy)

        for side in (across, along):
            if not self._is_open_leg(start, side, end):
                return const.STEP_CORNER

        return const.STEP_OK

    def _is_open_leg(self, start: tuple, side: tuple, end: tuple) -> bool:
        """Return True if start -> side -> end crosses no wall and no block."""
        entry = self._check_entry(side)

        if entry != const.STEP_OK:
            return False

        first_offset = (side[0] - start[0], side[1] - start[1])
        second_offset = (end[0] - side[0], end[1] - side[1])
        first = self._check_edge(start, side, first_offset)
        second = self._check_edge(side, end, second_offset)

        return first == const.STEP_OK and second == const.STEP_OK

    def _check_slope(self, start: tuple, end: tuple, walk_limit) -> str:
        """Refuse a height change above the walk limit."""
        if walk_limit is None:
            return const.STEP_OK

        rise = self.tile_height(end[0], end[1]) - self.tile_height(
            start[0], start[1])

        if abs(rise) > walk_limit:
            return const.STEP_TOO_STEEP

        return const.STEP_OK
