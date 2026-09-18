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

             A run is SCOPED by --map and --tile. Without either flag it
             rebuilds every map in the manifest, which is what it always did.
             With them it purges and respawns only what the operator named, so
             a one-tile edit no longer pays for the largest map on the grid.
             world/maps/scope.py owns the flag format and the resolution
             rules; this script only acts on the RebuildScope it returns.

             Only an UNSCOPED run prunes. Removing a map is about maps that
             are listed nowhere, and a run told to touch one map must not
             reach a second one on its own.

             A tile-scoped run repairs its neighbours. Deleting a room takes
             the exits INTO it with it (DefaultObject.clear_exits), and those
             exits belong to the neighbouring nodes, not to the rebuilt tile.
             So the link pass covers every node on the grid whose links end on
             a rebuilt tile -- see spawn_scope.

Usage:
    ../evenv/Scripts/python.exe scripts/map_sync.py [--dry-run]
        [--map ZCOORD ...] [--tile ZCOORD:X,Y ...]

    --dry-run reports what would be removed, purged and registered, and
    changes nothing. It is read-only, so it is safe with the server running.

    --map rebuilds one listed map end to end. Repeat it for several maps.

    --tile rebuilds one tile of one map, with its exits and the exits of its
    neighbours. Repeat it for several tiles. A map named by both flags is
    rebuilt whole.
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
_MAP_FLAG = "--map"
_TILE_FLAG = "--tile"
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

    # Import the tile typeclass, so that XYZRoom.__subclasses__() knows about
    # it. The contrib's own filter_family builds its typeclass list from that
    # call, and XYMap.spawn_nodes uses it to delete rooms that fell off the
    # map. Left unimported, that cleanup finds nothing and reports success.
    import typeclasses.rooms  # noqa: F401


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


def _objects_at_xyz(zcoord, x, y):
    """
    Purpose: Every object standing at one map coordinate, as a queryset.

    Entry:
        zcoord is a map name; x and y are map coordinates.

    Exit/Returns:
        Returns an ObjectDB queryset.

    Module Globals:
        None

    Methodology:
        Filter ObjectDB on all three xyzgrid coordinate tag categories at once.

    Notes/References:
        ObjectDB and the tag table, NOT XYZRoom.objects.filter_xyz. The
        contrib's manager calls filter_family, which builds its typeclass list
        from XYZRoom.__subclasses__() -- so it finds a GridTile only if
        something already imported typeclasses.rooms. An operator script that
        has not imported it gets an empty queryset and reports a tile as
        already clean. This query cannot go wrong that way, for the same
        reason _objects_tagged_zcoord does not.

        This catches the exits OUT of the tile as well as the room, because an
        XYZExit carries its source room's coordinates. The exits INTO the tile
        carry their own source coordinates and are destroyed by clear_exits
        when the room goes.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    from evennia.contrib.grid.xyzgrid.xyzroom import (
        MAP_X_TAG_CATEGORY,
        MAP_Y_TAG_CATEGORY,
        MAP_Z_TAG_CATEGORY,
    )
    from evennia.objects.models import ObjectDB

    return (
        ObjectDB.objects.filter(
            db_tags__db_key__iexact=zcoord,
            db_tags__db_category=MAP_Z_TAG_CATEGORY,
        )
        .filter(db_tags__db_key=str(x), db_tags__db_category=MAP_X_TAG_CATEGORY)
        .filter(db_tags__db_key=str(y), db_tags__db_category=MAP_Y_TAG_CATEGORY)
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


def validate_scope_tiles(grid, scope, map_data_list):
    """
    Purpose: Confirm that every tile the operator named is really a node on
             its map, before anything is deleted.

    Entry:
        grid is the XYZGrid Script; scope is a RebuildScope; map_data_list
        comes from load_map_data.

    Exit/Returns:
        Returns None. Raises RuntimeError naming the first tile that is not a
        node on its map.

    Module Globals:
        None

    Methodology:
        Parse a THROWAWAY XYMap from the map data just loaded, and ask it for
        a node at each coordinate.

    Notes/References:
        The parse is against the map data on disk, not against the grid's
        stored copy. That is what makes a dry run and a live run give the same
        answer for a tile the operator added to the map string one minute ago:
        the stored copy is still the previous map, and only a live run may
        replace it.

        calculate_path_matrix is deliberately not called. Node lookup does not
        need the pathfinding solution, and baking one for a validation pass
        would cost more than the rebuild it guards.

        A tile with no node is an error rather than a no-op. spawn_nodes
        silently spawns nothing for a coordinate that carries no node, so an
        operator mistyping a coordinate would otherwise watch a rebuild report
        success while changing nothing.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    from evennia.contrib.grid.xyzgrid.xymap import XYMap

    if not scope.tiles:
        return

    by_zcoord = {mapdata.get("zcoord"): mapdata for mapdata in map_data_list}

    for zcoord in scope.zcoords:
        tiles = scope.tiles_of(zcoord)
        if not tiles:
            continue

        xymap = XYMap(dict(by_zcoord[zcoord]), Z=zcoord, xyzgrid=grid)
        xymap.parse()

        for tile in tiles:
            try:
                node = xymap.get_node_from_coord(tile.xy)
            except Exception as exc:
                raise RuntimeError(f"Tile ({tile.x},{tile.y}) on map '{zcoord}': {exc}") from exc

            if node is None:
                raise RuntimeError(
                    f"Map '{zcoord}' has no room at ({tile.x},{tile.y}). "
                    "Check the coordinate against the map string."
                )


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
        split lives in systems/gameplay/spawning/teardown.py, reached through
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
        systems/gameplay/spawning/teardown.py. Those are not counted here: the tally is
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


def purge_tiles(tiles, dry_run):
    """
    Purpose: Delete the room standing at each named tile, so that tile
             respawns from source instead of being updated in place.

    Entry:
        tiles is an iterable of scope.TileRef; dry_run suppresses the deletion.

    Exit/Returns:
        Returns the number of rooms deleted (or that would be).

    Module Globals:
        _DRY_RUN_PREFIX, _LIVE_PREFIX read

    Methodology:
        Look the room up by its XYZ coordinate and delete it. Everything
        standing on it goes with it through GridTile.at_object_delete.

    Notes/References:
        The room is DELETED rather than respawned over the top of itself, and
        that is the whole reason a tile rebuild works. Evennia fires
        at_object_post_spawn only when a prototype update actually changes the
        object (see prototypes/spawner.py), so an unchanged tile would keep
        its old shopkeep, node or facility and the operator would see no
        effect. A fresh room always changes, so its spawners always run.

        The queryset is materialised before the loop. Deleting a room destroys
        the exits standing in it, and those exits are in the same queryset --
        so a lazy queryset would be re-evaluated mid-deletion.

        A missing room is not an error. The coordinate was already checked
        against the map by validate_scope_tiles, so nothing there simply means
        the tile was never built, and the spawn will build it.

        The count is of deletions that actually happened, matching
        purge_zcoords: an exit already destroyed with its room returns False
        from delete() without raising.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    prefix = _LIVE_PREFIX
    if dry_run:
        prefix = _DRY_RUN_PREFIX

    deleted = 0

    for tile in tiles:
        standing = list(_objects_at_xyz(tile.zcoord, tile.x, tile.y))
        print(
            f"  {prefix}purging tile ({tile.x},{tile.y}) on '{tile.zcoord}': "
            f"{len(standing)} object(s)"
        )

        if dry_run:
            deleted += len(standing)
            continue

        for obj in standing:
            try:
                removed = obj.delete()
                if removed:
                    deleted += 1
            except Exception as exc:
                print(f"    skipping #{obj.id} '{obj.key}': {exc}")

    return deleted


def purge_scope(scope, dry_run):
    """
    Purpose: Delete everything the scope says this run rebuilds.

    Entry:
        scope is a RebuildScope; dry_run suppresses the deletion.

    Exit/Returns:
        Returns the total number of objects deleted (or that would be).

    Module Globals:
        None

    Methodology:
        Send the whole maps through the z-tag purge and the individual tiles
        through the coordinate purge, and add the two tallies.

    Notes/References:
        The two purges cannot be merged. A whole map is found by its z-tag,
        which catches its exits and anything else the map ever tagged. A tile
        is found by its XYZ coordinate, because a z-tag query would take the
        entire map with it.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    deleted = purge_zcoords(scope.whole_maps, dry_run)
    deleted += purge_tiles(scope.tiles, dry_run)

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


def neighbours_of_tiles(grid, tiles):
    """
    Purpose: Find every node on the grid whose exits lead INTO one of the
             rebuilt tiles.

    Entry:
        grid is the XYZGrid Script, reloaded and parsed; tiles is an iterable
        of scope.TileRef.

    Exit/Returns:
        Returns a dict of z-coordinate to a list of MapNode.

    Module Globals:
        None

    Methodology:
        Walk every node of every parsed map and read MapNode.links, which maps
        a direction to the node that link ENDS on. A node with any link ending
        on a rebuilt tile is a neighbour whose exits need respawning.

    Notes/References:
        Deleting a room destroys the exits pointing at it as well as the exits
        leading out of it (DefaultObject.clear_exits). The exits leading out
        come back with the tile. The exits pointing at it belong to other
        nodes, and the contrib only respawns links for the nodes it is asked
        about -- so without this pass, a tile rebuild leaves its neighbours
        one-way and the map looks correct while the player cannot walk back.

        Every map is scanned, not just the tile's own. The xyzgrid links maps
        to each other, so a neighbour is not always on the same map.

        Reading links is pure memory work on already-parsed maps. Only the
        matched nodes cost a database write.

        A node that is itself a rebuilt tile is skipped. Its own links are
        already in the main spawn pass, and spawning them twice would double
        the work for no effect.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    targets = {(tile.zcoord, tile.x, tile.y) for tile in tiles}
    found = {}

    if not targets:
        return found

    for zcoord, xymap in grid.grid.items():
        for node in xymap.node_index_map.values():
            is_target = (node.Z, node.X, node.Y) in targets
            if is_target:
                continue

            ends = [(end.Z, end.X, end.Y) for end in node.links.values()]
            leads_in = any(end in targets for end in ends)

            if leads_in:
                found.setdefault(zcoord, []).append(node)

    return found


def spawn_scope(grid, scope, dry_run):
    """
    Purpose: Build the in-game rooms and exits for everything the scope covers.

    Entry:
        grid is the XYZGrid Script, already carrying the manifest's maps;
        scope is a RebuildScope; dry_run suppresses the spawn.

    Exit/Returns:
        Returns None. Propagates whatever the contrib raises.

    Module Globals:
        _DRY_RUN_PREFIX, _LIVE_PREFIX read

    Methodology:
        Three passes, in order: every room in scope, then every exit out of
        those rooms, then every exit leading back into a rebuilt tile.

    Notes/References:
        ALL rooms before ANY exit, across every map in scope. An exit needs
        its destination to exist, and the xyzgrid links maps to each other, so
        finishing one map before starting the next would leave a cross-map
        exit pointing at a room that is still one pass away. XYZGrid.spawn
        takes the same two passes for the same reason, and an unscoped run
        here does exactly what XYZGrid.spawn does.

        The wildcard pass over a whole map also deletes rooms that fell off
        the map string. The tile pass cannot: it is told one coordinate, and a
        room that no longer appears on the map is at a coordinate the operator
        did not name. That is the one job a tile rebuild leaves to a full one.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    prefix = _LIVE_PREFIX
    if dry_run:
        prefix = _DRY_RUN_PREFIX

    print(f"  {prefix}spawning rooms and exits for {scope.describe()}")

    if dry_run:
        return

    wildcard = "*"

    for zcoord in scope.zcoords:
        xymap = grid.get_map(zcoord)
        whole = scope.is_whole_map(zcoord)

        if whole:
            xymap.spawn_nodes(xy=(wildcard, wildcard))
            continue

        for tile in scope.tiles_of(zcoord):
            xymap.spawn_nodes(xy=tile.xy)

    for zcoord in scope.zcoords:
        xymap = grid.get_map(zcoord)
        whole = scope.is_whole_map(zcoord)

        if whole:
            xymap.spawn_links(xy=(wildcard, wildcard))
            continue

        for tile in scope.tiles_of(zcoord):
            xymap.spawn_links(xy=tile.xy)

    neighbours = neighbours_of_tiles(grid, scope.tiles)

    for zcoord, nodes in neighbours.items():
        print(f"  restoring exits into rebuilt tiles from {len(nodes)} node(s) on '{zcoord}'")
        grid.get_map(zcoord).spawn_links(nodes=nodes)


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


def _sync(scope, dry_run):
    """
    Purpose: Run the manifest-to-grid reconciliation over one scope.

    Entry:
        scope is a RebuildScope; dry_run is True to report without changing
        anything.

    Exit/Returns:
        Returns None. Raises ManifestError or RuntimeError on any failure.

    Module Globals:
        None

    Methodology:
        Read and validate the manifest, load every listed module, check the
        scope's tiles against those modules, then prune, purge, register and
        spawn.

    Notes/References:
        Loading comes first on purpose: nothing is deleted until every listed
        module has proven it exists and declares the promised z-coordinate.
        Tile validation joins it there for the same reason.

        The manifest is read in full even for a one-tile run. Registration
        keeps every listed map on the grid, so a scoped run never leaves the
        grid's stored map data behind the operator's files.

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
    validate_scope_tiles(grid, scope, map_data_list)
    objects_before = _total_object_count()

    print(f"Manifest lists {len(entries)} map(s): {', '.join(zcoords)}")
    print(f"This run rebuilds {scope.describe()}.")

    print("=== Removing maps no longer in the manifest ===")
    pruned = []

    if not scope.is_full:
        print("  skipped: a scoped run never removes a map")
    else:
        pruned = prune_unlisted_maps(grid, zcoords, dry_run)
        if not pruned:
            print("  none")

    print("=== Purging objects in scope ===")
    purged = purge_scope(scope, dry_run)

    print("=== Registering listed maps ===")
    register_maps(grid, map_data_list, dry_run)

    print("=== Spawning rooms and exits ===")
    spawn_scope(grid, scope, dry_run)

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


def _values_after(argv, flag):
    """
    Purpose: Collect the value of every occurrence of one repeatable flag.

    Entry:
        argv is the argument list without the program name; flag is the
        literal flag string.

    Exit/Returns:
        Returns a list of values, in the order they were given. Raises
        RuntimeError if the flag appears with nothing after it.

    Module Globals:
        None

    Methodology:
        Walk the list and take the next argument after each match.

    Notes/References:
        Hand-rolled rather than argparse, because this script already reads
        `--dry-run` as a plain membership test and the two styles must not sit
        side by side. Both flags stay repeatable, which argparse would need an
        action for anyway.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    values = []

    for index, argument in enumerate(argv):
        if argument != flag:
            continue

        has_value = index + 1 < len(argv)

        if not has_value:
            raise RuntimeError(f"{flag} needs a value after it.")

        values.append(argv[index + 1])

    return values


def main(argv):
    """Entry point. Bootstraps Evennia, then syncs the scoped part of the grid."""
    dry_run = _DRY_RUN_FLAG in argv

    _bootstrap_evennia()

    from world.maps import manifest as map_manifest
    from world.maps import scope as map_scope

    try:
        entries = map_manifest.load_entries()
        scope = map_scope.build_scope(
            _values_after(argv, _MAP_FLAG),
            _values_after(argv, _TILE_FLAG),
            entries,
        )
        _sync(scope, dry_run)
    except Exception as exc:
        print(f"Aborting: {exc}")
        sys.exit(1)

    if dry_run:
        print("Dry run: nothing was changed.")


if __name__ == "__main__":
    main(sys.argv[1:])
