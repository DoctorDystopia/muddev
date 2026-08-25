"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Owner of the map manifest -- scripts/map_manifest.json, the one
             file an operator edits to add or remove a map from the XYZ grid.
             Parsing and validation live here so the format has exactly one
             reader; the operator scripts stay thin CLIs on top of it.

             Pure data access. Importing this module touches no database and
             boots no Evennia, so it is safe to import from tests.
"""

import json
import os
from dataclasses import dataclass

# The game dir (blackout/), three levels up from world/maps/manifest.py.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SCRIPTS_DIRNAME = "scripts"
_MANIFEST_FILENAME = "map_manifest.json"
_MANIFEST_PATH = os.path.join(_GAME_DIR, _SCRIPTS_DIRNAME, _MANIFEST_FILENAME)

_MAPS_KEY = "maps"
_MODULE_KEY = "module"
_ZCOORD_KEY = "zcoord"


class ManifestError(RuntimeError):
    """Raised when map_manifest.json is missing, malformed or inconsistent."""


@dataclass(frozen=True)
class MapEntry:
    """One manifest row: a map module and the z-coordinate it is expected to declare."""

    module: str
    zcoord: str


def _read_manifest_file(path):
    """
    Purpose: Read and JSON-decode the manifest file.

    Entry:
        path is a filesystem path to a JSON file.

    Exit/Returns:
        Returns the decoded top-level dict.

    Module Globals:
        None

    Methodology:
        Open, decode, then reject anything that is not a JSON object, so the
        callers below can assume dict access is safe.

    Notes/References:
        Every failure is re-raised as ManifestError so a caller only has to
        catch one exception type.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise ManifestError(f"Could not read map manifest {path}: {exc}") from exc
    except ValueError as exc:
        raise ManifestError(f"Map manifest {path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError(f"Map manifest {path} must hold a JSON object at the top level.")

    return data


def _entry_from_raw(raw_entry, path, index):
    """
    Purpose: Validate one raw manifest row and convert it to a MapEntry.

    Entry:
        raw_entry is the decoded JSON value at position index of the "maps"
        list; path is the manifest path, used only in error text.

    Exit/Returns:
        Returns a MapEntry. Raises ManifestError if either field is missing or
        is not a non-blank string.

    Module Globals:
        _MODULE_KEY, _ZCOORD_KEY

    Methodology:
        Check the row is a dict, pull both fields, strip surrounding
        whitespace, and reject blanks.

    Notes/References:
        The strip() is not cosmetic. A stray carriage return in either field
        would otherwise reach `xyzgrid add` as part of the module path and
        fail with a message whose own '\\r' scrolls the error off the line.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    location = f"{path} entry #{index}"

    if not isinstance(raw_entry, dict):
        raise ManifestError(f"{location} must be an object, got {type(raw_entry).__name__}.")

    module = raw_entry.get(_MODULE_KEY)
    zcoord = raw_entry.get(_ZCOORD_KEY)

    if not isinstance(module, str) or not module.strip():
        raise ManifestError(f"{location} has no non-empty '{_MODULE_KEY}' string.")

    if not isinstance(zcoord, str) or not zcoord.strip():
        raise ManifestError(f"{location} has no non-empty '{_ZCOORD_KEY}' string.")

    return MapEntry(module=module.strip(), zcoord=zcoord.strip())


def get_manifest_path():
    """
    Purpose: Report where the manifest lives.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the absolute path of scripts/map_manifest.json.

    Module Globals:
        _MANIFEST_PATH read

    Notes/References:
        Callers print this path; they must not rebuild it themselves.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    return _MANIFEST_PATH


def load_entries(path=None):
    """
    Purpose: Read every map row from the manifest.

    Entry:
        path is a manifest path, or None to use the repo's own manifest.

    Exit/Returns:
        Returns a list of MapEntry in manifest order. Raises ManifestError if
        the file is unreadable, has no non-empty "maps" list, holds a
        malformed row, or lists one z-coordinate twice.

    Module Globals:
        _MANIFEST_PATH, _MAPS_KEY read

    Methodology:
        Decode the file, then validate each row in turn, tracking the
        z-coordinates already claimed.

    Notes/References:
        Duplicate z-coordinates are fatal rather than merged: two rows
        claiming one z-coordinate means a rebuild would purge a map's rooms
        after the map that owns them was already registered.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    manifest_path = path
    if manifest_path is None:
        manifest_path = _MANIFEST_PATH

    data = _read_manifest_file(manifest_path)
    raw_maps = data.get(_MAPS_KEY)

    if not isinstance(raw_maps, list) or not raw_maps:
        raise ManifestError(f"Map manifest {manifest_path} has no non-empty '{_MAPS_KEY}' list.")

    entries = []
    claimed_by = {}

    for index, raw_entry in enumerate(raw_maps):
        entry = _entry_from_raw(raw_entry, manifest_path, index)
        owner = claimed_by.get(entry.zcoord)

        if owner is not None:
            raise ManifestError(
                f"{manifest_path} lists z-coordinate '{entry.zcoord}' twice "
                f"('{owner}' and '{entry.module}')."
            )

        claimed_by[entry.zcoord] = entry.module
        entries.append(entry)

    return entries


def zcoords_of(entries):
    """
    Purpose: Project the z-coordinates out of a list of manifest entries.

    Entry:
        entries is an iterable of MapEntry.

    Exit/Returns:
        Returns a list of z-coordinate strings in the same order.

    Module Globals:
        None

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    zcoords = [entry.zcoord for entry in entries]

    return zcoords


def modules_of(entries):
    """
    Purpose: Project the module paths out of a list of manifest entries.

    Entry:
        entries is an iterable of MapEntry.

    Exit/Returns:
        Returns a list of python module path strings in the same order.

    Module Globals:
        None

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    modules = [entry.module for entry in entries]

    return modules
