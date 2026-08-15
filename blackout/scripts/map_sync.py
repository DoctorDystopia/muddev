"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Operator script. Reconciles the live XYZ grid with
             scripts/map_manifest.json, so that editing that one file is the
             whole of adding or removing a map:

               - a map listed in the manifest is loaded from its module, its
                 old objects are wiped, and it is (re)registered on the grid,
                 ready for `evennia xyzgrid spawn`;
               - a map still registered on the grid but no longer listed is
                 removed outright, along with its rooms and exits.

             The removal half is what the manifest could not do before. The
             grid keeps its own copy of every map ever passed to
             `xyzgrid add`, so dropping a manifest row used to leave the map
             registered and spawning; its surviving rooms then collided with
             the respawn ("XYRoom XYZ=(...) already exists").

             DESTRUCTIVE. Run deliberately, never import. Everything is behind
             an `if __name__ == "__main__"` guard: anything that merely
             imports a module in this directory -- a linter, a doc generator,
             a test collector walking the package -- must not be able to wipe
             the grid.

Usage:
    ../evenv/Scripts/python.exe scripts/map_sync.py [--dry-run]

    --dry-run reports what would be removed, purged and registered, and
    changes nothing. It is read-only, so it is safe with the server running.
"""

import os
import sys

# The game dir (blackout/), one level up from this file in scripts/. Running
# `python scripts/map_sync.py` puts THIS file's directory on sys.path[0], not
# the caller's cwd -- "server.conf.settings" and "world.maps.manifest" only
# resolve if the game dir itself is importable. Inserting it explicitly makes
# the script launchable from anywhere.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DRY_RUN_FLAG = "--dry-run"
_DRY_RUN_PREFIX = "[dry run] "
_LIVE_PREFIX = ""


def _bootstrap_evennia():
    """Bring Django/Evennia up so ObjectDB and the grid Script are usable."""
    if _GAME_DIR not in sys.path:
        sys.path.insert(0, _GAME_DIR)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

    import django

    django.setup()

    import evennia

    evennia._init()


def _get_grid():
    """Fetch the XYZGrid Script, echoing the grid's own log lines to console."""
    from evennia.contrib.grid.xyzgrid.xyzgrid import get_xyzgrid

    grid = get_xyzgrid()
    grid.log = print

    return grid


def load_map_data(grid, entries):
    """
    Purpose: Load each manifest module's map data and confirm it declares the
             z-coordinate the manifest promised.

    Entry:
        grid is the XYZGrid Script; entries is a list of manifest MapEntry.

    Exit/Returns:
        Returns a list of map-data dicts ready for XYZGrid.add_maps. Raises
        RuntimeError if a module yields no map, or declares anything other
        than exactly the manifest's z-coordinate.

    Module Globals:
        None

    Methodology:
        Ask the grid to import each module, then compare the z-coordinates it
        declared against the single one the manifest row claims.

    Notes/References:
        This runs before anything is deleted, so a typo in the manifest costs
        an error message rather than a half-rebuilt grid. `xyzgrid add` itself
        cannot be trusted for this: it prints its complaint and still exits 0,
        which is how a trailing carriage return in a module path once dropped
        a map from a rebuild silently.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    map_data_list = []

    for entry in entries:
        maps = grid.maps_from_module(entry.module)

        if not maps:
            raise RuntimeError(
                f"Manifest module '{entry.module}' yielded no map data. Check the "
                "module path and that it defines XYMAP_DATA or XYMAP_DATA_LIST."
            )

        declared = [mapdata.get("zcoord") for mapdata in maps]

        if declared != [entry.zcoord]:
            raise RuntimeError(
                f"Manifest lists '{entry.module}' as z-coordinate '{entry.zcoord}', "
                f"but the module declares {declared}. One manifest row means one map; "
                "give every map its own row, matching the zcoord in its module."
            )

        map_data_list.extend(maps)

    return map_data_list


def prune_unlisted_maps(grid, wanted_zcoords, dry_run):
    """
    Purpose: Remove maps that the grid still holds but the manifest no longer
             lists, together with their rooms and exits.

    Entry:
        grid is the XYZGrid Script; wanted_zcoords is the manifest's list of
        z-coordinates; dry_run suppresses the actual removal.

    Exit/Returns:
        Returns the list of z-coordinates removed (or that would be).

    Module Globals:
        _DRY_RUN_PREFIX, _LIVE_PREFIX read

    Methodology:
        Diff the grid's stored map_data keys against the manifest, then call
        XYZGrid.remove_map on each survivor of the diff.

    Notes/References:
        `evennia xyzgrid delete <zcoord>` is not usable here: launchcmd's
        _option_delete builds its zcoords as a generator, exhausts it while
        validating, and then unpacks the spent generator into remove_map --
        so it deletes nothing. Calling remove_map directly avoids that.

        Objects and characters standing in a removed room are sent to their
        home locations by the contrib, not deleted.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    prefix = _LIVE_PREFIX
    if dry_run:
        prefix = _DRY_RUN_PREFIX

    stored_zcoords = list(grid.db.map_data or {})
    unlisted = [zcoord for zcoord in stored_zcoords if zcoord not in wanted_zcoords]

    for zcoord in unlisted:
        print(f"  {prefix}removing unlisted map '{zcoord}' and every object on it")

        if not dry_run:
            grid.remove_map(zcoord, remove_objects=True)

    return unlisted


def purge_zcoords(zcoords, dry_run):
    """
    Purpose: Delete every object carrying one of the given map z-tags, so the
             listed maps respawn from source instead of colliding.

    Entry:
        zcoords is an iterable of z-coordinate strings; dry_run suppresses the
        deletion.

    Exit/Returns:
        Returns the total number of objects deleted (or that would be).

    Module Globals:
        _DRY_RUN_PREFIX, _LIVE_PREFIX read

    Methodology:
        Filter ObjectDB on the xyzgrid map z-tag category, then delete each
        match, reporting failures without aborting the run.

    Notes/References:
        Runs between `evennia stop` and `evennia xyzgrid spawn`, driven by
        scripts/clean_and_reload_all_maps.ps1 and .sh. The tag query catches
        exits as well as rooms, since both carry the z-tag.

    Author: Nick Hobar
    Creation date: 06/17/2026
    """
    from evennia.contrib.grid.xyzgrid.xyzroom import MAP_Z_TAG_CATEGORY
    from evennia.objects.models import ObjectDB

    prefix = _LIVE_PREFIX
    if dry_run:
        prefix = _DRY_RUN_PREFIX

    deleted = 0

    for zcoord in zcoords:
        rooms = ObjectDB.objects.filter(
            db_tags__db_key__iexact=zcoord,
            db_tags__db_category=MAP_Z_TAG_CATEGORY,
        )
        count = rooms.count()
        print(f"  {prefix}purging {count} objects tagged '{zcoord}'")

        if dry_run:
            deleted += count
            continue

        for room in rooms:
            try:
                room.delete()
                deleted += 1
            except Exception as exc:
                print(f"    skipping #{room.id} '{room.key}': {exc}")

    return deleted


def register_maps(grid, map_data_list, dry_run):
    """
    Purpose: (Re)register the manifest's maps on the grid and verify they took.

    Entry:
        grid is the XYZGrid Script; map_data_list comes from load_map_data;
        dry_run suppresses the registration.

    Exit/Returns:
        Returns None. Raises RuntimeError if a map is absent from the grid's
        stored map_data afterwards.

    Module Globals:
        None

    Methodology:
        Hand every map dict to add_maps in one call, reload the grid so the
        map strings are parsed, then read the stored keys back.

    Notes/References:
        The read-back is the point. add_maps is silent about what it stored,
        and a rebuild that quietly registers fewer maps than the manifest
        lists is exactly the failure this script exists to prevent.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    zcoords = [mapdata.get("zcoord") for mapdata in map_data_list]

    for zcoord in zcoords:
        print(f"  registering map '{zcoord}'")

    if dry_run:
        return

    grid.add_maps(*map_data_list)
    grid.reload()

    stored_zcoords = grid.db.map_data or {}
    missing = [zcoord for zcoord in zcoords if zcoord not in stored_zcoords]

    if missing:
        raise RuntimeError(f"Maps missing from the grid after add_maps: {missing}")


def _sync(dry_run):
    """
    Purpose: Run the whole manifest-to-grid reconciliation.

    Entry:
        dry_run is True to report without changing anything.

    Exit/Returns:
        Returns None. Raises ManifestError or RuntimeError on any failure.

    Module Globals:
        None

    Methodology:
        Read and validate the manifest, load every listed module, then prune
        the unlisted maps, purge the listed ones, and register them.

    Notes/References:
        Loading comes first on purpose: nothing is deleted until every listed
        module has proven it exists and declares the promised z-coordinate.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    from world.maps import manifest as map_manifest

    manifest_path = map_manifest.get_manifest_path()
    print(f"=== Reading {manifest_path} ===")

    entries = map_manifest.load_entries()
    zcoords = map_manifest.zcoords_of(entries)
    grid = _get_grid()
    map_data_list = load_map_data(grid, entries)

    print(f"Manifest lists {len(entries)} map(s): {', '.join(zcoords)}")

    print("=== Removing maps no longer in the manifest ===")
    pruned = prune_unlisted_maps(grid, zcoords, dry_run)
    if not pruned:
        print("  none")

    print("=== Purging objects of listed maps ===")
    purged = purge_zcoords(zcoords, dry_run)

    print("=== Registering listed maps ===")
    register_maps(grid, map_data_list, dry_run)

    print(f"Removed {len(pruned)} map(s), purged {purged} object(s).")


def main(argv):
    """Entry point. Bootstraps Evennia, then syncs the grid to the manifest."""
    dry_run = _DRY_RUN_FLAG in argv

    _bootstrap_evennia()

    try:
        _sync(dry_run)
    except Exception as exc:
        print(f"Aborting: {exc}")
        sys.exit(1)

    if dry_run:
        print("Dry run: nothing was changed.")


if __name__ == "__main__":
    main(sys.argv[1:])
