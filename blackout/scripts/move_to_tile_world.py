"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/25/2026
Description: Operator script. The cutover of DESIGN-0011 Phase 4b: it moves
             every character from the xyzgrid maps to the tile world, and
             then deletes the xyzgrid rooms, their exits, and the grid
             Script. `world/tile_cutover.py` holds the rules.

             DESTRUCTIVE with --apply: every xyzgrid room goes, with all that
             lies in it. Player characters are moved first. Without --apply,
             the script prints the plan and changes nothing. A second run
             finds nothing to do.

             Stop the server first. The server keeps the tile room index in
             memory. Run the tile sync (`sync_tile_objects.py`) before this,
             so that the tile world holds its objects.

             Run from blackout/:
                 ../evenv/Scripts/python.exe scripts/move_to_tile_world.py
                 ../evenv/Scripts/python.exe scripts/move_to_tile_world.py --apply

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
    """Bring Django and Evennia up, so rooms and characters work."""
    if _GAME_DIR not in sys.path:
        sys.path.insert(0, _GAME_DIR)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

    import django

    django.setup()

    import evennia

    evennia._init()


def _print_plan(cutover) -> None:
    """Print the moves, the homes, and the counts of the plan."""
    print(f"  respawn point: {cutover.respawn}")

    for move in cutover.moves:
        state = "online " if move.online else "offline"
        print(f"  move   {state} {move.character.key} "
              f"(#{move.character.id}): {move.source} -> {move.tile}")

    for character in cutover.rehome:
        print(f"  home   {character.key} (#{character.id}) -> respawn point")

    for zcoord, count in sorted(cutover.rooms.items()):
        print(f"  delete {count} rooms of map '{zcoord}'")

    print(f"  delete {cutover.exits} exits and {cutover.grids} grid Scripts")


def main(argv):
    """Entry point. Plans, prints, and applies if asked."""
    _bootstrap_evennia()

    from systems.core.tilegrid.world import load_world
    from world import tile_cutover

    world = load_world()
    cutover = tile_cutover.plan(world)

    if cutover.is_empty():
        print("Cutover: nothing to do. No character or room is on a map.")
        return

    print(f"Cutover: {len(cutover.moves)} characters to move, "
          f"{sum(cutover.rooms.values())} rooms to delete.")
    _print_plan(cutover)

    if _APPLY_FLAG not in argv:
        print(f"Plan only: nothing was changed. Use {_APPLY_FLAG}.")
        return

    deleted = tile_cutover.apply(world, cutover)
    print(f"Applied. Deleted {deleted} rooms. Start the server now.")


if __name__ == "__main__":
    main(sys.argv[1:])
