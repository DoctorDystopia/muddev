"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: Operator script. Deletes every object tagged with the configured
             XYZGrid z-coordinates so the maps can be respawned from source.

             DESTRUCTIVE. Run deliberately, never import. Everything is behind
             a __main__ guard: this module previously did its deleting at
             import time, so anything that merely imported it -- a linter, a
             doc generator, a test collector walking the package -- silently
             wiped the grid.

Usage:
    ../evenv/Scripts/python.exe scripts/xyz_cleanup.py
"""

import os
import sys

# Public constant definitions
ZCOORDS_TO_CLEAN = [
    "oasis",
    # "trade town sector 1",
]

# The game dir (blackout/), one level up from this file in scripts/. Running
# `python scripts/xyz_cleanup.py` puts THIS file's directory on sys.path[0],
# not the caller's cwd -- "server.conf.settings" only resolves if the game
# dir itself is importable, which was true by accident while this script
# lived directly in blackout/ and stopped being true the moment it moved into
# scripts/. Inserting it explicitly makes the script launchable from anywhere.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
        Called by scripts/clean_and_reload_all_maps.ps1 between `evennia
        stop` and `evennia xyzgrid spawn`.

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
    """Entry point. Bootstraps Evennia, then purges ZCOORDS_TO_CLEAN."""
    _bootstrap_evennia()
    total = purge_zcoords(ZCOORDS_TO_CLEAN)
    print(f"\nDone. Deleted {total} objects.")


if __name__ == "__main__":
    main()
