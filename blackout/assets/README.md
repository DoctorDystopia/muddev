# 3D models

This directory builds every 3D model that the Godot client shows. It is the
**authoring** side. The served files are in `web/static/webclient/models/`,
and the build writes every file there.

```
assets/
├── sources/<source_id>/                 one download, exactly as it arrived
│   └── source.toml                      author, URL, license, file hashes
├── models/<family>/<asset_key>.toml     one served model = one model record
├── pipeline/                            the build (python -m assets.pipeline)
├── build.lock.json                      what each served model was built from
├── package.json, package-lock.json      the Node half of the build
└── README.md
```

## Setup (one time, 5 minutes)

1. Install Node 20 or later.
2. In `blackout/assets/`, run `npm ci`.
3. Install Blender. You need it only for a source that is not glTF (FBX, OBJ,
   `.blend`). Set `BLENDER_EXE` if Blender is not in a standard location.

The check (`python -m assets.pipeline check`) and the test suite need neither
Node nor Blender.

## Add a model

Run each command from `blackout/`.

1. Put the download in `sources/`:

   ```bash
   ../evenv/Scripts/python.exe -m assets.pipeline fetch polyhaven wooden_crate_01
   ../evenv/Scripts/python.exe -m assets.pipeline fetch file C:/Downloads/pack.zip itch_kenney_city
   ```

   A Poly Haven fetch fills in the whole source record. A file fetch writes
   `TODO` in each field.
2. Open `sources/<source_id>/source.toml` and replace every `TODO`. Read the
   license on the download page. On itch.io the license is different on each
   page.
3. Write the model record:

   ```bash
   ../evenv/Scripts/python.exe -m assets.pipeline new items rusty_scrap_shortsword sketchfab_rusty_sword scene.gltf
   ```

4. Build it:

   ```bash
   ../evenv/Scripts/python.exe -m assets.pipeline build rusty_scrap_shortsword
   ```

5. Run `evennia reload`, and look at the model in the client. If it faces the
   wrong way or looks wrong, add a `[fix]` to its record and build again.
6. Commit the source, the record, `build.lock.json`, and the served tree in one
   commit.

The format of the download does not change a step. The build reads glTF and
GLB directly, runs a picoCAD save file (`.txt`) through `pipeline/picocad.py`,
and runs every other format through Blender.

## The source record

```toml
title     = "Rusty sword"
author    = "Léonard_Doye / Leoskateman"
url       = "https://sketchfab.com/3d-models/rusty-sword-42a0..."
site      = "sketchfab"
license   = "CC-BY-4.0"          # an SPDX id
retrieved = 2026-08-17
notes     = "Optional. Anything the next person must know."
exception = ""                   # optional. See "The license gate"

[files]                          # written by `seal`. Never edit it by hand
"scene.gltf" = "sha256:..."
```

**Never edit the art in a source.** Put a correction in the model record. If
you must change a file in a source (a wrong texture path, for example), say so
in `notes`, then run `python -m assets.pipeline seal <source_id>`. The check
fails on any file that does not match its hash.

## The license gate

The build refuses a source whose license is not one of these:

| SPDX id | Credit required |
|---|---|
| `CC0-1.0` | No |
| `CC-BY-3.0`, `CC-BY-4.0` | Yes |
| `LicenseRef-Blackout-Owned` | No. Art made for Blackout |

NC, ND and SA licenses, "Sketchfab Standard", and `TODO` are refused.
`pipeline/licenses.py` gives the reasons.

To serve a source anyway, add an `exception` with the reason. The check prints
every exception on every run, and the credits box marks it as "License not
confirmed". Two sources use an exception today: the OSRS player character and
the shopkeeper robot. Replace both before a public release.

## The model record

The file name is the asset key, and the directory is the family.

```toml
source  = "godot_kyle_fuji_food"          # a directory in sources/
file    = "Models/meat_haunch.glb"        # a file in that source
aliases = ["mutant_raider_cured_filet"]   # more keys that draw this model
node    = "center_h"                      # optional: one node of a tileset

[texture]                                 # optional
image     = "Textures/T_protein_atlas_diffuse.png"
roughness = 0.7

[fix]                                     # optional
rotate = [0, 90, 0]                       # degrees, baked into the file
opaque = true
filter = "nearest"                        # for pixel art and palettes

[output]                                  # optional
max_texture_edge = 256                    # below the family budget
texture_format   = "webp"                 # for photo textures only
```

| Field | Use it when |
|---|---|
| `aliases` | Two or more asset keys use one model. The build writes one file, and the client downloads it one time |
| `node` | One file holds many models, for example a tileset. Run a build with a wrong name, and the error lists every node |
| `[texture]` | The mesh has UVs, but its look is outside the file: a Godot Asset Library pack (the look is in a `.tres`), or an FBX with no image. It replaces every material with one opaque material |
| `[fix] rotate` | The model faces the wrong way. The rotation is baked into the file |
| `[fix] opaque` | A material says it is transparent, but the model must be solid |
| `[fix] filter` | The texture is pixel art or a palette. `nearest` also resizes with the nearest kernel |

**A fix corrects the EXPORT.** A display choice is the client's own and stays
in `ModelRegistry.PRESENTATION`. Two examples: the corpse skeleton lies on its
back because it stands in for a body, and the floating eye is lifted to look
level.

### Face +Z, with +Y up

glTF and Godot 4 use these conventions. A model that faces another way needs a
`rotate`. In Blender, face -Y with +Z up, and the exporter converts it.

## What the build does

| Step | Tool | What it does |
|---|---|---|
| 1. Ingest | Blender, or `picocad.py` | Only for a source that is not glTF |
| 2. Record and optimize | glTF Transform (`pipeline/build_model.mjs`) | Take the node, attach the texture, bake the fix, remove unused data, resize textures to the family budget |
| 3. Validate | Khronos glTF Validator | An error stops the model |
| 4. Budget | `pipeline/budgets.py` | Bytes, triangles and texture edge. Over budget stops the model |

Then it writes `manifest.json`, `credits.json` and `CREDITS.md` beside the
served models, and `build.lock.json` here. A second build with no change does
no work. `--force` builds again anyway. The same inputs give the same bytes.

The build removes a glTF extension that Godot cannot read at runtime, if the
file does not require it. If the file requires it, the build stops.
`pipeline/glb.py` holds the list. Draco, meshopt and mesh quantization are
never on it: every other glTF tool supports them, and Godot's runtime loader
does not.

Textures are lossless PNG by default. `texture_format = "webp"` gives lossy
WebP, which is much smaller for a photo texture. Never use it for pixel art or
a palette.

## The check

```bash
../evenv/Scripts/python.exe -m assets.pipeline check
```

It writes nothing. `systems/interface/statefeed/tests/test_model_pipeline.py`
runs it in the test suite. It fails on:

- a record or source that does not load, or a missing file
- a source that fails the license gate, or a file that does not match its hash
- a served model that is stale, over budget, not from the build, or uses an
  extension that Godot cannot read
- a `.glb` in the served tree that no record builds
- a stale `manifest.json`, `credits.json` or `CREDITS.md`

It warns about each license exception and each source that no record uses.

## Why the design is this way

- **Why glTF.** The Godot docs recommend glTF 2.0, and `.glb` is the smaller
  form. Khronos maintains it as a delivery format.
- **Why runtime fetch, not Godot import.** Art inside the `.pck` downloads
  before the login prompt on the web. `ModelLoader` fetches each `.glb` after
  login instead.
- **Why the sources are in git.** A CC-BY license file that lives only on one
  laptop stops existing. The hashes in each source record let the sources move
  to Git LFS or R2 later with no trust in the copy.
- **Why records, not a manifest.** Before 09/18/2026, the facts about one
  model lived in up to six files, and five converter scripts did the work in
  4,050 lines. Now one record holds the model, and one source record holds the
  download.

For the other commands (`inspect`, `budgets`, `seal`), run
`python -m assets.pipeline` with no argument.
