"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/28/2026
Description: Developer script. The world versions from a terminal: the
             shelf of saved worlds under world/versions/. The Versions tab
             of the terrain editor does the same with no terminal.
             `world/world_versions.py` holds the rules.

             SAFE: it touches no database. It copies, renames, and deletes
             files under world/chunks/ and world/versions/ only.

             It sits behind the `if __name__ == "__main__"` guard of this
             directory (CLAUDE.md, "Danger: blackout/scripts/"). One safe
             file does not change the rule of the directory.

             Run from blackout/:
                 ../evenv/Scripts/python.exe scripts/world_versions.py list
                 ../evenv/Scripts/python.exe scripts/world_versions.py save <key> [--note TEXT] [--overwrite]
                 ../evenv/Scripts/python.exe scripts/world_versions.py switch <key> [--drop]
                 ../evenv/Scripts/python.exe scripts/world_versions.py rename <old> <new>
                 ../evenv/Scripts/python.exe scripts/world_versions.py remove <key>

             A switch changes the chunk files only. The database follows
             after a stop of the server, `scripts/sync_tile_objects.py
             --apply`, and a start. `switch` refuses to drop a world that no
             version holds. `--drop` says that you mean it.
"""

import argparse
import os
import sys

# ─── Private constant definitions ────────────────────────────────────────────

_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SYNC_HINT = ("The database follows after a stop of the server, "
              "scripts/sync_tile_objects.py --apply, and a start.")


# ─── Private helper routines ─────────────────────────────────────────────────

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="The world versions.")
    verbs = parser.add_subparsers(dest="verb", required=True)

    verbs.add_parser("list", help="each version, with a mark on the current")
    save = verbs.add_parser("save", help="save the world as a version")
    save.add_argument("key")
    save.add_argument("--note", default="", help="one line about it")
    save.add_argument("--overwrite", action="store_true",
                      help="replace a version that exists")
    switch = verbs.add_parser("switch", help="make a version the world")
    switch.add_argument("key")
    switch.add_argument("--drop", action="store_true",
                        help="switch away from a world that no version holds")
    rename = verbs.add_parser("rename", help="give a version a new key")
    rename.add_argument("old")
    rename.add_argument("new")
    remove = verbs.add_parser("remove", help="delete a version")
    remove.add_argument("key")

    return parser


def _list(versions) -> None:
    current = versions.current_key()

    if not versions.list_versions():
        print("The shelf is empty. Save one: world_versions.py save <key>")
        return

    for version in versions.list_versions():
        mark = "*" if version.key == current else " "
        when = version.saved or "no date"
        print(f"{mark} {version.key:24} {version.chunk_count:3} chunks  "
              f"{when}  {version.note}")

    if not current:
        print("No version holds the world of now (*). Save it to keep it.")


def _run(versions, args) -> None:
    if args.verb == "list":
        _list(versions)
    elif args.verb == "save":
        saved = versions.save_version(args.key, args.note, args.overwrite)
        print(f"Saved {saved.chunk_count} chunk file(s) as {saved.key}.")
    elif args.verb == "switch":
        changed = versions.switch_to(args.key, args.drop)
        print(f"Switched to {args.key}: {len(changed)} chunk file(s) "
              f"changed. {_SYNC_HINT}")
    elif args.verb == "rename":
        versions.rename_version(args.old, args.new)
        print(f"Renamed {args.old} to {args.new}.")
    elif args.verb == "remove":
        versions.remove_version(args.key)
        print(f"Removed {args.key}.")


def main(argv) -> int:
    """Entry point. Returns the exit code."""
    if _GAME_DIR not in sys.path:
        sys.path.insert(0, _GAME_DIR)

    from world import world_versions as versions

    args = _parser().parse_args(argv)

    try:
        _run(versions, args)
    except versions.VersionError as error:
        print(f"Refused: {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
