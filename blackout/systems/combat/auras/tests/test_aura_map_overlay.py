"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/03/2026
Description: Tests for the aura map overlay — the tinting of in-radius tiles.

These build a fake grid rather than a real XYMap: the overlay's whole job is
positional arithmetic on the 2D character grid the contrib hands back, so the
tests pin that arithmetic directly. A real map would add an xyzgrid build to
every run and test the contrib rather than this code.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat
"""

import unittest

from systems.combat.auras.map_overlay import (
    _BLANK_CELL_CONTENTS,
    _CENTRE_SENTINEL,
    _find_centre,
    _tint_tiles,
    build_tinted_map,
)
from systems.ui.colors import TAG_AURA_TILE


def _make_grid(size: int = 9) -> list:
    """Build a square xygrid of '#' nodes joined by '-' and '|' links.

    Even indices are node positions, odd indices are links — the same layout
    the xyzgrid contrib produces, where world (X, Y) sits at xygrid (2X, 2Y).
    """
    grid = []

    for iy in range(size):
        row = []
        for ix in range(size):
            if ix % 2 == 0 and iy % 2 == 0:
                row.append("#")
            elif iy % 2 == 0:
                row.append("-")
            elif ix % 2 == 0:
                row.append("|")
            else:
                row.append(" ")
        grid.append(row)

    return grid


class TestFindCentre(unittest.TestCase):
    """Locating the planted sentinel."""

    def test_finds_the_sentinel(self):
        grid = _make_grid()
        grid[4][4] = _CENTRE_SENTINEL

        self.assertEqual(_find_centre(grid), (4, 4))

    def test_reports_absence_rather_than_raising(self):
        grid = _make_grid()

        self.assertEqual(_find_centre(grid), (None, None))


class TestTintTiles(unittest.TestCase):
    """The positional arithmetic that maps world offsets onto the grid."""

    def setUp(self):
        self.grid = _make_grid()
        self.centre = (4, 4)

    def _tint(self, radius: int) -> int:
        return _tint_tiles(self.grid, self.centre[0], self.centre[1], radius)

    def test_tints_the_orthogonal_neighbour(self):
        """World (1,0) is two xygrid cells away, not one."""
        self._tint(1)

        self.assertIn(TAG_AURA_TILE, self.grid[4][6])

    def test_never_tints_a_link_glyph(self):
        """Regression: stepping by 1 instead of 2 would colour the '-' between tiles.

        Deriving positions as centre + 2*delta is what keeps links untouched.
        """
        self._tint(2)

        self.assertEqual(self.grid[4][5], "-")
        self.assertEqual(self.grid[5][4], "|")

    def test_leaves_the_centre_alone(self):
        """The centre carries the caster's own '@' and must not be recoloured."""
        self._tint(2)

        self.assertEqual(self.grid[4][4], "#")

    def test_excludes_the_box_corner(self):
        """The euclidean trim must apply to the drawing exactly as to the damage."""
        self._tint(2)

        corner = self.grid[8][8]

        self.assertNotIn(TAG_AURA_TILE, corner)

    def test_includes_the_diagonal_inside_the_circle(self):
        self._tint(2)

        self.assertIn(TAG_AURA_TILE, self.grid[6][6])

    def test_skips_blank_cells(self):
        """A tile position off the visible topology must not gain a phantom mark."""
        self.grid[4][6] = " "

        self._tint(1)

        self.assertEqual(self.grid[4][6], " ")

    def test_tolerates_a_centre_at_the_grid_edge(self):
        """Half the radius falls outside the array; indexing must not raise."""
        tinted = _tint_tiles(self.grid, 0, 0, 2)

        self.assertGreater(tinted, 0)

    def test_blank_cell_set_covers_the_empty_string(self):
        self.assertIn("", _BLANK_CELL_CONTENTS)
        self.assertIn(" ", _BLANK_CELL_CONTENTS)


class _FakeXYMap:
    """Minimal stand-in for XYMap.get_visual_range."""

    def __init__(self, grid=None, raises=False, returns_str=False):
        self.grid = grid
        self.raises = raises
        self.returns_str = returns_str
        self.max_x = 9
        self.options = {}

    def get_visual_range(self, xy, character=None, **kwargs):
        if self.raises:
            raise RuntimeError("map exploded")

        if self.returns_str:
            return "@"

        grid = [list(row) for row in self.grid]
        grid[4][4] = character

        return grid


class TestBuildTintedMap(unittest.TestCase):
    """Assembly, and the fallback contract."""

    def test_returns_a_string_with_the_character_symbol_restored(self):
        xymap = _FakeXYMap(grid=_make_grid())

        rendered = build_tinted_map(
            xymap,
            (2, 2),
            radius=2,
            character_symbol="|g@|n",
            visual_range=10,
            mode="nodes",
            max_size=(78, None),
            indent=0,
        )

        self.assertIn("|g@|n", rendered)
        self.assertNotIn(_CENTRE_SENTINEL, rendered)
        self.assertIn(TAG_AURA_TILE, rendered)

    def test_returns_none_when_the_map_raises(self):
        """A cosmetic overlay must degrade to the plain map, never break look."""
        xymap = _FakeXYMap(raises=True)

        rendered = build_tinted_map(
            xymap,
            (2, 2),
            radius=2,
            character_symbol="@",
            visual_range=10,
            mode="nodes",
            max_size=(78, None),
            indent=0,
        )

        self.assertIsNone(rendered)

    def test_returns_none_when_standing_off_any_node(self):
        """get_visual_range returns a bare string, not a grid, in that case."""
        xymap = _FakeXYMap(returns_str=True)

        rendered = build_tinted_map(
            xymap,
            (2, 2),
            radius=2,
            character_symbol="@",
            visual_range=10,
            mode="nodes",
            max_size=(78, None),
            indent=0,
        )

        self.assertIsNone(rendered)

    def test_applies_the_indent_to_every_line(self):
        xymap = _FakeXYMap(grid=_make_grid())

        rendered = build_tinted_map(
            xymap,
            (2, 2),
            radius=1,
            character_symbol="@",
            visual_range=10,
            mode="nodes",
            max_size=(78, None),
            indent=4,
        )

        for line in rendered.split("\n"):
            self.assertTrue(line.startswith("    "))
