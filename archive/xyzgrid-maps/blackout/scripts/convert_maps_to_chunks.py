"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Operator script. Converts each map of scripts/map_manifest.json
             into one chunk file in world/chunks/. A one-time tool of
             DESIGN-0011 Phase 4. `world/maps/chunk_converter.py` holds the
             rules, and `world/tests/test_chunk_converter.py` tests them.

             It touches no database. It writes files, and a chunk file that
             Nick shaped in the editor is work that a rerun can destroy.
             Thus, it reports by default. `--write` writes each chunk file
             that does not exist. `--force` also replaces a file that exists.

             Run from blackout/:
                 ../evenv/Scripts/python.exe scripts/convert_maps_to_chunks.py
                 ../evenv/Scripts/python.exe scripts/convert_maps_to_chunks.py --write

             Behind an `if __name__ == "__main__"` guard, as every script in
             this directory is (CLAUDE.md, "Danger: blackout/scripts/").
"""

import importlib
import os
import sys

# ─── Private constant definitions ────────────────────────────────────────────

_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_WRITE_FLAG = "--write"
_FORCE_FLAG = "--force"


# ─── Private helper routines ─────────────────────────────────────────────────

def _bootstrap_evennia():
    """Bring Django up. The map modules import typeclasses."""
    if _GAME_DIR not in sys.path:
        sys.path.insert(0, _GAME_DIR)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

    import django

    django.setup()

    import evennia

    evennia._init()


def _conversions():
    """Return the Conversion of each map in the manifest."""
    from world.maps import chunk_converter
    from world.maps import manifest as map_manifest

    found = []

    for entry in map_manifest.load_entries():
        module = importlib.import_module(entry.module)

        for map_data in module.XYMAP_DATA_LIST:
            if map_data["zcoord"] == entry.zcoord:
                found.append(chunk_converter.convert_map(map_data))

    return found


def _report(conversion) -> None:
    """Print what one conversion holds."""
    chunk_file = conversion.chunk_file
    print(f"{conversion.zcoord} -> {chunk_file.file_name()}: "
          f"{len(conversion.walkable)} walkable tiles, "
          f"{len(chunk_file.objects)} objects, "
          f"{len(conversion.added_edges)} joins added for diagonals")

    for x, y, key in conversion.unmatched:
        print(f"  no kind for '{key}' at ({x}, {y}): the tile keeps no name")


def _write(conversion, directory: str, force: bool) -> None:
    """Write one chunk file, unless it exists and force is off."""
    from systems.core.tilegrid import chunkfile

    path = os.path.join(directory, conversion.chunk_file.file_name())

    if os.path.exists(path) and not force:
        print(f"  kept {path}: it exists. Use {_FORCE_FLAG} to replace it.")
        return

    chunkfile.write_file(path, conversion.chunk_file)
    print(f"  wrote {path}")


def main(argv):
    """Entry point. Converts, reports, and writes if asked."""
    _bootstrap_evennia()

    from systems.core.tilegrid import chunkfile
    from systems.core.tilegrid import constants as tile_const

    write = _WRITE_FLAG in argv
    force = _FORCE_FLAG in argv
    directory = os.path.join(_GAME_DIR, tile_const.CHUNK_DIRECTORY)
    conversions = _conversions()
    mismatches = chunkfile.seam_mismatches(
        [conversion.chunk_file for conversion in conversions])

    for conversion in conversions:
        _report(conversion)

        if write:
            _write(conversion, directory, force)

    if mismatches:
        print(f"Seam mismatches: {mismatches}")
        sys.exit(1)

    if not write:
        print(f"Report only: nothing was written. Use {_WRITE_FLAG}.")


if __name__ == "__main__":
    main(sys.argv[1:])
