"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/09/2026
Description: The wall styles of the tile grid, one row for each style.

             A wall style is the look of the walls of one tile, for example
             `brick` (DESIGN-0013 section 6.4). A chunk file of format 2
             stores an index into its own `wall_names` list. Every name in
             that list must be a key here. The Godot editor paints from this
             list, through the generated constants.

             A wall style sets no walk rule. The wall flag owns "no step and
             no shot". The wall style owns what the wall looks like. Thus, a
             style on a tile with no wall bit is legal, and nothing draws it.

             The client owns the colour of a style.
             `godot/world/terrain/wall_palette.gd` gives each name a colour.
             A style with no colour there draws in the colour of the first
             row. Thus, a new row needs no client edit.

             THE HEIGHT. `height` is the height of a wall with nothing above
             it, in height steps (16 steps are one tile). A wall under a floor
             of the plane above meets that floor at any height (section 6.3).
             The client reads the height through the generated constants.

             A starter list: Nick renames, adds, or removes rows.
"""

from dataclasses import dataclass

from systems.core.tilegrid import constants as tile_const


@dataclass(frozen=True)
class WallStyle:
    """One wall style. `key` is the name that a chunk file stores."""

    key: str
    note: str
    height: int


# The first row is the style of every tile of a format 1 file. Thus, its key
# is the default of the chunk file.
_WALL_ROWS: tuple = (
    WallStyle(tile_const.DEFAULT_WALL_STYLE,
              "A plain grey wall. Every wall before the wall styles.", 12),
    WallStyle("concrete", "Poured concrete, for a bank or a bunker.", 24),
    WallStyle("brick", "Old red brick, for a shop or a house.", 24),
    WallStyle("sheet_metal", "Corrugated sheet metal, for a shack.", 20),
    WallStyle("chain_link", "A chain-link fence on posts, for a yard.", 18),
    WallStyle("rubble", "A low broken wall, for a ruin.", 6),
)

# key -> WallStyle, in the order of _WALL_ROWS.
WALL_STYLES: dict = {row.key: row for row in _WALL_ROWS}

# The style of a tile that names none.
DEFAULT_WALL_STYLE: str = _WALL_ROWS[0].key
