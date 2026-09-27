# World chunk files

This directory holds the chunk files of the tile grid. One file holds one
64 x 64 chunk on one plane. DESIGN-0011 section 6.2 is the design.

The first three files came from the xyzgrid maps, through
`scripts/convert_maps_to_chunks.py`:

| File | Map |
|---|---|
| `chunk_0_0_p0.json` | `oasis` |
| `chunk_1_0_p0.json` | `oasis_outskirts` |
| `chunk_2_0_p0.json` | `azm_plains` |

`world/maps/chunk_converter.py` gives the rules. The script does not replace
a file that exists unless you add `--force`. After an edit in the editor,
do not run it again.

The terrain editor writes here: `godot/README.md`, "The terrain editor writes
chunk files, not scenes", tells how to use it.

Every name in a chunk file is a row of a table under `world/`:

| Key | Table |
|---|---|
| `floor_names` | `world/floor_types.py` |
| `area_names` | `world/areas.py` |
| `objects[].kind` | `world/object_kinds.py` |

`world/tests/test_tile_content.py` fails on a name that is not a row.

## The rules

- **Name:** `chunk_<cx>_<cy>_p<plane>.json`, for example
  `chunk_-1_2_p0.json`. The name must match the `chunk` and `plane` in the
  file. `load_directory` refuses a file whose name does not.
- **Format:** format 1, in the canonical layout. The module docstring of
  `systems/core/tilegrid/chunkfile.py` defines each key.
- **Objects:** at local coordinates, 0 to 63. The reader adds the chunk
  offset.
- **Seams:** two neighbour chunks hold the same corner heights on the edge
  that they share. A test fails on a mismatch.
- **Planes:** a file of plane 1 and up holds absolute heights. A tile with
  no floor there has the floor type `void` and the Blocked flag. The editor
  starts a new plane-1 chunk from the chunk below it.
- **Content checks:** `world/tile_checks.py` checks what the files mean
  together: each transition and each climb lands on an open tile, each object
  stands on a walkable tile, each void tile is Blocked, and the world has one
  respawn point. `world/tests/test_tile_content.py` runs it over this
  directory, and the editor runs the same rules as "Check world".
- **After an edit:** stop the server, run `scripts/sync_tile_objects.py
  --apply`, and start the server. The server loads these files one time, at
  start.
- **No hand edits of a big grid.** Use the editor, or a script that writes
  through `chunkfile.write_file`. A hand edit that breaks the layout still
  reads, but the next editor save rewrites every line of it.

## The tests that read this directory

`systems/core/tilegrid/tests/test_chunkfile.py` loads every file here and
checks every seam:

```bash
../evenv/Scripts/evennia.exe test --settings test_settings.py systems.core.tilegrid
```
