# 3D models

This directory builds every 3D model that the Godot client shows. It is the
**authoring** side. The served files are in `web/static/webclient/models/`,
and the build writes every file there.

```
assets/
├── sources/<source_id>/                 one download, exactly as it arrived
│   └── source.toml                      author, URL, license, file hashes
├── models/<family>/<asset_key>.toml     one served model = one model record
├── figure/                              the rigs, the worn looks, the clip lists and the palette
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
local     = false                # optional. See "A local source"

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
| `LicenseRef-Purchased` | No. A pack that Nick bought. Its source must be a local source |

NC, ND and SA licenses, "Sketchfab Standard", and `TODO` are refused.
`pipeline/licenses.py` gives the reasons.

## A local source

This repository is public. A purchase lets Blackout use the art. It does not
let Blackout give the download to other people. Thus, the files of a bought
pack stay out of git.

1. Add `local = true` to the source record, above `[files]`.
2. Run `python -m assets.pipeline seal <source_id>`. The seal writes a
   `.gitignore` into the source directory. git then keeps only `source.toml`
   and that `.gitignore`.
3. Commit the source record, the `.gitignore`, the model record,
   `build.lock.json`, and the served tree. Keep your own copy of the files.

The served `.glb` is the game, and it stays in git.

On a machine with no copy of the files, the check skips the file hashes of
that source and prints a warning. It still compares the served file with the
lock file. Such a machine cannot build a model of that source. After a change
to the pipeline code, build on the machine that holds the files.

The license gate refuses `LicenseRef-Purchased` on a source that is not local.
No `exception` waives that. The check fails on a local source that has no
`.gitignore` from the seal.

To serve a source anyway, add an `exception` with the reason. The check prints
every exception on every run, and the credits box marks it as "License not
confirmed". Two sources use an exception today: the shopkeeper robot and the
machine gun. Replace both before a public release. The OSRS player character
used one until 10/16/2026, and the figure replaced it.

## A source for clips

A source can hold a rig with clips, and no model record. The figure
workbench of the Godot project takes clips from it through a clip list:
`figure/clips/<source_id>.json`. The file name is the source id.
`godot/README.md` gives the steps.

The same rules hold for such a source. Fetch it, fill in the source record,
and seal it. The check counts a source that a clip list names as a used
source. `test_figure_files.py` fails on a clip list whose source does not
pass the license gate. `kaykit_adventurers` is the first one.

## A figure model

A figure model is a model whose nodes are parts of a figure: a helm, a
chainbody, a head of hair. Nick makes it in a modeler, over the reference
body that the figure workbench exports. `godot/README.md` gives those steps.

One command does steps 1 to 4 of "Add a model" for such a file, with no
`TODO` to replace. The import button of the figure workbench runs it, so the
author needs no terminal:

```bash
../evenv/Scripts/python.exe -m assets.pipeline figure-model items copper_great_helm C:/art/helm.glb --author "Nick Hobar"
```

| It writes | With |
|---|---|
| `sources/blackout_<model_key>/` | The file, as `<model_key>.<suffix>`, and a source record with `LicenseRef-Blackout-Owned` |
| `models/<family>/<model_key>.toml` | `color_roles = true` |
| The served `.glb`, `build.lock.json`, and the generated files | The build of that one model |

The rules of the command:

- **The family is `items` for the model of an item.** The inventory then
  draws the same file. Use `figure` for a model that is no item: a body, a
  head of hair.
- **A second import of one key puts the new file in the place of the old
  file.** The source of an import is art of Blackout, and a new export is a
  new download. The model record keeps each line but its `file` line, so a
  `[fix]` stays.
- **It refuses a key that another model record has**, as a file name or as
  an alias. Take the key out of that record first.
- **It refuses a source that is not `LicenseRef-Blackout-Owned`.** It never
  writes over a download.
- **The file must be in figure space:** the feet at the origin, +Y up, the
  face to +Z. The figure workbench does not put a figure model in the unit
  box.

`[output] color_roles = true` keeps the name of each material. In a figure
model, the name of a material is a color role of a worn look. The build
joins two materials that differ in the name only, and this field stops
that.

Since 10/16/2026 a model can also replace ONE part of any look, the body
included (DESIGN-0014 section 20). The part editor of the figure workbench
runs the same command for it: **Import model for part**. Its key is
`<look>_<part>` by default, for example `body_1_head`, in the family
`figure`. The part takes the node with its own name or with the name of
its bone, and each other part of the look stays. A `.blend` file and a
Blender `.glb` file both went through this path on 10/16/2026, a head and a
cap of hair for `body_1`. `reports/figure-player/` has the result.

## The figure set

The figure workbench writes one file for each rig and for each worn look,
into `figure/rigs/` and `figure/looks/`. It writes one palette file also,
`figure/palette.json`: the color and the finish of each named color that a
worn look names. The build puts the content of each one into one served
file, `figure.json`, beside the served models. The client makes one fetch
for all of them, and a new worn look needs no client export.

A tier is a worn look with a `base` and no part: the copper helm takes the
parts of the scrap helm, and it names only its own colors. With no palette
file, `figure.json` has an empty palette, and the client takes each named
color from its own start table.

`test_figure_files.py` checks the names of these files. Each color that a
look or a color role names must be in the palette. No two bases name each
other. Each stance of `godot/world/figure/stances.json` names a tool type
of the server, and each clip of it is a clip file.

`figure.json` is a generated file, as `manifest.json` is. Never edit it by
hand. The check fails on a stale one. A save in the figure workbench writes
it again. After a change to a figure file with another tool, run:

```bash
../evenv/Scripts/python.exe -m assets.pipeline figure-set
```

That command needs no Node, and it builds no model.

The game reads `figure.json` since 10/16/2026: each player character is a
figure of that file (DESIGN-0014 section 20). The client fetches it from
the origin of the models at its start and at each `char_avatar`. Thus:

- **Local:** a save in the workbench, then `evennia reload`. The reload
  copies the static files, and the client fetches the new file.
- **Public:** a save, then `deploy/webexport/publish.sh --changed-only`. The
  file and each new model go to R2 with no new client export.

The player model of the Jagex CreatorsKit left the served tree on
10/16/2026, with its source and its record. No model has the key
`player_character` now.

## The model record

The file name is the asset key, and the directory is the family.

```toml
source     = "godot_kyle_fuji_food"          # a directory in sources/
file       = "Models/meat_haunch.glb"        # a file in that source
aliases    = ["mutant_raider_cured_filet"]   # more keys that draw this model
variant_of = "rusty_pole"                    # optional: a second look of that model
node       = "center_h"                      # optional: one node of a tileset

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
animations       = false                  # drop every animation
color_roles      = true                   # keep the name of each material
```

| Field | Use it when |
|---|---|
| `aliases` | Two or more asset keys use one model. The build writes one file, and the client downloads it one time |
| `variant_of` | The model is a second look of another model: a bent rusty pole beside the straight one. The build writes `variants.json` beside the manifest. A chunk object picks a variant by its key, or lets the client pick one by a hash of its tile. The base must be a record of its own, not an alias, and not a variant itself. See "Variants" |
| `node` | One file holds many models, for example a tileset. Run a build with a wrong name, and the error lists every node |
| `[texture]` | The mesh has UVs, but its look is outside the file: a Godot Asset Library pack (the look is in a `.tres`), or an FBX with no image. It replaces every material with one opaque material |
| `[fix] rotate` | The model faces the wrong way. The rotation is baked into the file |
| `[fix] opaque` | A material says it is transparent, but the model must be solid |
| `[fix] filter` | The texture is pixel art or a palette. `nearest` also resizes with the nearest kernel |
| `[output] animations` | The file carries animations that the client does not play, and they put it over budget. `false` drops all of them. The model keeps its rest pose |
| `[output] color_roles` | The model is a figure model. `true` keeps the name of each material. See "A figure model" |

**A fix corrects the EXPORT.** A display choice is the client's own and stays
in `ModelRegistry.PRESENTATION`. Two examples: the corpse skeleton lies on its
back because it stands in for a body, and the floating eye is lifted to look
level.

### Variants

A variant is one more model record, with `variant_of` set to the key of the
base (Nick, 10/16/2026). Thus, a variant has its own source, its own fix, and
its own budget. The build serves it under its own key, and `variants.json`
lists it under its base:

```json
{
  "rusty_pole": ["rusty_pole_bent", "rusty_pole_short"]
}
```

A chunk object pins a variant in its `look` (`"variant": "rusty_pole_bent"`),
or asks for any (`"variant": "*"`). With any, the client picks the base or
one variant from a hash of the tile, so fifty poles vary with no edits. An
object with no variant draws the base. A variant key that the client cannot
fetch draws the base too. The terrain editor lists the variants of the model
of each kind, so an author never types a key. `world/tests/test_tile_content.py`
checks each pinned variant of the world against the records.

### Face +Z, with +Y up

glTF and Godot 4 use these conventions. A model that faces another way needs a
`rotate`. In Blender, face -Y with +Z up, and the exporter converts it.

## What the build does

| Step | Tool | What it does |
|---|---|---|
| 1. Ingest | Blender, or `picocad.py` | Only for a source that is not glTF |
| 2. Record and optimize | glTF Transform (`pipeline/build_model.mjs`) | Take the node, attach the texture, bake the fix, remove an all-black emissive texture, remove unused data, resize textures to the family budget |
| 3. Validate | Khronos glTF Validator | An error stops the model |
| 4. Budget | `pipeline/budgets.py` | Bytes, triangles and texture edge. Over budget stops the model |

Then it writes `manifest.json`, `variants.json`, `credits.json`, `CREDITS.md`
and `figure.json` beside the served models, and `build.lock.json` here. A second build with no change does
no work. `--force` builds again anyway. The same inputs give the same bytes.

The build removes a glTF extension that Godot cannot read at runtime, if the
file does not require it. If the file requires it, the build stops.
`pipeline/glb.py` holds the list. Draco, meshopt and mesh quantization are
never on it: every other glTF tool supports them, and Godot's runtime loader
does not.

An emissive texture that is black in every pixel emits nothing, and it stops
the hover glow. Godot imports a glTF emissive texture as a multiplier of the
emission colour, and the glow writes that colour. Thus, the build removes it.
VoxEdit writes one on every material.

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
- a local source with no `.gitignore` from the seal
- a served model that is stale, over budget, not from the build, or uses an
  extension that Godot cannot read
- a `.glb` in the served tree that no record builds
- a stale `manifest.json`, `variants.json`, `credits.json`, `CREDITS.md` or
  `figure.json`
- a variant whose base is an alias, a variant itself, or no record
- a rig or a worn look that is not valid JSON, or whose key is not its file
  name

It warns about each license exception, each source that no record uses, and
each local source whose files are not on the machine.

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
