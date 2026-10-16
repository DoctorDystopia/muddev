"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/09/2026
Description: The wall styles of the tile grid, one row for each style.

             A wall style is the look of the walls of one tile, for example
             `brick` (DESIGN-0013 section 6.4). A chunk file of format 2
             stores an index into its own `wall_names` list. Every name in
             that list must be a key here. The Godot editor paints from this
             list.

             THE ROWS ARE DATA. They live in `world/tables/wall_styles.json`
             (10/14/2026), and `world/table_file.py` reads them. The Tables
             tab of the terrain editor adds, edits, renames, and removes a
             row, and then runs the client export. The first row is
             `DEFAULT_WALL_STYLE` of the tile grid constants: the style of
             every tile of a format 1 file. The editor never renames or
             removes it.

             A wall style sets no walk rule. The wall flag owns "no step and
             no shot". The wall style owns what the wall looks like. Thus, a
             style on a tile with no wall bit is legal, and nothing draws it.

             THE LOOK is the client's: the colour and the height. The client
             palette (`godot/world/look/terrain_palette.json`, with
             `godot/world/terrain/wall_palette.gd` as its fallback) gives each
             style its colour and its height in height steps (16 steps are
             one tile). A style with no row there draws as the first row.
             Thus, a new row needs no client edit. No server rule reads a
             wall height: a wall blocks a step at any height.
"""

from dataclasses import dataclass

from world import table_file


@dataclass(frozen=True)
class WallStyle:
    """One wall style. `key` is the name that a chunk file stores."""

    key: str
    note: str


# The name of the table file, with no suffix.
TABLE_NAME: str = "wall_styles"

# The first row is the style of every tile of a format 1 file. Thus, its key
# is the default of the chunk file. A test holds the two equal.
_WALL_ROWS: tuple = table_file.read_rows(TABLE_NAME, WallStyle)

# key -> WallStyle, in the order of _WALL_ROWS.
WALL_STYLES: dict = {row.key: row for row in _WALL_ROWS}

# The style of a tile that names none.
DEFAULT_WALL_STYLE: str = _WALL_ROWS[0].key
