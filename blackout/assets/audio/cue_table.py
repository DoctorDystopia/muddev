"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/26/2026
Description: The cue table, godot/audio/cues.json. The one owner of its
             format. SoundCues in the client reads it, and the sound wizard
             writes it.

             THE FILE HOLDS:
               format   the number of the format, FORMAT.
               cues     cue -> {kind, clip, note}. clip is relative to
                        godot/audio/. note says when the cue plays.
               moments  moment -> cue. The server names the moment. The
                        client decides what it sounds like.

             A TABLE THAT AN AUTHOR GROWS IS A TABLE FILE (Nick, 10/14/2026).
             Until 10/26/2026, the table was two GDScript dictionaries of
             preload() rows in sound_cues.gd. Then each new sound was an edit
             of GDScript.

             The moment keys were constants of blackout_constants.gd, so a
             renamed moment broke the client file. A JSON key cannot do that.
             Thus, check.py refuses a moment that the server does not name,
             and statefeed/tests/test_cue_table.py runs that check on the file
             in git. A moment with no row plays nothing. That is fine.

             The write gives the same bytes for the same table: the format
             first, then each cue and each moment in key order.

             Reads and writes only the files that it is given.
"""

import json
import os
import re
from dataclasses import dataclass, replace

from assets.audio import paths


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass(frozen=True)
class Cue:
    """One row of the cue table: the cue, its sound kind, its sound clip
    relative to godot/audio/, and the note that says when it plays."""

    key: str
    kind: str
    clip: str
    note: str


@dataclass(frozen=True)
class CueTable:
    """The cue table. cues maps a cue to its Cue. moments maps a moment to
    a cue."""

    cues: dict
    moments: dict


class CueTableError(Exception):
    """The cue table, or the moment list, is not there or does not read."""


FORMAT: int = 1

KEY_FORMAT: str = "format"
KEY_CUES: str = "cues"
KEY_MOMENTS: str = "moments"
FIELD_KIND: str = "kind"
FIELD_CLIP: str = "clip"
FIELD_NOTE: str = "note"


# ─── Private constant definitions ────────────────────────────────────────────

_FIELDS: tuple = (FIELD_KIND, FIELD_CLIP, FIELD_NOTE)
_JSON_INDENT: int = 2

# One moment constant in the generated client constants, for example
#   const MOMENT_GUNS_SHOT := "guns_shot"
# clientexport.py writes each one in this shape.
_MOMENT_LINE: str = r'^const MOMENT_[A-Z0-9_]+ := "([a-z0-9_]+)"$'


# ─── Private helper routines ─────────────────────────────────────────────────

def _checked_cue(key, row, shown: str) -> Cue:
    """
    Purpose: Make one parsed row of the cues section into a Cue.

    Entry:
        shown names the file in a problem.

    Exit/Returns:
        Returns the Cue. Raises CueTableError for a row that is not an
        object, or a field that is missing or not text.

    Module Globals:
        _FIELDS read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    complete = isinstance(row, dict) and all(
        isinstance(row.get(field), str) for field in _FIELDS)

    if not complete:
        raise CueTableError("%s: the cue %s needs the text fields %s."
                            % (shown, key, ", ".join(_FIELDS)))

    return Cue(key=key, kind=row[FIELD_KIND], clip=row[FIELD_CLIP],
               note=row[FIELD_NOTE])


def _checked_table(content, shown: str) -> CueTable:
    """
    Purpose: Make the parsed JSON of a cue table into a CueTable.

    Entry:
        content is the parsed JSON. shown names the file in a problem.

    Exit/Returns:
        Returns the CueTable. Raises CueTableError for a file with no format
        number, a newer format, a section that is not an object, or a moment
        whose cue is not text.

    Module Globals:
        FORMAT read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    whole = isinstance(content, dict)
    version = content.get(KEY_FORMAT) if whole else None
    cue_rows = content.get(KEY_CUES, {}) if whole else None
    moment_rows = content.get(KEY_MOMENTS, {}) if whole else None
    shaped = (isinstance(version, int) and isinstance(cue_rows, dict)
              and isinstance(moment_rows, dict))

    if not shaped:
        raise CueTableError("%s has no format number, or a section that is "
                            "not an object." % shown)

    if version > FORMAT:
        raise CueTableError("%s has format %d. This reader reads format %d."
                            % (shown, version, FORMAT))

    cues = {key: _checked_cue(key, row, shown)
            for key, row in cue_rows.items()}
    named = all(isinstance(cue, str) for cue in moment_rows.values())

    if not named:
        raise CueTableError("%s: each moment needs the name of a cue."
                            % shown)

    return CueTable(cues=cues, moments=dict(moment_rows))


# ─── Public routines ─────────────────────────────────────────────────────────

def read_table(path: str) -> CueTable:
    """
    Purpose: Read a cue table file.

    Entry:
        path names the file, for example paths.CUE_TABLE_PATH.

    Exit/Returns:
        Returns the CueTable. Raises CueTableError when the file is not
        there, is not JSON, or does not have the shape of a cue table.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    if not os.path.isfile(path):
        raise CueTableError("%s is not there." % path)

    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = json.load(handle)
    except (OSError, ValueError) as problem:
        raise CueTableError("%s does not read: %s." % (path, problem))

    return _checked_table(content, path)


def render_table(table: CueTable) -> str:
    """
    Purpose: Give the text of a cue table file.

    Entry:
        table is a CueTable.

    Exit/Returns:
        Returns the JSON text: the format first, then each cue and each
        moment in key order. The same table gives the same bytes.

    Module Globals:
        FORMAT, _JSON_INDENT read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    cues = {}

    for key in sorted(table.cues):
        cue = table.cues[key]
        cues[key] = {FIELD_KIND: cue.kind, FIELD_CLIP: cue.clip,
                     FIELD_NOTE: cue.note}

    moments = {moment: table.moments[moment]
               for moment in sorted(table.moments)}
    content = {KEY_FORMAT: FORMAT, KEY_CUES: cues, KEY_MOMENTS: moments}
    text = json.dumps(content, indent=_JSON_INDENT, ensure_ascii=False)

    return text + "\n"


def write_table(table: CueTable, path: str) -> None:
    """
    Purpose: Write a cue table file.

    Entry:
        The folder of path exists.

    Exit/Returns:
        Returns None. Raises OSError when the write fails.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    text = render_table(table)

    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def with_cue(table: CueTable, cue: Cue, moment: str = "") -> CueTable:
    """
    Purpose: Give a copy of a cue table with one more cue.

    Entry:
        table has no cue cue.key. moment is "" or a moment with no cue.

    Exit/Returns:
        Returns the new CueTable. A moment maps to the new cue.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    cues = dict(table.cues)
    cues[cue.key] = cue
    moments = dict(table.moments)

    if moment:
        moments[moment] = cue.key

    return replace(table, cues=cues, moments=moments)


def clip_for(folder: str, cue_key: str, suffix: str) -> str:
    """Give the clip of a new cue, relative to godot/audio/: sfx/x.wav."""
    return "%s/%s%s" % (folder, cue_key, suffix)


def read_moments(path: str) -> tuple:
    """
    Purpose: Read each moment name from the generated client constants.

    Entry:
        path names blackout_constants.gd, for example
        paths.CLIENT_CONSTANTS_PATH.

    Exit/Returns:
        Returns the moment names, sorted. Raises CueTableError when the
        file is not there or names no moment.

    Module Globals:
        _MOMENT_LINE read.

    Notes:
        The sound wizard runs with no Django, so it cannot read MOMENTS in
        statefeed/constants.py. export_client_constants.py writes this file,
        and test_cue_table.py checks that the two lists agree.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as problem:
        raise CueTableError("%s does not read: %s." % (path, problem))

    found = re.findall(_MOMENT_LINE, text, re.MULTILINE)

    if not found:
        raise CueTableError("%s names no moment." % path)

    return tuple(sorted(found))


def import_path(clip: str) -> str:
    """Give the absolute path of the .import file of one sound clip."""
    return paths.clip_path(clip) + paths.IMPORT_SUFFIX
