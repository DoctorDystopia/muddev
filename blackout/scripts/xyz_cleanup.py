"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: Operator script. Deletes every object tagged with the z-coordinates
             listed in scripts/map_manifest.json so the maps can be respawned
             from source.

             DESTRUCTIVE. Run deliberately, never import. Everything is behind
             a __main__ guard: this module previously did its deleting at
             import time, so anything that merely imported it -- a linter, a
             doc generator, a test collector walking the package -- silently
             wiped the grid.

Usage:
    ../evenv/Scripts/python.exe scripts/xyz_cleanup.py
"""

import json
import os
import sys

# The game dir (blackout/), one level up from this file in scripts/. Running
# `python scripts/xyz_cleanup.py` puts THIS file's directory on sys.path[0],
# not the caller's cwd -- "server.conf.settings" only resolves if the game
# dir itself is importable, which was true by accident while this script
# lived directly in blackout/ and stopped being true the moment it moved into
# scripts/. Inserting it explicitly makes the script launchable from anywhere.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Single source of truth for which maps a clean-and-reload run applies to.
# Also read by clean_and_reload_all_maps.ps1 and clean_and_reload_all_maps.sh.
_MANIFEST_PATH = os.path.join(_GAME_DIR, "scripts", "map_manifest.json")


def _load_zcoords_from_manifest():
    """
    Purpose: Read the z-coordinates of every map in map_manifest.json.

    Entry:
        None.

    Exit/Returns:
        Returns a list of z-coordinate strings, one per manifest map.

    Module Globals:
        _MANIFEST_PATH

    Methodology:
        Parse the JSON manifest and collect each entry's "zcoord" field.

    Notes/References:
        Deleting the manifest map list here would orphan rooms for maps that
        are still in the database but no longer respawned.

    Author: Nick Hobar
    Creation date: 08/11/2026
    """
    with open(_MANIFEST_PATH, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    return [entry["zcoord"] for entry in data["maps"]]


def _bootstrap_evennia():
    """Bring Django/Evennia up so ObjectDB is usable from a bare script."""
    if _GAME_DIR not in sys.path:
        sys.path.insert(0, _GAME_DIR)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

    import django

    django.setup()

    import evennia

    evennia._init()


def purge_zcoords(zcoords):
    """
    Purpose: Delete every object carrying one of the given map z-tags.

    Entry:
        zcoords is an iterable of z-coordinate strings.

    Exit/Returns:
        Returns the total number of objects deleted.

    Module Globals:
        None

    Methodology:
        Filter ObjectDB on the xyzgrid map tag category, then delete each
        match, reporting failures without aborting the run.

    Notes/References:
        Called by scripts/clean_and_reload_all_maps.ps1 and
        scripts/clean_and_reload_all_maps.sh between `evennia stop` and
        `evennia xyzgrid spawn`. Z-coordinates come from
        scripts/map_manifest.json, not from this function's caller.

    Author: Nick Hobar
    Creation date: 06/17/2026
    """
    from evennia.contrib.grid.xyzgrid.xyzroom import MAP_Z_TAG_CATEGORY
    from evennia.objects.models import ObjectDB

    deleted = 0

    for zcoord in zcoords:
        rooms = ObjectDB.objects.filter(
            db_tags__db_key__iexact=zcoord,
            db_tags__db_category=MAP_Z_TAG_CATEGORY,
        )
        print(f"\nDeleting {rooms.count()} objects tagged '{zcoord}'...")

        for room in rooms:
            try:
                print(f"  #{room.id} '{room.key}' [{room.db_typeclass_path}]")
                room.delete()
                deleted += 1
            except Exception as exc:
                print(f"  Skipping #{room.id} '{room.key}': {exc}")

    return deleted


def main():
    """Entry point. Bootstraps Evennia, then purges the manifest z-coords."""
    _bootstrap_evennia()

    try:
        zcoords = _load_zcoords_from_manifest()
    except (OSError, ValueError, KeyError) as exc:
        print(f"Aborting: could not read map manifest: {exc}")
        sys.exit(1)

    total = purge_zcoords(zcoords)
    print(f"\nDone. Deleted {total} objects.")


if __name__ == "__main__":
    main()
