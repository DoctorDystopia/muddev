# Lone Android ("Clark")

> **Out of date since 09/18/2026.** The model pipeline builds this source now.
> The commands below and the generated `scene.gltf` files that they name are
> gone. The model record `assets/models/npcs/lone_android.toml` says how
> this source is built, and `assets/README.md` is the procedure. The rest of
> this note still describes the download.

The export `lone_android` is packed from — the quest giver of "Oasis in the
Wastes", drawn for `LoneAndroidNPC` in `typeclasses/npcs.py`.

- **Source:** "Robot_3D_Model", https://pensamientoazul.itch.io/robot-3d-model,
  by PensamientoAzul. Downloaded as FBX and exported through Blender; added
  09/13/2026.
- **Licence:** **CC0**, as stated on that page — free and commercial use,
  modification allowed, credit appreciated. The download carries no licence
  file, so the page is the only record and this row is it.

## What is here

| Path | What it is |
|---|---|
| `lone_android_clark.blend` | The Blender scene. Not read by anything here. |
| `lone_android_clark.glb` | Blender's glTF export, unmodified. What the source is split from. |
| `scene.gltf`, `scene.bin` | Written by `../../glb_to_gltf.py --as-exported`. Generated. |

Re-export over the `.glb`, then:

```bash
../evenv/Scripts/python.exe assets/glb_to_gltf.py \
    assets/npcs/lone_android_clark/lone_android_clark.glb \
    assets/npcs/lone_android_clark --as-exported
../evenv/Scripts/python.exe assets/pack_model.py assets/npcs/lone_android_clark lone_android
```

## What the model is

- One mesh, 17,071 vertices, no rig, no animations.
- One material, `01 - Default`: a flat rust red with no texture, so packing
  resamples nothing.
- **Upright and facing +Z**, the way the client expects a character — checked
  by render 09/13/2026 — so it has no `ModelRegistry.PRESENTATION` entry.
- **A T-pose, and that costs it size on a tile.** The arms span 2.4 against a
  height of 1.25, and `ModelLoader` scales the LONGEST axis to one unit, so the
  android is drawn about half the height of an NPC whose longest axis is its
  height.
