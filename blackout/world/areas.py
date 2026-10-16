"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The areas of the tile grid, one row for each area.

             An area is a named part of the world. A chunk file stores an
             index into its own `area_names` list, and every name in that list
             must be a key here. The Godot editor paints from this list.

             THE ROWS ARE DATA. They live in `world/tables/areas.json`
             (10/14/2026), and `world/table_file.py` reads them. The Tables
             tab of the terrain editor adds, edits, renames, and removes a
             row, and then runs the client export. A hand edit of the file is
             legal too. Then run `scripts/export_client_constants.py`.

             The client picks the fog and the light of a tile by its area:
             `godot/world/look/area_looks.json`, with `LOOKS` in
             `godot/world/area_look.gd` as its fallback. An area with no row
             there gets the fallback look, so a new area needs no client
             edit. DESIGN-0011 sections 6.2 and 6.7.

             A tile room stores no name and no description. On a tile with no
             named object, `look` shows the `name` and the `desc` of the area.
             `world/tile_text.py` owns that rule.
"""

from dataclasses import dataclass

from world import table_file


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


# The name of the table file, with no suffix.
TABLE_NAME: str = "areas"

# The first row is the area of a new chunk.
_AREA_ROWS: tuple = table_file.read_rows(TABLE_NAME, Area)

# key -> Area, in the order of _AREA_ROWS.
AREAS: dict = {row.key: row for row in _AREA_ROWS}

# The area of a new chunk.
DEFAULT_AREA: str = _AREA_ROWS[0].key
