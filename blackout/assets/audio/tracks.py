"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: The music track table, as the sound wizard and the check read
             and write it (DESIGN-0016). `world/music_tracks.py` owns the
             row, the vocabulary, and the rules, and the server reads the
             table through it at start. This module adds what a tool
             needs: a read of any file, a write in the format of the table
             files, and the names that a track gives its files.

             THE WRITE GIVES THE BYTES OF THE TABLES TAB. The Tables tab of
             the terrain editor writes a table file with Godot's JSON: a tab
             indent, the keys of a row sorted, and one line end at the end.
             This writer gives the same bytes, so a rename on the tab and a
             track from the wizard never fight over the format.

             Reads and writes only the files that it is given.
"""

import json
import os
from dataclasses import asdict

from assets.audio import kinds, paths
from assets.pipeline import records
from systems.core.tilegrid import constants as tile_const
from world import music_tracks, table_file
from world.music_tracks import Track


# ─── Private constant definitions ────────────────────────────────────────────

_JSON_INDENT: str = "\t"


# ─── Public routines ─────────────────────────────────────────────────────────

def read_table(path: str) -> tuple:
    """
    Purpose: Read a music track table file.

    Entry:
        path names the file, for example paths.TRACK_TABLE_PATH.

    Exit/Returns:
        Returns the Track rows, in file order. Raises
        table_file.TableFileError when the file is not there or breaks a
        rule of the table files. The rows of the vocabulary are not
        checked here: the server checks them at start, and the check of
        assets.audio reports them.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    directory = os.path.dirname(path)
    table = os.path.splitext(os.path.basename(path))[0]

    return table_file.read_rows(table, Track, directory, allow_empty=True)


def render_table(rows) -> str:
    """
    Purpose: Give the text of a music track table file.

    Entry:
        rows holds Track rows, in the order of the table.

    Exit/Returns:
        Returns the JSON text, as the Tables tab writes a table file. The
        same rows give the same bytes.

    Module Globals:
        _JSON_INDENT read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    content = {table_file.FORMAT_KEY: tile_const.TABLE_FORMAT_VERSION,
               table_file.ROWS_KEY: [asdict(row) for row in rows]}
    text = json.dumps(content, indent=_JSON_INDENT, sort_keys=True,
                      ensure_ascii=False)

    return text + "\n"


def write_table(rows, path: str) -> None:
    """Write a music track table file. Raises OSError when the write fails."""
    text = render_table(rows)

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def with_track(rows, track: Track) -> tuple:
    """Give the rows with one more track at the end."""
    return tuple(rows) + (track,)


def key_problem(value: str, rows) -> str:
    """
    Purpose: Refuse a track key that is no key, that the table has, or
    whose files are there already.

    Entry:
        rows holds the Track rows of the table.

    Exit/Returns:
        Returns the problem, or "".

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    fits = records.is_key(value)
    taken = any(row.key == value for row in rows)
    served = fits and os.path.exists(paths.track_path(value))
    sourced = fits and os.path.exists(paths.source_dir(value))

    if not fits:
        return "A track key uses only a-z, 0-9 and _, with a letter first."

    if taken:
        return "The track table has the track %s already." % value

    if served or sourced:
        return "The files of a track %s are there already. Type another " \
               "key." % value

    return ""


def served_relative(key: str) -> str:
    """Give the served file of a track, as the credits name it: music/x.ogg."""
    kind = kinds.KINDS[kinds.MUSIC_KIND]

    return "%s/%s%s" % (kind.folder, key, kind.output_suffix)


def source_ids(rows) -> set:
    """Give the source id of the master of each track."""
    return {music_tracks.source_id_for(row.key) for row in rows}
