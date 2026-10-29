"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/28/2026
Description: The world versions: a shelf of saved worlds that a developer
             switches between with one click. The Versions tab of the
             terrain editor and `scripts/world_versions.py` call here. The
             GDScript twin is `godot/addons/blackout_terrain/world_versions.gd`.

Why a shelf, and not a git branch
---------------------------------
A map author tries a layout, keeps it, and tries another (Nick, 10/28/2026).
A git branch switches the code with the map, and it needs a clean tree.
Thus, a version is a directory under `VERSION_DIRECTORY`, and nothing else
in the repo moves with it. A version is content, and git keeps its history
as it keeps the chunk files.

What a version is
-----------------
One directory of the shelf, `world/versions/<key>/`, holds one version: a
copy of every chunk file of the world, and `version.json`:

    {"format": 1, "note": "the market with two gates", "saved": "2026-10-28T15:04:05Z"}

The directory name is the key. A key is a legal chunk file name, so it
needs no escape. The meta file is optional: a directory that a developer
copies by hand, with no meta file, is a version with no note.

Four rules
----------
1. **A switch replaces the chunk files, and nothing else.** The world stays
   in `CHUNK_DIRECTORY`, so the server, the tests, and the tile sync read
   one directory as before. After a switch, the tile sync stands the
   version up in the database: stop the server, run
   `scripts/sync_tile_objects.py --apply`, and start it.
2. **A switch never drops a world that no version holds.** `current_key`
   names the version whose files equal the world, by digest. When no
   version does, `switch_to` refuses unless the caller says `drop=True`.
   The editor asks first and counts the files that go.
3. **A version is a whole copy.** Each version stands alone, so a removal of
   one changes no other. A version of thirty chunks is about one megabyte.
4. **The tables are shared.** A version names the areas, the floor types,
   the wall styles, and the object kinds of the tables of today. Thus, a
   rename of a row reaches each version, and a removal refuses a row that
   a version names. `TableEdits` in the editor keeps both.

This module imports no Evennia and no Django.
"""

import dataclasses
import datetime
import json
import os
import re
import shutil

from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import syncstamp
from systems.core.tilegrid.chunkfile import is_chunk_file_name


# ─── Public constant definitions ─────────────────────────────────────────────

# The keys of the meta file.
FORMAT_KEY: str = "format"
NOTE_KEY: str = "note"
SAVED_KEY: str = "saved"

# The game directory, one level above this file.
GAME_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The time format of SAVED_KEY: UTC, to the second.
SAVED_FORMAT: str = "%Y-%m-%dT%H:%M:%SZ"


# ─── Private module globals ──────────────────────────────────────────────────

_KEY_RE = re.compile(tile_const.CHUNK_NAME_PATTERN)


# ─── Public type definitions ─────────────────────────────────────────────────

class VersionError(ValueError):
    """A version that cannot be read, saved, switched to, or removed."""


@dataclasses.dataclass(frozen=True)
class Version:
    """One version of the shelf, as the list shows it."""

    key: str
    note: str
    saved: str
    chunk_count: int
    path: str


# ─── Private helper routines ─────────────────────────────────────────────────

def _fail(message: str, *args) -> None:
    raise VersionError(message % args)


def _now_text() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(SAVED_FORMAT)


def _chunk_names(directory: str) -> list:
    """Return the sorted chunk file names of a directory, or none."""
    if not os.path.isdir(directory):
        return []

    return sorted(name for name in os.listdir(directory)
                  if is_chunk_file_name(name))


def _copy_chunks(source: str, target: str) -> list:
    """Copy each chunk file of `source` into `target`. Return the names."""
    os.makedirs(target, exist_ok=True)
    names = _chunk_names(source)

    for name in names:
        shutil.copyfile(os.path.join(source, name), os.path.join(target, name))

    return names


def _remove_chunks(directory: str, keep: list) -> list:
    """Delete each chunk file of a directory not in `keep`. Return them."""
    removed = [name for name in _chunk_names(directory) if name not in keep]

    for name in removed:
        os.remove(os.path.join(directory, name))

    return removed


def _meta_problem(data) -> str:
    """Return why a meta file is wrong, or ""."""
    if not isinstance(data, dict):
        return "the meta file is not an object"

    if data.get(FORMAT_KEY) != tile_const.VERSION_FORMAT_VERSION:
        return "the meta file has format %r, not %d" % (
            data.get(FORMAT_KEY), tile_const.VERSION_FORMAT_VERSION)

    unknown = sorted(set(data) - {FORMAT_KEY, NOTE_KEY, SAVED_KEY})

    if unknown:
        return "the meta file has unknown keys: %s" % ", ".join(unknown)

    if not isinstance(data.get(NOTE_KEY, ""), str):
        return "the note is not text"

    if not isinstance(data.get(SAVED_KEY, ""), str):
        return "the save time is not text"

    return note_problem(data.get(NOTE_KEY, ""))


# ─── Public routines: the paths and the rules ────────────────────────────────

def shelf_path(game_dir: str = GAME_DIR) -> str:
    """Return the path of the shelf of a game directory."""
    return os.path.join(game_dir, *tile_const.VERSION_DIRECTORY.split("/"))


def chunks_path(game_dir: str = GAME_DIR) -> str:
    """Return the path of the world chunk directory of a game directory."""
    return os.path.join(game_dir, *tile_const.CHUNK_DIRECTORY.split("/"))


def version_path(key: str, game_dir: str = GAME_DIR) -> str:
    """Return the directory of the version `key`."""
    return os.path.join(shelf_path(game_dir), key)


def key_problem(key: str) -> str:
    """Return why `key` is not a legal version key, or ""."""
    if not key:
        return "A version needs a key."

    if _KEY_RE.search(key) is None:
        return "A key uses a-z, 0-9, and _ only."

    return ""


def note_problem(note: str) -> str:
    """Return why `note` is not a legal note, or ""."""
    if len(note) > tile_const.VERSION_NOTE_MAX_CHARS:
        return "A note has at most %d characters." % (
            tile_const.VERSION_NOTE_MAX_CHARS)

    if "\n" in note or "\r" in note:
        return "A note is one line."

    return ""


# ─── Public routines: reading the shelf ──────────────────────────────────────

def read_meta(key: str, game_dir: str = GAME_DIR) -> dict:
    """
    Return the meta of a version: `{format, note, saved}`. A version with no
    meta file gives an empty note and no save time. Raises VersionError for
    a meta file that does not read.
    """
    path = os.path.join(version_path(key, game_dir),
                        tile_const.VERSION_META_FILE)
    data = {FORMAT_KEY: tile_const.VERSION_FORMAT_VERSION, NOTE_KEY: "",
            SAVED_KEY: ""}

    if not os.path.isfile(path):
        return data

    try:
        with open(path, encoding="utf-8") as handle:
            found = json.load(handle)
    except (OSError, ValueError) as error:
        _fail("%s: %s", key, error)

    problem = _meta_problem(found)

    if problem:
        _fail("%s: %s", key, problem)

    data.update(found)

    return data


def list_versions(game_dir: str = GAME_DIR) -> list:
    """
    Purpose: List each version of the shelf.

    Entry:
        game_dir - the game directory. The default is this game.

    Exit/Returns:
        A list of Version, sorted by key. A missing shelf gives none.
        Raises VersionError for a directory whose name is not a legal key,
        or whose meta file does not read.

    Module Globals:
        _KEY_RE read.

    Methodology:
        Each directory of the shelf is a version. A file in the shelf is
        not, so a README may sit there.

    Notes/References:
        The GDScript twin is WorldVersions.list.

    Author: Nick Hobar
    Creation date: 10/28/2026
    """
    shelf = shelf_path(game_dir)

    if not os.path.isdir(shelf):
        return []

    found = []

    for key in sorted(os.listdir(shelf)):
        path = os.path.join(shelf, key)

        if not os.path.isdir(path):
            continue

        problem = key_problem(key)

        if problem:
            _fail("%s: %s", key, problem)

        meta = read_meta(key, game_dir)
        found.append(Version(key, meta[NOTE_KEY], meta[SAVED_KEY],
                             len(_chunk_names(path)), path))

    return found


def has_version(key: str, game_dir: str = GAME_DIR) -> bool:
    """Return True if the shelf holds the version `key`."""
    return os.path.isdir(version_path(key, game_dir))


def differences(key: str, game_dir: str = GAME_DIR) -> list:
    """
    Return each chunk file of the world that differs from the version
    `key`, as (file name, state) in the vocabulary of `syncstamp`: a file
    the version lacks is `new`, a file the world lacks is `removed`.
    """
    stamped = syncstamp.directory_digests(version_path(key, game_dir))

    return syncstamp.changed_files(chunks_path(game_dir), stamped)


def current_key(game_dir: str = GAME_DIR) -> str:
    """Return the key of the version that equals the world, or ""."""
    for version in list_versions(game_dir):
        if not differences(version.key, game_dir):
            return version.key

    return ""


# ─── Public routines: writing the shelf ──────────────────────────────────────

def save_version(key: str, note: str = "", overwrite: bool = False,
                 game_dir: str = GAME_DIR) -> Version:
    """
    Purpose: Save the world chunk files as the version `key`.

    Entry:
        key       - the key of the version.
        note      - one line about it, or "".
        overwrite - True to replace a version that exists.
        game_dir  - the game directory.

    Exit/Returns:
        The Version saved. Raises VersionError for a bad key or note, for a
        version that exists without `overwrite`, and for a world with no
        chunk file.

    Module Globals:
        None.

    Methodology:
        Copy each chunk file, delete the chunk files of the old version that
        the world lacks, then write the meta file with the time of now.

    Notes/References:
        The GDScript twin is WorldVersions.save. The editor saves the
        unsaved chunks of the block first, so the version is what the
        author sees.

    Author: Nick Hobar
    Creation date: 10/28/2026
    """
    problem = key_problem(key) or note_problem(note)

    if problem:
        _fail("%s", problem)

    if has_version(key, game_dir) and not overwrite:
        _fail("The version %s exists. Pick another key, or overwrite it.", key)

    if not _chunk_names(chunks_path(game_dir)):
        _fail("The world has no chunk file to save.")

    target = version_path(key, game_dir)
    names = _copy_chunks(chunks_path(game_dir), target)

    _remove_chunks(target, names)
    meta = {FORMAT_KEY: tile_const.VERSION_FORMAT_VERSION, NOTE_KEY: note,
            SAVED_KEY: _now_text()}

    with open(os.path.join(target, tile_const.VERSION_META_FILE), "w",
              encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(meta, indent=1, sort_keys=True) + "\n")

    return Version(key, note, meta[SAVED_KEY], len(names), target)


def switch_to(key: str, drop: bool = False, game_dir: str = GAME_DIR) -> list:
    """
    Purpose: Make the world chunk files the files of the version `key`.

    Entry:
        key      - the key of the version.
        drop     - True to switch when no version holds the world of now.
        game_dir - the game directory.

    Exit/Returns:
        The (file name, state) list of `differences` before the switch: the
        chunk files that the switch changed. Raises VersionError for a
        version that is not on the shelf, and for a world that no version
        holds without `drop`.

    Module Globals:
        None.

    Methodology:
        Copy each chunk file of the version over the world first, then
        delete the chunk files of the world that the version lacks. Thus, a
        copy that fails leaves every old file in place.

    Notes/References:
        Rule 2 of the module docstring. The GDScript twin is
        WorldVersions.switch_to.

    Author: Nick Hobar
    Creation date: 10/28/2026
    """
    if not has_version(key, game_dir):
        _fail("The shelf has no version %s.", key)

    changed = differences(key, game_dir)

    if not changed:
        return []

    if not drop and not current_key(game_dir):
        _fail("No version holds the world of now. Save it as a version "
              "first, or drop it: %d chunk file(s) differ.", len(changed))

    names = _copy_chunks(version_path(key, game_dir), chunks_path(game_dir))

    _remove_chunks(chunks_path(game_dir), names)

    return changed


def rename_version(old: str, new: str, game_dir: str = GAME_DIR) -> None:
    """Give the version `old` the key `new`. The files stay as they are."""
    problem = key_problem(new)

    if problem:
        _fail("%s", problem)

    if not has_version(old, game_dir):
        _fail("The shelf has no version %s.", old)

    if has_version(new, game_dir):
        _fail("The version %s exists.", new)

    os.rename(version_path(old, game_dir), version_path(new, game_dir))


def remove_version(key: str, game_dir: str = GAME_DIR) -> None:
    """Delete the version `key` from the shelf, with every file of it."""
    if not has_version(key, game_dir):
        _fail("The shelf has no version %s.", key)

    shutil.rmtree(version_path(key, game_dir))
