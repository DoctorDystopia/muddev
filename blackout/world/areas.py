"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The areas of the tile grid, one row for each area.

             An area is a named part of the world. A chunk file stores an
             index into its own `area_names` list, and every name in that list
             must be a key here. The Godot editor paints from this list,
             through the generated constants.

             The client picks the fog and the light of a tile by its area:
             `LOOKS` in `godot/world/area_look.gd`. An area with no row there
             gets the fallback look, so a new area needs no client edit.

             Until Phase 4 moves the live maps into chunk files, each area has
             the name of the map that it replaces. DESIGN-0011 sections 6.2
             and 6.7.

             A tile room stores no name and no description. On a tile with no
             named object, `look` shows the `name` and the `desc` of the area.
             `world/tile_text.py` owns that rule. The texts here are the
             default room texts of the xyzgrid maps.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Area:
    """
    One area. The `key` is the name that a chunk file stores. The `note`
    tells an author what the area is, and no player sees it. The `name` and
    the `desc` are the room texts of a plain tile of the area.
    """

    key: str
    note: str
    name: str
    desc: str


# The first row is the area of a new chunk.
_AREA_ROWS: tuple = (
    Area("oasis", "The Oasis settlement: the bank, the forges, the stalls.",
         "Oasis", "sand...everywhere."),
    Area("oasis_outskirts", "The dunes around the Oasis.",
         "Oasis Outskirts", "sand...everywhere."),
    Area("azm_plains", "The Azm plains.",
         "Azm Plains", "sand...everywhere."),
)

# key -> Area, in the order of _AREA_ROWS.
AREAS: dict = {row.key: row for row in _AREA_ROWS}

# The area of a new chunk.
DEFAULT_AREA: str = _AREA_ROWS[0].key
