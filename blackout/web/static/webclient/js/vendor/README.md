# Vendored third-party JavaScript

## `three/` — three.js as ES modules

Present, pinned at **three.js r159**, the ES-module build plus the two addons
the resolver needs:

    three/three.module.js                       1.24 MB   -> bare specifier `three`
    three/addons/loaders/GLTFLoader.js            106 KB   -> `three/addons/loaders/GLTFLoader.js`
    three/addons/utils/BufferGeometryUtils.js      31 KB   -> imported by GLTFLoader

The first two are named in the import map in
`web/templates/webclient/base.html`; the third is not, and does not need to be
— GLTFLoader imports it by a RELATIVE path (`../utils/BufferGeometryUtils.js`),
which is why the `addons/` directory structure has to be preserved exactly as
three.js ships it.

### What this replaced, and why

`three.min.js` (the UMD build) and a separately vendored `examples/js`
`GLTFLoader.js`, loaded as classic scripts that assigned the `THREE` global.
Two problems, both now gone:

- **A version ceiling.** three.js deprecated the UMD build at r150 and removed
  it at **r161**, so r159 was the newest version that architecture could ever
  run. The ESM build has no such limit; upgrading is now a normal dependency
  bump.
- **A version MISMATCH that was live.** The UMD loader was r147 paired against
  an r159 core, because r148 deleted the non-module `examples/js` directory —
  r147 was simply the newest UMD loader that existed. It worked only through
  an r159 compatibility accessor mapping the loader's `texture.encoding` onto
  the renamed `.colorSpace`, printing a deprecation warning per texture.
  **The loader and the core are now the same release**, and that whole
  paragraph of justification is deleted rather than maintained.

### This was NOT a version upgrade

Deliberately. r159 → r159, the same code the client was already running, so
nothing about rendering changed and the module conversion could be verified on
its own. **Upgrading three.js is a separate change** with its own API
migration (colour-space handling moved again after r159) and its own
click-testing.

### Replacing or upgrading the files

    V=0.159.0
    curl -sSL -o three/three.module.js "https://unpkg.com/three@$V/build/three.module.js"
    curl -sSL -o three/addons/loaders/GLTFLoader.js "https://unpkg.com/three@$V/examples/jsm/loaders/GLTFLoader.js"
    curl -sSL -o three/addons/utils/BufferGeometryUtils.js "https://unpkg.com/three@$V/examples/jsm/utils/BufferGeometryUtils.js"

If an upgrade makes GLTFLoader import something new, the import will 404 and
the WHOLE module graph fails to load — both panes vanish, not just the models.
`systems/statefeed/tests/test_client_assets.py` walks the graph and catches
exactly that without a browser; add the new file to `_MODULE_ASSETS` there.

Draco- and KTX2-compressed models are still **not** supported: those need
`DRACOLoader` / `KTX2Loader` vendored alongside and handed to the loader in
`blackout_meshes.js`. A compressed model without them fails to load, which the
resolver reports once and then renders procedurally — the item is still there
and still labelled, it just is not the model you expected.

### Licence

MIT.

## `goldenlayout.min.js` — required by `plugins/goldenlayout.js` (Evennia's own)

Present, 66,602 bytes, vendored **08/23/2026** from
`https://golden-layout.com/files/latest/js/goldenlayout.min.js`. Its two
stylesheets are vendored alongside it in `../../css/vendor/`.

### Why vendored

This one is not optional the way three.js is. GoldenLayout **is** the layout
engine: `plugins/goldenlayout.js` builds every pane in the client through it,
and its `init()` removes the HTML-defined prompt and input divs before
constructing the replacements. If the script does not load, the client does not
degrade to a plain text pane — it renders blank.

Evennia's stock template fetched it from `golden-layout.com/files/latest`, with
no SRI and no version. That is a third party able to change the whole client at
any time, and a hard external dependency for anyone self-hosting (see
`docs/2026-08-21-INFRA-0001-public-hosting.md`).

### Why not simply pin a release number

Because `latest` was not any release. Measured on the day it was vendored:

| Source | Bytes |
|---|---:|
| `golden-layout.com/files/latest` | 66,602 |
| cdnjs `golden-layout/1.5.9` | 67,923 |

Swapping the URL for a pinned release would therefore have been a **behaviour
change disguised as a freeze**. Vendoring the exact bytes that were already
running is the only move that changes nothing.

### Replacing or upgrading the file

There is no upgrade path worth taking blind — the panes in
`plugins/blackout3d.js` and `plugins/blackout_inventory.js` depend on
`registerComponent`, `getItemsByType`, `setActiveContentItem` and the
`onLayoutChanged` re-registration dance. **Open the client and click before
committing any replacement**: open both 3D panes, drag one into a stack, save a
layout, and reload.

### Licence

MIT.

## `favico.min.js` — required by `plugins/notifications.js` (Evennia's own)

Present, 9,033 bytes, favico.js **0.3.10**, vendored **08/23/2026**.

### Why vendored, and why this one mattered more than it looked

Evennia's stock template fetched it from `cdn.rawgit.com`. **RawGit shut down
in October 2019.** The URL kept working only because it 301-redirects to
jsDelivr, so the client had been depending on a defunct service's courtesy
redirect for years.

The failure mode if that redirect ever stopped is not a missing favicon badge:

- `notifications.js` calls `new Favico(...)` in its `init()` with no guard.
- `plugin_handler.init()` in `webclient_gui.js` is a bare loop over plugins
  with **no `try`/`catch`**.
- So a `ReferenceError` there aborts the loop, and every plugin loaded *after*
  `notifications.js` never initialises — including `goldenlayout`, and
  including both Blackout panes.

The page renders blank. The `document.write` warning the stock template pairs
with the script could never have caught it either: by the time it runs, writing
to a loaded document replaces the document.

### Replacing or upgrading the file

    curl -sSL -o favico.min.js https://cdn.jsdelivr.net/gh/ejci/favico.js@0.3.10/favico-0.3.10.min.js

### Licence

MIT.
