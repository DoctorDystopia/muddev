"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/26/2026
Description: The check of the sound clips. It reads the cue table, the
             moment list, the credits and the files under godot/audio/, and
             it writes nothing.

                 ../evenv/Scripts/python.exe -m assets.audio check

             statefeed/tests/test_cue_table.py runs it on the files in git.
             Thus, a cue that names no sound clip, a sound clip with no
             credits row, or a moment that the server does not name fails
             the test suite.

             A PROBLEM FAILS THE CHECK. A WARNING DOES NOT.
               Problems: the cue table does not read. A cue is no key, has an
                 unknown sound kind, or names a sound clip that is not
                 there, is outside its folder, or has no credits row. A
                 moment names a cue that is not there, or the server names
                 no such moment.
               Warnings: Godot did not import a sound clip yet. A file in a
                 kind folder has no cue. The web export ships it anyway.
"""

import os
from dataclasses import dataclass, field

from assets.audio import credits, cue_table, godot_import, kinds, paths
from assets.pipeline import records


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass
class CheckReport:
    """Everything the check found. ok is True when problems is empty."""

    problems: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing fails the check."""
        return not self.problems


# ─── Private helper routines ─────────────────────────────────────────────────

def _cue_problems(cue: cue_table.Cue, credited: set) -> list:
    """
    Purpose: Give each problem of one cue.

    Entry:
        credited holds each sound clip that a credits row names.

    Exit/Returns:
        Returns the problems, or an empty list.

    Module Globals:
        kinds.KINDS read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    kind = kinds.KINDS.get(cue.kind)
    folder = cue.clip.split("/")[0]
    suffix = os.path.splitext(cue.clip)[1].lower()
    fits = records.is_key(cue.key)
    present = os.path.isfile(paths.clip_path(cue.clip))
    found = []

    if not fits:
        found.append("the cue %r is no key: a-z, 0-9 and _, with a letter "
                     "first" % cue.key)

    if kind is None:
        found.append("the cue %s has the unknown sound kind %r"
                     % (cue.key, cue.kind))
    elif folder != kind.folder:
        found.append("the sound clip %s of the cue %s is not in %s/"
                     % (cue.clip, cue.key, kind.folder))
    elif suffix not in kind.suffixes:
        found.append("the sound clip %s of the cue %s is not one of %s"
                     % (cue.clip, cue.key, ", ".join(kind.suffixes)))

    if not present:
        found.append("the sound clip %s of the cue %s is not there"
                     % (cue.clip, cue.key))

    if cue.clip not in credited:
        found.append("the sound clip %s has no row in CREDITS.md" % cue.clip)

    return found


def _moment_problems(table: cue_table.CueTable, moments: tuple) -> list:
    """Give each moment row that names no server moment or no cue."""
    found = []

    for moment, cue in sorted(table.moments.items()):
        if moment not in moments:
            found.append("the server names no moment %r. A moment comes "
                         "from statefeed/constants.py" % moment)

        if cue not in table.cues:
            found.append("the moment %s names the cue %r, which the cue "
                         "table does not have" % (moment, cue))

    return found


def _file_warnings(table: cue_table.CueTable) -> list:
    """
    Purpose: Give a warning for each sound clip that Godot did not import,
    and for each file in a kind folder that no cue names.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the warnings, or an empty list.

    Module Globals:
        kinds.KINDS, paths.AUDIO_DIR, paths.IMPORT_SUFFIX read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    named = {cue.clip for cue in table.cues.values()}
    found = []

    for clip in sorted(named):
        import_file = cue_table.import_path(clip)
        present = os.path.isfile(paths.clip_path(clip))
        imported = godot_import.is_imported(import_file)

        if present and not imported:
            found.append("Godot did not import %s yet. Open the Godot "
                         "editor, or run the import of the sound wizard"
                         % clip)

    for kind in kinds.KINDS.values():
        folder = os.path.join(paths.AUDIO_DIR, kind.folder)
        names = os.listdir(folder) if os.path.isdir(folder) else []

        for name in sorted(names):
            clip = "%s/%s" % (kind.folder, name)
            extra = name.endswith(paths.IMPORT_SUFFIX) or clip in named

            if not extra:
                found.append("no cue plays %s, but the web export ships it"
                             % clip)

    return found


# ─── Public routines ─────────────────────────────────────────────────────────

def run_check() -> CheckReport:
    """
    Purpose: Run every check of the sound clips.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a CheckReport. Writes nothing.

    Module Globals:
        paths.CUE_TABLE_PATH, paths.CLIENT_CONSTANTS_PATH,
        paths.CREDITS_PATH read.

    Methodology:
        1. Read the cue table, the moment list and the credits. If one does
           not read, report it and stop, because each later check reads
           all three.
        2. Check each cue, then each moment row.
        3. Warn about each sound clip that is not imported, and each file
           that no cue names.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    report = CheckReport()

    try:
        table = cue_table.read_table(paths.CUE_TABLE_PATH)
        moments = cue_table.read_moments(paths.CLIENT_CONSTANTS_PATH)
        text = credits.read_credits(paths.CREDITS_PATH)
    except (cue_table.CueTableError, credits.CreditsError) as problem:
        report.problems.append(str(problem))
        return report

    credited = credits.credited_clips(text)

    for key in sorted(table.cues):
        report.problems.extend(_cue_problems(table.cues[key], credited))

    report.problems.extend(_moment_problems(table, moments))
    report.warnings.extend(_file_warnings(table))

    return report
