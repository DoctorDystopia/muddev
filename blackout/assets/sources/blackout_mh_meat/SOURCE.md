# Meat on the bone

The picoCAD project `food_meat` is packed from.

- **Source:** built for Blackout in [picoCAD](https://johanpeitz.itch.io/picocad)
  by Nick Hobar. No download, no third-party grant, nothing to keep intact.
- **Licence:** owned outright. The row in `models/CREDITS.md` is there for the
  reason the CC0 ones are — a file with no row is indistinguishable from one
  whose licence nobody checked.
- **Built:** 09/11/2026

## What is here

| Path | What it is |
|---|---|
| `mh_meat.txt` | The picoCAD save file. **The art.** Open it in picoCAD to change the model. |
| `scene.gltf`, `scene.bin`, `textures/` | Written by `../../../picocad_to_gltf.py`. Generated — never hand-edit. |

```bash
../evenv/Scripts/python.exe assets/picocad_to_gltf.py \
    assets/items/food/mh_meat/mh_meat.txt assets/items/food/mh_meat
../evenv/Scripts/python.exe assets/pack_model.py --all
```

Then `evennia reload`, which runs `collectstatic`. `assets/README.md` has the
rest.

## Why the save file is the source and not an export

picoCAD exports OBJ, and an OBJ export would be one more file to keep in step
with the project it came from — the thing `assets/README.md` warns about when it
says to keep a download unmodified. The save file is what the author edits and
it holds everything the mesh needs: seven objects, 147 faces, and the 128×120
palette sheet their UVs point into, all in one text file. The converter reads it
directly, so there is no export step to forget.

## Why `items/food/`

The first path component under `assets/` is the only thing deciding where the
packed model is served from, and this is an item — `items/food_meat.glb`. The
`food/` below it is for readers, not for the pipeline; `items/weapons/` already
sorts the same way.

It is the stand-in for the whole **food family** rather than art for one dish:
`FamilyShapes.MODELS` maps `ITEM_FAMILY_FOOD` onto it, so every edible in the
game draws this until the dish has a model of its own. Nothing on the server
names the file — `CLAUDE.md` draws that line and the corpse skeleton walks it
first.
