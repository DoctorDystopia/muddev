"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/03/2026
Description: Tints the grid map's tiles to show the footprint of the looker's
             active damage aura.

Why the map is rebuilt rather than patched
------------------------------------------
XYZRoom.return_appearance builds the map by calling
``xymap.get_visual_range(...)`` and msg()-ing the finished string. Patching that
string afterwards is not viable: it is already ANSI-marked, and Evennia's
``crop``/``len`` are not ANSI-aware in this build, so character positions in the
string do not correspond to screen columns.

Instead this asks the same call for its UNformatted 2D character grid
(``return_str=False``), recolors whole cells, and reassembles. That is exactly
the mechanism the contrib itself uses to colour a path to a goto-target
(xymap.py, the `target_path_style` block), so it is a supported shape rather
than a trick.

The two coordinate facts that make it work
------------------------------------------
1. World (X, Y) sits at xygrid (2X, 2Y) -- the contrib converts with
   ``ix, iy = iX * 2, iY * 2``. Tiles are therefore always at EVEN offsets from
   the centre, and the odd positions between them are link characters. Deriving
   positions as centre + 2*delta means link glyphs are never touched.
2. The grid is returned with y increasing UPWARD; the contrib flips it with
   ``[::-1]`` only at the moment it builds the string.

Neither the topology offset nor the crop offset is returned by the contrib, so
the centre is located by planting a sentinel through the ``character`` argument
and finding it again. That survives every crop the contrib may apply.
"""

from evennia.utils import logger

from systems.ui.colors import TAG_AURA_TILE, TAG_RESET

from .targeting import within_metric


# ─── Public constant definitions ───────────────────────────────────────────

# Planted as the map's centre symbol so the centre cell can be located in the
# returned grid, then swapped back for the real symbol. Must be something no
# map legend or colour tag could ever produce.
_CENTRE_SENTINEL = "\x00"

# Cell contents that mean "nothing is drawn here". A tile position holding one
# of these is off the map (or out of the visual topology) and must not be
# tinted -- colouring blank space would draw a phantom tile.
_BLANK_CELL_CONTENTS = frozenset({"", " "})


def _find_centre(gridmap) -> tuple:
    """
    Purpose: Locate the sentinel centre cell in a returned visual-range grid.

    Entry:
        gridmap - the 2D list from get_visual_range(return_str=False).

    Exit/Returns:
        Returns (ix, iy) indices of the centre cell, or (None, None) if the
        sentinel is absent.

    Module Globals:
        _CENTRE_SENTINEL read.

    Methodology:
        The contrib writes the `character` argument into the centre cell before
        any cropping, and cropping only slices -- it never rewrites cells. So
        finding the sentinel gives the caster's position in the FINAL grid,
        which is the only frame the tile offsets can be applied in.

    Notes/References:
        Returns (None, None) rather than raising: the sentinel is genuinely
        absent when the caster stands somewhere with no node, and a `look` must
        never fail because of a cosmetic overlay.

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    for iy, line in enumerate(gridmap):
        for ix, cell in enumerate(line):
            if cell == _CENTRE_SENTINEL:
                return ix, iy

    return None, None


def _tint_tiles(gridmap, centre_ix: int, centre_iy: int, radius: int) -> int:
    """
    Purpose: Recolour every drawn tile inside the radius, in place.

    Entry:
        gridmap             - the 2D list to mutate.
        centre_ix, centre_iy - the caster's cell indices within gridmap.
        radius              - aura radius in tiles.

    Exit/Returns:
        Returns the count of tiles tinted. The gridmap is mutated in place.

    Module Globals:
        _BLANK_CELL_CONTENTS, TAG_AURA_TILE, TAG_RESET read.

    Methodology:
        Walks the bounding box of world offsets and applies the SAME
        _within_metric predicate the damage path uses, so the highlight cannot
        disagree with what actually gets pulsed -- if the metric is ever
        retuned, both move together.

        Steps by 2 in grid space because one world tile is two xygrid cells.
        The centre itself is skipped: it carries the caster's own '@' marker.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    tinted = 0

    for delta_y in range(-radius, radius + 1):
        for delta_x in range(-radius, radius + 1):
            if delta_x == 0 and delta_y == 0:
                continue

            if not within_metric(delta_x, delta_y, radius):
                continue

            cell_ix = centre_ix + (delta_x * 2)
            cell_iy = centre_iy + (delta_y * 2)

            if not 0 <= cell_iy < len(gridmap):
                continue
            if not 0 <= cell_ix < len(gridmap[cell_iy]):
                continue

            cell = gridmap[cell_iy][cell_ix]

            if cell in _BLANK_CELL_CONTENTS:
                continue

            gridmap[cell_iy][cell_ix] = f"{TAG_AURA_TILE}{cell}{TAG_RESET}"
            tinted += 1

    return tinted


def build_tinted_map(
    xymap,
    xy: tuple,
    radius: int,
    character_symbol: str,
    visual_range: int,
    mode: str,
    max_size: tuple,
    indent: int,
    target_xy=None,
    target_path_style=None,
) -> str:
    """
    Purpose: Render the near-area map with the aura's tiles highlighted.

    Entry:
        xymap            - the XYMap for the caster's Z level.
        xy               - the caster's (X, Y) world coordinate.
        radius           - aura radius in tiles; 0 or less renders no highlight.
        character_symbol - the '@' marker for the caster's own tile.
        visual_range     - how far the map shows, in the units `mode` implies.
        mode             - 'nodes' or 'scan'.
        max_size         - (width, height) crop passed through to the contrib.
        indent           - left indent applied to every rendered line.
        target_xy        - optional goto-target coordinate, passed through.
        target_path_style - optional path styling, passed through.

    Exit/Returns:
        Returns the assembled map string, or None if the map could not be
        rendered with a highlight (caller should fall back to the plain map).

    Module Globals:
        _CENTRE_SENTINEL read.

    Methodology:
        Requests the raw 2D grid, locates the centre by sentinel, tints, swaps
        the sentinel back for the real character symbol, then assembles the
        string exactly as the contrib does -- reversing the y-axis and applying
        the indent to every line.

    Notes/References:
        get_visual_range returns a bare string (not a grid) when the caster is
        not standing on a node; that case is caught by the isinstance guard and
        reported as "no highlight available".

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    try:
        gridmap = xymap.get_visual_range(
            xy,
            dist=visual_range,
            mode=mode,
            target=target_xy,
            target_path_style=target_path_style,
            character=_CENTRE_SENTINEL,
            max_size=max_size,
            indent=indent,
            return_str=False,
        )
    except Exception:
        logger.log_trace()
        return None

    if not isinstance(gridmap, list):
        # No node at these coordinates -- the contrib short-circuits to a bare
        # symbol string. Nothing to highlight.
        return None

    centre_ix, centre_iy = _find_centre(gridmap)

    if centre_ix is None:
        return None

    _tint_tiles(gridmap, centre_ix, centre_iy, radius)

    gridmap[centre_iy][centre_ix] = character_symbol or _CENTRE_SENTINEL

    indent_str = indent * " "

    return indent_str + f"\n{indent_str}".join(
        "".join(line) for line in gridmap[::-1]
    )
