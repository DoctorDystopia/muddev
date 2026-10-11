# Structure templates

This directory holds the templates of the Build tab of the terrain editor.
One file holds one template. DESIGN-0013 section 6.6 is the design.

A template is a saved structure: a house, a stall, or a wall with a gate.
The Place tool writes a copy of it into the chunk files. The copy is plain
facts in the chunk files. Nothing links it to its template. An edit of a
template thus changes no structure that the world holds now.

The server never loads a template. `world/tests/test_structure_templates.py`
checks each name in each file against the tables of the server:

| Key | Table |
|---|---|
| `floor_names` | `world/floor_types.py` |
| `area_names` | `world/areas.py` |
| `wall_names` | `world/wall_styles.py` |
| `objects[].kind` | `world/object_kinds.py` |

## How to make one

Build it in the structure workbench, away from the world: open
`godot/addons/blackout_terrain/structure_workbench.tscn`. The same steps
work in the world too.

1. On the Build tab, pick the Select tool.
2. Click inside a room, or drag a rectangle.
3. Type a key in "Template key", and click "Save the selection as a
   template".
4. Commit the file with the chunk files that use it.

The editor writes the file. Do not edit a template by hand. To change one,
place it in the structure workbench, edit the copy, select the copy, and
save it again with the same key.

## The format

The canonical layout is the layout of a chunk file: one grid row on each
line, row 0 first. Row 0 is the south edge. Item 0 of a row is the west
edge.

| Key | Holds |
|---|---|
| `format` | `STRUCTURE_FORMAT_VERSION` of `systems/core/tilegrid/constants.py` |
| `key` | The key. It is the file name without `.json` |
| `size` | `[W, H]`, in tiles |
| `floor_names`, `area_names`, `wall_names` | The names that the grids index |
| `planes` | One entry for each plane with a covered tile, lowest first |
| `objects` | `{kind, x, y, plane, rotation}`, and `text` for a sign |

Each entry of `planes` holds:

| Key | Holds |
|---|---|
| `plane` | The plane, relative: 0 is the plane where the Place tool writes |
| `cover` | 1 on a tile that the template owns. The Place tool writes only these tiles |
| `heights` | (W + 1) x (H + 1) corners, in height steps above the base |
| `floors`, `flags`, `areas`, `walls` | One value for each tile, as in a chunk file |

The base is the lowest corner of a covered tile of plane 0. A capture
covers each selected tile of the ground plane, and each selected tile of a
plane above that is not void.
