"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The ASCII map of the tile world, for a telnet player.

Why a new renderer
------------------
The xyzgrid contrib draws its map from the map string of each map. The tile
world has no map string, so the xyzgrid map cannot draw it. Nick chose a small
renderer for Phase 4a on 09/24/2026 (DESIGN-0011 section 8, question 5).

The layout
----------
Each tile takes one character, and a gap column and a gap row sit between
tiles. A wall shows in the gap: `|` between two columns, `-` between two
rows. A window of radius 6 is thus 25 characters wide, the same as the
xyzgrid map at its range of 6 today. North is up.

| Glyph | Tile |
|---|---|
| `@` | the looker |
| `!` | a tile where an NPC stands now |
| a category glyph | a tile with a placed object that is not an NPC |
| `.` | walkable ground |
| `~` | water |
| ` ` | blocked, or off the loaded world |

The object glyphs come from `CATEGORY_GLYPHS`, one for each category. A new
category with no row draws `*`. A category of `SILENT_CATEGORIES` draws no
glyph: decor is a look, and the tile shows what is under it.

The aura tint
-------------
A looker with a burning damage aura sees the tiles of its reach in the aura
colour. The caller gives the radius and the metric. `TileRoom` passes
`targeting.within_metric`, the predicate of the damage path, so the tint
cannot differ from the tiles that take damage. A void tile and the looker's
own tile get no tint. This replaces the xyzgrid overlay of 08/03/2026
(`auras/map_overlay.py`), Phase 4b.
"""

from systems.core.tilegrid import constants as tile_const
from systems.interface.statefeed.constants import ASSET_KIND_NPC
from systems.interface.statefeed.serializers import entity_kind
from systems.interface.ui.colors import TAG_AURA_TILE, TAG_RESET
from world.object_kinds import OBJECT_KINDS


# ─── Public constant definitions ─────────────────────────────────────────────

# The glyphs of a tile. Public, because the world map overview of a telnet
# player (world/tile_world_map.py) draws with the same glyphs.
LOOKER_GLYPH = "@"
GROUND_GLYPH = "."
WATER_GLYPH = "~"
VOID_GLYPH = " "
UNKNOWN_OBJECT_GLYPH = "*"

# One glyph for each object category.
CATEGORY_GLYPHS: dict = {
    tile_const.OBJECT_CATEGORY_FACILITY: "F",
    tile_const.OBJECT_CATEGORY_GATHERING: "†",
    tile_const.OBJECT_CATEGORY_LANDMARK: "+",
    tile_const.OBJECT_CATEGORY_NPC: "!",
    tile_const.OBJECT_CATEGORY_SIGN: "?",
    tile_const.OBJECT_CATEGORY_TRANSITION: "T",
    tile_const.OBJECT_CATEGORY_CLIMB: "H",
}

# The categories that draw no glyph. A crate or a table is a look, as a floor
# colour is, and the telnet map draws no look.
SILENT_CATEGORIES: tuple = (tile_const.OBJECT_CATEGORY_DECOR,)

# The default radius of the window, in tiles.
MAP_RADIUS: int = 6


# ─── Private constant definitions ────────────────────────────────────────────

_WALL_BETWEEN_COLUMNS = "|"
_WALL_BETWEEN_ROWS = "-"
_OPEN_GAP = " "


# ─── Private helper routines ─────────────────────────────────────────────────

def _object_glyph(world, x: int, y: int):
    """
    Return the glyph of the first placed object on a tile, or None. An NPC
    kind draws nothing here: `_live_npc_tiles` draws each NPC where it stands.
    A kind of SILENT_CATEGORIES draws nothing anywhere.
    """
    for key in world.kinds_at(x, y):
        kind = OBJECT_KINDS.get(key)

        if kind is None or kind.category == tile_const.OBJECT_CATEGORY_NPC \
                or kind.category in SILENT_CATEGORIES:
            continue

        return CATEGORY_GLYPHS.get(kind.category, UNKNOWN_OBJECT_GLYPH)

    return None


def _live_npc_tiles(world, center: tuple, radius: int) -> set:
    """
    Return each tile inside the window where an NPC stands now. The room
    index answers with no query, and `entity_kind` decides what an NPC is.
    """
    npc_tiles = set()
    rooms = world.rooms.rooms_near(center[0], center[1], radius)

    for room in rooms:
        if any(entity_kind(obj) == ASSET_KIND_NPC for obj in room.contents):
            x, y, _z = room.xyz
            npc_tiles.add((int(x), int(y)))

    return npc_tiles


def _tile_glyph(world, x: int, y: int, looker_tile: tuple,
                npc_tiles=frozenset()) -> str:
    """Return the one character of a tile."""
    if (x, y) == looker_tile:
        return LOOKER_GLYPH

    flags = world.grid.flags_at(x, y)

    if flags & tile_const.FLAG_BLOCKED:
        return VOID_GLYPH

    if (x, y) in npc_tiles:
        return CATEGORY_GLYPHS[tile_const.OBJECT_CATEGORY_NPC]

    object_glyph = _object_glyph(world, x, y)

    if object_glyph is not None:
        return object_glyph

    if flags & tile_const.FLAG_WATER:
        return WATER_GLYPH

    return GROUND_GLYPH


def _walled(world, here: tuple, there: tuple) -> bool:
    """Return True if a wall sits on the edge between two open tiles."""
    offset = (there[0] - here[0], there[1] - here[1])
    here_flags = world.grid.flags_at(*here)
    there_flags = world.grid.flags_at(*there)

    if (here_flags | there_flags) & tile_const.FLAG_BLOCKED:
        return False

    leaving = here_flags & tile_const.EDGE_WALL_LEAVING[offset]
    entering = there_flags & tile_const.EDGE_WALL_ENTERING[offset]

    return bool(leaving or entering)


def _tinted(glyph: str, offset: tuple, aura) -> str:
    """
    Return a glyph in the aura colour if its tile is inside the aura. `aura`
    is (radius, metric) or None. The looker and a void tile stay plain.
    """
    if aura is None or glyph == VOID_GLYPH or offset == (0, 0):
        return glyph

    radius, metric = aura

    if not metric(offset[0], offset[1], radius):
        return glyph

    return f"{TAG_AURA_TILE}{glyph}{TAG_RESET}"


def _tile_line(world, y: int, columns: range, looker_tile: tuple,
               aura=None, npc_tiles=frozenset()) -> str:
    """Return the text line of one row of tiles, with its column gaps."""
    parts = []

    for x in columns:
        glyph = _tile_glyph(world, x, y, looker_tile, npc_tiles)
        offset = (x - looker_tile[0], y - looker_tile[1])
        parts.append(_tinted(glyph, offset, aura))

        if x != columns[-1]:
            wall = _walled(world, (x, y), (x + 1, y))
            parts.append(_WALL_BETWEEN_COLUMNS if wall else _OPEN_GAP)

    return "".join(parts)


def _gap_line(world, y: int, columns: range) -> str:
    """Return the text line between row y and the row south of it."""
    parts = []

    for x in columns:
        wall = _walled(world, (x, y), (x, y - 1))
        parts.append(_WALL_BETWEEN_ROWS if wall else _OPEN_GAP)

        if x != columns[-1]:
            parts.append(_OPEN_GAP)

    return "".join(parts)


# ─── Public routines ─────────────────────────────────────────────────────────

def render(world, center: tuple, radius: int = MAP_RADIUS,
           aura_radius: int = 0, aura_metric=None) -> str:
    """
    Purpose: Draw the tiles around a looker as text.

    Entry:
        world       - a TileWorld.
        center      - the (x, y) tile of the looker.
        radius      - the tiles to draw on each side of the center.
        aura_radius - the radius of the looker's aura. 0 draws no tint.
        aura_metric - `(dx, dy, radius) -> bool`, the reach of the aura.
                      None draws no tint.

    Exit/Returns:
        The map, one line for each row, north first. Trailing spaces are cut.

    Module Globals:
        The glyph constants of this module read.

    Methodology:
        The layout and the tint in the module docstring. A tile off the
        loaded world reads as blocked (`TileGrid.flags_at`), so the edge of
        the world draws as void. An NPC draws on the tile where it stands
        now, not on its spawn tile (handoff debt 14).

    Notes/References:
        `TileRoom.return_appearance` sends the result.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    cx, cy = center
    columns = range(cx - radius, cx + radius + 1)
    npc_tiles = _live_npc_tiles(world, center, radius)
    aura = None
    lines = []

    if aura_radius > 0 and aura_metric is not None:
        aura = (aura_radius, aura_metric)

    for y in range(cy + radius, cy - radius - 1, -1):
        row = _tile_line(world, y, columns, center, aura, npc_tiles)
        lines.append(row.rstrip())

        if y != cy - radius:
            lines.append(_gap_line(world, y, columns).rstrip())

    return "\n".join(lines)
