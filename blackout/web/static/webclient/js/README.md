# RETIRED — the three.js webclient

**Status: retired 08/27/2026. Superseded by the Godot client in `godot/`.**
Still here, still served, still working. That is deliberate; see below.

Replaced by: [godot/README.md](../../../../../godot/README.md).
Architecture of what is here: `docs/old/2026-08-23-ENG-0004-webclient-architecture.md`.
Why it was replaced: `docs/old/2026-08-25-ENG-0005-godot-vs-webclient.md`.

---

## Retired means "not where new work goes", not "deleted"

Nothing has been moved or removed, and none of it should be. Four reasons, in
order of how much they matter:

1. **It is the fallback when the renderer is not.** The Godot client is one
   canvas: if WebGL2 fails, the engine does not boot and there is no client at
   all. This one degrades — the panes are optional and the text pane is the
   authoritative view of the game, which `plugins/blackout3d.js` states in its
   own header. Keeping it bootable is the cheapest possible mitigation for
   ENG-0006's R5, and it costs nothing to leave alone.
2. **It still boots, so the archive is honest.** An archive that has quietly
   stopped working is not a reference, it is a fossil. This one is exercised
   every time anyone opens `/webclient/`.
3. **The guard tests read it as TEXT.** `test_client_assets.py` walks the module
   graph from `blackout_main.js`, and `test_client_constants.py` compares the
   `ROOM_KIND_COLORS` and `Z_LAYOUT_ORDER` tables in `plugins/blackout3d.js`
   against the Godot client's, key for key. Moving these files breaks both, and
   `test_client_constants.ClientTableDiscoveryTests` fails loudly rather than
   letting the checks go quiet — which is exactly what it is for.
4. **`clientexport` still renders into it.** `generated/blackout_constants.js`
   is regenerated from `systems/statefeed/constants.py` alongside the GDScript
   copy, and a test fails if either is stale. That keeps the archived client in
   step with the server for free.

**So: do not delete these files, and do not move them.** If that ever becomes
the right call, it is a deliberate change that removes the JS half of both guard
tests and the JS language from `clientexport` in the same commit — not a tidy-up.

## What changed, and what did not

`/play` on `playblackout-site` points at the Godot client. This one stays
reachable at `/webclient/` for anyone who wants it and for the reasons above.

Nothing about the server moved. `systems/statefeed/` never knew which renderer
was asking, which is the whole reason swapping one in was cheap: the Godot
contrib overrides exactly one method, `send_text`, to convert ANSI to BBCode.
Both clients are pure consumers of the same frames on two ports.

---

## Original Evennia note

You can replace the javascript files for Evennia's webclient page here.

You can find the original files in `evennia/web/static/webclient/js/`
