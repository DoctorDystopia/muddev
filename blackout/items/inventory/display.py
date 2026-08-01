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
        Lines that already fit are returned unchanged -- EvTable pads cells
        itself, so padding here as well double-counted the width and pushed
        the rendered grid past its maxwidth.

        Widths are measured through ANSIString so colour markup costs zero
        columns. Plain ``len()`` counted a ``|y`` tag as two characters,
        which mis-sized every cell holding a coloured item name and
        re-triggered the EvTable column-collapse this module exists to
        prevent. Note that ``evennia.utils.utils.crop`` is NOT usable here:
        it measures with plain ``len()`` too.
    """
    ansi_line = ANSIString(line)

    if len(ansi_line) <= width:
        return line

    if width <= 0:
        return ""

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
    if stackable and qty > 1:
        line2 = f"  (x{qty})"
    else:
        line2 = ""
    return f"{line1}\n{line2}"


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

    table = evtable.EvTable(border="cells", width=maxwidth, evenwidth=True)

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
