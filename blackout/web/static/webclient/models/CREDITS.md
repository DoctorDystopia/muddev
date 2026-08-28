# Model credits

Every model served from this directory, and the licence it arrived under.

**This file is the licence obligation, not a courtesy.** Most of what is
usable here is CC-BY, which requires the credit to travel with the work
wherever it is shared — so a model added without a row below is a licence
breach, not an untidy commit.

Add a row when `assets/pack_model.py` writes a new `.glb`, in the same commit.

---

## `items/rusty_scrap_shortsword.glb`

"Rusty sword" (https://skfb.ly/6WXoQ) by Léonard_Doye / Leoskateman is licensed
under Creative Commons Attribution (http://creativecommons.org/licenses/by/4.0/).

- Source download: `assets/items/weapons/rusty_sword/` (original `license.txt`
  kept alongside it)
- Packed with `assets/pack_model.py`, textures resampled 2048² → 512²

---

## `npcs/floating_eye.glb`

"sus eye 👁‍🗨 👁" (https://skfb.ly/p6vt6) by Jeff for no reason. is licensed
under Creative Commons Attribution (http://creativecommons.org/licenses/by/4.0/).

- Source download: `assets/npcs/sus_eye/` (original `license.txt` kept
  alongside it)
- Packed with `assets/pack_model.py`, textures resampled 1024² → 512²
- Its two materials arrived as `KHR_materials_pbrSpecularGlossiness`, which the
  vendored GLTFLoader no longer reads; the packer rewrote both as core
  metallic-roughness. Both are dielectric, so the conversion is exact.
- Carries a 12-bone skin and five animations (`idle`, `movimiento`, `ataque`,
  `muerte`, `ArmatureAction`). Nothing plays them yet.

## `world_objects/map_transition.glb`

"SM_Teleporter" (https://skfb.ly/osBBE) by Kain Hunter is licensed under
Creative Commons Attribution (http://creativecommons.org/licenses/by/4.0/).

- Source download: `assets/world_objects/sm_teleporter/` (original
  `license.txt` kept alongside it)
- Packed with `assets/pack_model.py`, textures resampled 2048² → 256²: six maps
  on something drawn flat on one tile, where 512² came to 1.1 MB for detail the
  tile is too small to show

## `characters/player_character.glb`

"Universal Base Characters" by Quaternius (https://quaternius.com) is released
under CC0 1.0 Universal (https://creativecommons.org/publicdomain/zero/1.0/),
which asks for nothing. The row is here anyway, because a file with no row is
indistinguishable from one whose licence nobody checked.

- Source download: `assets/characters/quaternius_universal_male/` — the
  `Base Characters/Godot - UE/` export of `Superhero_Male_FullBody`, with the
  original `License_Standard.txt` kept alongside it as `license.txt`
- Packed with `assets/pack_model.py`, textures resampled 2048² → 512²
- Two of its seven texture `uri`s arrive with a `_png` suffix naming files the
  download does not contain (`T_Hair_1_Normal_png.png`, `T_Eye_Normal_png.png`)
  — an exporter slip, not a missing asset. `scene.gltf` is the one file edited
  on the way in, and only those two strings, to point at the PNGs that are
  actually there. Copying the images under the wrong names would have been the
  other fix and costs 4 MiB of duplicate normal map to avoid a two-word edit.
- A T-POSE, and a bald one. It replaces a Spider-Man model on 08/27/2026
  because that model is 6.3 MiB and the R2-hosted client drew the fallback mesh
  rather than it; this is 2.0 MiB. Both facts are temporary — it is a base
  character kit, which is what a placeholder should look like.
