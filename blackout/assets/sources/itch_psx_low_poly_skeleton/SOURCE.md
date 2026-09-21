# PSX Low Poly Skeleton

The download `corpse_skeleton` is packed from.

- **Source:** https://puszke.itch.io/psx-low-poly-skeleton, by Puck (puszke)
- **Licence:** **CC0**, as stated on that page. The download carries no licence
  file, so the page is the only record and this row is it. CC0 asks for nothing
  — the credit in `models/CREDITS.md` is there because a file with no row is
  indistinguishable from one whose licence nobody checked.
- **Downloaded:** 09/11/2026

## What is here

| Path | What it is |
|---|---|
| `skeleton.fbx` | The download's mesh, unmodified. 1,969 vertices, UV'd, no rig. |
| `skeleton.blend` | The download's Blender scene, unmodified. Not read by anything here. |
| `base.png` | The 128² palette atlas the mesh's UVs point into. |
| `GameBoyColor/`, `Variant2/` | Two other recolours of the same atlas, as they arrived. |
| `scene.gltf`, `scene.bin`, `textures/` | Written by `../../fbx_to_gltf.py`. Generated. |

## Why the FBX and not the .blend

The `.blend` wires `GameBoyColor/base.png` through an **emission** shader and
carries a camera and a metarig the mesh is not skinned to. None of that is art
worth converting: the emission graph is the author's viewport look, the variant
is one of three recolours, and the rig drives nothing. The FBX is the same mesh
with the same UVs and no opinions, which is why it is the one converted.

The FBX arrives with a flat 0.8-grey material and **no reference to the atlas
at all**, so the texture is named on the command line rather than discovered:

```bash
../evenv/Scripts/python.exe assets/fbx_to_gltf.py \
    assets/npcs/psx_low_poly_skeleton/skeleton.fbx \
    assets/npcs/psx_low_poly_skeleton --texture base.png
```

Swapping `--texture Variant2/base.png` is the whole cost of trying a different
recolour. Then repack; `assets/README.md` has the rest.

## Why `npcs/`

A corpse is not an NPC, and there is no `corpses` family. `npcs` is the honest
fit anyway and needs no new budget tier: this is a body-sized mesh, several can
share a room, and it is never inspected close up — which is exactly what the
`npcs` entry in `assets/asset_budgets.py` is reasoning about. The served path
follows from the directory and nothing restates it.
