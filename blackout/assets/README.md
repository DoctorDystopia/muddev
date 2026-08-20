# Model sources

The **authoring** side of the webclient's 3D art. What the game actually serves
lives in `web/static/webclient/models/`; this directory holds the downloads
those files were built from, and nothing here is served to anyone.

```
assets/
├── pack_model.py                     the one build step
└── items/weapons/rusty_sword/        one download, as it arrived
    ├── scene.gltf  scene.bin  textures/  license.txt
```

## Adding a model

1. Drop the download in under `items/<family>/<name>/`, unmodified, licence
   file and all.
2. Pack it, naming the **asset key** it is for — not the file it came from:

   ```bash
   ../evenv/Scripts/python.exe assets/pack_model.py assets/items/weapons/rusty_sword rusty_scrap_shortsword
   ```

3. Register the key in `web/static/webclient/js/blackout_models.js`.
4. Add the credit to `web/static/webclient/models/CREDITS.md`, in the same
   commit. For CC-BY work this is the licence term, not politeness.
5. `evennia reload`, which runs `collectstatic`. A browser refresh alone will
   not pick up a new `.glb`.

Steps 2–4 are three files and no code. An item with no model registered renders
its family's procedural mesh, so a missing step 3 is invisible rather than
broken — check the item actually changed shape before believing it worked.

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
raise it for that model, by packing it separately, rather than for everything.

## Keeping the sources out of git

The packed `.glb` is self-contained, so committing it and *not* the download is
a coherent choice — `assets/` becomes a working directory and the repo carries
128 KB instead of 3.4 MB per model. The cost is that a repack needs the
download fetched again, from a URL recorded only in `CREDITS.md`.

Both are defensible. Committing the sources is the current default because a
CC-BY licence file that lives only on someone's laptop is a licence file that
eventually stops existing.
