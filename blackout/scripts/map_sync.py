"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Operator script. Reconciles the live XYZ grid with
             scripts/map_manifest.json, so that editing that one file is the
             whole of adding or removing a map:

               - a map listed in the manifest is loaded from its module, its
                 old objects are wiped, and it is (re)registered and spawned;
               - a map still present in the world but no longer listed is
                 removed outright, along with its rooms and exits.

             The removal half is what the manifest could not do before. The
             grid keeps its own copy of every map ever passed to
             `xyzgrid add`, so dropping a manifest row used to leave the map
             registered and spawning; its surviving rooms then collided with
             the respawn ("XYRoom XYZ=(...) already exists").

             The DATABASE, not the grid Script, is what this reconciles
             against. Diffing `grid.db.map_data` alone left a whole class of
             map permanently invisible: one dropped from the manifest while
             the grid had already forgotten it is in neither list, so nothing
             ever reaped it. That was not theoretical -- 'trade town sector 1'
             sat in the development database as 59 live rooms and 144 exits,
             belonging to no map, unreachable by any rebuild, until this was
             fixed on 08/28/2026.

             The spawn is run here rather than by the calling shell script.
             `evennia xyzgrid spawn` asks for confirmation on stdin
             (contrib/grid/xyzgrid/launchcmd.py) and offers no way to decline
             the question, so the rebuild could not run unattended; and its
             exit code was never checked, so a failed spawn still printed
             "Done". Doing it in-process also means Evennia is bootstrapped
             once instead of twice.

             A character standing on a purged room falls through to its
             `home`, which is Limbo for every character in this game --
             see relocate_stranded_characters. This script walks every
             character afterwards and moves anyone left off the grid to
             world.respawn's respawn room, so a rebuild never strands a
             player somewhere with no way back to the game world.

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

# The Tag.db_model value Evennia files object tags under.
_OBJECT_TAG_MODEL = "objectdb"


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


def _objects_tagged_zcoord(zcoord):
    """Every object carrying `zcoord` as its xyzgrid map z-tag, as a queryset."""
    from evennia.contrib.grid.xyzgrid.xyzroom import MAP_Z_TAG_CATEGORY
    from evennia.objects.models import ObjectDB

    return ObjectDB.objects.filter(
        db_tags__db_key__iexact=zcoord,
        db_tags__db_category=MAP_Z_TAG_CATEGORY,
    )


def _total_object_count():
    """The number of rows in ObjectDB, for reporting a rebuild's net effect."""
    from evennia.objects.models import ObjectDB

    return ObjectDB.objects.count()


def zcoords_in_world(grid):
    """
    Purpose: Every z-coordinate the world still knows about, from either the
             grid's registry or the database itself.

    Entry:
        grid is the XYZGrid Script.

    Exit/Returns:
        Returns a sorted list of z-coordinate strings.

    Module Globals:
        _OBJECT_TAG_MODEL read.

    Methodology:
        Union the grid's stored map_data keys with the z-tag values that live
        objects actually carry, so neither source can hide a map from the
        prune on its own.

    Notes/References:
        Candidate tags come from the Tag table and are then confirmed against
        ObjectDB, because Evennia never garbage-collects a Tag row -- a tag
        with no objects left would otherwise be reported as a map to remove.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    from evennia.contrib.grid.xyzgrid.xyzroom import MAP_Z_TAG_CATEGORY
    from evennia.typeclasses.tags import Tag

    found = set(grid.db.map_data or {})

    candidates = Tag.objects.filter(
        db_category=MAP_Z_TAG_CATEGORY,
        db_model=_OBJECT_TAG_MODEL,
    ).values_list("db_key", flat=True)

    for zcoord in candidates:
        tagged = _objects_tagged_zcoord(zcoord)
        in_use = tagged.exists()
        if in_use:
            found.add(zcoord)

    return sorted(found)


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
        Diff every z-coordinate the world knows about -- registered on the
        grid OR merely tagged on live objects -- against the manifest, then
        call XYZGrid.remove_map on each survivor of the diff.

    Notes/References:
        remove_map finds its rooms with a database query rather than through
        map_data, so it removes a map the grid has already forgotten just as
        happily as one it still holds. That is what lets the union above be
        acted on with a single call.

        `evennia xyzgrid delete <zcoord>` is not usable here: launchcmd's
        _option_delete builds its zcoords as a generator, exhausts it while
        validating, and then unpacks the spent generator into remove_map --
        so it deletes nothing. Calling remove_map directly avoids that.

        Characters standing in a removed room are sent to their home
        locations; everything else on the tile is destroyed with it. That
        split lives in systems/spawning/teardown.py, reached through
        GridTile.at_object_delete -- not here, because the contrib deletes
        rooms by two other paths this script cannot see.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    prefix = _LIVE_PREFIX
    if dry_run:
        prefix = _DRY_RUN_PREFIX

    known_zcoords = zcoords_in_world(grid)
    unlisted = [zcoord for zcoord in known_zcoords if zcoord not in wanted_zcoords]

    for zcoord in unlisted:
        tagged = _objects_tagged_zcoord(zcoord)
        count = tagged.count()
        print(f"  {prefix}removing unlisted map '{zcoord}' ({count} tagged objects)")

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
        Runs between `evennia stop` and the spawn. The tag query catches exits
        as well as rooms, since both carry the z-tag.

        Deleting a room now takes its NPCs, nodes, facilities and floor litter
        with it -- see GridTile.at_object_delete and
        systems/spawning/teardown.py. Those are not counted here: the tally is
        of tagged objects this loop asked to delete, and the run's true effect
        is reported as an ObjectDB delta by _sync.

        The count is of deletions that actually happened, not of attempts.
        Deleting a room destroys the exits standing in it, so by the time the
        loop reaches one of those its `delete()` returns False without raising
        -- which the old unconditional `deleted += 1` reported as a deletion.

    Author: Nick Hobar
    Creation date: 06/17/2026
    """
    prefix = _LIVE_PREFIX
    if dry_run:
        prefix = _DRY_RUN_PREFIX

    deleted = 0

    for zcoord in zcoords:
        tagged = _objects_tagged_zcoord(zcoord)
        count = tagged.count()
        print(f"  {prefix}purging {count} objects tagged '{zcoord}'")

        if dry_run:
            deleted += count
            continue

        for obj in tagged:
            try:
                removed = obj.delete()
                if removed:
                    deleted += 1
            except Exception as exc:
                print(f"    skipping #{obj.id} '{obj.key}': {exc}")

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


def spawn_maps(grid, dry_run):
    """
    Purpose: Build the in-game rooms and exits for every registered map.

    Entry:
        grid is the XYZGrid Script, already carrying the manifest's maps;
        dry_run suppresses the spawn.

    Exit/Returns:
        Returns None. Propagates whatever the contrib raises.

    Module Globals:
        _DRY_RUN_PREFIX, _LIVE_PREFIX read

    Methodology:
        Call XYZGrid.spawn over the full wildcard coordinate, which creates
        missing rooms, updates existing ones from their prototypes and deletes
        any that no longer appear on their map.

    Notes/References:
        This is what `evennia xyzgrid spawn` does once its confirmation prompt
        is answered. Calling the grid directly is not a shortcut around an
        operator safeguard -- the prompt guards an interactive typo, and this
        script has already read a manifest, validated every module and printed
        what it is about to do. It IS the safeguard, and unlike the prompt it
        also works when nothing is attached to stdin.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    prefix = _LIVE_PREFIX
    if dry_run:
        prefix = _DRY_RUN_PREFIX

    print(f"  {prefix}spawning rooms and exits for every registered map")

    if dry_run:
        return

    grid.spawn()


def relocate_stranded_characters(dry_run):
    """
    Purpose: Move every player character left off the grid to the respawn
             room, after a rebuild has purged and respawned the maps.

    Entry:
        dry_run is True to report without moving anyone.

    Exit/Returns:
        Returns the number of characters relocated (or that would be).

    Module Globals:
        _DRY_RUN_PREFIX, _LIVE_PREFIX read

    Methodology:
        A character standing in a purged room falls through
        GridTile.at_object_delete -> clear_contents to its `home`, which is
        Limbo (settings.DEFAULT_HOME) for every character in this game --
        nothing in typeclasses/characters.py sets Character.home to anything
        else. So once purge_zcoords and spawn_maps have run, any character
        not standing on a live grid room is one this rebuild displaced. Move
        it to world.respawn's respawn room and re-home it there too, so the
        next rebuild does not send it back to Limbo either.

    Notes/References:
        isinstance(location, XYZRoom), not a Limbo dbref comparison, is what
        catches a character with no location at all as well as one sitting
        in Limbo -- both read as "not on the grid".

        Runs after spawn_maps so the respawn room already exists.
        get_respawn_room degrades to None rather than raising if it does
        not, and this function reports that and does nothing rather than
        aborting a rebuild that otherwise succeeded.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom

    from typeclasses.characters import Character
    from world.respawn import get_respawn_room

    prefix = _LIVE_PREFIX
    if dry_run:
        prefix = _DRY_RUN_PREFIX

    respawn_room = get_respawn_room()
    if respawn_room is None:
        print(f"  {prefix}no respawn room found; leaving stranded characters where they are")
        return 0

    relocated = 0

    for char in Character.objects.all():
        on_grid = isinstance(char.location, XYZRoom)
        if on_grid:
            continue

        print(f"  {prefix}relocating '{char.key}' to the respawn room")

        if dry_run:
            relocated += 1
            continue

        char.move_to(respawn_room, quiet=True, move_type="teleport")
        char.home = respawn_room
        relocated += 1

    return relocated


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
        the unlisted maps, purge the listed ones, register them and spawn.

    Notes/References:
        Loading comes first on purpose: nothing is deleted until every listed
        module has proven it exists and declares the promised z-coordinate.

        The net ObjectDB delta is reported because the per-step tallies no
        longer describe the run. A purged room now destroys everything
        standing on it, and those objects are counted by neither loop -- a
        rebuild that says "purged 945 objects" while removing 1013 rows is
        telling an operator something they cannot act on.

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
    objects_before = _total_object_count()

    print(f"Manifest lists {len(entries)} map(s): {', '.join(zcoords)}")

    print("=== Removing maps no longer in the manifest ===")
    pruned = prune_unlisted_maps(grid, zcoords, dry_run)
    if not pruned:
        print("  none")

    print("=== Purging objects of listed maps ===")
    purged = purge_zcoords(zcoords, dry_run)

    print("=== Registering listed maps ===")
    register_maps(grid, map_data_list, dry_run)

    print("=== Spawning rooms and exits ===")
    spawn_maps(grid, dry_run)

    print("=== Relocating stranded player characters ===")
    relocated = relocate_stranded_characters(dry_run)
    if not relocated:
        print("  none")

    objects_after = _total_object_count()
    net = objects_after - objects_before

    print(
        f"Removed {len(pruned)} map(s), purged {purged} tagged object(s), "
        f"relocated {relocated} character(s)."
    )
    print(f"ObjectDB: {objects_before} -> {objects_after} ({net:+d}).")


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
