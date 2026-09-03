/*
 * Blackout's entry point — the one module tag base.html carries.
 *
 * WHAT THIS REPLACED. Seven <script> tags whose ORDER was the architecture,
 * under a 27-line comment in base.html explaining the six constraints binding
 * them: three.js before the panes, blackout_meshes before blackout_models,
 * blackout_channels before everything, the panes after default_out.js, all of
 * it inside the `guilib_import` block rather than `scripts`. Not one of those
 * was checkable. A reordered tag failed at runtime, sometimes silently — a
 * missing `blackoutMeshes` meant every item in the game rendered as a grey
 * blob, warned once in a console nobody had open, and otherwise worked.
 *
 * Those constraints have not gone away. They are now IMPORTS, so the browser
 * enforces them: each module names what it needs, the graph is evaluated
 * depth-first, and a cycle or a missing file is a load error that names the
 * file instead of a pane that draws nothing.
 *
 * WHY IMPORTING THE PANES IS ENOUGH. Each pane imports the resolver, the
 * channel registry and the generated constants; the resolver imports three.js
 * and the glTF loader. So this file names two modules and gets nine.
 *
 * blackout_models.js is imported for its SIDE EFFECT and nothing else — it
 * exports no value, it registers the .glb files against asset keys. It is
 * named here rather than left to a pane because it belongs to neither: both
 * panes draw the models, and whichever imported it would look like its owner.
 *
 * TIMING, and it is the thing that makes this work at all. A module script is
 * deferred: it runs after every classic script has run, but BEFORE
 * DOMContentLoaded. Evennia's webclient_gui.js calls plugin_handler.init()
 * inside $(document).ready, which fires on DOMContentLoaded. So the window is
 * exactly right — `plugin_handler` already exists when the panes register
 * themselves, and `plugin_handler.init()` has not run yet when they do.
 *
 * Measured rather than assumed, in a browser, against the same jQuery build
 * this page loads. See docs/2026-08-23-ENG-0004-webclient-architecture.md.
 *
 * WHAT IS NOT HERE. plugins/hotkeys.js stays a CLASSIC script and must, which
 * is the one case this file cannot absorb: it has to load before Evennia's own
 * default_in.js or keyboard input breaks, and a module runs after every
 * classic script by definition. A module could not be early enough.
 *
 * Author: Nick Hobar
 * Creation date: 08/23/2026
 */

// Side effect only: registers each .glb against the asset key the server
// sends. Imported first so the registry is populated before a pane can ask
// for a mesh — though nothing depends on that ordering, because a resolve()
// for an unregistered key returns a procedural mesh rather than failing.
import "./blackout_models.js";

// Each of these registers itself with plugin_handler as it evaluates.
import "./plugins/blackout3d.js";
import "./plugins/blackout_inventory.js";
