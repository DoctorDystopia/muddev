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
