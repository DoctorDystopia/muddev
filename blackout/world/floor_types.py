"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The floor types of the tile grid, one row for each type.

             A floor type is the named ground on a tile, for example `sand`.
             A chunk file stores an index into its own `floor_names` list, and
             every name in that list must be a key here. The Godot editor
             paints from this list.

             THE ROWS ARE DATA. They live in `world/tables/floor_types.json`
             (10/14/2026), and `world/table_file.py` reads them. The Tables
             tab of the terrain editor adds, edits, renames, and removes a
             row, and then runs the client export. The order counts: the
             world map sends the index of a floor type in this table.

             A floor type is a server fact. What it LOOKS like is the client's
             own: `godot/world/look/terrain_palette.json`, with
             `godot/world/terrain/floor_palette.gd` as its fallback, gives each
             name a colour. A name with no colour gets a hashed hue, so a new
             row needs no client edit.

             A floor type sets no walk rule. Water, walls, and blocked tiles
             are walk flags. Thus, a `water_bed` tile with no water flag is
             dry ground.

             THE VOID. `void` is "no floor here", for a tile of plane 1 and
             up that has nothing to stand on (Nick, 09/26/2026). The mesh
             builder draws no triangle on it, so the plane below shows
             through. It sets no walk rule either: the author sets Blocked
             with it, and `world/tile_checks.py` refuses a void tile with no
             Blocked flag. The editor sets both at once.

             ROOFS. A row with `roof` set is a roof floor type (DESIGN-0013
             section 6.2). A roof is the ground of the plane above a
             structure: the Roof tool of the editor shapes its corner heights
             and sets Blocked with it. `world/tile_checks.py` refuses a roof
             tile with no Blocked flag. The client draws no cliff colour on a
             roof, so a steep roof keeps its own colour.

             DESIGN-0011 sections 6.2 and 6.3.
"""

from dataclasses import dataclass

from world import table_file


@dataclass(frozen=True)
class FloorType:
    """One floor type. `key` is the name that a chunk file stores."""

    key: str
    note: str
    roof: bool = False


# The name of the table file, with no suffix.
TABLE_NAME: str = "floor_types"

# The first row is the floor of a new chunk. The editor fills a new chunk with
# it, so it must be the most common ground of the world.
_FLOOR_ROWS: tuple = table_file.read_rows(TABLE_NAME, FloorType)

# key -> FloorType, in the order of _FLOOR_ROWS.
FLOOR_TYPES: dict = {row.key: row for row in _FLOOR_ROWS}

# The floor type of a new chunk.
DEFAULT_FLOOR_TYPE: str = _FLOOR_ROWS[0].key

# The floor type of a tile with no floor. See THE VOID above.
VOID_FLOOR_TYPE: str = "void"

# The roof floor types, in the order of _FLOOR_ROWS. See ROOFS above.
ROOF_FLOOR_TYPES: tuple = tuple(row.key for row in _FLOOR_ROWS if row.roof)
