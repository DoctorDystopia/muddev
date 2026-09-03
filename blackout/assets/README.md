# Model sources

The **authoring** side of the Godot client's 3D art. What the game actually
serves lives in `web/static/webclient/models/`; this directory holds the
downloads those files were built from, and nothing here is served to anyone.

```
assets/
├── pack_model.py                     the one build step
├── split_tileset.py                  the step in FRONT of it, for tilesets
├── items/weapons/rusty_sword/        one download, as it arrived
│   ├── scene.gltf  scene.bin  textures/  license.txt
├── npcs/sus_eye/
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
   so any asset key packed is one it can resolve. A TERRAIN tile is the
   exception: it has no per-entity asset key to send, so it is registered by
   map instead, in `godot/world/map_palette.gd` (`TILE_MODELS`).
4. Add the credit to `web/static/webclient/models/CREDITS.md`, in the same
   commit. For CC-BY work this is the licence term, not politeness.
5. `evennia reload`, which runs `collectstatic`. A browser refresh alone will
   not pick up a new `.glb`.

Steps 2–4 are three files and no code. An item with no model registered renders
its family's procedural mesh, so a missing step 3 is invisible rather than
broken — check the item actually changed shape before believing it worked. A
TILE prop is the exception: a room kind with nothing registered draws no prop
at all, so there the missing step is simply nothing appearing.

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
