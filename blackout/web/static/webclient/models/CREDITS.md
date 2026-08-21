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
