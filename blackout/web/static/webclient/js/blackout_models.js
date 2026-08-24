/*
 * The model registry — every asset key that has real art, and nothing else.
 *
 * An ES MODULE, imported for its SIDE EFFECT: importing it registers the
 * models. It exports nothing, which is the honest shape -- there is no value
 * here, only the registrations. The "REQUIRES: blackout_meshes.js (loaded
 * before this file)" this used to carry is now an import.
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



import { registerModel } from "./blackout_meshes.js";
import {
ASSET_KEY_CHARACTER, ROOM_KIND_TRANSITION
} from "./generated/blackout_constants.js";

// The served tree mirrors the source tree under assets/, so the family
// directory is part of what a registration names. assets/pack_model.py
// decides which one a download lands in, from where the download sits.
const MODEL_ROOT = "/static/webclient/models/";

// The two keys below that the SERVER owns are imported from the generated
// module; the rest are content keys (an ITEM_DB prototype, an NPC_DB key)
// that no constant names and that this file is the right place to spell.
//
// There is no "is blackoutMeshes loaded?" guard any more. It is an import:
// if it could not be fetched this module never evaluated. The guard used to
// warn and register nothing, which meant a load-order slip silently cost
// every model in the game its art.
const register = function (assetKey, filename, options) {
    registerModel(assetKey, MODEL_ROOT + filename, options);
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
//
// The lift was 1.0 and is 0.16 for the SAME on-screen result. It was never
// really a lift: this model is rigged, measure() used to mis-measure a
// rigged import, and the eye came out of prepare() at twice its intended
// size and offset downward — so a whole unit of correction was what it
// took to sit it on its tile. With the measurement fixed the eye is
// normalised the way every other entity is, and 0.16 puts its base back
// where 1.0 used to put it: 0.024 above the tile against 0.025 before.
//
// It is now HALF the size it was on screen, which is the correction rather
// than a side effect of it — one unit across the longest axis is the
// contract every other mesh in the game is drawn to. If the eye wants to
// be a bigger monster than that, `scale` is the knob that says so out loud.
register("floating_eye", "npcs/floating_eye.glb", {
    opaque: true,
    position: [0, 0.16, 0]
});

// ─── Characters ─────────────────────────────────────────────────────────

// "Spider-man - SM:BND MCU" by YE YE, CC-BY-4.0. See models/CREDITS.md.
//
// The key is const.ASSET_KEY_CHARACTER in systems/statefeed/constants.py,
// which _classify reports for every puppetable character — so this one
// line is what the local player, the person standing next to them, and
// everyone in the neighbourhood are all drawn with. The local player is
// additionally told their own key on `char_avatar`, because the server
// leaves an observer out of their own room_players list.
//
// NO ROTATION, and that is a measured claim rather than an omission. The
// export carries the same Sketchfab Y-up-to-Z-up matrix the rusty sword
// does, so the quarter turn that stands the SWORD up is the obvious thing
// to write here — and it lays this one flat. Measured through resolve():
// no rotation gives a figure 0.340 tall, which is ENTITY_SCALE exactly;
// either quarter turn gives one 0.059 tall and 0.340 deep.
//
// The difference is that this model is rigged, and a rigged import has to
// be measured with its world matrices current or it reads as lying down
// when it is not. See measure() in blackout_meshes.js — that is where the
// box worth believing comes from, and it is worth reading before adding a
// rotation to any rigged model.
//
// No scale bias either. It arrives 1.79 units tall against 1.32 of
// outstretched arms, so normalising on the longest axis is normalising on
// its height, which is what a figure wants.
register(ASSET_KEY_CHARACTER,
    "characters/player_character.glb");

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
register(ROOM_KIND_TRANSITION,
    "world_objects/map_transition.glb");
