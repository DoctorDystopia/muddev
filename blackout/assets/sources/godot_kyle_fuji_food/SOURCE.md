# Low Poly Food Asset Pack — Kyle Fuji

> **Out of date since 09/18/2026.** The model pipeline builds this source now.
> The commands below and the generated `scene.gltf` files that they name are
> gone. The model record `assets/models/items/moderator_egg.toml`, `assets/models/items/mutant_raider_steak.toml`, `assets/models/items/mutant_raider_cured_chuck.toml`, `assets/models/items/mutant_raider_cured_meat_sandwich.toml` says how
> this source is built, and `assets/README.md` is the procedure. The rest of
> this note still describes the download.

- **Author:** Kyle Fuji (https://www.patreon.com/kylefuji)
- **Licence:** CC0 1.0 — see `license.txt`, kept as it arrived
- **Obtained:** 09/12/2026, through the Godot editor's Asset Library

## What is here

`Models/`, `Textures/`, `Materials/`, `Prefabs/`, `license.txt` and
`support_me.txt` are the download. Two things were removed on the way in, both
Godot-editor artefacts rather than art:

- every `.import` sidecar, which Godot regenerates and nothing outside a Godot
  project reads;
- the seven `food_scene*.tscn` demo scenes the Asset Library installed into
  `godot/scenes/`.

The pack was first installed into the root of `godot/`, the client project. It
cannot stay there: the Web export preset has no exclude filter, so 9.5 MB of
atlases would have shipped inside the `.pck` before the login prompt, which is
exactly what `ModelRegistry` fetching at runtime exists to prevent.

`Materials/` and `Prefabs/` are kept although nothing reads them, because they
are the only record of which atlas each model is drawn from. Their `res://`
paths point at `Low Poly Food Asset Pack/Kyle Fuji/`, where the Asset Library
meant to install the pack; that is a fact about the download, not a breakage.

## Why a converter step

Every `.glb` here carries geometry and UVs and **no material**. The look is a
`StandardMaterial3D` a prefab applies with `material_override`, so a model
packed as-is renders untextured. `assets/glb_to_gltf.py` splits one `.glb` into
the `scene.gltf` + `scene.bin` shape `pack_model.py` reads and attaches the
base-colour atlas. The directories beside `Models/` are its output:

| Directory | Model | Atlas (from the prefab's material) |
|---|---|---|
| `egg/` | `Models/egg.glb` | `T_protein_atlas_diffuse.png` (`M_protein.tres`) |
| `steak/` | `Models/steak.glb` | `T_protein_atlas_diffuse.png` (`M_protein.tres`) |
| `meat_haunch/` | `Models/meat_haunch.glb` | `T_protein_atlas_diffuse.png` (`M_protein.tres`) |
| `burger/` | `Models/burger.glb` | `T_junk_atlas_diffuse.png` (`M_junk_food.tres`) |

To add another, look its prefab up under `Prefabs/` for the material, the
material under `Materials/` for the atlas, then:

```bash
../evenv/Scripts/python.exe assets/glb_to_gltf.py \
    assets/items/food/kyle_fuji_food/Models/<model>.glb \
    assets/items/food/kyle_fuji_food/<model> \
    --texture assets/items/food/kyle_fuji_food/Textures/<atlas>.png
```

**The protein atlas's alpha channel is roughness, not transparency** —
`M_protein.tres` reads `roughness_texture_channel = 3`, and it samples 128–211,
never 255. The converter writes `alphaMode: OPAQUE` for that reason.
