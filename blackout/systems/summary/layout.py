"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Fixed-width row builders for the player summary screen.

             Every panel draws through these so the dossier reads as one grid
             rather than six panels that each invented their own spacing. No
             panel is allowed to pad or rule on its own.
"""

from systems.ui.colors import (
    DIM_COLOR,
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    TITLE_COLOR,
)

from . import constants as const


# ─── Private helper routines ─────────────────────────────────────────────────

def _colored(text: str, color: str) -> str:
    """
    Purpose: Wrap already-padded text in a colour tag.

    Entry:
        text is a plain string, ALREADY padded to its final column width.
        color is an Evennia colour token from systems.ui.colors, or "".

    Exit/Returns:
        Returns the text with colour markup applied, or unchanged if no colour
        was asked for.

    Module Globals:
        RESET_COLOR read.

    Methodology:
        Padding happens before colouring, never after. Evennia colour tokens
        are two characters of markup that render as zero columns, so ljust on
        an already-coloured string overpads by exactly the markup length --
        which is the whole reason this module pads plain text first and hands
        the result here. It is also why nothing in this file needs ANSIString:
        every string it measures is plain at the moment it is measured.

    Notes/References:
        CLAUDE.md §"Evennia gotchas": `crop` is not ANSI-aware in this build
        either. The same trap, avoided the same way.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    if not color:
        return text

    colored_text = f"{color}{text}{RESET_COLOR}"

    return colored_text


def _cell(label: str, value: str, color: str, pad_value: bool = True) -> str:
    """
    Purpose: Render one label/value pair as a fixed-width cell.

    Entry:
        label is a plain string. Longer than FIELD_LABEL_WIDTH truncates.
        value is a plain string. Longer than FIELD_VALUE_WIDTH is NOT
        truncated -- an overlong value pushes the row wide rather than losing
        digits, because a silently clipped number is worse than a ragged row.
        color is a colour token or "".
        pad_value is False for the last cell on a row.

    Exit/Returns:
        Returns the rendered cell string.

    Module Globals:
        const.FIELD_LABEL_WIDTH, const.FIELD_VALUE_WIDTH read.
        DIM_COLOR read.

    Methodology:
        Label is dimmed and value carries the caller's colour, so the eye lands
        on numbers rather than on the words naming them.

        The last cell on a row skips its value padding. Padding it would leave
        trailing spaces INSIDE the colour markup, where an rstrip on the
        finished row cannot reach them -- which is how a 60-column screen ends
        up shipping rows of invisible filler to every client.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    clipped_label = label[: const.FIELD_LABEL_WIDTH]
    padded_label = clipped_label.ljust(const.FIELD_LABEL_WIDTH)

    if pad_value:
        padded_value = value.ljust(const.FIELD_VALUE_WIDTH)
    else:
        padded_value = value

    label_text = _colored(padded_label, DIM_COLOR)
    value_text = _colored(padded_value, color)
    cell_text = f"{label_text}{value_text}"

    return cell_text


# ─── Public routines ─────────────────────────────────────────────────────────

def rule(heavy: bool = False) -> str:
    """
    Purpose: Build a horizontal rule the full width of the screen.

    Entry:
        heavy selects the bracketing rule over the panel separator.

    Exit/Returns:
        Returns the rule as a dim-coloured string.

    Module Globals:
        const.HEAVY_RULE_CHAR, const.LIGHT_RULE_CHAR, const.SUMMARY_WIDTH read.
        DIM_COLOR read.

    Methodology:
        One routine for both rules so the two can never drift in width.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    if heavy:
        rule_char = const.HEAVY_RULE_CHAR
    else:
        rule_char = const.LIGHT_RULE_CHAR

    rule_text = _colored(rule_char * const.SUMMARY_WIDTH, DIM_COLOR)

    return rule_text


def split_line(left: str, right: str) -> str:
    """
    Purpose: Render two plain strings on one row, one flush left and one flush
    right against SUMMARY_WIDTH. Used for the dossier's title bar.

    Entry:
        left and right are plain strings carrying no colour markup.

    Exit/Returns:
        Returns the padded row. If the two texts cannot both fit, they are
        separated by a single space and the row runs over rather than
        truncating either.

    Module Globals:
        const.SUMMARY_WIDTH read.
        TITLE_COLOR, HIGHLIGHT_COLOR read.

    Methodology:
        Compute the gap from the plain lengths, then colour each half. Same
        pad-then-colour order as _cell, for the same reason.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    used = len(left) + len(right)
    gap_width = const.SUMMARY_WIDTH - used

    if gap_width < 1:
        gap_width = 1

    left_text = _colored(left, TITLE_COLOR)
    right_text = _colored(right, HIGHLIGHT_COLOR)
    row = f"{left_text}{' ' * gap_width}{right_text}"

    return row


def section(title: str) -> list:
    """
    Purpose: Open a panel with its separator and heading.

    Entry:
        title is the panel's plain-text heading.

    Exit/Returns:
        Returns a list of display lines: a light rule, then the heading.

    Module Globals:
        TITLE_COLOR read.

    Methodology:
        Headings sit flush left while field rows are indented, which is what
        makes the six panels scannable without any boxing characters.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    separator = rule()
    heading = _colored(title.upper(), TITLE_COLOR)
    lines = [separator, heading]

    return lines


def fields(pairs: list, color: str = HIGHLIGHT_COLOR) -> list:
    """
    Purpose: Render label/value pairs into rows of FIELDS_PER_ROW cells.

    Entry:
        pairs is a list of (label, value) tuples. Both members must be plain
        strings -- callers format numbers before handing them over.
        color is the colour applied to every value in this batch.

    Exit/Returns:
        Returns a list of display lines. An empty `pairs` yields an empty list,
        so a panel with nothing to say contributes nothing rather than an
        empty heading.

    Module Globals:
        const.FIELDS_PER_ROW, const.FIELD_INDENT, const.FIELD_GUTTER read.

    Methodology:
        Chunk the pairs, build each cell, join with the gutter. A trailing odd
        pair simply renders a one-cell row; the cell is already padded, so the
        column still lines up with the rows above it.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    lines = []
    total = len(pairs)

    for start in range(0, total, const.FIELDS_PER_ROW):
        chunk = pairs[start : start + const.FIELDS_PER_ROW]
        last_index = len(chunk) - 1
        cells = []

        for index, pair in enumerate(chunk):
            label, value = pair
            is_last = index == last_index
            cell_text = _cell(label, value, color, pad_value=not is_last)
            cells.append(cell_text)

        joined = const.FIELD_GUTTER.join(cells)
        row = f"{const.FIELD_INDENT}{joined}"
        lines.append(row)

    return lines


def wide_field(label: str, value: str, color: str = HIGHLIGHT_COLOR) -> str:
    """
    Purpose: Render one label/value row where the value may be any width.

    Entry:
        label is a plain string.
        value may already carry colour markup -- an HP meter does. It is never
        padded here, so markup in it is harmless.
        color is applied only when the value is plain; pass "" for a
        pre-coloured value.

    Exit/Returns:
        Returns the rendered row.

    Module Globals:
        const.FIELD_INDENT, const.FIELD_LABEL_WIDTH read.
        DIM_COLOR read.

    Methodology:
        The label is padded to the same column as fields() uses, so a wide row
        and a paired row still align on the left edge of their values. Only the
        value differs: it runs to whatever width it needs.

    Notes/References:
        Meters from systems/ui/meters.py are the main caller -- they arrive
        pre-coloured and exactly METER_WIDTH columns wide.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    clipped_label = label[: const.FIELD_LABEL_WIDTH]
    padded_label = clipped_label.ljust(const.FIELD_LABEL_WIDTH)

    label_text = _colored(padded_label, DIM_COLOR)
    value_text = _colored(value, color)
    row = f"{const.FIELD_INDENT}{label_text}{value_text}"

    return row


def wrapped_field(label: str, items: list, color: str = HIGHLIGHT_COLOR) -> list:
    """
    Purpose: Render a label followed by an arbitrary run of short items,
    wrapping onto continuation rows indented under the value column.

    Entry:
        label is a plain string.
        items is a list of plain strings, each already formatted (e.g.
        "Cutting 30"). An empty list yields an empty result.
        color is applied to the joined item text.

    Exit/Returns:
        Returns a list of display lines.

    Module Globals:
        const.FIELD_INDENT, const.FIELD_LABEL_WIDTH, const.SUMMARY_WIDTH,
        const.FIELD_GUTTER read.

    Methodology:
        Greedy fill against the remaining width. Written by hand rather than
        with textwrap because the items must never be split mid-token -- a
        skill name broken across two rows is unreadable, and textwrap's
        break_long_words=False still splits on the spaces INSIDE "Brain
        Farming 12".

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    if not items:
        return []

    value_width = const.SUMMARY_WIDTH - len(const.FIELD_INDENT) - const.FIELD_LABEL_WIDTH
    rows = []
    current = []
    current_width = 0

    gutter_width = len(const.FIELD_GUTTER)

    for item in items:
        addition = len(item) + gutter_width
        is_overflow = current and (current_width + addition) > value_width

        if is_overflow:
            rows.append(const.FIELD_GUTTER.join(current))
            current = []
            current_width = 0

        current.append(item)
        current_width += addition

    if current:
        rows.append(const.FIELD_GUTTER.join(current))

    lines = []
    for index, row_text in enumerate(rows):
        row_label = label if index == 0 else ""
        line = wide_field(row_label, row_text, color)
        lines.append(line)

    return lines
