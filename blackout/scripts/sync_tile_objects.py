"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Operator script. Makes the objects on the tile grid match the
             chunk files in world/chunks/. `systems/gameplay/spawning/
             tile_sync.py` holds the rules and the four verbs.

             DESTRUCTIVE with --apply: a changed or a removed tile loses its
             contents, as a rebuilt xyzgrid tile does. Player characters are
             spared. Without --apply, the script prints the plan and changes
             nothing.

             The server keeps the tile room index in memory. Stop the server
             first, or run `evennia reload` after --apply.

             Run from blackout/:
                 ../evenv/Scripts/python.exe scripts/sync_tile_objects.py
                 ../evenv/Scripts/python.exe scripts/sync_tile_objects.py --apply

             Behind an `if __name__ == "__main__"` guard, as every script in
             this directory is (CLAUDE.md, "Danger: blackout/scripts/").
"""

import os
import sys

# ─── Private constant definitions ────────────────────────────────────────────

_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_APPLY_FLAG = "--apply"


# ─── Private helper routines ─────────────────────────────────────────────────

def _bootstrap_evennia():
    """Bring Django and Evennia up, so rooms and spawners work."""
    if _GAME_DIR not in sys.path:
        sys.path.insert(0, _GAME_DIR)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

    import django

    django.setup()

    import evennia

    evennia._init()


def _print_plan(actions) -> None:
    """Print one line for each tile of the plan."""
    for action in actions:
        line = f"  {action.verb:8} {action.tile}: {', '.join(action.kinds)}"

        if action.previous and action.previous != action.kinds:
            line += f" (was {', '.join(action.previous)})"

        print(line)


def main(argv):
    """Entry point. Plans, prints, and applies if asked."""
    _bootstrap_evennia()

    from systems.core.tilegrid.world import load_world
    from systems.gameplay.spawning import tile_sync

    world = load_world()
    actions = tile_sync.plan(world)
    print(f"Tile sync: {len(actions)} tiles, "
          f"{len(world.chunk_keys())} chunks.")
    _print_plan(actions)

    if _APPLY_FLAG not in argv:
        print(f"Plan only: nothing was changed. Use {_APPLY_FLAG}.")
        return

    destroyed = tile_sync.apply(world, actions)
    print(f"Applied. Teardown destroyed {destroyed} objects. "
          "Reload the server now.")


if __name__ == "__main__":
    main(sys.argv[1:])
