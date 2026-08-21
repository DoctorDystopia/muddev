/*
 * The model registry — every asset key that has real art, and nothing else.
 *
 * REQUIRES: blackout_meshes.js (loaded before this file)
 *
 * ONE ENTRY PER MODEL. That is the whole file, and it is deliberately the only
 * place a .glb is named: an item with no line here renders its family's
 * procedural mesh, which is the guarantee that art never blocks content.
 * Adding art to an item is adding a line here, in the same way adding an item
 * is adding a dict entry to ITEM_DB.
 *
 * WHY A FILE RATHER THAN A DIRECTORY SCAN. Registering by convention —
 * models/<asset_key>.glb, and let a 404 mean "no model" — reads as less
 * bookkeeping until you count the requests: 16 items in ITEM_DB and one model
 * between them means fifteen 404s are the NORMAL case, on every pane open, in
 * a console where a real 404 then has nowhere to stand out. A manifest fetched
 * as JSON has the opposite problem: resolve() would have to wait on it before
 * it could tell "no model registered" from "manifest not here yet", which is a
 * gate on the first snapshot in exchange for nothing at this size.
 *
 * The URL prefix is Evennia's STATIC_URL plus this game's static tree. It is
 * spelled out because a plain .js file cannot use the {% static %} tag; if
 * STATIC_URL ever moves, it moves here too.
 *
 * Author: Nick Hobar
 * Creation date: 08/17/2026
 */

(function () {
    "use strict";

    // The served tree mirrors the source tree under assets/, so the family
    // directory is part of what a registration names. assets/pack_model.py
    // decides which one a download lands in, from where the download sits.
    const MODEL_ROOT = "/static/webclient/models/";

    if (!window.blackoutMeshes) {
        console.warn("blackout_models.js: blackoutMeshes is not loaded; "
            + "no models registered, every item stays procedural");
        return;
    }

    const register = function (assetKey, filename, options) {
        window.blackoutMeshes.registerModel(
            assetKey, MODEL_ROOT + filename, options);
    };

    // ─── Weapons ────────────────────────────────────────────────────────────

    // "Rusty sword" by Léonard_Doye / Leoskateman, CC-BY-4.0. Packed from the
    // Sketchfab download by assets/pack_model.py; see models/CREDITS.md.

    // The quarter turn stands it up. The export carries a Y-up conversion
    // matrix that leaves the blade running along Z — pointing straight at the
    // camera in an inventory cell, where a sword is a smudge two pixels wide.
    // +PI/2 rather than -PI/2 puts the TIP up and the guard down, which is how
    // the procedural weapon in tier 2 is built and therefore how the pane's
    // labels and tilt are aimed.
    register("rusty_scrap_shortsword", "items/rusty_scrap_shortsword.glb",
        { rotation: [Math.PI / 2, 0, 0] });

    // ─── NPCs ───────────────────────────────────────────────────────────────

    // "sus eye" by Jeff for no reason., CC-BY-4.0. The key is the NPC_DB key,
    // which is what serializers._classify sends as the asset for anything
    // carrying db.npc_key — so this line is the whole wiring.
    //
    // No rotation: the export already stands eyeball-up with the tail hanging,
    // which is the way the procedural figure it replaces stands.
    //
    // `opaque` because the body material arrived with a base-colour alpha of
    // zero against alphaMode BLEND — an invisible body around a floating
    // eyeball. Nothing measures that; see forceOpaque in blackout_meshes.js.
    // register("floating_eye", "npcs/floating_eye.glb", { opaque: true });
    register("floating_eye", "npcs/floating_eye.glb", { 
        opaque: true,
        position: [0, 1.0, 0]
    });

    // ─── World ──────────────────────────────────────────────────────────────

    // "SM_Teleporter" by Kain Hunter, CC-BY-4.0. Keyed by ROOM KIND rather
    // than by an entity's asset key: this is a prop the world pane draws on a
    // tile, and mapexport names a map-transition node "map_transition" so the
    // tile a `T` glyph spawns can be told from the sand around it.
    //
    // The export is a flat pad twenty units across with a beam thirteen tall,
    // so normalising on the longest axis lands the pad flush with the tile and
    // the beam at about two thirds of one. That is the whole reason it needs
    // no correction here.
    register("map_transition", "world_objects/map_transition.glb");
})();
