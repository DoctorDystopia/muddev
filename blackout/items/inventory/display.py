"""Inventory grid rendering.

Renders the character's inventory slots as a fixed 4x8 grid table.

The layout is resilient to long item names: each cell's content is
pre-truncated to the per-column width before being handed to Evennia's
``EvTable``. Combined with locking the table width explicitly, this
prevents ``EvTable._balance`` from collapsing columns into a "tall"
per-character wrapping mode (see the layout bug where item names were
rendered one character per row).

Empty slots (``[empty]``) are never truncated.
"""

from evennia.utils import evtable
from evennia.utils.ansi import ANSIString

from .handler import SLOTS_TOTAL, GRID_COLS, GRID_ROWS

EMPTY_CELL_TEXT = "[empty]"

# Total character width the rendered grid is allowed to occupy. 100 fits
# comfortably on any modern terminal (default widths are >=80, and most are
# >=120) while giving each item cell enough room for typical names.
INVENTORY_MAX_WIDTH = 100

# Each EvCell in a "cells"-bordered table reserves 4 chars of non-content
# space per column: border_left + pad_left + pad_right + border_right.
_CELL_OVERHEAD = 4

# Width available for the actual text inside a single cell.
_CELL_CONTENT_WIDTH = (INVENTORY_MAX_WIDTH - (GRID_COLS * _CELL_OVERHEAD)) // GRID_COLS

# Ellipsis appended when an item name is truncated. A single character keeps
# the truncation marker within the reserved content width.
_TRUNCATION_MARKER = "\u2026"


def _truncate_line(line, width):
    """Truncate a single text line to ``width``, keeping the slot prefix.

    The inventory cell's first line has the shape ``"NN: {item key}"``. The
    ``"NN: "`` prefix is always preserved intact; only the item key portion
    is shortened, with an ellipsis appended when truncation occurs.

    Args:
        line (str): The cell line to truncate (e.g. ``"3: Rusty Metal Chunk"``).
        width (int): Maximum number of *visible* characters the line may
            occupy.

    Returns:
        str: The (possibly truncated) line, never wider than ``width``.

    Notes:
        Every returned line is padded to EXACTLY ``width`` visible characters,
        whether or not it needed truncating. EvTable does not reliably pad
        multi-line cells to a uniform per-column width on its own -- leaving
        short lines unpadded lets its column-width negotiation see wildly
        different natural widths per column and collapse the narrow ones
        into one-character-per-row wrapping, which is the exact bug this
        module exists to prevent (confirmed by reproducing it: removing this
        padding broke a real inventory render even though it made no test
        fail, since none of the fixtures mix short and long names across
        enough rows to trigger it).

        Widths are measured and padded through ANSIString so colour markup
        costs zero columns. Plain ``len()``/``ljust()`` count a ``|y`` tag as
        two characters, which mis-sizes any cell holding a coloured item
        name. Note that ``evennia.utils.utils.crop`` is NOT usable here: it
        measures with plain ``len()`` too.
    """
    ansi_line = ANSIString(line)
    visible_len = len(ansi_line)

    if width <= 0:
        return ""

    if visible_len <= width:
        return line + (" " * (width - visible_len))

    # Reserve one char for the ellipsis when we must shorten.
    if width == 1:
        return _TRUNCATION_MARKER

    # Try to keep a leading "NN: " slot prefix intact when present so the
    # slot number stays readable. Only the trailing portion (the item key)
    # is shortened.
    if ": " in line:
        prefix_end = ANSIString(line.split(": ")[0]).__len__() + 2
        prefix = ansi_line[:prefix_end]
        if len(prefix) < width:
            available = width - len(prefix) - 1  # -1 for the ellipsis
            if available > 0:
                kept = ansi_line[prefix_end : prefix_end + available]
                return str(prefix) + str(kept) + _TRUNCATION_MARKER
            return str(prefix[: width - 1]) + _TRUNCATION_MARKER

    return str(ansi_line[: width - 1]) + _TRUNCATION_MARKER


def _truncate_cell(cell_text, width):
    """Truncate each line of a multi-line cell to ``width``.

    Args:
        cell_text (str): The full cell text, possibly containing ``\\n``.
        width (int): Maximum characters per line.

    Returns:
        str: The cell text with each line truncated to ``width``.
    """
    lines = cell_text.split("\n")
    return "\n".join(_truncate_line(line, width) for line in lines)


def format_slot_cell(slot_idx, item):
    """Build the text for a single inventory slot cell.

    Args:
        slot_idx (int): Zero-based slot index.
        item (object or None): The item occupying the slot, or ``None`` when
            the slot is empty.

    Returns:
        str: The cell text. For a filled slot this is ``"N: {key}"`` on the
        first line, optionally followed by ``"  (x{qty})"`` on a second line
        for stackable items with a quantity greater than one. Empty slots
        produce ``"N: [empty]"``.
    """
    if item is None:
        return f"{slot_idx + 1}: {EMPTY_CELL_TEXT}"

    line1 = f"{slot_idx + 1}: {item.key}"
    qty = getattr(item, "quantity", 1)
    stackable = getattr(item, "is_stackable", False)

    # The quantity line is genuinely optional -- appending an unconditional
    # "\n" gave every non-stackable cell a trailing blank line, contradicting
    # both this function's docstring and the empty-slot branch above (which
    # returns a single line). Only visible now because the test asserting it
    # was a bare module-level function the Django runner never collected.
    if stackable and qty > 1:
        return f"{line1}\n  (x{qty})"

    return line1


def build_grid(handler):
    """Build the raw 4x8 grid of (slot_idx, item) tuples.

    Args:
        handler (InventoryHandler): The inventory handler to read slots from.

    Returns:
        list: A list of ``GRID_ROWS`` rows, each a list of ``GRID_COLS``
        ``(slot_idx, item)`` tuples.
    """
    rows = []
    for row_idx in range(GRID_ROWS):
        row_cells = []
        for col_idx in range(GRID_COLS):
            slot_idx = row_idx * GRID_COLS + col_idx
            item = handler.get_slot_content(slot_idx)
            row_cells.append((slot_idx, item))
        rows.append(row_cells)
    return rows


def render_grid(handler, maxwidth=INVENTORY_MAX_WIDTH):
    """Render the inventory as a fixed-width 4x8 grid table.

    Each cell is pre-truncated to the per-column content width AND the table
    width is locked explicitly. Both halves are required: pre-truncation
    alone still let EvTable size columns to their natural content and
    overflow maxwidth, while locking the width alone lets EvTable collapse
    columns into per-character wrapping when a name is too long.

    Args:
        handler (InventoryHandler): The inventory handler to render.
        maxwidth (int, optional): Total character width to target. Defaults
            to :data:`INVENTORY_MAX_WIDTH`. Used to recompute the per-cell
            content width.

    Returns:
        tuple: A ``(title, table_str)`` 2-tuple where ``title`` is the
        ``"Carrying N/32 slots"`` header line and ``table_str`` is the
        rendered grid as a single string with embedded newlines.
    """
    rows = build_grid(handler)

    # Recompute the per-cell content width from the requested maxwidth so the
    # function stays usable at other widths (e.g. narrower clients).
    cell_width = (maxwidth - (GRID_COLS * _CELL_OVERHEAD)) // GRID_COLS

    # `width` and `evenwidth` together are broken in this EvTable build:
    # confirmed by isolating EvTable from every other part of this module --
    # four columns of already-uniform, already-padded cells still collapsed
    # three columns to width 1 and blew the fourth out past 80 chars, but
    # ONLY when both kwargs were passed together. `width` alone renders the
    # same content compactly at the requested width, and column evenness is
    # already guaranteed upstream (every cell is pre-padded to cell_width),
    # so `evenwidth` was doing nothing useful here anyway.
    table = evtable.EvTable(border="cells", width=maxwidth)

    for row_cells in rows:
        formatted = [
            _truncate_cell(format_slot_cell(slot_idx, item), cell_width)
            for slot_idx, item in row_cells
        ]
        if len(formatted) == GRID_COLS:
            # valign="t" keeps multi-line (e.g. stackable) cells top-aligned
            # so they don't vertically float within an otherwise single-line
            # row.
            table.add_row(*formatted, valign="t")

    used = handler.count_used()
    title = f"Carrying {used}/{SLOTS_TOTAL} slots"
    return title, str(table)
