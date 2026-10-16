# Table files

This directory holds the rows of four tables of the tile grid. One JSON
file holds one table:

| File | Table | Python module |
|---|---|---|
| `areas.json` | The areas: a key, a note, and the room name and room text of a plain tile | `world/areas.py` |
| `floor_types.json` | The floor types: a key, a note, and the roof flag | `world/floor_types.py` |
| `wall_styles.json` | The wall styles: a key and a note | `world/wall_styles.py` |
| `decor_kinds.json` | The decor kinds: a key, a note, and the scenery | `world/decor_kinds.py`, then `world/object_kinds.py` |

`world/table_file.py` reads each file at import, and its docstring gives
the format and the rules. A bad row stops the server at start. Each module
keeps its public names (`AREAS`, `DEFAULT_AREA`, and so on), so no reader
of a table changed when the rows moved here on 10/14/2026.

The order of the rows counts. The first row of the areas and of the floor
types is the default of a new chunk. The first wall style is `plain`, the
style of each chunk file of format 1. The world map sends a floor type as
its index in the table.

## How to add a row

Use the Tables tab of the terrain editor. It needs no terminal.

1. Open `godot/addons/blackout_terrain/terrain_editor.tscn`, and select the
   `TerrainWorld` node.
2. Click **New** beside the Floor, the Area, or the Wall list of the paint
   values strip. For a decor kind, open the **Tables** tab and pick
   **Decor kinds**.
3. Type the key and each field. Click **New row**.
4. Paint with the new row. Give it a colour or a light on the Look tab.
5. Restart the server, so that it reads the new row.

After each change, the tab writes the file. Then it runs
`scripts/export_client_constants.py` and the check fixture builder of the
tests on a thread. The status box gives the result.

## Rename and remove

**Rename row** gives a row a new key. It asks first, and it counts the
files. It writes the new key into each file that names the old one:

- each chunk file of the world and of the structure workbench
- each template, and the template fixture of the tests
- the look rows of the key, in `godot/world/look/`
- the fallback rows of the client, for example `AreaLook.LOOKS`
- the table file, last.

**Remove row** takes out a row that no chunk file and no template uses. It
takes the look rows and the fallback rows out too. Three rows stay:

- the first row of the areas, the floor types, and the wall styles
- `void` and `plain`, which the client and the chunk file format name
- the last roof floor type, because the Roof tool needs one.

## A hand edit

A hand edit of a file is legal. Then click **Read files again** on the
Tables tab. It reads the files again and runs the export. Without the
editor, run this from `blackout/`:

    python scripts/export_client_constants.py
