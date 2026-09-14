# Model sources

The **authoring** side of the Godot client's 3D art. What the game actually
serves lives in `web/static/webclient/models/`; this directory holds the
downloads those files were built from, and nothing here is served to anyone.

```
assets/
├── pack_model.py                     the one build step
├── split_tileset.py                  a step in FRONT of it, for tilesets
├── fbx_to_gltf.py                    a step in FRONT of it, for FBX downloads
├── picocad_to_gltf.py                a step in FRONT of it, for picoCAD saves
├── glb_to_gltf.py                    a step in FRONT of it, for untextured .glb packs
├── items/weapons/rusty_sword/        one download, as it arrived
│   ├── scene.gltf  scene.bin  textures/  license.txt
├── items/food/mh_meat/               built here, not downloaded
│   ├── mh_meat.txt  SOURCE.md         the picoCAD save file IS the art
│   └── scene.gltf  scene.bin  textures/   written by picocad_to_gltf.py
├── items/food/kyle_fuji_food/        a Godot Asset Library pack, 47 models
│   ├── Models/  Textures/  Materials/  Prefabs/  SOURCE.md
│   └── egg/  steak/  meat_haunch/  burger/   written by glb_to_gltf.py
├── npcs/sus_eye/
├── npcs/psx_low_poly_skeleton/       an FBX download, converted in place
│   ├── skeleton.fbx  base.png  SOURCE.md
│   └── scene.gltf  scene.bin  textures/   written by fbx_to_gltf.py
├── npcs/lone_android_clark/          a Blender export, split in place
│   ├── lone_android_clark.blend  lone_android_clark.glb  SOURCE.md
│   └── scene.gltf  scene.bin          written by glb_to_gltf.py --as-exported
├── characters/quaternius_universal_male/
├── world_objects/sm_teleporter/
└── tiles/desert/                     one download holding 34 tiles
    ├── Tileset.gltf  ColorPalette.png  SOURCE.md
    └── center_h/  center_b/           split out of it, one per tile
```

The **top directory** a download sits in — `items`, `npcs`, `characters`,
`world_objects` — is the only thing that decides where the packed file is
served from:
`assets/npcs/x/` can only ever pack into `models/npcs/`. Nothing restates that
mapping, so it cannot be typed inconsistently.

## Adding a model

1. Drop the download in under `<family>/<name>/`, unmodified, licence file and
   all. The one exception is a download that is wrong about itself: the
   Quaternius character's `scene.gltf` names two textures with a `_png` suffix
   no file in the export carries, so those two `uri` strings were corrected on
   the way in. Fix the reference, never the art, and say so in `CREDITS.md` —
   an edit nobody recorded is one the next repack silently loses.
2. Pack it, naming the **asset key** it is for — not the file it came from:

   ```bash
   ../evenv/Scripts/python.exe assets/pack_model.py assets/items/weapons/rusty_sword rusty_scrap_shortsword
   ```

   A third argument overrides `MAX_TEXTURE_EDGE` for that one model. The
   teleporter is packed at 256 because it is drawn flat on a single tile; at
   512 its six maps came to 1.1 MB of detail the tile cannot show.

3. Nothing to register for an ITEM, NPC or CHARACTER model — the client's
   `ModelRegistry` ingests `models/manifest.json` (step 2's output) directly,
   so any asset key packed is one it can resolve. Two kinds of model are the
   exception, both because the server sends no per-entity asset key for them:

   - a TERRAIN tile is registered by map, in `godot/world/map_palette.gd`
     (`TILE_MODELS`);
   - a FAMILY stand-in — one model for every corpse, say — is registered by
     family, in `godot/world/meshes/family_shapes.gd` (`MODELS`).
4. Add the credit to `web/static/webclient/models/CREDITS.md`, in the same
   commit. For CC-BY work this is the licence term, not politeness.
5. `evennia reload`, which runs `collectstatic`. A browser refresh alone will
   not pick up a new `.glb`.

Steps 2–4 are three files and no code. An item with no model registered renders
its family's procedural mesh, so a missing step 3 is invisible rather than
broken — check the item actually changed shape before believing it worked. A
TILE prop is the exception: a room kind with nothing registered draws no prop
at all, so there the missing step is simply nothing appearing.

## Converting an untextured GLB pack

A pack installed from the **Godot Asset Library** is shaped for Godot, not for
a pipeline: every model is a `.glb` holding a mesh and its UVs and **no
material**, and the look is a `StandardMaterial3D` `.tres` a prefab applies with
`material_override`. Packed as-is the model loads, reports nothing, and renders
untextured. `glb_to_gltf.py` is the step in front:

```bash
../evenv/Scripts/python.exe assets/glb_to_gltf.py \
    assets/items/food/kyle_fuji_food/Models/egg.glb \
    assets/items/food/kyle_fuji_food/egg \
    --texture assets/items/food/kyle_fuji_food/Textures/T_protein_atlas_diffuse.png
```

That writes `scene.gltf` and `scene.bin` into the destination, and from there
every step above applies unchanged: a manifest row, a pack, a credit.

- **Find the atlas through the prefab.** `Prefabs/<group>/<model>.tscn` names
  its material; the material's `albedo_texture` names the image. Nothing in the
  `.glb` says which of the pack's atlases it was UV-mapped against.
- **The image is referenced, not copied.** Its `uri` is written relative to the
  destination (`../Textures/...`), because several models share one atlas and a
  copy per model would commit the same half-megabyte once for each.
- **The material is opaque, always.** Pack atlases put ROUGHNESS in the alpha
  channel (`roughness_texture_channel = 3` in the `.tres`); read as coverage,
  that draws the model partly see-through.
- **Base colour only.** Normal, roughness and metallic maps are left out: an
  item is seventy pixels across in an inventory cell, and each map would still
  cost a 512² PNG in the served file. `--roughness` sets the constant, default
  0.7, the `.tres`'s own scalar.
- **It refuses rather than guesses** when a `.glb` already has a material or
  images, holds more than one buffer, or has a primitive with no UVs.
- **Godot's `.import` sidecars and demo scenes are not the download.** Do not
  leave an Asset Library pack where the editor installed it: inside `godot/` it
  ships in the `.pck` before the login prompt. Move it under `assets/`.

## Splitting a Blender export

A `.glb` exported from Blender already says how it looks — its materials are in
it, often flat colours with no texture at all — and the step above refuses to
replace them. `--as-exported` is the same converter with nothing added:

```bash
../evenv/Scripts/python.exe assets/glb_to_gltf.py \
    assets/npcs/lone_android_clark/lone_android_clark.glb \
    assets/npcs/lone_android_clark --as-exported
```

- **Export into the source directory**, under the family the model is for — an
  NPC under `npcs/` — and keep the `.glb` (and the `.blend`) beside what the
  converter writes. Re-export over it, re-run, repack.
- **A flag, not a missing `--texture`.** Forgetting `--texture` on an Asset
  Library mesh is refused rather than quietly producing a grey source.
- **It refuses** a `.glb` with no materials (that wants `--texture`) and one
  carrying images, which `pack_model.py` would ship at authoring size.
- **Materials pass through as authored**, alpha modes included, so the
  manifest test's OPAQUE rule does not apply to these sources; the generator
  string's `--as-exported` mark is how it tells them apart.
- **Face -Y in Blender with +Z up.** The exporter turns that into glTF's +Z
  forward and +Y up, which is how the client expects a character to stand;
  anything else needs a `ModelRegistry.PRESENTATION` rotation.

## Converting an FBX download

Not every download arrives as glTF. itch.io packs routinely ship `.blend` +
`.fbx` + a loose texture, and `pack_model.py` has nothing to point at.
`fbx_to_gltf.py` is the step in front, and like `split_tileset.py` all it does
is manufacture the shape the pipeline already takes:

```bash
../evenv/Scripts/python.exe assets/fbx_to_gltf.py \
    assets/npcs/psx_low_poly_skeleton/skeleton.fbx \
    assets/npcs/psx_low_poly_skeleton --texture base.png
```

That writes `scene.gltf`, `scene.bin` and `textures/` into the download's own
directory, and from there every step above applies unchanged: a manifest row, a
pack, a credit.

- **It runs inside Blender**, which it finds itself; set `BLENDER_EXE` if yours
  is installed somewhere unusual. The script is handed to Blender as its own
  script, so the file you read and the settings that produced a served model
  are the same file.
- **`--texture` names an image beside the FBX**, and is needed more often than
  it should be: an FBX whose mesh carries UVs and whose material references no
  image at all is the normal case for a pack built around a palette atlas. The
  material is then rebuilt as a Principled BSDF with NEAREST sampling — pixel
  art filtered smoothly is pixel art nobody can see. Omit it and the material
  is exported exactly as it arrived.
- **The download is not written to**, only the three generated paths beside it.
  Re-running overwrites those and nothing else.
- **Prefer the FBX to the `.blend`.** A `.blend` carries the author's viewport
  look — the skeleton's is an emission shader against one of three recolours,
  plus a camera and an unused rig — and none of that is art. The FBX is the
  mesh and the UVs, which is all the pipeline wants.

## Splitting a tileset

A tileset is not a download in the sense the step above means. `Tileset.gltf`
in `tiles/desert/` is **34 tiles in one file** sharing one palette image, and
there is no download boundary between them — so `pack_model.py`, which packs a
directory, has nothing to be pointed at. Packing the whole file as one model is
not a workaround either: the bounding box would be the whole set, and the
normalise in the client would leave a single tile under a millimetre across.

`split_tileset.py` is the step in front, and all it does is manufacture the
shape the pipeline already takes:

```bash
../evenv/Scripts/python.exe assets/split_tileset.py \n    assets/tiles/desert/Tileset.gltf assets/tiles/desert center_h center_b
```

That writes `assets/tiles/desert/center_h/` and `.../center_b/` as ordinary
source directories — `scene.gltf`, `scene.bin`, `textures/` — and from there
every step above applies unchanged: a manifest row, a pack, a credit.

Run it with a node name the file does not hold and it prints every name that IS
in there, which is the fastest way to see what a tileset contains.

- **The tileset itself is never written to.** Re-running produces the same
  bytes, exactly as re-packing does.
- **The image comes out as a file, not embedded.** That is the one place the
  output is not a subset of the input, and it is deliberate: `pack_model.py`
  resamples an image it finds at a `uri` and leaves an embedded one alone, so a
  tile split with its palette still inside the buffer would be served at the
  tileset's authoring resolution whatever its family budget says.
- **Materials, textures and samplers are copied whole**, so indices inside the
  surviving mesh stay valid with no remapping. Right for a palette atlas, where
  one image serves every tile; a tileset with a texture per tile would want them
  pruned too, and `_split_document` is where that goes.
- **A tile has to come out a unit SQUARE.** The client normalises by the longest
  axis, so a tile with a decorative lip hanging past its edge — `block_a` reaches
  0.28 past its south side — normalises its 2x2 footprint down to 0.877 and
  leaves a gap between every pair of tiles in the world. Nothing about the file
  is wrong and nothing reports it. `godot/tests/smoke_model_load.gd` measures
  the footprint of every terrain tile for that reason.

## Converting a picoCAD model

Art built here rather than downloaded arrives as neither glTF nor FBX.
[picoCAD](https://johanpeitz.itch.io/picocad) saves one text file — a Lua table
of objects, then a 128×120 sheet of PICO-8 palette indices — and exports nothing
`pack_model.py` can point at. `picocad_to_gltf.py` is the step in front, and
like the two above it all it does is manufacture the shape the pipeline already
takes:

```bash
../evenv/Scripts/python.exe assets/picocad_to_gltf.py \
    assets/items/food/mh_meat/mh_meat.txt assets/items/food/mh_meat
```

That writes `scene.gltf`, `scene.bin` and `textures/` beside the save file, and
from there every step above applies unchanged: a manifest row, a pack, a credit.

- **The save file is the art.** There is no export to keep in step with it —
  edit the `.txt` in picoCAD, re-run the converter, repack. The save file is
  never written to.
- **picoCAD's Y points DOWN and its Z points AWAY**, the way a PICO-8 screen
  does. The conversion is `(x, -y, -z)`, which is a half turn about X — a
  rotation and not a mirror, so face winding carries over and normals stay
  outward. The half turn is the half of this that is *checked*: the first model
  through is near enough symmetric that an upside-down import would look
  identical, so what a render proves is that the mesh, the UVs and the winding
  survive, not which way is up. The first asymmetric model settles it.
- **A flat-shaded face has nowhere to put its colour**, so the 128×120 sheet is
  padded to 128×128 and the eight new rows are written as sixteen 8×8 palette
  swatches for those faces to sit on. One image and one material, rather than a
  primitive per colour. It is also why the sampler is NEAREST with **no
  mipmaps**: a minified mip would blend the swatch strip into the art above it.
- **Everything is drawn double-sided.** picoCAD carries `dbl` per face and glTF
  carries it per material, and the flag only ever makes a face more visible.
- **The header's alpha colour is reported, not applied.** Punching every texel
  of one palette index out of the sheet turns a model somebody painted black
  into a model full of holes; a solid pixel where transparency was wanted is the
  failure a person can see.
- **A rotated object warns.** picoCAD bakes an edited turn into its vertices, so
  `rot` is zero in every file seen so far and the rotation order the converter
  assumes has never been checked against picoCAD's own view. If that warning
  ever prints, look at the model before believing it.

## What packing does, and why

A Sketchfab-shaped download is four HTTP requests (`.gltf`, `.bin`, and a
texture each) and ships textures sized for a hero asset filling a screen. The
rusty sword arrived as two 2048² PNGs — 1.1 MB, for something drawn about two
centimetres wide in an inventory cell, where 512² is already more than the
screen can resolve.

`pack_model.py` resamples the textures to `MAX_TEXTURE_EDGE` and embeds
everything in one self-contained `.glb`: 1.1 MB and four requests become 128 KB
and one. It never writes to the source directory, so re-running it is safe and
the original stays the original.

Raise `MAX_TEXTURE_EDGE` if a model is ever shown large enough to want it — but
raise it for that model, with the optional third argument, rather than for
everything. It cuts both ways: the teleporter is packed at 256 rather than 512
because six maps on a tile-sized pad is where the default stops being honest.

It also normalises what the download declares. Sketchfab still exports
`KHR_materials_pbrSpecularGlossiness`, which the vendored GLTFLoader dropped —
a model left in that form loads with no error and renders flat white, which is
the worst kind of failure because nothing reports it. The packer rewrites those
materials as core metallic-roughness, and refuses rather than approximates when
the material is one it cannot convert exactly.

## Keeping the sources out of git

The packed `.glb` is self-contained, so committing it and *not* the download is
a coherent choice — `assets/` becomes a working directory and the repo carries
128 KB instead of 3.4 MB per model. The cost is that a repack needs the
download fetched again, from a URL recorded only in `CREDITS.md`.

Both are defensible. Committing the sources is the current default because a
CC-BY licence file that lives only on someone's laptop is a licence file that
eventually stops existing.
