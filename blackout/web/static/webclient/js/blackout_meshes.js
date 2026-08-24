/*
 * Blackout mesh resolver — one answer to "what does this item look like".
 *
 * REQUIRES: three.js, then GLTFLoader.js (both loaded before this file)
 *
 * Not a plugin. A plain global that any pane can call, because the answer must
 * not differ between them: the mesh drawn for a spear in the inventory is the
 * mesh drawn for the same spear lying on the ground.
 *
 * THREE TIERS, most specific first:
 *
 *   1. A glTF model registered for the exact asset key, loaded from a .glb
 *      in webclient/models/ and normalised into the same unit box tier 2
 *      builds into. blackout_models.js is where keys are registered.
 *   2. A procedural mesh for the FAMILY the server named. For an item that
 *      is the tag category the item database already declares (weapon, armor,
 *      jewellery, crafting_material, crafting_tool, currency); for anything
 *      else standing in the world it is the entity's kind (npc, character,
 *      station, gatherable). One vocabulary, because the two halves cannot
 *      collide and a caller should not have to decide which it is holding.
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
 * A CALLER OWNS WHAT IT GETS BACK, BUT NOT ALWAYS WHAT HANGS OFF IT. resolve()
 * returns a fresh Object3D every time; a procedural one owns its geometry and
 * materials, a clone of a cached model shares the prototype's with every other
 * clone — except for a SKELETON, which is the one thing a clone must have to
 * itself and must therefore free. Callers hand a mesh back to release() instead
 * of disposing it themselves, because only this module knows which is which.
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

    // The other half of the same vocabulary: what serialize_entity sends as
    // `family` for anything that is not an item, which is its ASSET_KIND_*.
    const FAMILY_NPC        = "npc";
    const FAMILY_CHARACTER  = "character";
    const FAMILY_STATION    = "station";
    const FAMILY_GATHERABLE = "gatherable";

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

    // Moved here from blackout3d.js, where they were the world pane's entity
    // palette. They are the same fact as every colour above — what a thing
    // looks like — and a pane that keeps its own copy is a pane that can
    // disagree with the inventory about what a shopkeeper is.
    const COLOR_NPC        = 0xff5f56;
    const COLOR_CHARACTER  = 0x7fb3ff;
    const COLOR_STATION    = 0x9d7bd8;
    const COLOR_GATHERABLE = 0x7ac74f;
    const COLOR_PANEL      = 0x35e0c0;   // a lit screen on a station

    // Everything is built inside a unit box so a caller can scale one number
    // and get a grid of consistently-sized items regardless of family.
    const UNIT = 1.0;

    // ─── Module state ───────────────────────────────────────────────────────

    // assetKey -> {url, rotation, scale, opaque} for tier 1, from registerModel.
    const models = {};

    // assetKey -> Promise<THREE.Object3D | null>, so ten stacks of the same
    // item cost one load rather than ten. Resolving to NULL is a real answer
    // and a permanent one: it means this key was registered and could not be
    // loaded, and every later resolve of it should go straight to tier 2
    // rather than re-requesting a file that is not coming.
    const prototypes = {};

    // One loader for the module. Built on first use rather than at definition
    // time, so a missing GLTFLoader.js degrades to tier 2 instead of throwing
    // while this file is still being evaluated.
    let gltfLoader = null;

    // Whether the missing-loader warning has been printed. Once is a fact
    // worth knowing; once per item is noise the real errors hide in.
    let warnedNoLoader = false;

    // userData flag: whether the mesh handed out owns the geometry and
    // materials hanging off it and may therefore free them. Absent means owned,
    // so anything this module did not build is disposed as it always was.
    const OWNS_RESOURCES = "blackoutOwnsResources";

    // userData flag on a PROTOTYPE: it holds at least one SkinnedMesh, so it
    // must be copied by cloneSkinned rather than by clone(). Recorded once at
    // prepare() time because it is a fact about the download, and re-deriving
    // it would be a full traversal per entity per snapshot.
    const HAS_SKIN = "blackoutHasSkin";

    // userData flag on a CLONED SkinnedMesh: the skeleton hanging off it was
    // built for that clone alone, and uploads a bone texture of its own.
    const OWNS_SKELETON = "blackoutOwnsSkeleton";

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

    // Visit every material on one node.
    //
    // A glTF primitive drawn with several materials carries an ARRAY here
    // rather than a single material, and every routine that touches materials
    // has to know it. One owner for that, rather than the same two-branch test
    // copied into each of them.
    const eachMaterial = function (node, visit) {
        if (!node.material) {
            return;
        }
        if (Array.isArray(node.material)) {
            node.material.forEach(visit);
            return;
        }
        visit(node.material);
    };

    // Textures are deliberately left alone. Nothing procedural has any, and a
    // model's belong to the cached prototype, which outlives every clone.
    const disposeMaterial = function (material) {
        material.dispose();
    };

    const disposeNode = function (node) {
        if (node.geometry) {
            node.geometry.dispose();
        }
        eachMaterial(node, disposeMaterial);
    };

    // Free the bone texture a rebound skeleton uploaded. Only a skeleton this
    // module built for one clone is freed; a prototype's is shared and outlives
    // every copy of it, exactly as its geometry does.
    const releaseSkeleton = function (node) {
        if (!node.isSkinnedMesh) {
            return;
        }
        if (!node.userData[OWNS_SKELETON]) {
            return;
        }
        node.skeleton.dispose();
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

    // ─── Procedural world kinds ─────────────────────────────────────────────

    // These replace the coloured spheres the world pane drew for everything
    // that was not scenery. A sphere told a player only "something is here",
    // and colour had to carry the whole distinction; a silhouette carries it
    // at a glance and leaves colour free to mean the same thing it means in
    // the inventory.

    // One shape for both kinds of person, because they ARE the same shape.
    // Only the colour separates a wandering NPC from another player, which is
    // the distinction the old palette drew and the one players already read.
    const buildFigure = function (color) {
        const group = new THREE.Group();
        const headGeo = new THREE.SphereGeometry(UNIT * 0.15, 10, 8);
        const head = new THREE.Mesh(headGeo, matte(color));
        head.position.y = UNIT * 0.36;

        const torsoGeo = new THREE.CylinderGeometry(
            UNIT * 0.12, UNIT * 0.2, UNIT * 0.46, 10);
        const torso = new THREE.Mesh(torsoGeo, matte(color));

        const baseGeo = new THREE.CylinderGeometry(
            UNIT * 0.2, UNIT * 0.24, UNIT * 0.24, 10);
        const base = new THREE.Mesh(baseGeo, matte(color));
        base.position.y = UNIT * -0.35;

        group.add(head, torso, base);
        return group;
    };

    const buildNpc = function () {
        return buildFigure(COLOR_NPC);
    };

    const buildCharacter = function () {
        return buildFigure(COLOR_CHARACTER);
    };

    // A console: a plinth with a screen tilted toward whoever is standing at
    // it. Reads as a thing you USE rather than a thing you pick up, which is
    // the one distinction a bank terminal has to make from a dropped item.
    const buildStation = function () {
        const group = new THREE.Group();
        const plinthGeo = new THREE.BoxGeometry(
            UNIT * 0.46, UNIT * 0.34, UNIT * 0.34);
        const plinth = new THREE.Mesh(plinthGeo, matte(COLOR_STATION));
        plinth.position.y = UNIT * -0.26;

        const screenGeo = new THREE.BoxGeometry(
            UNIT * 0.42, UNIT * 0.38, UNIT * 0.07);
        const screen = new THREE.Mesh(screenGeo, metal(COLOR_STATION));
        screen.position.set(0, UNIT * 0.12, UNIT * 0.04);
        screen.rotation.x = -0.34;

        const litGeo = new THREE.BoxGeometry(
            UNIT * 0.3, UNIT * 0.24, UNIT * 0.02);
        const lit = new THREE.Mesh(litGeo, standardMaterial(COLOR_PANEL, 0.1, 0.4));
        lit.position.set(0, UNIT * 0.14, UNIT * 0.11);
        lit.rotation.x = -0.34;

        group.add(plinth, screen, lit);
        return group;
    };

    // A rock with something growing out of it. Deliberately NOT the material
    // family's two lumps: an ore you can carry and a node you mine are
    // different affordances, and drawing them the same way is how the rusty
    // pole came to be offered as `get`.
    const buildGatherable = function () {
        const group = new THREE.Group();
        const rockGeo = new THREE.IcosahedronGeometry(UNIT * 0.3, 0);
        const rock = new THREE.Mesh(rockGeo, matte(COLOR_STONE));
        rock.position.y = UNIT * -0.2;
        rock.rotation.set(0.5, 0.3, 0.2);

        const shardGeo = new THREE.ConeGeometry(UNIT * 0.09, UNIT * 0.4, 6);
        const tall = new THREE.Mesh(shardGeo, matte(COLOR_GATHERABLE));
        tall.position.y = UNIT * 0.22;
        tall.rotation.z = 0.16;

        const short = new THREE.Mesh(shardGeo, matte(COLOR_GATHERABLE));
        short.scale.setScalar(0.62);
        short.position.set(UNIT * 0.17, UNIT * 0.05, UNIT * -0.08);
        short.rotation.z = -0.5;

        group.add(rock, tall, short);
        return group;
    };

    const BUILDERS = {};
    BUILDERS[FAMILY_WEAPON]   = buildWeapon;
    BUILDERS[FAMILY_ARMOR]    = buildArmor;
    BUILDERS[FAMILY_JEWEL]    = buildJewellery;
    BUILDERS[FAMILY_MATERIAL] = buildMaterial;
    BUILDERS[FAMILY_TOOL]     = buildTool;
    BUILDERS[FAMILY_CURRENCY] = buildCurrency;
    BUILDERS[FAMILY_NPC]        = buildNpc;
    BUILDERS[FAMILY_CHARACTER]  = buildCharacter;
    BUILDERS[FAMILY_STATION]    = buildStation;
    BUILDERS[FAMILY_GATHERABLE] = buildGatherable;

    const buildProcedural = function (family) {
        const builder = BUILDERS[family];
        let group = null;

        if (builder) {
            group = builder();
        } else {
            group = buildGeneric();
        }
        group.userData[OWNS_RESOURCES] = true;
        return group;
    };

    // ─── Tier 1: models ─────────────────────────────────────────────────────

    const loader = function () {
        if (gltfLoader) {
            return gltfLoader;
        }
        if (!THREE.GLTFLoader) {
            if (!warnedNoLoader) {
                console.warn("blackoutMeshes: GLTFLoader.js is not loaded; "
                    + "every item falls back to a procedural mesh");
                warnedNoLoader = true;
            }
            return null;
        }
        gltfLoader = new THREE.GLTFLoader();
        return gltfLoader;
    };

    // Force every material in an import opaque.
    //
    // A per-model correction like `rotation`, and it exists for the same
    // reason: an export can be wrong about itself in a way no measurement
    // catches. Sketchfab's converter writes the authoring tool's base-colour
    // ALPHA into the glTF, and the floating eye's body arrived with alpha 0
    // against `alphaMode: BLEND` — a fully transparent material on a mesh that
    // is plainly meant to be seen. Nothing downstream can recover from that:
    // the model loads, reports no error, and renders an invisible body around
    // a floating eyeball.
    const forceOpaque = function (root) {
        root.traverse(function (node) {
            eachMaterial(node, function (material) {
                material.transparent = false;
                material.opacity = 1.0;
            });
        });
    };

    // Record whether an import is skinned, for cloneForCaller to dispatch on.
    const markSkinned = function (root) {
        let skinned = false;

        root.traverse(function (node) {
            if (node.isSkinnedMesh) {
                skinned = true;
            }
        });
        root.userData[HAS_SKIN] = skinned;
    };

    // Measure one subtree, after making sure it knows where its own parts are.
    //
    // THE updateMatrixWorld IS THE WHOLE ROUTINE, and leaving it out is a bug
    // that reads as a broken model rather than a broken measurement.
    //
    // Box3.setFromObject refreshes each node it visits with
    // updateWorldMatrix(false, false) — from the node's own `matrix`, without
    // recomputing that matrix. GLTFLoader leaves an imported node's matrix
    // baked and its matrixAutoUpdate off, so what gets measured is whichever
    // matrixWorld the import happens to be holding at that moment, which for a
    // freshly parsed file is not the one it will render with.
    //
    // Measured on the character model the difference is ninety degrees. Its
    // bind-pose geometry stands 1.790 tall on Y; measured cold it comes back
    // 1.790 deep on Z and 0.308 tall — a figure lying on its back — and
    // measured after this call it comes back upright, which is how it draws.
    //
    // What that costs downstream is not a wrong SIZE. The scale is taken from
    // the longest axis and a person is as tall as they are long, so it lands
    // right by luck; it is the CENTRE that comes out of the wrong axis, and
    // the model ends up offset by half its own height — floating over the
    // tile it is standing on.
    //
    // The trap is that `rotation` looks like the fix. It is what stands the
    // rusty sword up, the export has the same Sketchfab conversion matrix on
    // its root, and a quarter turn does make the BOX agree with the model. It
    // does it by laying the model down. Measured through resolve(), a
    // character registered with rotation [PI/2, 0, 0] is 0.059 tall and 0.340
    // deep; with no rotation at all it is 0.340 tall, which is exactly
    // ENTITY_SCALE and exactly right.
    //
    // Box3's `precise` flag is NOT the answer here and was tried: it walks
    // real vertices through the bone transform, costs a pass over all 39k of
    // them twice per model, and returns the same box either way. The stale
    // matrix is upstream of it.
    const measure = function (bounds, object) {
        object.updateMatrixWorld(true);
        bounds.setFromObject(object);

        return bounds;
    };

    // Fit a loaded scene into the same box a procedural build occupies, and
    // apply the per-key corrections a bounding box cannot infer.
    //
    // This is the whole difference between a model and an ORNAMENT. A download
    // arrives at whatever scale, origin and axis convention its author worked
    // in — the rusty sword is four units long, pivoted under the grip, lying
    // along Z because its exporter wrote a Y-up conversion matrix — while
    // callers scale one number and expect a grid of consistently sized items
    // standing the same way up. Tier 2 promises UNIT across the longest axis,
    // centred, blade up the Y axis. Tier 1 owes the same promise, or the two
    // tiers cannot stand in for each other.
    //
    // THREE NESTED GROUPS, AND EACH ONE EARNS ITS PLACE:
    //
    //   pivot  — identity, and stays that way. It is the caller's handle: the
    //            inventory pane assigns rotation.x and scale outright, so
    //            anything this module writes there is overwritten on placement.
    //   shell  — the measured fit: scale to UNIT, then offset to centre.
    //   frame  — the author correction, rotation only, INSIDE the measurement
    //            so that turning a sword upright re-measures the box it turned
    //            into rather than centring the box it used to fill.
    //
    // Measured twice, deliberately. The first pass sizes the corrected import,
    // the second re-centres what the scaling moved. One pass would mean
    // assuming the imported root has an identity transform, and that Y-up
    // conversion matrix is exactly the case where it does not.
    //
    // Both passes go through measure(), which is where a SKINNED import stops
    // being measurable the cheap way. Read that before adding a `rotation` to
    // a rigged model: the correction a mis-measured skeleton seems to ask for
    // is the one that breaks it.
    const prepare = function (scene, entry) {
        const pivot = new THREE.Group();
        const shell = new THREE.Group();
        const frame = new THREE.Group();
        const bounds = new THREE.Box3();
        const size = new THREE.Vector3();
        const centre = new THREE.Vector3();
        const rotation = entry.rotation;
        const bias = entry.scale || 1.0;

        frame.add(scene);

        if (rotation) {
            frame.rotation.set(rotation[0], rotation[1], rotation[2]);
        }

        shell.add(frame);
        measure(bounds, shell);
        bounds.getSize(size);
        const longest = Math.max(size.x, size.y, size.z);

        if (longest > 0) {
            shell.scale.setScalar((UNIT / longest) * bias);
        }
        measure(bounds, shell);
        bounds.getCenter(centre);
        shell.position.sub(centre);

        // Add positional offset support after auto-centering:
        if (entry.position) {
            shell.position.x += entry.position[0];
            shell.position.y += entry.position[1];
            shell.position.z += entry.position[2];
        }

        pivot.add(shell);

        if (entry.opaque) {
            forceOpaque(pivot);
        }
        markSkinned(pivot);
        return pivot;
    };

    // Load one registered model, or answer that there is none.
    //
    // NEVER returns a rejected promise, and that is the important part. A
    // rejection would propagate into the caller's .then, which is a placement
    // loop — the inventory pane's callback never runs, the slot stays empty,
    // and a cached rejection makes that permanent for the session. Failure is
    // reported as a resolved null instead, which the caller reads as "use
    // tier 2", exactly as an unregistered key does.
    const loadModel = function (assetKey) {
        const entry = models[assetKey];

        if (!entry) {
            return null;
        }
        const gltf = loader();

        if (!gltf) {
            return null;
        }
        return gltf.loadAsync(entry.url).then(function (loaded) {
            return prepare(loaded.scene, entry);
        }).catch(function (error) {
            console.warn("blackoutMeshes: " + assetKey + " failed to load from "
                + entry.url + "; falling back to a procedural mesh", error);
            return null;
        });
    };

    // Walk two matching hierarchies at once, visiting each node beside its
    // counterpart. Safe only because `copy` came from `source.clone()`, so the
    // two trees have identical shape and identical child order — which is what
    // lets a bone be paired with its copy without matching on names a glTF is
    // under no obligation to give them.
    const parallelTraverse = function (source, copy, visit) {
        const children = source.children;

        visit(source, copy);

        for (let i = 0; i < children.length; i += 1) {
            parallelTraverse(children[i], copy.children[i], visit);
        }
    };

    // Copy a SKINNED prototype so the copy stands where it is put.
    //
    // A plain clone() of a skinned model does not. This is not a subtle
    // difference: measured against the floating eye, a clone moved to
    // (7, 0, -3) renders its vertices at the PROTOTYPE's position, exactly as
    // if it had never been moved — so every eye in the world would stack on
    // one spot at the origin, and nothing about the scene graph would look
    // wrong while it happened.
    //
    // The cause is the skinning chain the vertex shader runs:
    //
    //     world = modelMatrix * bindMatrixInverse * boneMatrix * bindMatrix * v
    //
    // clone() copies the SkinnedMesh but leaves `skeleton` pointing at the
    // prototype's, so `boneMatrix` is built from the prototype's bones and
    // carries the prototype's world transform. Meanwhile the default 'attached'
    // bind mode sets `bindMatrixInverse` to the inverse of the CLONE's world
    // matrix — which then cancels the clone's own `modelMatrix` exactly, and
    // what is left is the prototype's placement.
    //
    // The fix is the one three.js prescribes in SkeletonUtils: give the copy
    // its own skeleton, bound to the bones inside the copy. It is written out
    // here rather than vendored because it is twenty lines of the addon and
    // the addon is seven hundred, most of them animation retargeting.
    //
    // Each rebound skeleton uploads a bone texture of its own, so a clone made
    // here has something to free that a plain clone does not; release() is
    // where that is answered.
    const cloneSkinned = function (prototype) {
        const copy = prototype.clone();
        const sourceOf = new Map();
        const cloneOf = new Map();

        parallelTraverse(prototype, copy, function (source, target) {
            sourceOf.set(target, source);
            cloneOf.set(source, target);
        });
        copy.traverse(function (node) {
            if (!node.isSkinnedMesh) {
                return;
            }
            const source = sourceOf.get(node);
            const skeleton = source.skeleton.clone();
            const bones = source.skeleton.bones.map(function (bone) {
                return cloneOf.get(bone);
            });

            skeleton.bones = bones;
            node.bindMatrix.copy(source.bindMatrix);
            node.bind(skeleton, node.bindMatrix);
            node.userData[OWNS_SKELETON] = true;
        });
        return copy;
    };

    // Hand a caller its own copy of a cached prototype.
    //
    // clone() deep-copies the scene GRAPH and shallow-copies everything that
    // hangs off it: the copy points at the prototype's geometry, materials and
    // textures. That sharing is the entire value of the cache — ten stacks of
    // one item upload one set of buffers — and it is exactly why the copy must
    // be marked as not owning them before it leaves this module.
    //
    // A skeleton is the one thing that cannot be shared; see cloneSkinned.
    const cloneForCaller = function (prototype) {
        const skinned = prototype.userData[HAS_SKIN];
        let copy = null;

        if (skinned) {
            copy = cloneSkinned(prototype);
        } else {
            copy = prototype.clone();
        }
        copy.userData[OWNS_RESOURCES] = false;
        return copy;
    };

    // ─── Public interface ───────────────────────────────────────────────────

    // Name a model file for an asset key.
    //
    // `options` is optional and carries corrections measuring cannot infer:
    //   rotation - [x, y, z] radians, applied before the model is measured, to
    //              stand an export up the way its family's procedural mesh
    //              stands. A bounding box cannot tell you which end is the tip.
    //   scale    - a multiplier on the normalised UNIT size, for a model whose
    //              bounding box is mostly empty space
    //   opaque   - force every material solid, for an export that declares
    //              itself transparent and is not. See forceOpaque.
    const registerModel = function (assetKey, url, options) {
        const entry = options || {};

        entry.url = url;
        models[assetKey] = entry;
    };

    // Whether a model is REGISTERED for a key.
    //
    // Not "is it loaded" and not "will it load" — resolve() answers those, and
    // answers them asynchronously and with a tier 2 mesh when the answer is no.
    // This is for the caller that has to decide whether to ask at all, because
    // for it tier 2 is not a fallback but a wrong answer: the world pane draws
    // a prop on a tile that has art and NOTHING on one that does not, since a
    // generic block on every unmodelled tile is scenery nobody asked for.
    const hasModel = function (assetKey) {
        const entry = models[assetKey];
        const registered = Boolean(entry);

        return registered;
    };

    // Give back a mesh that resolve() handed out.
    //
    // The resolver owns the model cache, so the resolver — not the pane —
    // decides what a mesh is allowed to free. A pane that disposes a clone
    // directly frees the PROTOTYPE's geometry and materials, and every later
    // clone of that asset key then re-uploads its buffers, once per rebuild,
    // for the rest of the session.
    //
    // Takes what resolve() returned, not some child of it: the flag is on the
    // root, and the children of a clone share just as much as the root does.
    const release = function (object) {
        if (!object) {
            return;
        }
        // Before the ownership test, not after it. A clone is precisely the
        // case that owns NO geometry and NO materials and DOES own a skeleton,
        // so a skeleton freed after the early return below is never freed at
        // all — one bone texture per entity that ever walked out of radius.
        object.traverse(releaseSkeleton);

        const owned = object.userData[OWNS_RESOURCES];

        if (owned === false) {
            return;
        }
        object.traverse(disposeNode);
    };

    // Resolve one item to a fresh Object3D.
    //
    // Always returns a Promise, and never returns the cached original — always
    // a clone, because callers position, scale and reparent what they get back.
    // What they may FREE is a narrower question, and release() answers it.
    const resolve = function (assetKey, family) {
        let pending = prototypes[assetKey];

        if (!pending) {
            pending = loadModel(assetKey);
        }
        if (!pending) {
            return Promise.resolve(buildProcedural(family));
        }
        prototypes[assetKey] = pending;
        return pending.then(function (prototype) {
            if (!prototype) {
                return buildProcedural(family);
            }
            return cloneForCaller(prototype);
        });
    };

    return {
        resolve: resolve,
        release: release,
        registerModel: registerModel,
        hasModel: hasModel
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
