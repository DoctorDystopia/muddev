"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/26/2026
Description: The credits of the sound clips, godot/audio/CREDITS.md.

             A PERSON WRITES THE FILE, AND THE WIZARD ADDS ROWS. The license
             prose of each sound pack stays as Nick wrote it. The sound wizard
             adds one row to the table of a sound pack, or a new section for
             a new sound pack at the end. It changes no other line.

             THE SHAPE THAT THIS MODULE READS:
               - A sound pack is a "## " heading. Its section ends at the
                 next "## " heading.
               - A table row starts with "|". The first cell of a row names
                 the sound clip in backticks, relative to godot/audio/.
               - Any other line is prose, and this module keeps it as is.

             The check (check.py) reads credited_clips. Thus, a sound clip of
             the cue table with no credits row fails the test suite. A file
             with no row looks the same as a file whose license nobody
             checked.

             Reads and writes only the text that it is given.
"""

from dataclasses import dataclass


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass(frozen=True)
class Pack:
    """One sound pack of the credits: the text of its heading, and the
    sound clip of each row of its table."""

    heading: str
    clips: tuple


class CreditsError(Exception):
    """The credits file is not there, or a cell cannot go in a table."""


# ─── Private constant definitions ────────────────────────────────────────────

_PACK_PREFIX: str = "## "
_ROW_PREFIX: str = "|"
_CELL_SEPARATOR: str = "|"
_CODE_MARK: str = "`"

# The two lines that start a table, as the sections in git write them.
_TABLE_HEAD: tuple = ("| Clip | Source file in the pack | Changes |",
                      "|---|---|---|")
_ROW_TEMPLATE: str = "| `%s` | `%s` | %s |"

# What the credits say about a source file that the wizard copies.
_RENAMED: str = "Renamed."
_UNMODIFIED: str = "The source file is unmodified."

# A text that a table cell cannot hold: it ends the cell or the code mark.
_CELL_BREAKERS: tuple = (_CELL_SEPARATOR, _CODE_MARK, "\n", "\r")


# ─── Private helper routines ─────────────────────────────────────────────────

def _clip_of(line: str) -> str:
    """
    Purpose: Give the sound clip that one table row names.

    Entry:
        line starts with "|".

    Exit/Returns:
        Returns the text in the backticks of the first cell. Returns "" for
        the head of a table, its rule, and a row with no backticks.

    Module Globals:
        _CELL_SEPARATOR, _CODE_MARK read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    cells = line.split(_CELL_SEPARATOR)
    first = cells[1].strip() if len(cells) > 2 else ""
    marked = (len(first) > 2 and first.startswith(_CODE_MARK)
              and first.endswith(_CODE_MARK))

    return first[1:-1] if marked else ""


def _section_end(lines: list, start: int) -> int:
    """Give the index after the last line of the section at start."""
    for index in range(start + 1, len(lines)):
        if lines[index].startswith(_PACK_PREFIX):
            return index

    return len(lines)


def _heading_index(lines: list, heading: str) -> int:
    """Give the index of the heading line of one sound pack, or -1."""
    for index, line in enumerate(lines):
        if line == _PACK_PREFIX + heading:
            return index

    return -1


# ─── Public routines ─────────────────────────────────────────────────────────

def read_credits(path: str) -> str:
    """
    Purpose: Read the credits file.

    Entry:
        path names the file, for example paths.CREDITS_PATH.

    Exit/Returns:
        Returns the text, with "\n" at each line end. Raises CreditsError
        when the file is not there or does not read.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as problem:
        raise CreditsError("%s does not read: %s." % (path, problem))

    return text


def write_credits(text: str, path: str) -> None:
    """Write the credits file. Raises OSError when the write fails."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def packs_of(text: str) -> list:
    """
    Purpose: Give each sound pack of the credits, in file order.

    Entry:
        text is the content of a credits file.

    Exit/Returns:
        Returns one Pack for each "## " heading, with the sound clip of
        each row of its table.

    Module Globals:
        _PACK_PREFIX, _ROW_PREFIX read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    lines = text.split("\n")
    found = []

    for index, line in enumerate(lines):
        if not line.startswith(_PACK_PREFIX):
            continue

        end = _section_end(lines, index)
        rows = [_clip_of(row) for row in lines[index + 1:end]
                if row.startswith(_ROW_PREFIX)]
        heading = line[len(_PACK_PREFIX):].strip()
        found.append(Pack(heading=heading,
                          clips=tuple(clip for clip in rows if clip)))

    return found


def credited_clips(text: str) -> set:
    """Give each sound clip that a row of the credits names."""
    return {clip for pack in packs_of(text) for clip in pack.clips}


def cell_problem(value: str) -> str:
    """Refuse a text that would break a table cell: a "|" or a "`"."""
    breaks = any(breaker in value for breaker in _CELL_BREAKERS)

    return "The credits table cannot hold | or `." if breaks else ""


def changes_text(renamed: bool, import_note: str) -> str:
    """
    Purpose: Give the Changes cell of a sound clip that the wizard copies.

    Entry:
        renamed is True when the copy has a new name. import_note is what
        the import does, from the sound kind.

    Exit/Returns:
        Returns the cell, for example "Renamed. Imported as mono (Force →
        Mono). The source file is unmodified."

    Module Globals:
        _RENAMED, _UNMODIFIED read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    parts = [_RENAMED] if renamed else []
    parts.extend(part for part in (import_note, _UNMODIFIED) if part)

    return " ".join(parts)


def render_row(clip: str, source_file: str, changes: str) -> str:
    """Give one table row: the sound clip, its file in the pack, changes."""
    return _ROW_TEMPLATE % (clip, source_file, changes)


def with_row(text: str, heading: str, row: str) -> str:
    """
    Purpose: Give the credits with one more row in the table of one pack.

    Entry:
        heading is the heading of a Pack of packs_of(text).

    Exit/Returns:
        Returns the new text. The row goes after the last table row of the
        section. A section with no table gets the head of a table, then the
        row. Raises CreditsError for a heading that the text does not have.

    Module Globals:
        _ROW_PREFIX, _TABLE_HEAD read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    lines = text.split("\n")
    start = _heading_index(lines, heading)

    if start < 0:
        raise CreditsError("The credits have no sound pack %r." % heading)

    end = _section_end(lines, start)
    rows = [index for index in range(start + 1, end)
            if lines[index].startswith(_ROW_PREFIX)]

    if rows:
        lines.insert(rows[-1] + 1, row)
        return "\n".join(lines)

    last = max(index for index in range(start, end) if lines[index].strip())
    lines[last + 1:last + 1] = ["", *_TABLE_HEAD, row]

    return "\n".join(lines)


def render_pack(heading: str, prose: list, row: str) -> str:
    """
    Purpose: Give the section of a new sound pack, with its first row.

    Entry:
        prose holds the lines under the heading, for example the license.

    Exit/Returns:
        Returns the section text: the heading, the prose, and a table with
        one row. It ends with a line end.

    Module Globals:
        _PACK_PREFIX, _TABLE_HEAD read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    lines = [_PACK_PREFIX + heading, ""]

    for line in prose:
        lines.extend([line, ""])

    lines.extend([*_TABLE_HEAD, row])

    return "\n".join(lines) + "\n"


def with_pack(text: str, section: str) -> str:
    """Give the credits with a new sound pack section at the end."""
    body = text.rstrip("\n")

    return body + "\n\n" + section
