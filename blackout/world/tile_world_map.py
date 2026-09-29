"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/28/2026
Description: The world map of a telnet player: one plane of the tile world,
             drawn small, as text.

Why a second text map
---------------------
The Godot client draws the world map from the world map feed. A session that
does not subscribe to it, telnet included, gets this text from the `worldmap`
command. The pop-ups make the same split (`service.wants_popup`).

The layout
----------
One glyph stands for a square of OVERVIEW_BLOCK x OVERVIEW_BLOCK tiles. The
glyphs are those of the tile map (world/tile_map.py), so a telnet player
learns one set:

| Glyph | Square |
|---|---|
| `@` | the square of the player |
| a category glyph | a square with a placed object that is not an NPC or a sign |
| `.` | most tiles are walkable ground |
| `~` | most tiles are water |
| ` ` | most tiles are blocked, void, or off the loaded world |

North is up. The map covers the rectangle of every loaded chunk of the plane.
"""

from systems.core.tilegrid import constants as tile_const
from world import tile_map
from world.object_kinds import OBJECT_KINDS


# ─── Public constant definitions ─────────────────────────────────────────────

# The tiles along one side of the square that one glyph stands for.
OVERVIEW_BLOCK: int = 8


# ─── Private constant definitions ────────────────────────────────────────────

# The object categories that the overview draws. An NPC moves, and a sign
# says nothing at this size.
_DRAWN_CATEGORIES: tuple = (
    tile_const.OBJECT_CATEGORY_FACILITY,
    tile_const.OBJECT_CATEGORY_LANDMARK,
    tile_const.OBJECT_CATEGORY_TRANSITION,
    tile_const.OBJECT_CATEGORY_CLIMB,
    tile_const.OBJECT_CATEGORY_GATHERING,
)


# ─── Private helper routines ─────────────────────────────────────────────────

def _bounds(tile_plane) -> tuple:
    """Return (low_x, low_y, high_x, high_y) of the loaded tiles of a plane."""
    size = tile_const.CHUNK_SIZE
    keys = tile_plane.chunk_keys()
    low_x = min(cx for cx, _cy in keys) * size
    low_y = min(cy for _cx, cy in keys) * size
    high_x = (max(cx for cx, _cy in keys) + 1) * size - 1
    high_y = (max(cy for _cx, cy in keys) + 1) * size - 1

    return low_x, low_y, high_x, high_y


def _object_squares(tile_plane) -> dict:
    """Return (square x, square y) -> the glyph of its first drawn object."""
    squares = {}

    for kind_key, x, y, _rotation in tile_plane.placed_objects():
        kind = OBJECT_KINDS.get(kind_key)

        if kind is None or kind.category not in _DRAWN_CATEGORIES:
            continue

        square = (x // OVERVIEW_BLOCK, y // OVERVIEW_BLOCK)
        glyph = tile_map.CATEGORY_GLYPHS.get(kind.category,
                                             tile_map.UNKNOWN_OBJECT_GLYPH)
        squares.setdefault(square, glyph)

    return squares


def _ground_glyph(tile_plane, square_x: int, square_y: int) -> str:
    """Return the glyph of the tiles that most of one square holds."""
    counts = {tile_map.GROUND_GLYPH: 0, tile_map.WATER_GLYPH: 0,
              tile_map.VOID_GLYPH: 0}
    low_x = square_x * OVERVIEW_BLOCK
    low_y = square_y * OVERVIEW_BLOCK

    for y in range(low_y, low_y + OVERVIEW_BLOCK):
        for x in range(low_x, low_x + OVERVIEW_BLOCK):
            counts[_tile_class_glyph(tile_plane, x, y)] += 1

    # The first of the largest counts, in the order ground, water, void.
    return max(counts, key=counts.get)


def _tile_class_glyph(tile_plane, x: int, y: int) -> str:
    """Return ground, water, or void for one tile."""
    if not tile_plane.has_tile(x, y):
        return tile_map.VOID_GLYPH

    flags = tile_plane.grid.flags_at(x, y)

    if flags & tile_const.FLAG_BLOCKED:
        return tile_map.VOID_GLYPH

    if flags & tile_const.FLAG_WATER:
        return tile_map.WATER_GLYPH

    return tile_map.GROUND_GLYPH


# ─── Public routines ─────────────────────────────────────────────────────────

def render_overview(tile_plane, looker_tile) -> str:
    """
    Purpose: Draw one plane of the tile world as text. One glyph stands for
             one square of tiles.

    Entry:
        tile_plane  - a tilegrid.world.TilePlane.
        looker_tile - the (x, y) of the player, or None to draw no `@`.

    Exit/Returns:
        The map, one line for each row of squares, north first. Trailing
        spaces are cut. "" for a plane with no loaded chunk.

    Module Globals:
        OVERVIEW_BLOCK and _DRAWN_CATEGORIES read.

    Methodology:
        The layout in the module docstring. The looker wins over an object,
        and an object wins over the ground.

    Notes/References:
        commands/world_map_cmds.py sends the result.

    Author: Nick Hobar
    Creation date: 09/28/2026
    """
    if not tile_plane.has_chunks():
        return ""

    low_x, low_y, high_x, high_y = _bounds(tile_plane)
    objects = _object_squares(tile_plane)
    looker_square = None

    if looker_tile is not None:
        looker_square = (looker_tile[0] // OVERVIEW_BLOCK,
                         looker_tile[1] // OVERVIEW_BLOCK)

    columns = range(low_x // OVERVIEW_BLOCK, high_x // OVERVIEW_BLOCK + 1)
    lines = []

    for square_y in range(high_y // OVERVIEW_BLOCK,
                          low_y // OVERVIEW_BLOCK - 1, -1):
        row = []

        for square_x in columns:
            square = (square_x, square_y)

            if square == looker_square:
                row.append(tile_map.LOOKER_GLYPH)
            elif square in objects:
                row.append(objects[square])
            else:
                row.append(_ground_glyph(tile_plane, square_x, square_y))

        lines.append("".join(row).rstrip())

    return "\n".join(lines)
