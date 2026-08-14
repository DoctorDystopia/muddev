/*
 * Blackout 3D — a live diorama of the game world, docked beside the text.
 *
 * REQUIRES: goldenlayout.js, three.js (loaded before this file)
 *
 * This is a MIRROR, not a controller. It sends exactly one kind of message —
 * the subscription handshake — and never anything else. Everything it draws
 * arrives on the structured state feed (systems/statefeed/), which is itself
 * only a mirror of what the text channel already said. The text pane remains
 * the authoritative, complete view of the game; if this pane is closed,
 * broken, or has no mesh for something, nothing about play changes.
 *
 * That degradation path is deliberate and load-bearing. An entity whose asset
 * key we do not recognise is drawn as a generic marker labelled with its real
 * name, so content can be added to the game without ever waiting on art.
 *
 * Author: Nick Hobar
 * Creation date: 08/07/2026
 */

let blackout3d = (function () {
    "use strict";

    // ─── Channel names (must match systems/statefeed/constants.py) ──────────

    const CH_ROOM_INFO      = "room_info";
    const CH_ROOM_PLAYERS   = "room_players";
    const CH_PLAYER_ADD     = "room_add_player";
    const CH_PLAYER_REMOVE  = "room_remove_player";
    const CH_CHAR_VITALS    = "char_vitals";
    const CH_CHAR_STATUS    = "char_status";
    const CH_CHAR_SUMMARY   = "char_summary";
    const CH_MAP            = "blackout_map";
    const CH_COMBAT         = "blackout_combat";
    const CH_AURA           = "blackout_aura";
    const CH_SUBSCRIBED     = "blackout_subscribed";

    // The channels known at authoring time. This list is a STARTING POINT, not
    // the authority — see bindAcknowledged. It exists only so the handshake
    // channel itself is bound before the first acknowledgement arrives.
    const CHANNELS = [
        CH_ROOM_INFO, CH_ROOM_PLAYERS, CH_PLAYER_ADD, CH_PLAYER_REMOVE,
        CH_CHAR_VITALS, CH_CHAR_STATUS, CH_CHAR_SUMMARY, CH_MAP, CH_COMBAT,
        CH_AURA, CH_SUBSCRIBED
    ];

    // ─── Layout tunables ────────────────────────────────────────────────────

    const TILE_SIZE       = 1.0;    // world units per grid tile
    const TILE_GAP        = 0.18;   // visible seam between tiles
    const TILE_HEIGHT     = 0.16;
    const Z_LEVEL_GAP     = 4.0;    // gap between the disconnected map islands
    const ENTITY_RADIUS   = 0.26;   // ring radius for entities inside one tile
    const ENTITY_SIZE     = 0.13;

    // Z is a map NAME, not an elevation, so the islands' relative placement
    // cannot be derived — it has to be authored. Maps not listed here fall in
    // after the named ones, in arrival order, so a new map still shows up.
    const Z_LAYOUT_ORDER = ["oasis", "oasis_outskirts", "trade town sector 1"];

    // ─── Animation tunables ─────────────────────────────────────────────────

    // The server tick is 0.6s. Every animation below must COMPLETE inside that
    // budget, so the world is never mid-tween when the next state arrives.
    // This is not snapshot interpolation: we do not render in the past, which
    // at this tick rate would be a visible half-second lag on your own moves.
    const SERVER_TICK_MS   = 600;
    const MOVE_TWEEN_MS    = 260;
    const HIT_FLASH_MS     = 320;
    const AMBIENT_BOB_AMP  = 0.035;
    const AMBIENT_BOB_HZ   = 0.35;

    // ─── Camera tunables ────────────────────────────────────────────────────

    // The camera is an orbit rig: it always looks at the local player and is
    // positioned on a sphere around them, so following costs nothing extra —
    // moving the focus point moves the eye with it, at a fixed angle.
    //
    // Pitch here is ELEVATION above the horizon, not three.js's polar angle,
    // because every clamp below is naturally expressed that way: floor it just
    // above ground level, cap it just under straight down. Straight down is
    // excluded on purpose — at exactly PI/2 the look-at up-vector degenerates
    // and the view snaps to an arbitrary yaw.
    const CAM_DISTANCE       = 14.0;    // starting orbit radius, world units
    const CAM_DISTANCE_MIN   = 3.5;
    const CAM_DISTANCE_MAX   = 60.0;
    const CAM_YAW            = 0.40;    // radians; approximates the old fixed view
    const CAM_PITCH          = 0.63;
    const CAM_PITCH_MIN      = 0.12;
    const CAM_PITCH_MAX      = 1.45;
    const CAM_ORBIT_SPEED    = 0.008;   // radians per pixel dragged
    const CAM_ZOOM_STEP      = 1.12;    // distance multiplier per wheel notch
    const CAM_FOCUS_HEIGHT   = 0.30;    // aim above the marker's base, not at it
    const MOUSE_BUTTON_RIGHT = 2;

    // ─── Palette ────────────────────────────────────────────────────────────

    const COLOR_BACKGROUND   = 0x0b0f14;
    const COLOR_TILE_DEFAULT = 0x2b3a4a;
    const COLOR_TILE_CURRENT = 0x35e0c0;
    const COLOR_LINK         = 0x2e4256;
    const COLOR_PLAYER       = 0x35e0c0;
    const COLOR_ENTITY_NPC   = 0xff5f56;
    const COLOR_ENTITY_ITEM  = 0xf0c674;
    const COLOR_ENTITY_CHAR  = 0x7fb3ff;
    const COLOR_HIT_FLASH    = 0xffffff;
    const COLOR_AURA         = 0xff8c42;

    // Known room kinds get a deliberate colour; everything else is hashed to a
    // stable hue so a new room type is visually distinct without an edit here.
    const ROOM_KIND_COLORS = {
        "Bank":                       0x4488ff,
        "Foundry Furnace Facility":   0xdd4422,
        "Metalsmith Anvil Facility":  0xaaaaaa,
        "Pole clearing":              0xcc6633,
        "Shopkeeper":                 0xddcc44,
        "Mutant Raider Tile":         0x8fbf00,
        "Big Mutant Tile":            0xbf3f00
    };

    // ─── Module state ───────────────────────────────────────────────────────

    let debug = false;              // toggled from the options pane

    let scene = null;
    let camera = null;
    let renderer = null;
    let container = null;
    let animationHandle = null;
    let clock = 0;

    let tileGroup = null;
    let entityGroup = null;

    // Everything the feed has told us, kept whether or not a pane exists to
    // draw it. The pane is optional and can be opened at any point in a
    // session, so the feed is recorded first and rendered second — the render
    // side is what gets skipped when there is no scene, never the record side.
    const maps = {};                // z -> {nodes, links, chunksSeen, chunkCount}
    const zOffsets = {};            // z -> world X offset
    const tileMeshes = {};          // "z:x:y" -> Mesh
    const entityMeshes = {};        // entity id -> Mesh
    const flashes = [];             // {mesh, until, baseColor}

    let currentRoom = null;         // {num, coords:[x,y,z], room_kind}
    let lastEntities = [];          // last room_players payload, for replay
    let auraRadius = 0;             // last aura radius, for replay
    let playerMarker = null;
    let playerAnchor = null;        // settled marker position, WITHOUT the bob
    let playerTween = null;         // {from:Vector3, to:Vector3, start, dur}
    let auraRing = null;

    // Orbit rig. These survive a pane rebuild deliberately: re-opening the
    // pane, or activating a saved layout, should not throw away the angle the
    // player chose. The camera OBJECT is rebuilt; these three numbers are not.
    let cameraYaw = CAM_YAW;
    let cameraPitch = CAM_PITCH;
    let cameraDistance = CAM_DISTANCE;
    let cameraFocus = null;         // Vector3 the rig orbits and looks at
    let orbitDrag = null;           // {pointerId, x, y} while right-dragging

    // ─── Private helpers ────────────────────────────────────────────────────

    // Stable pseudo-random hue from a string. Deterministic on purpose: the
    // same room kind must be the same colour every session and for every
    // player, and the same entity must sit in the same spot in its tile
    // between frames rather than jittering.
    const hashString = function (text) {
        let hash = 0;
        for (let i = 0; i < text.length; i++) {
            hash = ((hash << 5) - hash) + text.charCodeAt(i);
            hash = hash & hash;
        }
        return Math.abs(hash);
    };

    const roomKindColor = function (kind) {
        if (!kind) {
            return COLOR_TILE_DEFAULT;
        }
        if (ROOM_KIND_COLORS.hasOwnProperty(kind)) {
            return ROOM_KIND_COLORS[kind];
        }
        const hue = (hashString(kind) % 360) / 360;
        const color = new THREE.Color();
        color.setHSL(hue, 0.42, 0.42);
        return color.getHex();
    };

    const entityColor = function (entity) {
        if (entity.kind === "npc")       { return COLOR_ENTITY_NPC; }
        if (entity.kind === "character") { return COLOR_ENTITY_CHAR; }
        return COLOR_ENTITY_ITEM;
    };

    // Assign each map island a world offset. Named maps keep their authored
    // order; anything new lands after them so it is still visible.
    const offsetForZ = function (z) {
        if (zOffsets.hasOwnProperty(z)) {
            return zOffsets[z];
        }
        let index = Z_LAYOUT_ORDER.indexOf(z);
        if (index < 0) {
            index = Z_LAYOUT_ORDER.length + Object.keys(zOffsets).length;
        }
        const span = 11 * (TILE_SIZE + TILE_GAP) + Z_LEVEL_GAP;
        zOffsets[z] = index * span;
        return zOffsets[z];
    };

    const tileKey = function (z, x, y) {
        return z + ":" + x + ":" + y;
    };

    const tileWorldPos = function (z, x, y) {
        const pitch = TILE_SIZE + TILE_GAP;
        return new THREE.Vector3(
            (x * pitch) + offsetForZ(z),
            0,
            -(y * pitch)
        );
    };

    // Deterministic slot inside a tile, so two entities never overlap and
    // neither of them moves between frames.
    const entitySlotPos = function (basePos, entityId, slotIndex, slotCount) {
        const spread = Math.max(slotCount, 1);
        const jitter = (hashString(String(entityId)) % 100) / 100;
        const angle = ((slotIndex + jitter * 0.35) / spread) * Math.PI * 2;
        return new THREE.Vector3(
            basePos.x + Math.cos(angle) * ENTITY_RADIUS,
            basePos.y + 0.22,
            basePos.z + Math.sin(angle) * ENTITY_RADIUS
        );
    };

    const log = function () {
        if (debug) {
            console.log.apply(console, ["[blackout3d]"].concat(
                Array.prototype.slice.call(arguments)));
        }
    };

    // ─── Scene construction ─────────────────────────────────────────────────

    const buildScene = function (element) {
        scene = new THREE.Scene();
        scene.background = new THREE.Color(COLOR_BACKGROUND);
        scene.fog = new THREE.Fog(COLOR_BACKGROUND, 18, 60);

        camera = new THREE.PerspectiveCamera(50, 1, 0.1, 400);
        cameraFocus = new THREE.Vector3(0, CAM_FOCUS_HEIGHT, 0);

        renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setPixelRatio(window.devicePixelRatio || 1);
        element.appendChild(renderer.domElement);
        bindCameraInput(renderer.domElement);

        scene.add(new THREE.AmbientLight(0xffffff, 0.55));
        const key = new THREE.DirectionalLight(0xffffff, 0.8);
        key.position.set(5, 12, 8);
        scene.add(key);

        tileGroup = new THREE.Group();
        entityGroup = new THREE.Group();
        scene.add(tileGroup);
        scene.add(entityGroup);

        const markerGeo = new THREE.ConeGeometry(0.16, 0.42, 6);
        const markerMat = new THREE.MeshStandardMaterial({
            color: COLOR_PLAYER, emissive: COLOR_PLAYER, emissiveIntensity: 0.6
        });
        playerMarker = new THREE.Mesh(markerGeo, markerMat);
        playerMarker.visible = false;
        scene.add(playerMarker);
        if (!playerAnchor) {
            playerAnchor = new THREE.Vector3();
        }
        playerMarker.position.copy(playerAnchor);
        updateCamera();
    };

    const resizeToContainer = function () {
        if (!renderer || !container) {
            return;
        }
        const width = container.clientWidth || 1;
        const height = container.clientHeight || 1;
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
    };

    // ─── Orbit-follow camera ────────────────────────────────────────────────

    // Re-seat the eye on its orbit around the focus point and aim it there.
    //
    // Called every frame rather than only on change, because the focus point
    // moves whenever the player does: following is not a separate mechanism
    // here, it is what recomputing from a moving focus already does.
    const updateCamera = function () {
        if (!camera || !cameraFocus) {
            return;
        }
        if (playerMarker && playerMarker.visible) {
            cameraFocus.copy(playerAnchor);
            cameraFocus.y += CAM_FOCUS_HEIGHT;
        }
        const horizontal = Math.cos(cameraPitch) * cameraDistance;
        camera.position.set(
            cameraFocus.x + Math.sin(cameraYaw) * horizontal,
            cameraFocus.y + Math.sin(cameraPitch) * cameraDistance,
            cameraFocus.z + Math.cos(cameraYaw) * horizontal
        );
        camera.lookAt(cameraFocus);
    };

    const onCameraPointerDown = function (event) {
        if (event.button !== MOUSE_BUTTON_RIGHT) {
            return;
        }
        orbitDrag = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
        // Capture so a drag that leaves the canvas — very easy in a pane this
        // small — keeps rotating instead of sticking mid-turn.
        if (event.target.setPointerCapture) {
            event.target.setPointerCapture(event.pointerId);
        }
        event.preventDefault();
    };

    const onCameraPointerMove = function (event) {
        if (!orbitDrag || event.pointerId !== orbitDrag.pointerId) {
            return;
        }
        const deltaX = event.clientX - orbitDrag.x;
        const deltaY = event.clientY - orbitDrag.y;
        orbitDrag.x = event.clientX;
        orbitDrag.y = event.clientY;

        // Dragging right swings the world right, i.e. the eye orbits left.
        cameraYaw -= deltaX * CAM_ORBIT_SPEED;
        cameraPitch += deltaY * CAM_ORBIT_SPEED;
        cameraPitch = Math.max(CAM_PITCH_MIN,
            Math.min(CAM_PITCH_MAX, cameraPitch));
        event.preventDefault();
    };

    const onCameraPointerUp = function (event) {
        if (!orbitDrag || event.pointerId !== orbitDrag.pointerId) {
            return;
        }
        if (event.target.releasePointerCapture) {
            event.target.releasePointerCapture(event.pointerId);
        }
        orbitDrag = null;
    };

    const onCameraWheel = function (event) {
        const factor = event.deltaY > 0 ? CAM_ZOOM_STEP : (1 / CAM_ZOOM_STEP);
        cameraDistance = Math.max(CAM_DISTANCE_MIN,
            Math.min(CAM_DISTANCE_MAX, cameraDistance * factor));
        event.preventDefault();
    };

    // Bind to the canvas only. Nothing here touches the rest of the page, so
    // the text pane keeps its normal right-click menu and normal scrolling.
    const bindCameraInput = function (element) {
        element.addEventListener("pointerdown", onCameraPointerDown);
        element.addEventListener("pointermove", onCameraPointerMove);
        element.addEventListener("pointerup", onCameraPointerUp);
        element.addEventListener("pointercancel", onCameraPointerUp);
        element.addEventListener("wheel", onCameraWheel, { passive: false });
        // Without this the browser menu opens on mouse-DOWN on some platforms
        // and swallows the drag before it starts.
        element.addEventListener("contextmenu", function (event) {
            event.preventDefault();
        });
    };

    // ─── Map rendering ──────────────────────────────────────────────────────

    const drawMap = function (z) {
        const data = maps[z];
        if (!data || !tileGroup) {
            return;
        }

        data.nodes.forEach(function (node) {
            const key = tileKey(z, node.x, node.y);
            if (tileMeshes[key]) {
                return;
            }
            const geo = new THREE.BoxGeometry(TILE_SIZE, TILE_HEIGHT, TILE_SIZE);
            const mat = new THREE.MeshStandardMaterial({
                color: roomKindColor(node.room_kind)
            });
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.copy(tileWorldPos(z, node.x, node.y));
            mesh.userData.baseColor = mat.color.getHex();
            tileGroup.add(mesh);
            tileMeshes[key] = mesh;
        });

        if (data.links.length && !data.linksDrawn) {
            const points = [];
            data.links.forEach(function (link) {
                const from = tileWorldPos(z, link.from[0], link.from[1]);
                const to = tileWorldPos(z, link.to[0], link.to[1]);
                from.y += TILE_HEIGHT;
                to.y += TILE_HEIGHT;
                points.push(from, to);
            });
            const geo = new THREE.BufferGeometry().setFromPoints(points);
            const mat = new THREE.LineBasicMaterial({ color: COLOR_LINK });
            tileGroup.add(new THREE.LineSegments(geo, mat));
            data.linksDrawn = true;
        }
    };

    const highlightCurrentTile = function () {
        Object.keys(tileMeshes).forEach(function (key) {
            const mesh = tileMeshes[key];
            mesh.material.color.setHex(mesh.userData.baseColor);
        });

        if (!currentRoom || !currentRoom.coords || currentRoom.coords.length < 3) {
            return;
        }
        const coords = currentRoom.coords;
        const mesh = tileMeshes[tileKey(coords[2], coords[0], coords[1])];
        if (mesh) {
            mesh.material.color.setHex(COLOR_TILE_CURRENT);
        }
    };

    // ─── Entity rendering ───────────────────────────────────────────────────

    const clearEntities = function () {
        Object.keys(entityMeshes).forEach(function (id) {
            entityGroup.remove(entityMeshes[id]);
        });
        Object.keys(entityMeshes).forEach(function (id) {
            delete entityMeshes[id];
        });
    };

    const placeEntities = function (entities) {
        lastEntities = entities;
        if (!entityGroup) {
            return;
        }
        clearEntities();
        if (!currentRoom || !currentRoom.coords || currentRoom.coords.length < 3) {
            return;
        }
        const coords = currentRoom.coords;
        const base = tileWorldPos(coords[2], coords[0], coords[1]);

        entities.forEach(function (entity, index) {
            const geo = new THREE.SphereGeometry(ENTITY_SIZE, 10, 8);
            const mat = new THREE.MeshStandardMaterial({
                color: entityColor(entity)
            });
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.copy(
                entitySlotPos(base, entity.id, index, entities.length));
            mesh.userData.baseColor = mat.color.getHex();
            mesh.userData.entity = entity;
            entityGroup.add(mesh);
            entityMeshes[entity.id] = mesh;
        });
    };

    const flashEntity = function (entityId) {
        const mesh = entityMeshes[entityId];
        if (!mesh) {
            return;
        }
        mesh.material.color.setHex(COLOR_HIT_FLASH);
        flashes.push({
            mesh: mesh,
            until: performance.now() + HIT_FLASH_MS,
            baseColor: mesh.userData.baseColor
        });
    };

    // ─── Aura ring ──────────────────────────────────────────────────────────

    const setAuraRing = function (radius) {
        auraRadius = radius || 0;
        if (!scene) {
            return;
        }
        if (auraRing) {
            scene.remove(auraRing);
            auraRing = null;
        }
        if (auraRadius <= 0) {
            return;
        }
        const pitch = TILE_SIZE + TILE_GAP;
        const geo = new THREE.RingGeometry(
            (radius * pitch) - 0.06, (radius * pitch) + 0.06, 48);
        const mat = new THREE.MeshBasicMaterial({
            color: COLOR_AURA, side: THREE.DoubleSide,
            transparent: true, opacity: 0.55
        });
        auraRing = new THREE.Mesh(geo, mat);
        auraRing.rotation.x = -Math.PI / 2;
        scene.add(auraRing);
    };

    // ─── The frame loop ─────────────────────────────────────────────────────

    const animate = function () {
        animationHandle = requestAnimationFrame(animate);
        if (!renderer) {
            return;
        }

        const now = performance.now();
        clock = now / 1000;

        // Local-player move tween. Started on arrival and always shorter than
        // one server tick, so the marker has settled before the next update.
        if (playerTween) {
            const elapsed = now - playerTween.start;
            const t = Math.min(1, elapsed / playerTween.dur);
            const eased = t * t * (3 - 2 * t);
            playerAnchor.lerpVectors(playerTween.from, playerTween.to, eased);
            if (t >= 1) {
                playerTween = null;
            }
        }

        // Ambient motion. This runs at display rate regardless of the server,
        // and is most of what stops a 0.6s-tick world from reading as frozen.
        //
        // The bob is applied as an OFFSET from the anchor rather than
        // accumulated onto the marker: the anchor is what the camera follows,
        // and a per-frame `+=` would both drift the marker and hand the camera
        // a target that jitters with the frame rate.
        playerMarker.position.copy(playerAnchor);
        if (playerMarker.visible) {
            const bob = Math.sin(clock * Math.PI * 2 * AMBIENT_BOB_HZ);
            playerMarker.position.y += bob * AMBIENT_BOB_AMP;
            playerMarker.rotation.y = clock * 0.6;
        }
        if (auraRing) {
            auraRing.material.opacity = 0.4 + 0.15 *
                Math.sin(clock * Math.PI * 2 * 0.8);
        }

        while (flashes.length && flashes[0].until <= now) {
            const flash = flashes.shift();
            flash.mesh.material.color.setHex(flash.baseColor);
        }

        updateCamera();
        renderer.render(scene, camera);
    };

    // ─── Channel handlers ───────────────────────────────────────────────────

    const onMapChunk = function (data) {
        const z = data.z;
        if (!maps[z]) {
            maps[z] = { nodes: [], links: [], chunksSeen: 0, chunkCount: 0 };
        }
        const entry = maps[z];
        entry.chunkCount = data.chunk_count;
        entry.chunksSeen += 1;
        entry.nodes = entry.nodes.concat(data.nodes || []);
        entry.links = entry.links.concat(data.links || []);

        drawMap(z);
        highlightCurrentTile();
    };

    const onRoomInfo = function (data) {
        const previous = currentRoom;
        currentRoom = data;
        highlightCurrentTile();

        // No scene yet: the room is recorded and buildPane replays it. This is
        // the common case for a player who never opens the pane at all.
        if (!playerMarker) {
            return;
        }
        if (!data.coords || data.coords.length < 3) {
            playerMarker.visible = false;
            return;
        }
        const target = tileWorldPos(data.coords[2], data.coords[0], data.coords[1]);
        target.y += 0.42;

        const adjacent = previous && previous.coords &&
            previous.coords.length === 3 &&
            previous.coords[2] === data.coords[2] &&
            Math.abs(previous.coords[0] - data.coords[0]) <= 1 &&
            Math.abs(previous.coords[1] - data.coords[1]) <= 1;

        if (playerMarker.visible && adjacent) {
            // Only tween between neighbouring tiles. Sliding a character
            // through intervening walls on a teleport reads far worse than a
            // hard cut, so anything non-adjacent snaps. The camera inherits
            // both behaviours for free, since it tracks the same anchor.
            playerTween = {
                from: playerAnchor.clone(),
                to: target,
                start: performance.now(),
                dur: Math.min(MOVE_TWEEN_MS, SERVER_TICK_MS)
            };
        } else {
            playerAnchor.copy(target);
            playerTween = null;
        }
        playerMarker.position.copy(playerAnchor);
        playerMarker.visible = true;
        updateCamera();
    };

    const onCombat = function (data) {
        flashEntity(data.target_id);
        flashEntity(data.attacker_id);
    };

    const onAura = function (data) {
        if (data.event === "activate") {
            setAuraRing(data.radius);
        } else if (data.event === "deactivate") {
            setAuraRing(0);
        } else if (data.event === "pulse" && auraRing) {
            auraRing.material.opacity = 0.9;
        }
    };

    // ─── GoldenLayout wiring ────────────────────────────────────────────────

    // Drop every reference to the previous scene's objects.
    //
    // The pane can be built more than once in a session: GoldenLayout throws
    // the whole layout away and rebuilds it when the user activates a saved
    // layout. The mesh caches survive that, and without clearing them drawMap
    // would skip every tile as "already drawn" — into a scene that no longer
    // exists — leaving the new pane empty. The `maps` data itself is kept, so
    // the world redraws without having to re-request it from the server.
    const resetRenderState = function () {
        Object.keys(tileMeshes).forEach(function (k) { delete tileMeshes[k]; });
        Object.keys(entityMeshes).forEach(function (k) { delete entityMeshes[k]; });
        Object.keys(maps).forEach(function (z) { maps[z].linksDrawn = false; });
        flashes.length = 0;
        playerTween = null;
        auraRing = null;
        // The canvas the drag was captured on is about to be discarded, so the
        // pointerup for an in-flight drag can never arrive. The orbit ANGLES
        // are kept: a rebuilt pane should look the way the player left it.
        orbitDrag = null;

        if (animationHandle && typeof cancelAnimationFrame === "function") {
            cancelAnimationFrame(animationHandle);
            animationHandle = null;
        }
    };

    const buildPane = function (glContainer) {
        const element = glContainer.getElement()[0];
        element.style.width = "100%";
        element.style.height = "100%";
        container = element;

        if (!window.THREE) {
            element.innerHTML =
                "<p style='padding:1em'>three.js is not loaded — " +
                "the 3D view is unavailable. The text pane is unaffected.</p>";
            return;
        }

        resetRenderState();
        buildScene(element);
        resizeToContainer();
        glContainer.on("resize", resizeToContainer);
        animate();

        // Replay whatever the feed has already sent. A pane opened ten minutes
        // into a session must show the world, not wait for the next move.
        Object.keys(maps).forEach(drawMap);
        highlightCurrentTile();

        // Order matters: entities are positioned relative to the current room,
        // so the room has to land first.
        if (currentRoom) {
            onRoomInfo(currentRoom);
        }
        placeEntities(lastEntities);
        setAuraRing(auraRadius);
    };

    // Teach GoldenLayout how to build our pane.
    //
    // This MUST happen before GoldenLayout itself starts, and the only hook
    // early enough is init(). The sequence is: plugin_handler.init() runs
    // every plugin's init(), during which goldenlayout's init() constructs
    // myLayout from the layout saved in localStorage; only afterwards does
    // plugin_handler.postInit() run, and goldenlayout's postInit() is what
    // calls myLayout.init() and actually instantiates the panes.
    //
    // A player who has ever opened the 3D pane has "blackout3d" written into
    // that saved layout. Registering in postInit() is a page-blanking bug for
    // exactly those players: we are the last plugin loaded, so goldenlayout's
    // postInit reaches myLayout.init() first, GoldenLayout throws on the
    // component type it has never heard of, and it throws AFTER goldenlayout's
    // init() has already removed the HTML-defined prompt and input divs — so
    // the whole client renders as a blank page, not just this pane.
    const createComponent = function () {
        const goldenlayout = window.plugins["goldenlayout"];
        if (!goldenlayout) {
            return false;
        }
        const myLayout = goldenlayout.getGL();
        if (!myLayout) {
            return false;
        }
        myLayout.registerComponent("blackout3d", buildPane);
        return true;
    };

    const registerSafely = function (where) {
        try {
            return createComponent();
        } catch (err) {
            console.log("[blackout3d] component registration failed in " +
                where + ": " + err.message);
            return false;
        }
    };

    // GoldenLayout discards the entire layout and constructs a new one when a
    // saved layout is activated, then calls this so plugins can re-register.
    // Without it, the component type is unknown to the new layout and opening
    // the pane fails outright.
    const onLayoutChanged = function () {
        registerSafely("onLayoutChanged");
    };

    const openPane = function () {
        const component = {
            title: "World",
            type: "component",
            componentName: "blackout3d",
            componentState: {}
        };
        const myLayout = window.plugins["goldenlayout"].getGL();
        const main = myLayout.root.getItemsByType("stack")[0].getActiveContentItem();
        main.parent.addChild(component);
    };

    // ─── Plugin interface ───────────────────────────────────────────────────

    // The one and only message this plugin ever sends. Called from two places
    // — see onLoggedIn and bindAcknowledged — because there are two distinct
    // moments a subscription has to be asked for, and only one of them is
    // logging in.
    const subscribe = function () {
        Evennia.msg("blackout_subscribe", [], { channels: "all" });
        log("subscribe sent");
    };

    const onLoggedIn = function () {
        subscribe();
    };

    // Channels this plugin has actually bound a listener for. The authority on
    // "is this message ours", replacing the CHANNELS list, which is now only a
    // seed. Bound once per name; re-binding would double-route every message.
    const boundChannels = {};

    // The most recent char_summary snapshot. Kept rather than rendered: the
    // dossier is text, and this pane is a diorama. It is exposed on the plugin
    // object so a future stats overlay has the data waiting instead of having
    // to ask for a resync.
    let latestSummary = null;

    // Route one feed payload. Every payload arrives as the outputfunc's
    // kwargs. Evennia injects an "options" key into all of them; it is not
    // ours and is ignored.
    //
    // A channel with no branch here is CLAIMED AND DROPPED, deliberately. That
    // is the whole point of binding from the acknowledgement: the server may
    // grow a channel this pane has no use for, and the correct behaviour is
    // silence, not "Error or Unhandled event" printed into the player's text.
    const route = function (cmdname, kwargs) {
        log(cmdname, kwargs);
        const data = kwargs || {};

        if (cmdname === CH_MAP)                { onMapChunk(data); }
        else if (cmdname === CH_ROOM_INFO)     { onRoomInfo(data); }
        else if (cmdname === CH_ROOM_PLAYERS)  { placeEntities(data.entities || []); }
        else if (cmdname === CH_COMBAT)        { onCombat(data); }
        else if (cmdname === CH_AURA)          { onAura(data); }
        else if (cmdname === CH_CHAR_SUMMARY)  { latestSummary = data.panels || {}; }
        else if (cmdname === CH_SUBSCRIBED)    { bindAcknowledged(data.channels); }
    };

    // Bind one named listener per channel, straight onto Evennia's emitter.
    //
    // This is the load-bearing part of the wiring, and it is NOT
    // interchangeable with the onUnknownCmd plugin hook below. DefaultEmitter
    // dispatches to listeners[cmdname] if one exists and only otherwise falls
    // back to listeners["default"] -> plugin_handler.onDefault. And
    // onDefault's very first taker is default_out.js, whose onUnknownCmd
    // returns true unconditionally, claiming every unknown command and
    // printing it as "Error or Unhandled event" — so a plugin loaded after it
    // can never see one. This plugin necessarily loads after it, because
    // Evennia's own plugins occupy the guilib_import block and ours goes in
    // the scripts block below it.
    //
    // Binding by name sidesteps that ordering entirely.
    const bindChannel = function (channel) {
        if (!channel || boundChannels[channel]) {
            return;
        }
        boundChannels[channel] = true;
        Evennia.emitter.on(channel, function (args, kwargs) {
            route(channel, kwargs);
        });
    };

    // Bind every channel the SERVER says we are subscribed to.
    //
    // The server's blackout_subscribed acknowledgement carries the set it
    // actually accepted, and it arrives before the snapshot that follows it —
    // so binding here is early enough for the very first message on a channel
    // this file has never heard of.
    //
    // This exists because the hardcoded list alone was a latent bug, and it
    // fired: adding char_summary to SUBSCRIBABLE_CHANNELS server-side put it
    // into the "all" subscription, the plugin had no listener for it, and
    // default_out.js printed the entire JSON payload at the player as an
    // unhandled event. Any channel added later would have done the same. The
    // client now learns the channel list from the server instead of restating
    // it, which is the same "one owner per fact" rule the Python side follows.
    // An EMPTY set is not "nothing to bind" — it is the server saying it has
    // forgotten us, and the only signal that ever says so. ServerSession
    // .at_sync sends it on connect and after every reload, because a reload
    // wipes the Session ndb subscriptions live on WITHOUT dropping the
    // websocket. Before this branch existed, an `evennia reload` left this
    // pane rendering a world that had silently stopped updating, and only a
    // browser refresh brought it back.
    //
    // onLoggedIn cannot cover that case: it fires once, at login, and a reload
    // is not a login.
    const bindAcknowledged = function (channels) {
        if (!channels || !channels.forEach) {
            return;
        }
        if (channels.length === 0) {
            log("server has no subscription for us");
            subscribe();
            return;
        }
        channels.forEach(bindChannel);
    };

    const bindListeners = function () {
        if (!window.Evennia || !Evennia.emitter) {
            return false;
        }
        CHANNELS.forEach(bindChannel);
        return true;
    };

    // Retained as a fallback only. It fires if this plugin is ever loaded
    // BEFORE default_out.js, in which case onDefault reaches us first and the
    // named listeners are redundant. Harmless either way; routing is
    // idempotent per message.
    const onUnknownCmd = function (cmdname, args, kwargs) {
        if (!boundChannels[cmdname]) {
            return false;
        }
        route(cmdname, kwargs);
        return true;
    };

    const onOptionsUI = function (parentdiv) {
        const openButton = $('<input type="button" value="Open 3D World" />');
        openButton.on("click", openPane);

        const debugBox = $('<input type="checkbox" id="blackout3d-debug" />');
        debugBox.on("change", function () {
            debug = this.checked;
            console.log("[blackout3d] debug logging " + (debug ? "on" : "off"));
        });

        parentdiv.append('<div style="font-weight: bold">Blackout 3D:</div>');
        parentdiv.append(openButton);
        parentdiv.append('<div>Camera: right-click and drag to orbit, ' +
                         'mouse wheel to zoom. It stays centred on you.</div>');
        parentdiv.append('<div><label>Log feed messages </label></div>');
        parentdiv.append(debugBox);
    };

    // Runs while goldenlayout's own init() has already built myLayout but
    // before anything has been instantiated from it. See createComponent.
    const init = function () {
        registerSafely("init");
    };

    const postInit = function () {
        // Belt and braces. If the plugin order ever changes so that our init()
        // ran before goldenlayout's, this is the next chance to register — and
        // re-registering an already-known type is a harmless overwrite.
        registerSafely("postInit");

        // Safe here: webclient_gui.js calls Evennia.init() and wires its own
        // listeners before it calls plugin_handler.postInit(), so the emitter
        // exists by now. We only ADD names; nothing existing is replaced.
        const bound = bindListeners();
        console.log("Blackout 3D plugin loaded." +
            (bound ? "" : " WARNING: emitter unavailable, feed will not route."));
    };

    return {
        init: init,
        postInit: postInit,
        onLayoutChanged: onLayoutChanged,
        onLoggedIn: onLoggedIn,
        onUnknownCmd: onUnknownCmd,
        onOptionsUI: onOptionsUI,
        // Read-only accessor for the last dossier snapshot. Not part of the
        // plugin_handler interface; here so a stats overlay can be built as a
        // separate plugin without re-plumbing the feed.
        getSummary: function () { return latestSummary; }
    };
})();

window.plugin_handler.add("blackout3d", blackout3d);
