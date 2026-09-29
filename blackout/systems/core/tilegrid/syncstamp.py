"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/26/2026
Description: The tile sync stamp: a digest of each chunk file at the last
             `sync_tile_objects.py --apply`.

Why a stamp
-----------
The server loads the chunk files one time, at start. The tile sync stands up
the chunk objects in the database. Thus, an edit in the Godot terrain editor
reaches the game only after a stop, a sync with --apply, and a start (Nick,
09/26/2026). The stamp lets the editor tell the author which chunk files
changed since that last sync, so no edit waits for a sync that nobody runs.

The stamp describes the dev database, not the repo. It lives beside the
database, at `SYNC_STAMP_FILE` from the game directory, and git ignores it.

The digest
----------
SHA-256 of the file text with each CRLF made LF. Git may check a file out
with either line end, and the meaning does not change. The GDScript twin,
`godot/addons/blackout_terrain/terrain_sync_state.gd`, uses the same rule.

This module imports no Evennia.
"""

import hashlib
import json
import os

from . import constants as const
from .chunkfile import is_chunk_file_name


# ─── Public constant definitions ─────────────────────────────────────────────

# The state of a chunk file against the stamp.
STATE_NEW: str = "new"
STATE_CHANGED: str = "changed"
STATE_REMOVED: str = "removed"

# The key of the digest map in the stamp file.
STAMP_KEY: str = "chunks"


# ─── Public routines ─────────────────────────────────────────────────────────

def file_digest(path: str) -> str:
    """Return the SHA-256 hex digest of a text file, CRLF read as LF."""
    with open(path, "rb") as handle:
        data = handle.read().replace(b"\r\n", b"\n")

    return hashlib.sha256(data).hexdigest()


def directory_digests(directory: str) -> dict:
    """Return file name -> digest for each chunk file of a directory."""
    if not os.path.isdir(directory):
        return {}

    return {name: file_digest(os.path.join(directory, name))
            for name in sorted(os.listdir(directory))
            if is_chunk_file_name(name)}


def stamp_text(digests: dict) -> str:
    """Return the text of a stamp file: one chunk file on each line."""
    return json.dumps({STAMP_KEY: digests}, indent=1, sort_keys=True) + "\n"


def stamp_path(game_dir: str) -> str:
    """Return the path of the stamp file of a game directory."""
    return os.path.join(game_dir, *const.SYNC_STAMP_FILE.split("/"))


def write_stamp(directory: str, path: str) -> None:
    """Write the digests of every chunk file of `directory` to `path`."""
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(stamp_text(directory_digests(directory)))


def read_stamp(path: str):
    """Return the digest map of a stamp file, or None if there is none."""
    if not os.path.isfile(path):
        return None

    with open(path, encoding="utf-8") as handle:
        return json.load(handle).get(STAMP_KEY, {})


def changed_files(directory: str, stamped: dict) -> list:
    """
    Purpose: List each chunk file that differs from a stamp.

    Entry:
        directory - the chunk directory.
        stamped   - the digest map of the stamp.

    Exit/Returns:
        A list of (file name, state), sorted by name. State is STATE_NEW,
        STATE_CHANGED, or STATE_REMOVED. Empty means the files match.

    Module Globals:
        STATE_* read.

    Methodology:
        Compare the digests of the files now with the stamp, both ways.

    Notes/References:
        The GDScript twin is TerrainSyncState.changed_files.

    Author: Nick Hobar
    Creation date: 09/26/2026
    """
    now = directory_digests(directory)
    found = []

    for name in sorted(set(now) | set(stamped)):
        if name not in stamped:
            found.append((name, STATE_NEW))
        elif name not in now:
            found.append((name, STATE_REMOVED))
        elif now[name] != stamped[name]:
            found.append((name, STATE_CHANGED))

    return found
