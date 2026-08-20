# Vendored third-party JavaScript

## `three.min.js` — required by `plugins/blackout3d.js`

Present, pinned at **three.js r159** (`three@0.159.0`), the minified UMD build,
668 KB.

If it is ever missing, the 3D pane renders a short "three.js is not loaded"
message and everything else about the webclient — the text pane, input,
history, the whole default plugin set — works exactly as before. Nothing in the
game depends on it.

### Why vendored rather than a CDN

Evennia's stock `base.html` does pull jQuery, mustache, popper and bootstrap
from CDNs, so a CDN would not be out of character for this page. It is still
the wrong call here:

- A `<script>` from a third-party origin executes with full access to the
  webclient page, which is the page carrying the player's authenticated
  session. Every CDN added is another party who can run code in it.
- The game is expected to run on a LAN or a private host during development.
  A CDN dependency means the 3D pane silently stops working offline, at the
  exact moment it is least obvious why.
- Version drift. A pinned local file renders the same next year.

### Replacing or upgrading the file

    curl -sSL -o three.min.js https://unpkg.com/three@0.159.0/build/three.min.js

**Do not upgrade past r159 without changing `blackout3d.js` first.** three.js
deprecated the UMD build at r150 and *removed* it at r160 — the file still
downloads at newer versions, but you are one release away from the ES-module-only
world, at which point `blackout3d.js` must be rewritten as a module with an
import map. It currently reads the global `THREE`, which an ES-module build
never defines, and the failure mode is a blank pane rather than an error.

The file opens with a `console.warn` about that deprecation. That is expected —
the real, MIT-licensed library follows it in the same file.

It is served from `STATIC_ROOT`, so run `evennia reload` (or `evennia start`)
after replacing it; both run `collectstatic` automatically, and a browser
refresh alone will not pick it up.

### Licence

three.js is MIT licensed. Keep its licence header intact in the minified file.

## `GLTFLoader.js` — required by `blackout_meshes.js` tier 1

Present, pinned at **three.js r147** (`three@0.147.0`), the `examples/js` UMD
build, 103 KB. It attaches `THREE.GLTFLoader` to the global namespace and is
loaded straight after `three.min.js`.

### Why r147 against an r159 core

Because r159 does not have one. three.js deprecated the non-module
`examples/js` directory at r147 and **deleted it at r148**; from r148 onward
the loader ships only as an ES module importing from `'three'`, which the UMD
global build never satisfies. r147 is therefore the newest UMD loader that
exists at all, and pairing it with an r159 core was checked rather than hoped:

- Every one of the 63 `THREE.*` symbols the loader touches is present in the
  vendored r159 build.
- The one API that moved between them is colour space — the loader still writes
  `texture.encoding = THREE.sRGBEncoding`, renamed to `.colorSpace` at r152.
  r159 keeps a compatibility accessor that maps the old property onto the new
  one, so base-colour textures come out correctly sRGB and each one prints a
  deprecation warning saying so.
- Parsing was verified end to end against the real vendored core: a GLB in,
  a `MeshStandardMaterial` with the right factors out.

`toTrianglesDrawMode` is inlined in this build, so unlike the ES-module version
it needs no `BufferGeometryUtils` alongside it.

**This is the same r160 cliff `three.min.js` sits on, and they fall off it
together.** Whichever release forces three.js into ES modules forces this
loader into ES modules on the same day; the fix for both is one import map, not
two separate migrations.

### Replacing or upgrading the file

    curl -sSL -o GLTFLoader.js https://unpkg.com/three@0.147.0/examples/js/loaders/GLTFLoader.js

Draco- and KTX2-compressed models are **not** supported: those need
`DRACOLoader` / `KTX2Loader` vendored beside this file and handed to the loader
instance in `blackout_meshes.js`. A compressed model without them fails to
load, which the resolver reports once and then renders procedurally — the item
is still there and still labelled, it just is not the model you expected.

If this file is missing entirely, `blackout_meshes.js` warns once and every
item falls back to its procedural family mesh. Nothing breaks.

### Licence

MIT, same as three.js itself.

