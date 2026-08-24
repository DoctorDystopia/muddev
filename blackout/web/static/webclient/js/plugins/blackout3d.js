/*
 * Blackout 3D — a live diorama of the game world, docked beside the text.
 *
 * REQUIRES: goldenlayout.js, three.js (loaded before this file)
 *
 * Everything it draws arrives on the structured state feed
 * (systems/statefeed/), which is itself only a mirror of what the text channel
 * already said. The text pane remains the authoritative, complete view of the
 * game; if this pane is closed, broken, or has no mesh for something, nothing
 * about play changes.
 *
 * That degradation path is deliberate and load-bearing. An entity whose asset
 * key we do not recognise is drawn as a generic marker labelled with its real
 * name, so content can be added to the game without ever waiting on art.
 *
 * IT ALSO DRIVES THE PLAYER, under one rule:
 *
 *     This pane sends only what a telnet player could type. Clicking a tile
 *     sends ["text", ["north"], {}]. There is no privileged client channel
 *     that bypasses a Command.
 *
 * That is not a limitation, it is the guarantee: a graphical client can never
 * do something a text player cannot, so every existing permission, lock and
 * cooldown keeps working with no audit. The one exception is the subscription
 * handshake, which carries no gameplay effect.
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
    const CH_CHAR_AVATAR    = "char_avatar";
    const CH_MAP            = "blackout_map";
    const CH_COMBAT         = "blackout_combat";
    const CH_AURA           = "blackout_aura";
    const CH_SUBSCRIBED     = "blackout_subscribed";

    // The channels known at authoring time. This list is a STARTING POINT, not
    // the authority — see bindAcknowledged. It exists only so the handshake
    // channel itself is bound before the first acknowledgement arrives.
    const CHANNELS = [
        CH_ROOM_INFO, CH_ROOM_PLAYERS, CH_PLAYER_ADD, CH_PLAYER_REMOVE,
        CH_CHAR_VITALS, CH_CHAR_STATUS, CH_CHAR_SUMMARY, CH_CHAR_AVATAR,
        CH_MAP, CH_COMBAT, CH_AURA, CH_SUBSCRIBED
    ];

    // The one family name this pane has to know, because it is the one it
    // asks for on its own behalf rather than passing through from a payload.
    // Must match const.ASSET_KIND_CHARACTER in systems/statefeed/constants.py,
    // the same way every CH_* above matches a CHANNEL_* there.
    const FAMILY_CHARACTER = "character";

    // ─── Layout tunables ────────────────────────────────────────────────────

    const TILE_SIZE       = 1.0;    // world units per grid tile
    const TILE_GAP        = 0.18;   // visible seam between tiles
    const TILE_HEIGHT     = 0.16;
    const Z_LEVEL_GAP     = 4.0;    // gap between the disconnected map islands
    const ENTITY_RADIUS   = 0.26;   // ring radius for entities inside one tile

    // Entities come from blackoutMeshes, which returns everything inside a
    // unit box, so this is how much of a tile one of them fills rather than a
    // radius. Close to the 0.26 diameter of the spheres it replaced: big
    // enough that a silhouette reads, small enough that four in a ring do not
    // touch.
    const ENTITY_SCALE    = 0.34;

    // How far above a tile the CENTRE of a character sits. One constant
    // because it is one fact: the local player is drawn by a different routine
    // from everyone else in the room, and the two heights disagreeing is the
    // difference between standing among people and hovering over them. It was
    // 0.22 for entities and 0.42 for the local marker, which was correct only
    // while the marker was a cone half a tile tall and nothing else.
    const ENTITY_LIFT     = 0.22;

    // How much of a tile a prop drawn ON that tile covers. Bigger than an
    // entity on purpose: a prop is part of the ground rather than something
    // standing on it, and the teleporter it was set for is a floor pad that
    // reads as a pad only when it reaches the tile's edges.
    const TILE_PROP_SCALE = 0.9;

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
    const MOUSE_BUTTON_LEFT  = 0;

    // ─── Interaction tunables ───────────────────────────────────────────────

    // What still counts as a click rather than a drag. Left-drag is unbound
    // today, so this is not about disambiguating two gestures — it is about
    // never sending a command because a hand moved two pixels on the way up.
    const CLICK_SLOP_PX      = 5;
    const CLICK_MAX_MS       = 600;

    // Cursor-to-entity distance, in pixels, that counts as picking it.
    //
    // Entities are ENTITY_SCALE of a tile, which at a normal zoom is a handful
    // of pixels — small enough that an honest ray/mesh intersection would make
    // them a test of aim rather than an interface. Comparing cursor distance to
    // each entity's projected position is forgiving, and does the more
    // obliging thing when two of them overlap in the ring: it takes whichever
    // one LOOKS nearest, which is the one the player was aiming at.
    const ENTITY_PICK_PX     = 22;

    // Tiles are ordinary meshes here, so THEY are picked with a real raycast —
    // no plane-intersection trick is needed. (The Godot client has to intersect
    // the tile plane instead, because its tiles are MultiMesh instances with no
    // bodies to hit.)

    // How long a walk step waits for the room_info that confirms it before the
    // walk is abandoned. Generous on purpose: this is the backstop for a step
    // the server never answered at all, not the normal cancel path, which is
    // arriving somewhere unexpected.
    const PATH_STEP_TIMEOUT_MS = 4000;

    // Grid delta -> the exit name the server would spawn for it. +y is north
    // because tileWorldPos maps +y to -Z, which is into the screen at the
    // default camera yaw.
    const DIRECTION_NAMES = {
        "0:1":   "north",
        "1:1":   "northeast",
        "1:0":   "east",
        "1:-1":  "southeast",
        "0:-1":  "south",
        "-1:-1": "southwest",
        "-1:0":  "west",
        "-1:1":  "northwest"
    };

    // There is deliberately NO verb table here. serialize_entity names the
    // whole command in the payload's `interact` field — "craft", "talk",
    // "attack mutant raider" — and this pane sends it verbatim.
    //
    // It used to be a table, and the table was wrong within a week. A Foundry
    // Furnace has nothing in its storage to distinguish it from a dropped
    // sword, so it fell through to "item" and the pane confidently offered
    // `get Foundry Furnace`. A shopkeeper did the same. Both are typeclasses
    // this file has never heard of and should never have to hear of: the
    // server knows what a thing is, and now says what to do with it.
    //
    // An empty `interact` means the entity affords nothing — a character, or
    // anything the server has not given a verb — and the pane leaves it
    // unlit and unclickable.

    // Sent when the player clicks the tile they are already standing on.
    const CMD_LOOK = "look";

    // The contrib's pathfinder, reached exactly as a telnet player reaches it.
    // Bare `goto` aborts a walk in progress; `goto (X,Y)` starts one.
    //
    // Everything about the walk then belongs to the server: scipy's Dijkstra
    // over a baked path matrix, `interrupt_path` map nodes that stop it, and a
    // re-path when the player walks off-route by hand. None of that is worth
    // reimplementing here, and a second pathfinder would be a second answer to
    // "what is the shortest way there".
    //
    // Blackout lifts the contrib's Builder lock on the coordinate form —
    // see commands/movement_cmds.py — because a tile is the only name a
    // graphical client has for a room.
    const CMD_GOTO = "goto";

    // ─── Palette ────────────────────────────────────────────────────────────

    const COLOR_BACKGROUND   = 0x0b0f14;
    const COLOR_TILE_DEFAULT = 0x2b3a4a;
    const COLOR_TILE_CURRENT = 0x35e0c0;
    const COLOR_LINK         = 0x2e4256;
    const COLOR_PLAYER       = 0x35e0c0;
    const COLOR_HIT_FLASH    = 0xffffff;

    // The COLOR_ENTITY_* palette that used to sit here now lives in
    // blackout_meshes.js, with the shapes it paints. What an entity looks like
    // is one fact and it has one owner; this pane asks for a mesh and draws
    // what it is given.
    const COLOR_AURA         = 0xff8c42;

    // Hover is an EMISSIVE tint, not a colour swap, so it cannot fight the two
    // things that already own a mesh's `color`: highlightCurrentTile, which
    // repaints every tile from its base colour, and the hit flash, which
    // restores from the same. Three owners of one channel is how a tile ends
    // up stuck the wrong colour; emissive has one.
    const COLOR_HOVER_GLOW   = 0x2f5f6b;
    const COLOR_NO_GLOW      = 0x000000;

    // How strongly COLOR_PLAYER is burnt into the local player's own mesh.
    // See markAsSelf: enough to pick yourself out of a tile with company,
    // far short of repainting the model. Lower than the 0.6 the cone carried,
    // because the cone had nothing underneath the tint to preserve.
    const SELF_GLOW_INTENSITY = 0.3;

    // Known room kinds get a deliberate colour; everything else is hashed to a
    // stable hue so a new room type is visually distinct without an edit here.
    const ROOM_KIND_COLORS = {
        "Bank":                       0x4488ff,
        "Foundry Furnace Facility":   0xdd4422,
        "Metalsmith Anvil Facility":  0xaaaaaa,
        "Pole clearing":              0xcc6633,
        "Shopkeeper":                 0xddcc44,
        "Mutant Raider Tile":         0x8fbf00,
        "Big Mutant Tile":            0xbf3f00,
        // Not a prototype key like the rest: the server synthesises this one
        // for a node that spawns no room. It is the way OFF the map, so it is
        // coloured whether or not the teleporter model is there to stand on it.
        "map_transition":             0x35e0c0
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
    const tileProps = {};           // "z:x:y" -> Object3D, for tiles with art
    const entityMeshes = {};        // entity id -> Object3D from the resolver
    const flashes = [];             // {mesh, until, baseColors}

    // Bumped every time the entity list is redrawn. A mesh resolved for an
    // older one is discarded rather than placed — see placeEntity.
    let entityGeneration = 0;

    let currentRoom = null;         // {num, coords:[x,y,z], room_kind}
    let lastEntities = [];          // last room_players payload, for replay
    let auraRadius = 0;             // last aura radius, for replay
    let playerMarker = null;
    let playerAnchor = null;        // settled marker position, WITHOUT the bob
    let playerTween = null;         // {from:Vector3, to:Vector3, start, dur}
    let auraRing = null;

    // Who the local player IS, from char_avatar: {id, asset, family}.
    //
    // The pane cannot work this out for itself. emit_room_contents excludes
    // the observer from their own entity list — a client already knows where
    // it put the camera — so every OTHER character arrives carrying an asset
    // key and the local one arrives on a channel of its own.
    //
    // Null until that channel lands, and null is a working state rather than a
    // wait: resolvePlayerMarker asks for the character FAMILY with no key,
    // which is the procedural figure. A player whose avatar message is slow,
    // or who is playing against a server too old to send one, gets the same
    // figure the pane drew before any of this existed.
    let selfEntity = null;

    // Whether the local player has a known position to be drawn at.
    //
    // Deliberately NOT `playerMarker.visible`. The marker is now resolved
    // asynchronously, so there are frames — and, for a slow model, seconds —
    // where the pane knows exactly where the player is standing and has
    // nothing yet to stand there. Keeping the FACT separate from the object
    // that displays it is what lets room_info land during that window without
    // being dropped, and what lets the camera follow a player who is still
    // loading.
    let playerVisible = false;

    // Which way the marker is turned, in radians. Held rather than read back
    // off the mesh because the mesh is replaced whenever the avatar changes,
    // and a replacement that faced east again on every re-resolve would spin
    // the player at random.
    let playerYaw = 0;

    // Bumped on every marker re-resolve, for the same reason entityGeneration
    // exists: char_avatar can arrive while an earlier resolve is still in
    // flight, and the loser must be released rather than added.
    let markerGeneration = 0;

    // Orbit rig. These survive a pane rebuild deliberately: re-opening the
    // pane, or activating a saved layout, should not throw away the angle the
    // player chose. The camera OBJECT is rebuilt; these three numbers are not.
    let cameraYaw = CAM_YAW;
    let cameraPitch = CAM_PITCH;
    let cameraDistance = CAM_DISTANCE;
    let cameraFocus = null;         // Vector3 the rig orbits and looks at
    let orbitDrag = null;           // {pointerId, x, y} while right-dragging

    // Picking and control.
    let raycaster = null;
    let hoverMesh = null;           // mesh under the cursor, or null
    let pressStart = null;          // {x, y, at} between left down and up

    // The tile of the last `goto` we sent, as "x:y", or null when not walking.
    //
    // The server owns the walk; this is only enough to know that clicking your
    // own tile should mean STOP rather than `look`. It is cleared on arrival,
    // and on any single step taken by hand, because both mean the walk this
    // pane started is over as far as the pane is concerned.
    let autoWalkTarget = null;

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
            basePos.y + ENTITY_LIFT,
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
        bindPickInput(renderer.domElement);

        scene.add(new THREE.AmbientLight(0xffffff, 0.55));
        const key = new THREE.DirectionalLight(0xffffff, 0.8);
        key.position.set(5, 12, 8);
        scene.add(key);

        tileGroup = new THREE.Group();
        entityGroup = new THREE.Group();
        scene.add(tileGroup);
        scene.add(entityGroup);

        // The local player used to be a cone built right here, and it was the
        // last thing in the pane that decided for itself what something looks
        // like. It is now resolved exactly as every other character is, which
        // is what makes "you" and "the person standing next to you" the same
        // mesh at the same size — they were a teal cone and a blue figure.
        //
        // The anchor is created BEFORE the resolve and outlives every rebuild:
        // it is where the player is standing, which is true whether or not
        // there is currently anything drawn there.
        if (!playerAnchor) {
            playerAnchor = new THREE.Vector3();
        }
        resolvePlayerMarker();
        updateCamera();
    };

    const resizeToContainer = function () {
        if (!renderer || !container) {
            return;
        }
        const width = container.clientWidth || 1;
        const height = container.clientHeight || 1;

        // Let three.js set the canvas CSS size as well as its backing store.
        //
        // Passing updateStyle=false here — as this did — sets only the width
        // and height ATTRIBUTES, which are `size * devicePixelRatio`. With no
        // CSS size to override them, the element then lays out at that pixel
        // count in CSS pixels: on a display-scaled screen the canvas is 1.25x
        // or 1.5x larger than the pane holding it, overflowing and clipped.
        //
        // Rendering survives that (you see a cropped, zoomed diorama and would
        // not necessarily call it wrong), which is how it went unnoticed. It is
        // fatal to picking: getBoundingClientRect then reports the oversized
        // box, so cursor-to-NDC is scaled by the pixel ratio and the hit drifts
        // further from the cursor the further you get from the top-left corner.
        //
        // Any DPR-1 display — a plain 1080p monitor at 100% scaling — hides
        // this completely, which is worth knowing before trusting one machine.
        renderer.setSize(width, height);
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
        // Follows the ANCHOR, not the mesh. A player whose model is still
        // downloading is a player the camera should already be pointed at.
        if (playerVisible) {
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

    // Stand a model on one tile, if that tile's room kind has one registered.
    //
    // Deliberately NOT the entity path. An entity always gets a mesh, because
    // an item nobody has modelled still has to be visible and clickable, so the
    // resolver falls through to a procedural family shape. A prop is scenery:
    // a tile whose kind has no art keeps being a plain coloured slab, which is
    // what every tile in the game was before this. Asking hasModel() first is
    // what draws that line — resolve() alone cannot, since it answers every
    // key with something.
    //
    // The key IS the room kind. mapexport names a transition node
    // "map_transition"; blackout_models.js registers a .glb under that name;
    // nothing in between has to be edited to give another room kind a prop.
    const placeTileProp = function (z, node, position) {
        const kind = node.room_kind;
        const modelled = blackoutMeshes.hasModel(kind);

        if (!modelled) {
            return;
        }
        const key = tileKey(z, node.x, node.y);
        const group = tileGroup;

        blackoutMeshes.resolve(kind, kind).then(function (mesh) {
            // The pane can be rebuilt while a .glb is still in flight, and the
            // group this was resolved for is then no longer the one on screen.
            // Adding it anyway would leave a prop in a discarded scene and a
            // second copy when drawMap runs again against the new one.
            if (group !== tileGroup) {
                blackoutMeshes.release(mesh);
                return;
            }
            const bounds = new THREE.Box3();

            mesh.scale.setScalar(TILE_PROP_SCALE);
            mesh.position.copy(position);
            // Rest it ON the tile rather than through it. The resolver centres
            // every model in a unit box, but only the LONGEST axis is a unit
            // long — the teleporter is a flat pad two thirds as tall as it is
            // wide — so half the prop's height is not half the scale. Measuring
            // the scaled copy is the answer that also holds for the next model.
            bounds.setFromObject(mesh);
            mesh.position.y += (position.y + (TILE_HEIGHT / 2)) - bounds.min.y;
            tileGroup.add(mesh);
            tileProps[key] = mesh;
        });
    };

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
            // What a click on this mesh means. tileGroup also holds the link
            // LineSegments, which carries no such stamp — that is what tells
            // the two apart when a ray hits both.
            mesh.userData.tile = { z: z, x: node.x, y: node.y };
            tileGroup.add(mesh);
            tileMeshes[key] = mesh;
            // After the tile is registered, so the guard above covers the prop
            // too: a second drawMap for the same z returns before it can ask
            // for a second copy of a model still loading for the first.
            placeTileProp(z, node, mesh.position);
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

    // Give an entity mesh materials of its OWN, and remember them.
    //
    // Hover and the hit flash both write to a material — emissive for one,
    // colour for the other — and a mesh from the resolver may be a clone whose
    // materials belong to a cached prototype shared with every other entity of
    // that asset key. Writing through that would flash every mutant raider in
    // the neighbourhood when one of them is hit.
    //
    // Cloning is per material, not per resource: geometry and textures stay
    // shared, which is the expensive half. What it costs is that this pane now
    // owns something it has to free, hence the list.
    const takeOwnMaterials = function (mesh) {
        const owned = [];

        mesh.traverse(function (child) {
            if (!child.material) {
                return;
            }
            if (Array.isArray(child.material)) {
                child.material = child.material.map(function (material) {
                    const copy = material.clone();

                    owned.push(copy);
                    return copy;
                });
                return;
            }
            child.material = child.material.clone();
            owned.push(child.material);
        });
        mesh.userData.ownMaterials = owned;
    };

    // Write one colour channel across every material an entity owns.
    //
    // A resolved entity is a Group of several meshes, so neither the flash nor
    // the hover glow can reach for `mesh.material` any more. Both take the
    // list takeOwnMaterials built rather than traversing again, so a mesh this
    // pane did not prepare is silently left alone instead of half-tinted.
    const paintOwned = function (mesh, channel, hex) {
        const owned = mesh.userData.ownMaterials;

        if (!owned) {
            return;
        }
        owned.forEach(function (material) {
            if (material[channel]) {
                material[channel].setHex(hex);
            }
        });
    };

    const readOwnedColors = function (mesh) {
        const owned = mesh.userData.ownMaterials || [];

        return owned.map(function (material) {
            return material.color.getHex();
        });
    };

    const restoreOwnedColors = function (mesh, colors) {
        const owned = mesh.userData.ownMaterials || [];

        owned.forEach(function (material, index) {
            if (index < colors.length) {
                material.color.setHex(colors[index]);
            }
        });
    };

    const clearEntities = function () {
        // Whatever was under the cursor is about to stop existing. The next
        // pointermove re-establishes the hover against the new meshes.
        setHover(null);

        // A flash outlives its mesh otherwise, and restoring a colour onto a
        // freed material is how a disposed entity comes back as a white ghost.
        flashes.length = 0;

        Object.keys(entityMeshes).forEach(function (id) {
            const mesh = entityMeshes[id];

            entityGroup.remove(mesh);
            (mesh.userData.ownMaterials || []).forEach(function (material) {
                material.dispose();
            });
            // Geometry and anything shared: the resolver decides, because the
            // resolver is what knows whether this was built for us or cloned
            // from a cached model. Before this call the pane freed NOTHING —
            // every placeEntities left a geometry and a material behind, and
            // an entity walking in and out of radius did it once each way.
            blackoutMeshes.release(mesh);
            delete entityMeshes[id];
        });
    };

    // Where an entity stands. Its own coords when the server sent them, and
    // the observer's room otherwise — which is what every entity looked like
    // back when STATEFEED_ENTITY_RADIUS was 0 and the feed only ever described
    // the tile you were on.
    const entityCoords = function (entity) {
        if (entity.coords && entity.coords.length === 3) {
            return entity.coords;
        }
        if (currentRoom && currentRoom.coords &&
                currentRoom.coords.length === 3) {
            return currentRoom.coords;
        }
        return null;
    };

    // Put one resolved mesh in the scene, if the scene it was resolved for is
    // still the current one.
    //
    // `generation` is the whole reason this is a separate routine. Resolving
    // is asynchronous, entity lists arrive on every delta, and a mesh whose
    // snapshot has already been replaced must be thrown away rather than
    // added — otherwise an NPC that left the radius reappears a frame later,
    // placed where it used to stand, with nothing to remove it.
    const placeEntity = function (entity, position, generation) {
        blackoutMeshes.resolve(entity.asset, entity.family).then(function (mesh) {
            if (generation !== entityGeneration || !entityGroup) {
                blackoutMeshes.release(mesh);
                return;
            }
            takeOwnMaterials(mesh);
            mesh.scale.setScalar(ENTITY_SCALE);
            mesh.position.copy(position);
            mesh.userData.entity = entity;
            entityGroup.add(mesh);
            entityMeshes[entity.id] = mesh;
        });
    };

    const placeEntities = function (entities) {
        lastEntities = entities;
        if (!entityGroup) {
            return;
        }
        clearEntities();
        entityGeneration += 1;
        const generation = entityGeneration;

        // Group by tile before placing. entitySlotPos spreads N entities
        // evenly around one tile's ring, so the count it is given has to be
        // the count IN THAT TILE — handing it the whole payload's length would
        // size every ring for the entire neighbourhood and leave two NPCs
        // standing together almost on top of each other.
        const tiles = {};

        entities.forEach(function (entity) {
            const coords = entityCoords(entity);

            if (!coords) {
                return;
            }
            const key = tileKey(coords[2], coords[0], coords[1]);

            if (!tiles[key]) {
                tiles[key] = { coords: coords, members: [] };
            }
            tiles[key].members.push(entity);
        });

        Object.keys(tiles).forEach(function (key) {
            const tile = tiles[key];
            const base = tileWorldPos(
                tile.coords[2], tile.coords[0], tile.coords[1]);

            tile.members.forEach(function (entity, index) {
                const position = entitySlotPos(
                    base, entity.id, index, tile.members.length);

                placeEntity(entity, position, generation);
            });
        });
    };

    // ─── Entity deltas ──────────────────────────────────────────────────────

    // The "delta" half of list-then-delta. These were arriving and being
    // dropped, which cost nothing while the feed only described the tile you
    // were standing on: you got a fresh full list every time you moved, and
    // moving was the only way the picture could change. With a radius, an NPC
    // three tiles away can wander in and die without the observer moving at
    // all, and a dropped delta leaves it drawn there until they walk far
    // enough to trigger a new list.
    //
    // Both rebuild the whole scene rather than editing one mesh, matching what
    // placeEntities already does: ring position depends on how many share the
    // tile, so one arrival moves everything standing with it.

    const onEntityAdded = function (data) {
        const entity = data.entity;

        if (!entity || !entity.id) {
            return;
        }
        // Filter first, so a duplicate add — a resync racing a delta — updates
        // the entity rather than drawing it twice.
        const merged = lastEntities.filter(function (known) {
            return known.id !== entity.id;
        });
        merged.push(entity);
        placeEntities(merged);
    };

    const onEntityRemoved = function (data) {
        const remaining = lastEntities.filter(function (known) {
            return known.id !== data.entity_id;
        });

        if (remaining.length === lastEntities.length) {
            return;
        }
        placeEntities(remaining);
    };

    // The mesh drawn for one entity id, wherever it happens to live.
    //
    // Two homes, because the local player is not in the entity list: the
    // server excludes an observer from their own room_players payload, so the
    // marker is the pane's only copy of them. Before char_avatar existed the
    // pane had no id for itself at all, which is why a combat event naming YOU
    // as the target flashed nothing and every hit you took looked like a miss.
    const meshForEntityId = function (entityId) {
        const known = entityMeshes[entityId];

        if (known) {
            return known;
        }
        const isSelf = selfEntity && selfEntity.id === entityId;

        if (isSelf) {
            // Null while the marker is still resolving, which flashEntity
            // reads the same way it reads an NPC that has walked out of range.
            return playerMarker;
        }
        return null;
    };

    // Forget any running flash on one mesh.
    //
    // A flash outlives its mesh otherwise, and restoring a colour onto a freed
    // material is how a disposed entity comes back as a white ghost —
    // clearEntities empties the whole list for the same reason. This is the
    // narrow version, for the one mesh that is replaced without the rest of
    // the scene being torn down with it.
    const dropFlashesFor = function (mesh) {
        let index = flashes.length - 1;

        while (index >= 0) {
            if (flashes[index].mesh === mesh) {
                flashes.splice(index, 1);
            }
            index -= 1;
        }
    };

    const flashEntity = function (entityId) {
        const mesh = meshForEntityId(entityId);
        if (!mesh) {
            return;
        }
        // A second hit inside the first flash extends it rather than starting
        // again. Restarting would record WHITE as the colour to restore, and
        // the entity would stay white until it was next redrawn — which for a
        // stationary NPC being hit repeatedly is the whole fight.
        const running = flashes.find(function (flash) {
            return flash.mesh === mesh;
        });

        if (running) {
            running.until = performance.now() + HIT_FLASH_MS;
            return;
        }
        flashes.push({
            mesh: mesh,
            until: performance.now() + HIT_FLASH_MS,
            baseColors: readOwnedColors(mesh)
        });
        paintOwned(mesh, "color", COLOR_HIT_FLASH);
    };

    // ─── The local player ───────────────────────────────────────────────────

    // Tint the marker so you can find yourself in a crowd.
    //
    // This is what the teal cone was FOR. Drawing the local player with the
    // same mesh as everyone else is the point of the change, and it costs
    // exactly one thing on the way: in a tile holding three characters,
    // nothing says which one you are steering. The camera centres on you and
    // your tile is highlighted, but neither survives a tile with company.
    //
    // Emissive rather than colour, and for the reason COLOR_HOVER_GLOW is:
    // `color` already has two owners on this mesh — the hit flash writes it
    // and restoreOwnedColors puts it back — and a third would leave the player
    // stuck teal after the next swing. Emissive has one owner here, since the
    // marker is deliberately not pickable and so never hovers.
    //
    // Applied at low intensity on purpose. At 1.0 a teal emissive swallows
    // whatever the model's own materials say and hands back a flat silhouette,
    // which is the same as having no model.
    const markAsSelf = function (mesh) {
        const owned = mesh.userData.ownMaterials || [];

        owned.forEach(function (material) {
            if (!material.emissive) {
                return;
            }
            material.emissive.setHex(COLOR_PLAYER);
            material.emissiveIntensity = SELF_GLOW_INTENSITY;
        });
    };

    // Which way to turn a figure walking from `from` to `to`.
    //
    // atan2(dx, dz), not the atan2(dz, dx) a maths text would write. This is
    // the rotation that puts +Z along the direction of travel, and +Z is the
    // way a glTF character is authored to face. Returns the CURRENT yaw for a
    // zero-length move rather than snapping to zero, so a player who arrives
    // where they already were keeps facing the way they were going.
    const yawTowards = function (from, to) {
        const dx = to.x - from.x;
        const dz = to.z - from.z;
        const still = dx === 0 && dz === 0;

        if (still) {
            return playerYaw;
        }
        const yaw = Math.atan2(dx, dz);

        return yaw;
    };

    // Give the marker's mesh back to the resolver.
    //
    // Materials first and the resolver second, in that order, mirroring
    // clearEntities: takeOwnMaterials cloned the materials for this mesh alone
    // so the pane owns those outright, while the geometry underneath them may
    // belong to a cached prototype shared with every other character in the
    // room. Only the resolver knows which, so only the resolver decides.
    const releasePlayerMarker = function () {
        if (!playerMarker) {
            return;
        }
        const going = playerMarker;

        playerMarker = null;
        dropFlashesFor(going);

        if (scene) {
            scene.remove(going);
        }
        (going.userData.ownMaterials || []).forEach(function (material) {
            material.dispose();
        });
        blackoutMeshes.release(going);
    };

    // Draw the local player as whatever the pane currently knows them to be.
    //
    // Called twice in the ordinary case and that is by design: once from
    // buildScene, which cannot wait for a channel, and again from onCharAvatar
    // when the server says who this is. Between the two the player is the
    // procedural figure — the same tier-2 guarantee every unmodelled entity
    // in the game gets, applied to the one entity the pane draws itself.
    //
    // The generation check is entityGeneration's reasoning applied to one
    // mesh. A .glb is slow enough that a second avatar message, or a pane
    // rebuilt while the first is still in flight, is an ordinary race rather
    // than a theoretical one; the loser is released instead of added, or the
    // pane ends up with two players in it and a handle on only one.
    const resolvePlayerMarker = function () {
        if (!scene) {
            return;
        }
        const asset = selfEntity ? selfEntity.asset : "";
        const family = selfEntity ? selfEntity.family : FAMILY_CHARACTER;
        const target = scene;

        markerGeneration += 1;
        const generation = markerGeneration;

        blackoutMeshes.resolve(asset, family).then(function (mesh) {
            if (generation !== markerGeneration || scene !== target) {
                blackoutMeshes.release(mesh);
                return;
            }
            releasePlayerMarker();
            takeOwnMaterials(mesh);
            markAsSelf(mesh);
            mesh.scale.setScalar(ENTITY_SCALE);
            mesh.position.copy(playerAnchor);
            mesh.rotation.y = playerYaw;
            mesh.visible = playerVisible;
            scene.add(mesh);
            playerMarker = mesh;
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

    // ─── Picking ────────────────────────────────────────────────────────────

    // Which entity, if any, the cursor is on.
    //
    // Screen-space distance rather than a ray intersection — see ENTITY_PICK_PX
    // for why. The nearest one wins, so overlapping entities resolve to the one
    // that looks closest to the cursor rather than the one that happens to be
    // in front.
    const pickEntity = function (event, rect) {
        let best = null;
        let bestDistance = ENTITY_PICK_PX;

        Object.keys(entityMeshes).forEach(function (id) {
            const mesh = entityMeshes[id];
            const ndc = mesh.position.clone().project(camera);

            // project() wraps around for points behind the eye, which would
            // otherwise make an entity at your back pickable through the floor.
            if (ndc.z > 1) {
                return;
            }
            const screenX = rect.left + (ndc.x + 1) * 0.5 * rect.width;
            const screenY = rect.top + (1 - ndc.y) * 0.5 * rect.height;
            const distance = Math.sqrt(
                Math.pow(screenX - event.clientX, 2) +
                Math.pow(screenY - event.clientY, 2));

            if (distance < bestDistance) {
                bestDistance = distance;
                best = mesh;
            }
        });

        return best;
    };

    // Which tile, if any, the cursor is on.
    const pickTile = function (event, rect) {
        if (!raycaster) {
            raycaster = new THREE.Raycaster();
        }
        const ndc = new THREE.Vector2(
            ((event.clientX - rect.left) / rect.width) * 2 - 1,
            -((event.clientY - rect.top) / rect.height) * 2 + 1
        );
        raycaster.setFromCamera(ndc, camera);

        const hits = raycaster.intersectObjects(tileGroup.children, false);

        for (let i = 0; i < hits.length; i++) {
            if (hits[i].object.userData.tile) {
                return hits[i].object;
            }
        }
        return null;
    };

    // ─── What a click means ─────────────────────────────────────────────────

    // Both the hover glow and the click go through these two, so what lights up
    // under the cursor is by construction the thing that will happen. A null
    // means "nothing to do here", and the pane says so by not glowing.

    const tileAction = function (tile) {
        if (!currentRoom || !currentRoom.coords ||
                currentRoom.coords.length < 3) {
            return null;
        }
        const here = currentRoom.coords;

        // Z is a map name, and the maps are disconnected islands with no
        // transition nodes between them. The server would refuse this walk
        // ("target outside of area"), so the pane refuses it first.
        if (tile.z !== here[2]) {
            return null;
        }
        const deltaX = tile.x - here[0];
        const deltaY = tile.y - here[1];

        if (deltaX === 0 && deltaY === 0) {
            if (autoWalkTarget) {
                return { command: CMD_GOTO, stops: true };
            }
            return { command: CMD_LOOK };
        }

        // The pathfinder answer, and the fallback for a neighbour no single
        // step reaches.
        const walk = {
            command: CMD_GOTO + " (" + tile.x + "," + tile.y + ")",
            walksTo: tile.x + ":" + tile.y
        };

        if (Math.abs(deltaX) <= 1 && Math.abs(deltaY) <= 1) {
            const direction = DIRECTION_NAMES[deltaX + ":" + deltaY];
            const exits = currentRoom.exits || {};
            const stepping = direction && exits.hasOwnProperty(direction);

            if (stepping) {
                return { command: direction, steps: true };
            }

            // A neighbouring TILE is not a neighbouring ROOM, and most maps
            // are drawn with cardinal links only — so the eight tiles around
            // the player are mostly NOT eight exits. A DIAGONAL neighbour with
            // no diagonal link is the ordinary case, not a wall: it is two
            // cardinal steps away and the pathfinder walks it. Refusing it
            // left the tiles nearest the player the only ones in the pane that
            // could not be clicked.
            if (deltaX !== 0 && deltaY !== 0) {
                return walk;
            }

            // A CARDINAL neighbour with no exit is a wall. Refusing here means
            // the pane never sends a move the server could only answer "you
            // cannot go that way" to — the wall is visible as a tile that
            // does not light up, and a click on it does not send the player
            // the long way around a barrier they can see.
            return null;
        }

        return walk;
    };

    const entityAction = function (entity) {
        if (!entity || !entity.interact) {
            return null;
        }
        return { command: entity.interact };
    };

    // Resolve the cursor to a mesh and the action it carries.
    //
    // Entities are tested BEFORE tiles, and an entity with no action stops the
    // search rather than falling through to the tile under it. Falling through
    // would mean a click aimed at another player walks you somewhere instead,
    // which is worse than a click that does nothing.
    const pickAt = function (event) {
        if (!renderer || !camera || !tileGroup) {
            return null;
        }
        // Measure the canvas the EVENT came from, never the module's current
        // renderer. The two are the same in a healthy pane, and when they are
        // not, the event's own element is the one whose coordinate space
        // clientX/clientY are expressed in — which is the only one that can
        // turn them into a correct NDC pair.
        const element = event.currentTarget || renderer.domElement;
        const rect = element.getBoundingClientRect();

        // A pane that is laid out but not displayed measures zero, and the NDC
        // maths below would divide by it. Nothing is visible to click anyway.
        if (!rect.width || !rect.height) {
            return null;
        }
        const entityMesh = pickEntity(event, rect);

        if (entityMesh) {
            return {
                mesh: entityMesh,
                action: entityAction(entityMesh.userData.entity)
            };
        }
        const tileMesh = pickTile(event, rect);

        if (tileMesh) {
            return {
                mesh: tileMesh,
                action: tileAction(tileMesh.userData.tile)
            };
        }
        return null;
    };

    // ─── Hover feedback ─────────────────────────────────────────────────────

    // Tiles are single meshes this pane built and own their materials
    // outright; entities are Groups carrying the list takeOwnMaterials made.
    // One routine covers both rather than branching on which was hovered.
    const glow = function (mesh, hex) {
        if (!mesh) {
            return;
        }
        if (mesh.material && mesh.material.emissive) {
            mesh.material.emissive.setHex(hex);
            return;
        }
        paintOwned(mesh, "emissive", hex);
    };

    const setHover = function (mesh) {
        if (hoverMesh === mesh) {
            return;
        }
        glow(hoverMesh, COLOR_NO_GLOW);
        hoverMesh = mesh;
        glow(hoverMesh, COLOR_HOVER_GLOW);
    };

    // ─── Control ────────────────────────────────────────────────────────────

    // Every command this pane sends leaves through here, and it is deliberately
    // the ONLY way out. What goes down the wire is the same ["text", [...]] a
    // player typing in the input box sends, so there is one code path on the
    // server for both and no permission, lock or cooldown to audit twice.
    const sendCommand = function (command) {
        Evennia.msg("text", [command], {});
        log("sent", command);
    };

    const runAction = function (action) {
        if (!action) {
            return;
        }
        sendCommand(action.command);

        if (action.walksTo) {
            autoWalkTarget = action.walksTo;
        } else if (action.steps || action.stops) {
            // A hand-taken step ends the walk this pane is tracking: the server
            // re-paths off the player's real position, but the pane no longer
            // knows where it is going, and claiming to would make the
            // click-your-own-tile gesture mean "stop" long after it stopped.
            autoWalkTarget = null;
        }
    };

    // Clear the walk once the player is standing on its destination. Called
    // from route rather than from onRoomInfo, so replaying a stored room into
    // a freshly-built pane cannot be mistaken for arriving somewhere.
    const noteArrival = function (data) {
        if (!autoWalkTarget || !data.coords || data.coords.length < 3) {
            return;
        }
        if (data.coords[0] + ":" + data.coords[1] === autoWalkTarget) {
            autoWalkTarget = null;
        }
    };

    const onPickPointerDown = function (event) {
        if (event.button !== MOUSE_BUTTON_LEFT) {
            return;
        }
        pressStart = { x: event.clientX, y: event.clientY, at: performance.now() };
    };

    // Fire on release rather than on press, so a press that turns out to be a
    // drag — or that wanders off the tile it started on — sends nothing. Left
    // drag is unbound today; this is about not acting on a shaky hand.
    const onPickPointerUp = function (event) {
        if (event.button !== MOUSE_BUTTON_LEFT || !pressStart) {
            return;
        }
        const travel = Math.sqrt(
            Math.pow(event.clientX - pressStart.x, 2) +
            Math.pow(event.clientY - pressStart.y, 2));
        const held = performance.now() - pressStart.at;
        pressStart = null;

        if (travel > CLICK_SLOP_PX || held > CLICK_MAX_MS || orbitDrag) {
            return;
        }
        const picked = pickAt(event);

        if (!picked) {
            return;
        }
        runAction(picked.action);
    };

    const onPickPointerMove = function (event) {
        if (!renderer) {
            return;
        }
        if (orbitDrag) {
            // Mid-orbit the cursor is steering the camera, not pointing at
            // anything. Glowing whatever sweeps under it would be noise.
            setHover(null);
            return;
        }
        const picked = pickAt(event);
        const actionable = picked && picked.action ? picked.mesh : null;

        setHover(actionable);
        renderer.domElement.style.cursor = actionable ? "pointer" : "";
    };

    const bindPickInput = function (element) {
        element.addEventListener("pointerdown", onPickPointerDown);
        element.addEventListener("pointermove", onPickPointerMove);
        element.addEventListener("pointerup", onPickPointerUp);
        element.addEventListener("pointerleave", function () {
            setHover(null);
            pressStart = null;
        });
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
        //
        // Null for the first frames of a session and for as long as a .glb
        // takes, since the marker is resolved rather than built here now.
        if (playerMarker) {
            playerMarker.visible = playerVisible;
            playerMarker.position.copy(playerAnchor);

            if (playerVisible) {
                const bob = Math.sin(clock * Math.PI * 2 * AMBIENT_BOB_HZ);
                playerMarker.position.y += bob * AMBIENT_BOB_AMP;

                // The cone span here (`clock * 0.6`), because a cone has no
                // front and turning is what stopped it reading as a stuck
                // triangle. A figure does have a front, and a person revolving
                // on the spot while they walk reads as a bug rather than as
                // ambient motion. Facing is set where the move is: onRoomInfo.
                playerMarker.rotation.y = playerYaw;
            }
        }
        if (auraRing) {
            auraRing.material.opacity = 0.4 + 0.15 *
                Math.sin(clock * Math.PI * 2 * 0.8);
        }

        while (flashes.length && flashes[0].until <= now) {
            const flash = flashes.shift();

            restoreOwnedColors(flash.mesh, flash.baseColors);
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
        //
        // Tested on the SCENE rather than on the marker, which is what it used
        // to mean back when buildScene made a cone on the spot. The marker is
        // resolved asynchronously now, so testing it here would drop every
        // room_info that arrived while a model was loading — including the
        // first one, which is the whole reason the pane knows where you are.
        if (!scene) {
            return;
        }
        if (!data.coords || data.coords.length < 3) {
            playerVisible = false;
            return;
        }
        const target = tileWorldPos(data.coords[2], data.coords[0], data.coords[1]);

        // The same height every other character in the room is drawn at. It
        // was 0.42 while the marker was a cone standing on its base and the
        // rest of the room stood at 0.22.
        target.y += ENTITY_LIFT;

        const adjacent = previous && previous.coords &&
            previous.coords.length === 3 &&
            previous.coords[2] === data.coords[2] &&
            Math.abs(previous.coords[0] - data.coords[0]) <= 1 &&
            Math.abs(previous.coords[1] - data.coords[1]) <= 1;

        if (playerVisible && adjacent) {
            // Only tween between neighbouring tiles. Sliding a character
            // through intervening walls on a teleport reads far worse than a
            // hard cut, so anything non-adjacent snaps. The camera inherits
            // both behaviours for free, since it tracks the same anchor.
            //
            // Turning happens here and only here, on the one move the pane
            // actually watches happen. A snap has no direction worth facing --
            // a teleport is not a walk -- so it leaves the yaw alone.
            playerYaw = yawTowards(playerAnchor, target);
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
        // The mesh is not touched here. The frame loop copies the anchor onto
        // whatever is currently drawn, which is the only arrangement that
        // works when "whatever is currently drawn" can be nothing yet.
        playerVisible = true;
        updateCamera();
    };

    // Who the server says the local player is.
    //
    // Re-resolves only when the ASSET changed, which today means only on the
    // first message: a character's asset key is fixed for its lifetime, and
    // this channel is a resync snapshot, so a reconnect resends a value the
    // pane already has. Rebuilding the marker on every reconnect would throw
    // away a loaded model to load the same file again.
    //
    // The id is recorded whether or not anything is redrawn, because it is
    // what makes a combat event about you recognisable as being about you.
    const onCharAvatar = function (data) {
        const previous = selfEntity;

        selfEntity = {
            id: data.entity_id,
            asset: data.asset || "",
            family: data.family || FAMILY_CHARACTER
        };

        const changed = !previous || previous.asset !== selfEntity.asset;

        if (changed) {
            resolvePlayerMarker();
        }
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
        // Props are handed back rather than just forgotten: a prop for a
        // skinned model owns a skeleton, and only the resolver knows that.
        Object.keys(tileProps).forEach(function (k) {
            blackoutMeshes.release(tileProps[k]);
            delete tileProps[k];
        });
        Object.keys(entityMeshes).forEach(function (k) { delete entityMeshes[k]; });
        Object.keys(maps).forEach(function (z) { maps[z].linksDrawn = false; });
        flashes.length = 0;
        playerTween = null;
        auraRing = null;

        // The marker is handed back for the same reason the props above are:
        // it is a resolver mesh now, so it may be a clone of a cached model
        // and may own a skeleton, and forgetting it would leak both. Bumping
        // the generation on the way out retires any resolve still in flight,
        // which would otherwise land its mesh in a scene being discarded.
        //
        // playerVisible and playerAnchor deliberately survive: the player has
        // not moved just because the pane was rebuilt around them, and
        // buildPane replays the room that put them there.
        releasePlayerMarker();
        markerGeneration += 1;
        // The canvas the drag was captured on is about to be discarded, so the
        // pointerup for an in-flight drag can never arrive. The orbit ANGLES
        // are kept: a rebuilt pane should look the way the player left it.
        orbitDrag = null;

        // Same reasoning for the click gesture, and the hovered mesh is one of
        // the ones being thrown away. autoWalkTarget is NOT cleared: the walk
        // is running on the server and is not the pane's to cancel just
        // because the pane was rebuilt underneath it.
        pressStart = null;
        hoverMesh = null;

        if (animationHandle && typeof cancelAnimationFrame === "function") {
            cancelAnimationFrame(animationHandle);
            animationHandle = null;
        }

        // Throw away the previous canvas, and the GPU context behind it.
        //
        // buildPane appends a canvas per call and GoldenLayout calls it more
        // than once — on a saved-layout activation, and on re-parenting a pane.
        // Without this, canvases accumulate in the DOM: the module's `renderer`
        // points at the newest, every older one is left orphaned at its last
        // size, and the browser's ~16-live-context cap eventually starts
        // dropping contexts out from under the pane.
        //
        // It was invisible while this pane only rendered — the newest canvas is
        // the one on screen and nothing consulted the others. Picking is what
        // made it bite: pointer events arrive on the canvas the player can SEE,
        // while `renderer.domElement` was an orphan measuring 1x1, so every
        // click divided by a zero-width rect and resolved to nothing.
        if (renderer) {
            const previous = renderer.domElement;

            if (previous && previous.parentNode) {
                previous.parentNode.removeChild(previous);
            }
            renderer.dispose();

            if (typeof renderer.forceContextLoss === "function") {
                renderer.forceContextLoss();
            }
            renderer = null;
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
        // Second thing this pane cannot draw without, since the entities stopped
        // being spheres it built itself. Same degradation: say so, and leave
        // everything else about the client working.
        if (!window.blackoutMeshes) {
            element.innerHTML =
                "<p style='padding:1em'>blackout_meshes.js is not loaded — " +
                "the world pane has nothing to draw entities with.</p>";
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

    // Bring up the world pane, or surface the one that already exists.
    //
    // There can only be ONE. The scene, camera, renderer and mesh caches are
    // module state, so a second pane does not get a second world — it takes the
    // first one's, and buildPane's own reset then disposes the canvas the first
    // pane was drawing on. Before this guard, clicking "Open 3D World" twice
    // (or once in a session whose layout GoldenLayout had already saved) left a
    // pane that looked fine and was not the one the module was pointing at:
    // rendering carried on in one canvas while pointer events arrived on
    // another, and every click silently resolved to nothing.
    //
    // Making a second pane impossible is a smaller fix than making the plugin
    // multi-pane, and multi-pane buys nothing — two views of one diorama, from
    // one camera the player steers in one place.
    const openPane = function () {
        const myLayout = window.plugins["goldenlayout"].getGL();
        const existing = myLayout.root.getItemsByType("component").filter(
            function (item) {
                return item.config.componentName === "blackout3d";
            });

        if (existing.length) {
            const pane = existing[0];

            // Already open, possibly as a background tab in its stack. Show it.
            if (pane.parent && pane.parent.setActiveContentItem) {
                pane.parent.setActiveContentItem(pane);
            }
            return;
        }
        const component = {
            title: "World",
            type: "component",
            componentName: "blackout3d",
            componentState: {}
        };
        const main = myLayout.root.getItemsByType("stack")[0].getActiveContentItem();
        main.parent.addChild(component);
    };

    // ─── Plugin interface ───────────────────────────────────────────────────

    // The only message this plugin sends that is not a player command. Called
    // from two places — see onLoggedIn and bindAcknowledged — because there are
    // two distinct moments a subscription has to be asked for, and only one of
    // them is logging in.
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
        else if (cmdname === CH_ROOM_INFO)     { onRoomInfo(data); noteArrival(data); }
        else if (cmdname === CH_ROOM_PLAYERS)  { placeEntities(data.entities || []); }
        else if (cmdname === CH_PLAYER_ADD)    { onEntityAdded(data); }
        else if (cmdname === CH_PLAYER_REMOVE) { onEntityRemoved(data); }
        else if (cmdname === CH_COMBAT)        { onCombat(data); }
        else if (cmdname === CH_AURA)          { onAura(data); }
        else if (cmdname === CH_CHAR_SUMMARY)  { latestSummary = data.panels || {}; }
        else if (cmdname === CH_CHAR_AVATAR)   { onCharAvatar(data); }
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
    // A CHANNEL HAS EXACTLY ONE LISTENER. DefaultEmitter.on does
    // `listeners[cmdname] = listener` — it REPLACES rather than appends. That
    // matters here more than anywhere else, because bindAcknowledged below
    // deliberately claims channels this file has never heard of: without a
    // check, this pane would take a channel that belongs to another one the
    // moment the server started acknowledging it.
    //
    // It has already happened in the other direction — see blackout_channels.js
    // for what a silently stolen channel looks like from the losing side.
    const bindChannel = function (channel) {
        if (!channel || boundChannels[channel]) {
            return;
        }
        if (window.blackoutChannels &&
                !window.blackoutChannels.claim(channel, "blackout3d")) {
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
        parentdiv.append('<div>Left-click a lit tile to walk to it — one step ' +
                         'if it is next door, otherwise the shortest path. ' +
                         'Click yourself to stop walking, or to look. ' +
                         'Click a creature to attack it, an item to take it, ' +
                         'a node to cut it. Anything that does not light up ' +
                         'is not something you can act on.</div>');
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
