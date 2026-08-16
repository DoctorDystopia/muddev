/*
 * Blackout mesh resolver — one answer to "what does this item look like".
 *
 * REQUIRES: three.js (loaded before this file)
 *
 * Not a plugin. A plain global that any pane can call, because the answer must
 * not differ between them: the mesh drawn for a spear in the inventory is the
 * mesh drawn for the same spear lying on the ground.
 *
 * THREE TIERS, most specific first:
 *
 *   1. A glTF model registered for the exact asset key. NOT IMPLEMENTED YET —
 *      see registerModel below, which is the whole hook.
 *   2. A procedural mesh for the item's FAMILY, which is the tag category the
 *      item database already declares (weapon, armor, jewellery,
 *      crafting_material, crafting_tool, currency).
 *   3. A generic block.
 *
 * Tier 2 is what stops art from blocking content. An item added to ITEM_DB
 * renders the moment it exists, in a silhouette that says what kind of thing
 * it is, labelled with its real name — the same guarantee the world pane's
 * generic marker gives.
 *
 * THE API IS ASYNCHRONOUS AND THAT IS DELIBERATE, even though nothing it does
 * today needs to be. A glTF arrives some frames after the slot that wants it,
 * so tier 1 is inherently async; building the callers around a synchronous
 * resolve now would mean rewriting their placement loops later, and placement
 * loops that get rewritten around asynchrony are where frame-loop bugs come
 * from. Resolving an already-loaded value through a Promise costs one
 * microtask.
 *
 * Author: Nick Hobar
 * Creation date: 08/15/2026
 */

let blackoutMeshes = (function () {
    "use strict";

    // ─── Families (must match systems/statefeed/constants.py) ───────────────

    const FAMILY_WEAPON   = "weapon";
    const FAMILY_ARMOR    = "armor";
    const FAMILY_JEWEL    = "jewellery";
    const FAMILY_MATERIAL = "crafting_material";
    const FAMILY_TOOL     = "crafting_tool";
    const FAMILY_CURRENCY = "currency";

    // ─── Palette ────────────────────────────────────────────────────────────

    // Deliberately close to the world pane's entity colours, so an item on the
    // ground and the same item in the inventory read as the same object.
    const COLOR_STEEL   = 0xb9c6d2;
    const COLOR_RUST    = 0x9c5a35;
    const COLOR_GOLD    = 0xf0c674;
    const COLOR_GEM     = 0x7fb3ff;
    const COLOR_STONE   = 0x8a8f98;
    const COLOR_WOOD    = 0x6b4b32;
    const COLOR_GENERIC = 0x7a8894;

    // Everything is built inside a unit box so a caller can scale one number
    // and get a grid of consistently-sized items regardless of family.
    const UNIT = 1.0;

    // ─── Module state ───────────────────────────────────────────────────────

    // assetKey -> {url} for tier 1. Empty until phase 4; see registerModel.
    const models = {};

    // assetKey -> Promise<THREE.Object3D>, so ten stacks of the same item cost
    // one load rather than ten.
    const loading = {};

    // ─── Private helpers ────────────────────────────────────────────────────

    const standardMaterial = function (color, metalness, roughness) {
        return new THREE.MeshStandardMaterial({
            color: color,
            metalness: metalness,
            roughness: roughness
        });
    };

    const metal = function (color) {
        return standardMaterial(color, 0.65, 0.35);
    };

    const matte = function (color) {
        return standardMaterial(color, 0.05, 0.85);
    };

    // ─── Procedural families ────────────────────────────────────────────────

    // Each builder returns a Group centred on the origin and roughly UNIT
    // across its longest axis. Silhouette is doing all the work here — these
    // are read at a couple of centimetres on screen, so what matters is that a
    // blade is not confusable with an ore, not that either is detailed.

    const buildWeapon = function () {
        const group = new THREE.Group();
        const bladeGeo = new THREE.BoxGeometry(UNIT * 0.11, UNIT * 0.66, UNIT * 0.03);
        const blade = new THREE.Mesh(bladeGeo, metal(COLOR_STEEL));
        blade.position.y = UNIT * 0.2;

        const guardGeo = new THREE.BoxGeometry(UNIT * 0.34, UNIT * 0.06, UNIT * 0.06);
        const guard = new THREE.Mesh(guardGeo, metal(COLOR_RUST));
        guard.position.y = UNIT * -0.14;

        const gripGeo = new THREE.CylinderGeometry(
            UNIT * 0.035, UNIT * 0.045, UNIT * 0.26, 8);
        const grip = new THREE.Mesh(gripGeo, matte(COLOR_WOOD));
        grip.position.y = UNIT * -0.3;

        group.add(blade, guard, grip);
        return group;
    };

    const buildArmor = function () {
        const group = new THREE.Group();
        // An open-ended cylinder, squashed on Z, reads as a curved breastplate
        // from the front without needing a modelled torso.
        const torsoGeo = new THREE.CylinderGeometry(
            UNIT * 0.3, UNIT * 0.26, UNIT * 0.5, 12, 1, true);
        const torso = new THREE.Mesh(torsoGeo, metal(COLOR_STEEL));
        torso.scale.z = 0.55;
        torso.material.side = THREE.DoubleSide;

        const collarGeo = new THREE.TorusGeometry(
            UNIT * 0.15, UNIT * 0.035, 6, 14);
        const collar = new THREE.Mesh(collarGeo, metal(COLOR_RUST));
        collar.rotation.x = Math.PI / 2;
        collar.position.y = UNIT * 0.26;
        collar.scale.z = 0.55;

        group.add(torso, collar);
        return group;
    };

    const buildJewellery = function () {
        const group = new THREE.Group();
        const bandGeo = new THREE.TorusGeometry(
            UNIT * 0.24, UNIT * 0.045, 10, 24);
        const band = new THREE.Mesh(bandGeo, metal(COLOR_GOLD));

        const stoneGeo = new THREE.OctahedronGeometry(UNIT * 0.1);
        const stone = new THREE.Mesh(stoneGeo, standardMaterial(COLOR_GEM, 0.2, 0.1));
        stone.position.y = UNIT * 0.26;

        group.add(band, stone);
        return group;
    };

    const buildMaterial = function () {
        const group = new THREE.Group();
        // Two lumps rather than one, so an ore reads as a quantity of raw
        // stuff rather than as a single carved object.
        const bigGeo = new THREE.IcosahedronGeometry(UNIT * 0.26, 0);
        const big = new THREE.Mesh(bigGeo, matte(COLOR_STONE));
        big.rotation.set(0.4, 0.8, 0.2);

        const smallGeo = new THREE.IcosahedronGeometry(UNIT * 0.14, 0);
        const small = new THREE.Mesh(smallGeo, matte(COLOR_RUST));
        small.position.set(UNIT * 0.22, UNIT * -0.18, UNIT * 0.1);
        small.rotation.set(0.9, 0.3, 0.5);

        group.add(big, small);
        return group;
    };

    const buildTool = function () {
        const group = new THREE.Group();
        const shaftGeo = new THREE.CylinderGeometry(
            UNIT * 0.04, UNIT * 0.04, UNIT * 0.62, 8);
        const shaft = new THREE.Mesh(shaftGeo, matte(COLOR_WOOD));
        shaft.position.y = UNIT * -0.08;

        const headGeo = new THREE.BoxGeometry(UNIT * 0.34, UNIT * 0.15, UNIT * 0.15);
        const head = new THREE.Mesh(headGeo, metal(COLOR_STEEL));
        head.position.y = UNIT * 0.26;

        group.add(shaft, head);
        return group;
    };

    const buildCurrency = function () {
        const group = new THREE.Group();
        const coinGeo = new THREE.CylinderGeometry(
            UNIT * 0.22, UNIT * 0.22, UNIT * 0.045, 18);
        const offsets = [-0.09, 0.0, 0.09];

        offsets.forEach(function (offset, index) {
            const coin = new THREE.Mesh(coinGeo, metal(COLOR_GOLD));
            coin.position.y = UNIT * offset;
            coin.rotation.y = index * 0.4;
            group.add(coin);
        });

        return group;
    };

    const buildGeneric = function () {
        const group = new THREE.Group();
        const boxGeo = new THREE.BoxGeometry(UNIT * 0.42, UNIT * 0.42, UNIT * 0.42);
        const box = new THREE.Mesh(boxGeo, matte(COLOR_GENERIC));
        group.add(box);
        return group;
    };

    const BUILDERS = {};
    BUILDERS[FAMILY_WEAPON]   = buildWeapon;
    BUILDERS[FAMILY_ARMOR]    = buildArmor;
    BUILDERS[FAMILY_JEWEL]    = buildJewellery;
    BUILDERS[FAMILY_MATERIAL] = buildMaterial;
    BUILDERS[FAMILY_TOOL]     = buildTool;
    BUILDERS[FAMILY_CURRENCY] = buildCurrency;

    const buildProcedural = function (family) {
        const builder = BUILDERS[family];

        if (builder) {
            return builder();
        }
        return buildGeneric();
    };

    // ─── Tier 1: models ─────────────────────────────────────────────────────

    // Phase 4 fills this in. The shape is fixed now so callers never change:
    // registerModel names a file for an asset key, and resolve() prefers it.
    //
    // Implementing it means adding GLTFLoader to vendor/, serving .glb from
    // the static tree, and returning loader.loadAsync(entry.url) below. The
    // per-key `loading` cache and the clone() in resolve() already assume it.
    const loadModel = function (assetKey) {
        const entry = models[assetKey];

        if (!entry) {
            return null;
        }
        // No loader wired yet. Returning null here — rather than a rejected
        // promise — keeps a registered-but-unloadable key on the procedural
        // path instead of leaving a slot empty.
        return null;
    };

    // ─── Public interface ───────────────────────────────────────────────────

    // Name a model file for an asset key. Phase 4; harmless to call today.
    const registerModel = function (assetKey, url) {
        models[assetKey] = { url: url };
    };

    // Resolve one item to a fresh Object3D.
    //
    // Always returns a Promise, and always returns an object the caller OWNS —
    // a clone, never the cached original — because callers position, scale and
    // dispose what they get back.
    const resolve = function (assetKey, family) {
        const cached = loading[assetKey];

        if (cached) {
            return cached.then(function (prototype) {
                return prototype.clone();
            });
        }
        const model = loadModel(assetKey);

        if (model) {
            loading[assetKey] = model;
            return model.then(function (prototype) {
                return prototype.clone();
            });
        }
        return Promise.resolve(buildProcedural(family));
    };

    return {
        resolve: resolve,
        registerModel: registerModel
    };
})();

// Published on `window` explicitly, and it has to be.
//
// A top-level `let` creates a lexical binding in the global SCOPE but no
// property on the global OBJECT, so `blackoutMeshes` resolves fine from
// another script while `window.blackoutMeshes` stays undefined. Panes guard on
// the window property before building — it is the only form that can be tested
// without throwing a ReferenceError — so without this line every pane would
// correctly report the resolver missing and fall back to its no-3D message.
window.blackoutMeshes = blackoutMeshes;
