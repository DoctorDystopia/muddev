"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/03/2026
Description: Developer script. Writes the showroom world, and with --apply
             stands it up in the showroom database. The showroom holds one
             of each item and one of each object kind, side by side.
             `world/showroom.py` holds the layout rules, and
             `server/conf/showroom_settings.py` the server.

             It reads the settings of the showroom ALWAYS, whatever
             DJANGO_SETTINGS_MODULE says, and it stops if those settings
             name the live database or the live chunk directory.

             Without --apply: it writes `world/showroom/` and prints a
             report. It touches no database.

             With --apply: it also runs the tile sync into
             `server/showroom.db3`, and sends each character that waits in
             Limbo to the respawn point at its next login. It does NOT
             write the tile sync stamp of the terrain editor. That stamp
             belongs to the live world.

             First run, from blackout/ (the live server stopped):
                 ../evenv/Scripts/evennia.exe --settings showroom_settings.py migrate
                 ../evenv/Scripts/evennia.exe --settings showroom_settings.py start
                 ../evenv/Scripts/evennia.exe --settings showroom_settings.py stop
                 ../evenv/Scripts/python.exe scripts/showroom.py --apply
                 ../evenv/Scripts/evennia.exe --settings showroom_settings.py start

             The first start asks for the superuser. Each later run needs
             the last three lines only.

             Behind an `if __name__ == "__main__"` guard, as every script in
             this directory is (CLAUDE.md, "Danger: blackout/scripts/").
"""

import importlib
import os
import sys
from collections import Counter

# ─── Private constant definitions ────────────────────────────────────────────

_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_APPLY_FLAG = "--apply"

_SETTINGS_ENV_VAR = "DJANGO_SETTINGS_MODULE"
_SHOWROOM_SETTINGS = "server.conf.showroom_settings"
_LIVE_SETTINGS = "server.conf.settings"

_EVENNIA = "../evenv/Scripts/evennia.exe --settings showroom_settings.py"

_NOT_READY = (
    "The showroom database is not ready. From blackout/, with the live "
    "server stopped:\n"
    f"  {_EVENNIA} migrate\n"
    f"  {_EVENNIA} start      (it asks for the superuser)\n"
    f"  {_EVENNIA} stop\n"
    "Then run this script with --apply again.")

_NEXT_STEP = (f"Start the showroom server: {_EVENNIA} start\n"
              "Start the Godot client with --server=ws://127.0.0.1:4108")


# ─── Private helper routines ─────────────────────────────────────────────────

def _bootstrap_django() -> None:
    """
    Start Django on the showroom settings, whatever the shell says. Opens
    no database. `_start_evennia` does the rest, for --apply only.
    """
    if _GAME_DIR not in sys.path:
        sys.path.insert(0, _GAME_DIR)

    # Set, never setdefault. A shell that names the live settings must not
    # send the tile sync into the live database.
    os.environ[_SETTINGS_ENV_VAR] = _SHOWROOM_SETTINGS

    import django

    django.setup()


def _same_path(first: str, second: str) -> bool:
    """Return True if two paths name one file or one directory."""
    first_path = os.path.normcase(os.path.abspath(first))
    second_path = os.path.normcase(os.path.abspath(second))

    return first_path == second_path


def _refuse_live_targets() -> None:
    """Stop if the settings name the live database or chunk directory."""
    from django.conf import settings

    from systems.core.tilegrid import constants as tile_const

    live = importlib.import_module(_LIVE_SETTINGS)
    live_database = live.DATABASES["default"]["NAME"]
    database = settings.DATABASES["default"]["NAME"]
    live_chunks = os.path.join(_GAME_DIR, tile_const.CHUNK_DIRECTORY)
    chunks = getattr(settings, "TILE_WORLD_DIR", "") or live_chunks
    live_db_named = _same_path(database, live_database)
    live_chunks_named = _same_path(chunks, live_chunks)

    if live_db_named:
        sys.exit(f"Refused: the showroom settings name the live database, "
                 f"{database}.")

    if live_chunks_named:
        sys.exit(f"Refused: the showroom settings name the live chunk "
                 f"directory, {chunks}.")


def _build():
    """Write the showroom chunk files. Return the Showroom and the paths."""
    from django.conf import settings

    from systems.core.tilegrid import constants as tile_const
    from systems.interface.statefeed import spawn_items
    from world import showroom

    item_rows = spawn_items.item_rows()
    room = showroom.build(item_rows)
    live_chunks = os.path.join(_GAME_DIR, tile_const.CHUNK_DIRECTORY)
    paths = showroom.write(room, settings.TILE_WORLD_DIR, live_chunks)

    return room, paths


def _print_left_out(room) -> None:
    """Print each item, kind, and NPC that the showroom does not hold."""
    from systems.interface.statefeed import spawn_items
    from world.item_database import ITEM_DB
    from world.npc_database import NPC_DB
    from world.object_kinds import OBJECT_KINDS

    items = sorted(set(ITEM_DB) - set(spawn_items.stacking()))
    npcs = sorted(set(NPC_DB) - set(OBJECT_KINDS))

    for key, reason in room.skipped_kinds:
        print(f"  Left out, kind {key}: {reason}.")

    for key in items:
        print(f"  Left out, item {key}: no item spawn may name a dev tool.")

    for key in npcs:
        print(f"  Left out, NPC {key}: it has no object kind.")


def _print_checks(room) -> None:
    """Run the content checks of the world on the showroom, and print them."""
    from systems.interface.statefeed import spawn_items
    from world import tile_checks

    findings = tile_checks.check_world(room.chunk_files,
                                       spawn_items.stacking())
    print(f"Content checks: {len(findings)} findings.")

    for finding in findings:
        print(f"  {finding}")


def _report(room, paths: list) -> None:
    """Print the aisles, what is left out, and the content checks."""
    placed = sum(len(chunk.objects) for chunk in room.chunk_files)
    print(f"Showroom: {len(room.aisles)} aisles, {placed} objects, "
          f"{len(paths)} chunk files.")

    for aisle in room.aisles:
        print(f"  {aisle.label}")

    for path in paths:
        print(f"  Wrote {path}")

    _print_left_out(room)
    _print_checks(room)


def _database_ready() -> bool:
    """Return True if the showroom database holds the home of Evennia."""
    from django.conf import settings
    from django.db import DatabaseError

    path = settings.DATABASES["default"]["NAME"]
    exists = os.path.exists(path)

    # A query on a missing SQLite file makes an empty file. Look first.
    if not exists:
        return False

    from evennia.objects.models import ObjectDB

    home_id = int(settings.DEFAULT_HOME.lstrip("#"))

    try:
        found = ObjectDB.objects.filter(id=home_id).exists()
    except DatabaseError:
        found = False

    return found


def _start_evennia() -> None:
    """
    Stop if the showroom database is not ready. Else fill the flat API of
    Evennia.

    `evennia._init()` must come before the first import of a game module.
    A module that does `from evennia import create_object` binds the name
    at import. Before `_init()`, the name is None, and the tile sync fails
    at the first NPC with "'NoneType' object is not callable" (11/03/2026).
    `_init()` also opens the database. Thus, a run without --apply does not
    call it.
    """
    ready = _database_ready()

    if not ready:
        sys.exit(_NOT_READY)

    import evennia

    evennia._init()


def _bring_characters_in(world) -> int:
    """
    Send each character in Limbo to the respawn point at its next login.
    Return the count. The first superuser starts in Limbo, which the
    Godot client does not draw.
    """
    from django.conf import settings

    from systems.core.tilegrid import constants as tile_const
    from typeclasses.characters import PRELOGOUT_TILE_ATTR, Character
    from world.respawn import get_respawn_room, respawn_tile

    tile = respawn_tile(world)
    room = get_respawn_room(world)

    if tile is None or room is None:
        print("No respawn point: each character stays where it is.")
        return 0

    limbo_id = int(settings.DEFAULT_HOME.lstrip("#"))
    stored = [tile[0], tile[1], tile_const.GROUND_PLANE]
    moved = 0

    for character in Character.objects.all_family():
        location = character.location

        if location is None or location.id != limbo_id:
            continue

        character.home = room
        character.location = None
        character.attributes.add(PRELOGOUT_TILE_ATTR, stored)
        moved += 1

    return moved


def _apply() -> None:
    """
    Run the tile sync into the showroom database, then bring each
    character in Limbo to the respawn point. `_start_evennia` comes first.
    """
    from systems.core.tilegrid.world import load_world
    from systems.gameplay.spawning import tile_sync

    world = load_world()
    actions = tile_sync.plan(world)
    verbs = Counter(action.verb for action in actions)
    counts = ", ".join(f"{verb} {count}" for verb, count in sorted(verbs.items()))
    print(f"Tile sync: {len(actions)} tiles ({counts or 'none'}).")

    destroyed = tile_sync.apply(world, actions)
    moved = _bring_characters_in(world)
    print(f"Applied. Teardown destroyed {destroyed} objects. "
          f"{moved} characters go to the respawn point at login.")


def main(argv) -> None:
    """Entry point. Writes the showroom, reports, and applies if asked."""
    applying = _APPLY_FLAG in argv
    _bootstrap_django()
    _refuse_live_targets()

    # Before _build: it imports the game modules (see _start_evennia).
    if applying:
        _start_evennia()

    room, paths = _build()
    _report(room, paths)

    if not applying:
        print(f"Files only: no database changed. Use {_APPLY_FLAG} to run "
              "the tile sync into the showroom database.")
        return

    _apply()
    print(_NEXT_STEP)


if __name__ == "__main__":
    main(sys.argv[1:])
