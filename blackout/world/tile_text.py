"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The room name and the room description of a tile on the tile
             grid.

Why no room stores them
-----------------------
A tile room moves from tile to tile through the pool. A name in the room row
would thus cost a write on each move, and a stale name would follow the room
to its next tile. Nick chose a derived name on 09/24/2026. The chunk file says
what stands on a tile and which area it is in. This module turns those two
facts into text.

The rule
--------
1. The first object kind on the tile that has a `name` gives the name and
   the desc. The kinds come in chunk file order. A sign has no name, so a
   signed bank reads "Bank".
2. Else, the area of the tile gives them.
3. Else, the caller's fallback applies. A pooled room is not on the grid, and
   an unknown name in a chunk file is a test failure, not a crash.

This module imports only the two data tables, so a plain `unittest.TestCase`
tests it.
"""

from world.areas import AREAS
from world.object_kinds import OBJECT_KINDS


# ─── Private helper routines ─────────────────────────────────────────────────

def _naming_kind(kinds):
    """Return the first ObjectKind in `kinds` that has a name, or None."""
    for key in kinds:
        kind = OBJECT_KINDS.get(key)

        if kind is not None and kind.name:
            return kind

    return None


# ─── Public routines ─────────────────────────────────────────────────────────

def tile_name(kinds, area_key, fallback: str = "") -> str:
    """
    Purpose: Give the room name that a player sees on one tile.

    Entry:
        kinds    - the object kind keys on the tile, in chunk file order.
        area_key - the area of the tile, or None off the grid.
        fallback - the name to give when the rule finds none.

    Exit/Returns:
        A name. Never None.

    Module Globals:
        OBJECT_KINDS, AREAS read.

    Methodology:
        The rule in the module docstring.

    Notes/References:
        `TileRoom.get_display_name` calls this.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    kind = _naming_kind(kinds)

    if kind is not None:
        return kind.name

    area = AREAS.get(area_key)

    if area is not None:
        return area.name

    return fallback


def tile_desc(kinds, area_key) -> str:
    """
    Purpose: Give the room description that a player sees on one tile.

    Entry:
        kinds    - the object kind keys on the tile, in chunk file order.
        area_key - the area of the tile, or None off the grid.

    Exit/Returns:
        A description, or "" when the rule finds none. The caller then uses
        its own.

    Module Globals:
        OBJECT_KINDS, AREAS read.

    Methodology:
        The same kind as `tile_name` gives the text, so a name and its desc
        cannot come from two objects.

    Notes/References:
        `TileRoom.get_display_desc` calls this.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    kind = _naming_kind(kinds)

    if kind is not None:
        return kind.desc

    area = AREAS.get(area_key)

    if area is not None:
        return area.desc

    return ""
