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

## `items/food_meat.glb`

Built for Blackout by Nick Hobar in picoCAD (https://johanpeitz.itch.io/picocad)
and owned outright — no third-party grant is involved, and the row is here
because a file with no row is indistinguishable from one whose licence nobody
checked.

- Source: `assets/items/food/mh_meat/mh_meat.txt`, the picoCAD save file
  itself. The FIRST model in the served tree that is not somebody's download,
  so the "source" is a project to reopen rather than an archive to keep intact.
- Converted by `assets/picocad_to_gltf.py` into the ordinary source-directory
  shape and packed like any download. picoCAD exports nothing this pipeline can
  read, so the converter is the step in front, the way `fbx_to_gltf.py` and
  `split_tileset.py` are for their formats.
- Textures unchanged at 128²: the picoCAD sheet is 128×120 of PICO-8 palette
  indices, padded to a square by sixteen 8×8 swatches the flat-shaded faces are
  mapped onto. Its sampler is NEAREST with no mipmaps — the padding is a chart
  of colours and a mip level would blend it into the art above.
- **Not a meat model, and not pretending to be one.** It is the stand-in for
  the whole FOOD FAMILY (`FamilyShapes.MODELS`), so every edible in the game is
  a hunk on the bone until the dish has art of its own. Laid on its side by
  `ModelRegistry.PRESENTATION`; the export points along Z, at the camera.

---

## `items/moderator_egg.glb`, the two steaks, the four cured meats, the two sandwiches

"Low Poly Food Asset Pack" by Kyle Fuji (https://www.patreon.com/kylefuji) is
released under CC0 1.0 (https://creativecommons.org/publicdomain/zero/1.0/),
which asks for nothing. The row is here anyway, because a file with no row is
indistinguishable from one whose licence nobody checked.

| Served files | Pack model |
|---|---|
| `items/moderator_egg.glb` | `egg` |
| `items/mutant_raider_steak.glb`, `items/mutant_raider_prime_steak.glb` | `steak` |
| `items/mutant_raider_cured_chuck.glb`, `items/mutant_raider_cured_fatless_meat.glb`, `items/mutant_raider_cured_filet.glb`, `items/mutant_raider_cured_prime_meat.glb` | `meat_haunch` |
| `items/mutant_raider_cured_meat_sandwich.glb`, `items/mutant_raider_prime_cured_meat_sandwich.glb` | `burger` |

- Source download: `assets/items/food/kyle_fuji_food/` — `Models/`, `Textures/`,
  `Materials/`, `Prefabs/` and the original `license.txt`, as the Godot Asset
  Library delivered them, less Godot's `.import` sidecars and seven demo
  scenes; see `SOURCE.md` there.
- The first models from a pack shaped for **Godot**: each `.glb` carries a
  mesh and UVs and no material, the look living in a `.tres` its prefab applies.
  `assets/glb_to_gltf.py` splits one into the ordinary source-directory shape
  and attaches the base-colour atlas that `.tres` names; `pack_model.py` packs
  that. The normal and metallic maps are not carried — nothing an inventory
  cell draws can resolve them.
- Atlases resampled 1024² → 512². Opaque on purpose: the protein atlas's alpha
  channel is the pack's roughness map, not coverage.
- **Several served files are the same bytes under different asset keys.** Two
  steaks, four cured cuts and two sandwiches each share one model, because an
  asset key names one item and the client fetches by key. A player who carries
  only a chuck downloads only the chuck.

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

## `npcs/corpse_skeleton.glb`

"PSX Low Poly Skeleton" (https://puszke.itch.io/psx-low-poly-skeleton) by Puck
is released under CC0 (https://creativecommons.org/publicdomain/zero/1.0/),
which asks for nothing. The row is here anyway, for the reason the Quaternius
one below gives: a file with no row is indistinguishable from one whose licence
nobody checked. The download carries no licence file, so the itch.io page is
the only record of the grant — see `assets/npcs/psx_low_poly_skeleton/SOURCE.md`.

- Source download: `assets/npcs/psx_low_poly_skeleton/` — `.blend`, `.fbx` and
  three recolours of one 128² atlas, as they arrived
- The first model built from an **FBX**. `assets/fbx_to_gltf.py` converts it
  into the ordinary source-directory shape and `pack_model.py` packs that; the
  atlas is named on the converter's command line because the FBX carries UVs
  and no material reference at all. Its sampler is NEAREST — a 128² pixel-art
  atlas filtered any other way arrives as mud.
- Textures unchanged at 128²: already far inside the `npcs` ceiling of 512².
- **Not a corpse model, and not pretending to be one.** It is the stand-in for
  the whole CORPSE FAMILY (`FamilyShapes.MODELS`), so every body in the game is
  a skeleton until the creature that left it has art of its own. Laid on its
  back by `ModelRegistry.PRESENTATION`; the download stands upright.

## `npcs/lone_android.glb`

"Robot_3D_Model" (https://pensamientoazul.itch.io/robot-3d-model) by
PensamientoAzul is released under CC0, per that page: usable in free and
commercial projects, modifiable, with credit appreciated rather than required.
It is credited here anyway. The download carries no licence file, so the page
is the only record of the grant.

- Source: `assets/npcs/lone_android_clark/` — a `.blend` and `.glb` exported
  from the download's FBX; see `SOURCE.md` there
- The first model split by `assets/glb_to_gltf.py --as-exported`: the `.glb`
  already carries its material, which the `--texture` mode refuses to replace
- One flat-colour material and no textures, so packing resampled nothing

## `npcs/shopkeeper.glb`

"Robot" (https://modosa-kun.itch.io/robot2) by Modo (modosa-kun), sold as
name-your-own-price. **The page states no licence**, and a price of zero is not
a grant to redistribute. Ask the author, or record whatever terms the download
itself carries, before this art ships anywhere public — this row records the
source and not the grant, the way the desert tileset's does.

- Source: `assets/npcs/little_robot_shopkeep/` — a `.glb` exported from the
  download's `.blend`; see `SOURCE.md` there
- Split by `assets/glb_to_gltf.py --as-exported` and packed; nine flat-colour
  materials and no textures, so packing resampled nothing

## `world_objects/map_transition.glb`

"SM_Teleporter" (https://skfb.ly/osBBE) by Kain Hunter is licensed under
Creative Commons Attribution (http://creativecommons.org/licenses/by/4.0/).

- Source download: `assets/world_objects/sm_teleporter/` (original
  `license.txt` kept alongside it)
- Packed with `assets/pack_model.py`, textures resampled 2048² → 256²: six maps
  on something drawn flat on one tile, where 512² came to 1.1 MB for detail the
  tile is too small to show

## `characters/player_character.glb`

A test export of an Old School RuneScape player model. The source glTF's
generator is `CreatorsKit`, which names a tool for exporting models out of the
OSRS client, so the art is almost certainly Jagex's. **No grant to
redistribute it is recorded**, and it should not ship anywhere public until
one is, or until it is replaced.

- Source: `assets/characters/old_school_runescape_models/` —
  `OSRS_player_model_test.gltf` (the CreatorsKit export, its buffers embedded
  as data URIs) and `OSRS_player_model_test_blender.glb` (the same model
  round-tripped through Blender)
- Split from the Blender `.glb` by `assets/glb_to_gltf.py --as-exported` and
  packed, 09/13/2026. Until then the served file was that `.glb` copied in
  unpacked, and the manifest row named a directory holding no `scene.gltf`, so
  `pack_model.py --all` failed on it
- 91 flat-colour materials and no textures, so packing resampled nothing

The Quaternius "Universal Base Characters" model it replaced (CC0 1.0) is still
in `assets/characters/quaternius_universal_male/` with its licence file. No
manifest row names it, so nothing packs or serves it.

## `tiles/tile_oasis.glb`, `tiles/tile_oasis_outskirts.glb`

"3D Tileset" (https://wizp.itch.io/3d-tileset) by wizp. **The licence is
whatever that page states; the download carries no licence file.** Confirm the
terms before this art ships anywhere public — a row that records the source but
not the grant is half a licence obligation, and it is recorded that way here
rather than guessed at.

- Source download: `assets/tiles/desert/` — `Tileset.gltf` and
  `ColorPalette.png` as they arrived. The `.dae` and `.fbx` from the same
  download are the same 34 tiles in two other formats and were not kept; see
  `assets/tiles/desert/SOURCE.md`.
- These are TWO NODES out of that one file, split out by
  `assets/split_tileset.py` into ordinary source directories and then packed
  like any download. `tile_oasis` is the tileset's `center_h` (sand, rock
  plates, one small water pool); `tile_oasis_outskirts` is `center_b` (open
  sand with a few pebbles).
- Packed with `assets/pack_model.py`, palette resampled 1024² → 512². The
  ceiling is not about detail: the image is a chart of flat swatches and a
  tile's UVs sit in an 11-pixel column of it, so the resample is bounded by how
  much margin has to survive between one swatch and the next. See the `tiles`
  entry in `assets/asset_budgets.py`.
- **Temporary art.** They are placeholders for a real Blackout tileset, and the
  desert set has no green in it at all — the only non-sand colour anywhere in
  the 34 tiles is the water in five of them.
