"""Tests for the inventory grid renderer.

The layout bug being guarded against: when item names were long enough that
the four-column natural width exceeded ~78 chars, ``EvTable`` collapsed the
columns and wrapped spaceless item names one character per row, producing a
"tall" vertically-stacked layout. These tests assert the rendered grid
remains a compact, one-text-line-per-grid-row table with bounded width even
when long item names are present.
"""

import re
from unittest import TestCase

from evennia import create_object
from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaCommandTest

from items.inventory import display
from items.inventory.handler import InventoryHandler, SLOTS_TOTAL

from typeclasses.objects import DefaultObject

_LONG_KEY = "Some Very Long Item Name That Needs Truncation"
_MEDIUM_KEY = "Rusty Metal Chunk"
_SHORT_KEY = "Hammer"


class TestDisplayHelpers(TestCase):
    """Pure formatting helpers. Wrapped in a TestCase so `evennia test`
    collects them -- as bare functions they were silently skipped by the
    Django/unittest runner that runs every other suite."""

    def test_truncate_line_short_line_is_padded_to_width(self):
        # Short lines are PADDED, not left as-is: every cell in a table column
        # must report the same visible width, or EvTable's column-width
        # negotiation collapses the narrower columns into one-character-per-row
        # wrapping. See display._truncate_line's docstring.
        line = "3: Rusty Metal Chunk"
        assert len(line) == 20
        result = display._truncate_line(line, 21)
        assert result == line + " "
        assert len(result) == 21


    def test_truncate_line_long_line_uses_ellipsis(self):
        # width=21, prefix "NN: " preserved, item key shortened by 1 for ellipsis
        line = "2: " + "A" * 25  # 28 chars total
        result = display._truncate_line(line, 21)
        assert len(result) == 21
        assert result.startswith("2: ")
        assert result.endswith("\u2026")


    def test_truncate_line_keeps_length_within_width(self):
        for width in (1, 5, 10, 21):
            line = "x" * 50
            result = display._truncate_line(line, width)
            assert len(result) == width


    def test_truncate_cell_preserves_newline_structure(self):
        cell = "3: Hammer\n  (x40)"
        result = display._truncate_cell(cell, 50)
        lines = result.split("\n")
        # Content is preserved but every line is padded out to the full width.
        assert lines[0].rstrip() == "3: Hammer"
        assert lines[1].rstrip() == "  (x40)"
        assert len(lines[0]) == 50
        assert len(lines[1]) == 50


    def test_format_slot_cell_empty(self):
        assert display.format_slot_cell(0, None) == "1: [empty]"


    def test_format_slot_cell_non_stackable(self):
        class _FakeItem:
            key = "Hammer"
            quantity = 1
            is_stackable = False

        text = display.format_slot_cell(0, _FakeItem())
        assert text == "1: Hammer"


    def test_format_slot_cell_stackable_with_qty(self):
        class _FakeItem:
            key = "Credits"
            quantity = 40
            is_stackable = True

        text = display.format_slot_cell(1, _FakeItem())
        assert text == "2: Credits\n  (x40)"


class TestRenderGridLayout(EvenniaCommandTest):

    def setUp(self) -> None:
        super().setUp()
        self.handler = InventoryHandler(self.char1)

    def _fill_slots(self, keys):
        """Create items with the given keys and add them to free slots."""
        for key in keys:
            item = create_object(DefaultObject, key=key, location=self.char1)
            self.handler.add_item(item)

    def test_render_grid_width_bounded_by_maxwidth(self):
        self._fill_slots([_MEDIUM_KEY] * 4)
        title, table = display.render_grid(self.handler, maxwidth=100)
        # Every line of the rendered table must not exceed the maxwidth.
        # Measure VISIBLE width: EvTable emits ANSI reset codes around every
        # cell, and raw len() counts each of those four escape chars as
        # content, so a correctly-sized 100-column row measures ~144 and this
        # assertion could never pass.
        for line in table.split("\n"):
            visible = len(strip_ansi(line))
            assert visible <= 100, f"line too wide ({visible}): {line!r}"

    def test_render_grid_stays_compact_with_long_names(self):
        # The bug case: four cells filled, three with a name long enough to
        # push the natural 4-col width past the limit. The grid must NOT
        # balloon into a tall per-character wrapping layout.
        self._fill_slots([_LONG_KEY, _MEDIUM_KEY, _LONG_KEY, _LONG_KEY])
        title, table = display.render_grid(self.handler, maxwidth=100)

        # A healthy compact grid for 32 slots in 4 columns has exactly 9
        # horizontal border lines (top + 8 row separators). The buggy tall
        # layout produced dozens. We assert there are <= 9 such lines so we
        # catch any wrap-induced vertical blow-up while still allowing the
        # expected count.
        border_lines = [
            line for line in table.split("\n")
            if line and set(line) <= set("+-") and "+" in line
        ]
        assert len(border_lines) <= 9, (
            f"grid has {len(border_lines)} border lines (expected ~9): "
            "names appear to be wrapping per-character"
        )

    def test_render_grid_truncates_long_item_names(self):
        self._fill_slots([_LONG_KEY])
        title, table = display.render_grid(self.handler, maxwidth=100)
        plain = strip_ansi(table)
        # The long name must be truncated (ellipsis marker present) and the
        # [empty] cell must be intact in the same row.
        assert "\u2026" in plain, "long item name was not truncated"
        # Anchored on a cell boundary ("|" then spaces then the slot number):
        # a bare substring check for "1: [empty]" also matches inside
        # "21: [empty]", "31: [empty]", etc. once the grid renders compactly
        # rather than character-wrapped.
        assert not re.search(r"\|\s*1: \[empty\]", plain)  # slot 1 holds the long item now
        assert re.search(r"\|\s*2: \[empty\]", plain)  # remaining slots are empty and intact

    def test_render_grid_title_reports_used_count(self):
        self._fill_slots([_SHORT_KEY, _MEDIUM_KEY, _SHORT_KEY])
        title, table = display.render_grid(self.handler, maxwidth=100)
        assert title == f"Carrying 3/{SLOTS_TOTAL} slots"

    def test_render_grid_total_width_matches_maxwidth(self):
        # With width locked and evenwidth=True, the table should be exactly
        # maxwidth chars wide (modulo EvTable's rounding). Assert each
        # border line is within one char of the target.
        self._fill_slots([_MEDIUM_KEY, _MEDIUM_KEY, _MEDIUM_KEY, _MEDIUM_KEY])
        _, table = display.render_grid(self.handler, maxwidth=100)
        for line in table.split("\n"):
            if line and set(line) <= set("+-") and "+" in line:
                assert abs(len(line) - 100) <= 1
