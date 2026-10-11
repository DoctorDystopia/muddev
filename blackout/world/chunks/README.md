# World chunk files

This directory holds the chunk files of the tile grid. One file holds one
64 x 64 chunk on one plane. DESIGN-0011 section 6.2 is the design.

The first three files came from the xyzgrid maps (DESIGN-0011 Phase 4a):

| File | Map |
|---|---|
| `chunk_0_0_p0.json` | `oasis` |
| `chunk_1_0_p0.json` | `oasis_outskirts` |
| `chunk_2_0_p0.json` | `azm_plains` |

The converter is in `archive/xyzgrid-maps/`, and nothing runs it now. The
terrain editor makes every other file here. A brush at the edge of a chunk
writes the shared corners into the neighbour chunk, so a save can add a
neighbour file (`chunk_0_-1_p0.json` is an example).

`godot/README.md`, "The terrain editor writes chunk files, not scenes", tells
how to use the editor. `docs/2026-09-22-ENG-0010-godot-ui-authoring.md` is the
step-by-step guide.

Every name in a chunk file is a row of a table under `world/`:

| Key | Table |
|---|---|
| `floor_names` | `world/floor_types.py` |
| `area_names` | `world/areas.py` |
| `wall_names` | `world/wall_styles.py` |
| `objects[].kind` | `world/object_kinds.py` |

`world/tests/test_tile_content.py` fails on a name that is not a row.

## The rules

- **Name:** `chunk_<cx>_<cy>_p<plane>.json`, for example
  `chunk_-1_2_p0.json`. The name must match the `chunk` and `plane` in the
  file. `load_directory` refuses a file whose name does not.
- **Format:** format 1 or format 2, in the canonical layout. The module
  docstring of `systems/core/tilegrid/chunkfile.py` defines each key.
- **Wall styles:** format 2 adds `wall_names` and `walls`: one wall style
  for each tile (DESIGN-0013 section 6.4). The writer writes format 2 only
  when a tile has a style other than `plain`. Thus, a chunk with only plain
  walls stays format 1, and its file does not change. A style on a tile with
  no wall bit is legal, and nothing draws it.
- **Objects:** at local coordinates, 0 to 63. The reader adds the chunk
  offset. The rotation is 0 to 3 quarter turns, clockwise from above. At
  rotation 0, the front of an object faces north.
- **Sign text:** a `signpost` object holds its words in `text`, for example
  `{"kind":"signpost","x":10,"y":0,"rotation":0,"text":"Bank"}`. One line of
  printable ASCII, 64 characters at most, with no `"`, `\`, or `|`. Only a
  sign has text, and a sign must have it. Type the words in "Sign text" in
  the editor.
- **Seams:** two neighbour chunks hold the same corner heights on the edge
  that they share. A test fails on a mismatch.
- **Planes:** a file of plane 1 and up holds absolute heights. A tile with
  no floor there has the floor type `void` and the Blocked flag. The editor
  starts a new plane-1 chunk from the chunk below it.
- **Content checks:** `world/tile_checks.py` checks what the files mean
  together: each transition and each climb lands on an open tile, each object
  stands on a walkable tile, each void tile is Blocked, each sign has words,
  and the world has one respawn point. `world/tests/test_tile_content.py` runs it over this
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
