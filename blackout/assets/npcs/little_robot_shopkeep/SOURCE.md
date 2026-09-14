# Little robot shopkeep

The export `shopkeeper` is packed from — the robot behind the Oasis stall.

- **Source:** "Robot", https://modosa-kun.itch.io/robot2, by Modo
  (modosa-kun), sold as name-your-own-price. Downloaded as `.blend` and
  exported through Blender; added 09/13/2026.
- **Licence:** **none stated on the page.** Name-your-own-price is a price, not
  a grant to redistribute. Confirm terms with the author before this ships
  anywhere public; see `web/static/webclient/models/CREDITS.md`.

## What is here

| Path | What it is |
|---|---|
| `little_robot_shopkeep.glb` | Blender's glTF export, unmodified. What the source is split from. |
| `scene.gltf`, `scene.bin` | Written by `../../glb_to_gltf.py --as-exported`. Generated. |

Re-export over the `.glb`, then:

```bash
../evenv/Scripts/python.exe assets/glb_to_gltf.py \
    assets/npcs/little_robot_shopkeep/little_robot_shopkeep.glb \
    assets/npcs/little_robot_shopkeep --as-exported
../evenv/Scripts/python.exe assets/pack_model.py assets/npcs/little_robot_shopkeep shopkeeper
```

## What the model is

- 32 meshes, 45,297 vertices, no rig, no animations.
- Nine flat-colour materials and no textures, so packing resamples nothing.
  `Glass` has no `pbrMetallicRoughness` block at all, so it renders as glTF's
  default opaque white rather than as glass.
- **Upright and facing +Z** — checked by render 09/13/2026 — so it has no
  `ModelRegistry.PRESENTATION` entry.
- **1,668 KB of the `npcs` family's 2,048 KB**, nearly all of it vertex data.
  A second prop this size on the same model would not fit.

## Why `shopkeeper` and not an Oasis key

`asset_key = "shopkeeper"` is declared on the `ShopkeepNPC` CLASS, so every
shopkeeper draws this robot. Today that is exactly one: Oasis (10, 4) is the
only map spawning a `Shopkeeper` — `azm_plains.py`'s is commented out — and
`spawn_shopkeep` already describes it as "a tiny robot". A second shopkeep
needing different art is a class attribute on a subclass, not a change here.
