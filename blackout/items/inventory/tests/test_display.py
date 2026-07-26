"""Tests for the inventory grid renderer.

The layout bug being guarded against: when item names were long enough that
the four-column natural width exceeded ~78 chars, ``EvTable`` collapsed the
columns and wrapped spaceless item names one character per row, producing a
"tall" vertically-stacked layout. These tests assert the rendered grid
remains a compact, one-text-line-per-grid-row table with bounded width even
when long item names are present.
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from items.inventory import display
from items.inventory.handler import InventoryHandler, SLOTS_TOTAL

from typeclasses.objects import DefaultObject

_LONG_KEY = "Some Very Long Item Name That Needs Truncation"
_MEDIUM_KEY = "Rusty Metal Chunk"
_SHORT_KEY = "Hammer"


def test_truncate_line_short_line_unchanged():
    line = "3: Rusty Metal Chunk"
    assert len(line) == 20
    assert display._truncate_line(line, 21) == line


def test_truncate_line_long_line_uses_ellipsis():
    # width=21, prefix "NN: " preserved, item key shortened by 1 for ellipsis
    line = "2: " + "A" * 25  # 28 chars total
    result = display._truncate_line(line, 21)
    assert len(result) == 21
    assert result.startswith("2: ")
    assert result.endswith("\u2026")


def test_truncate_line_keeps_length_within_width():
    for width in (1, 5, 10, 21):
        line = "x" * 50
        result = display._truncate_line(line, width)
        assert len(result) == width


def test_truncate_cell_preserves_newline_structure():
    cell = "3: Hammer\n  (x40)"
    result = display._truncate_cell(cell, 50)
    assert result.split("\n") == ["3: Hammer", "  (x40)"]


def test_format_slot_cell_empty():
    assert display.format_slot_cell(0, None) == "1: [empty]"


def test_format_slot_cell_non_stackable():
    class _FakeItem:
        key = "Hammer"
        quantity = 1
        is_stackable = False

    text = display.format_slot_cell(0, _FakeItem())
    assert text == "1: Hammer"


def test_format_slot_cell_stackable_with_qty():
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
        for line in table.split("\n"):
            assert len(line) <= 100, f"line too wide ({len(line)}): {line!r}"

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
        # The long name must be truncated (ellipsis marker present) and the
        # [empty] cell must be intact in the same row.
        assert "\u2026" in table, "long item name was not truncated"
        assert "1: [empty]" not in table  # slot 1 holds the long item now
        assert "2: [empty]" in table  # remaining slots are empty and intact

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
