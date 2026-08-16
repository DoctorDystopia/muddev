/*
 * Blackout Inventory — the carried grid and the worn gear, in 3D.
 *
 * REQUIRES: goldenlayout.js, three.js, blackout_meshes.js (loaded before this)
 *
 * A sibling of blackout3d.js, not part of it. Separate scene, separate camera,
 * separate renderer, separate GoldenLayout component. The world pane's camera
 * is an orbit rig wound through player-follow and its picking is tuned for
 * entities a few pixels across; a second camera and a modal picking state
 * inside that file is how it stops being maintainable.
 *
 * It obeys the same rule the world pane does, and the rule is the whole
 * safety argument:
 *
 *     This pane sends only what a telnet player could type. Dragging slot 3
 *     onto slot 17 sends ["text", ["swap 3 17"], {}]. There is no privileged
 *     client channel that bypasses a Command.
 *
 * Which is why `swap`, `equip <target>` and `unequip <target>` had to exist
 * server-side before any of this could be written. Every command this pane
 * sends is named BY THE SERVER, in the payload's `actions` list — there is no
 * verb table here, for the same reason blackout3d.js deleted its own.
 *
 * The server's snapshot is the truth. A drag moves a mesh immediately because
 * waiting a tick feels dead, but the next char_items_list overrules it — so a
 * refused move corrects itself within a tick and the text pane says why.
 *
 * Author: Nick Hobar
 * Creation date: 08/15/2026
 */

let blackoutInventory = (function () {
    "use strict";

    // ─── Channel names (must match systems/statefeed/constants.py) ──────────

    const CH_CHAR_ITEMS = "char_items_list";

    // How this pane identifies itself when claiming a channel. Must be unique
    // across the Blackout plugins; see blackout_channels.js.
    const PLUGIN_NAME = "blackout_inventory";

    // ─── Layout tunables ────────────────────────────────────────────────────

    // Columns in the carried grid. Matches items/inventory/handler.py's
    // GRID_COLS so the pane and the text grid agree about which slot is where.
    // The ROW count is derived from the payload's slots_total instead of being
    // stated here, so raising MAX_INVENTORY_SLOTS needs no client edit.
    const GRID_COLS        = 4;
    const EQUIP_COLS       = 2;

    const CELL_PITCH       = 1.0;
    const FRAME_SIZE       = 0.86;
    const FRAME_DEPTH      = 0.06;
    const ITEM_SCALE       = 0.62;
    const ITEM_LIFT        = 0.28;   // how far an item floats off its frame
    const SECTION_GAP      = 1.1;    // between the paper doll and the grid

    // Ortho half-height. The camera frames this many world units vertically
    // regardless of pane size; width follows the aspect ratio.
    const VIEW_MARGIN      = 0.8;

    // ─── Animation tunables ─────────────────────────────────────────────────

    // Items are shown at a fixed tilt and spun slowly. The tilt is what makes
    // a flat-on orthographic camera read as 3D without shearing the FRAMES,
    // which stay square because they are what the player aims at.
    const ITEM_TILT_X      = -0.34;
    const ITEM_SPIN_HZ     = 0.08;
    const ITEM_BOB_AMP     = 0.03;
    const ITEM_BOB_HZ      = 0.3;

    // A dragged item is lifted toward the camera and shrunk slightly, so it
    // reads as picked up rather than as sitting in whatever it passes over.
    const DRAG_LIFT        = 0.9;
    const DRAG_SCALE       = 0.85;

    // ─── Interaction tunables ───────────────────────────────────────────────

    // Below this, a pointer gesture is a click and not a drag. Same reasoning
    // as the world pane: never act on a hand that moved two pixels.
    const DRAG_SLOP_PX     = 5;

    const MOUSE_BUTTON_LEFT  = 0;
    const MOUSE_BUTTON_RIGHT = 2;

    // ─── Palette ────────────────────────────────────────────────────────────

    const COLOR_BACKGROUND   = 0x0b0f14;
    const COLOR_BACKPLATE    = 0x141c25;
    const COLOR_FRAME        = 0x22303d;
    const COLOR_FRAME_EQUIP  = 0x2a2438;   // paper doll reads as its own zone
    const COLOR_NO_GLOW      = 0x000000;

    // Hover and drag feedback are EMISSIVE, never a colour swap, for the same
    // reason the world pane uses emissive: `color` already has an owner on
    // these meshes and three owners of one channel is how a frame ends up
    // stuck lit.
    const COLOR_HOVER_GLOW   = 0x2f5f6b;
    const COLOR_TARGET_GLOW  = 0x2f6b45;   // a legal drop
    const COLOR_REFUSE_GLOW  = 0x000000;   // an illegal one: no glow at all

    // ─── Module state ───────────────────────────────────────────────────────

    let debug = false;

    let scene = null;
    let camera = null;
    let renderer = null;
    let container = null;
    let labelLayer = null;          // DOM overlay holding item labels
    let animationHandle = null;

    let frameGroup = null;
    let itemGroup = null;
    let raycaster = null;

    // Everything the feed has said, kept whether or not a pane exists to draw
    // it — same discipline as the world pane. The record side never gets
    // skipped; only the render side does.
    let snapshot = null;

    // Frame meshes, keyed by their target id: "inv:6" or "equip:main_hand".
    const frameMeshes = {};
    // Item meshes, keyed the same way, so a frame and its occupant are always
    // looked up by one string.
    const itemMeshes = {};
    // DOM label divs, keyed the same way again.
    const labels = {};

    // A snapshot was wanted before the wire was ready. onLoggedIn retries it.
    let wantSnapshot = false;

    let hoverKey = null;
    let pressStart = null;          // {x, y, key} between pointerdown and move
    let drag = null;                // {key, mesh, home, targetKey}
    let contextMenu = null;         // the open DOM menu, or null
    let tooltip = null;

    // Bumped on every rebuild. An async mesh that resolves after its snapshot
    // was replaced checks this and throws itself away, which is the whole
    // reason the resolver is promise-shaped.
    let renderGeneration = 0;

    // ─── Private helpers ────────────────────────────────────────────────────

    const log = function () {
        if (debug) {
            console.log.apply(console, ["[blackout_inventory]"].concat(
                Array.prototype.slice.call(arguments)));
        }
    };

    const invKey = function (slotIndex) {
        return "inv:" + slotIndex;
    };

    const equipKey = function (slotValue) {
        return "equip:" + slotValue;
    };

    const gridRows = function () {
        if (!snapshot || !snapshot.slots_total) {
            return 0;
        }
        return Math.ceil(snapshot.slots_total / GRID_COLS);
    };

    const equipRows = function () {
        if (!snapshot || !snapshot.equip_slots) {
            return 0;
        }
        return Math.ceil(snapshot.equip_slots.length / EQUIP_COLS);
    };

    // Total width of both sections, in world units. Used to centre the layout
    // and to size the orthographic frustum.
    const layoutWidth = function () {
        const columns = EQUIP_COLS + GRID_COLS;
        return (columns * CELL_PITCH) + SECTION_GAP;
    };

    const layoutHeight = function () {
        const rows = Math.max(gridRows(), equipRows());
        return rows * CELL_PITCH;
    };

    // Where the paper doll's cells start on X. Everything is laid out left to
    // right from here, with the grid to the right of the gap.
    const originX = function () {
        return -(layoutWidth() / 2) + (CELL_PITCH / 2);
    };

    const originY = function () {
        return (layoutHeight() / 2) - (CELL_PITCH / 2);
    };

    const equipCellPos = function (index) {
        const column = index % EQUIP_COLS;
        const row = Math.floor(index / EQUIP_COLS);
        return new THREE.Vector3(
            originX() + (column * CELL_PITCH),
            originY() - (row * CELL_PITCH),
            0
        );
    };

    const gridCellPos = function (slotIndex) {
        const column = slotIndex % GRID_COLS;
        const row = Math.floor(slotIndex / GRID_COLS);
        const offset = (EQUIP_COLS * CELL_PITCH) + SECTION_GAP;
        return new THREE.Vector3(
            originX() + offset + (column * CELL_PITCH),
            originY() - (row * CELL_PITCH),
            0
        );
    };

    // ─── Scene construction ─────────────────────────────────────────────────

    const buildScene = function (element) {
        scene = new THREE.Scene();
        scene.background = new THREE.Color(COLOR_BACKGROUND);

        // Orthographic, not perspective. A grid read at a glance wants every
        // cell the same size on screen; under perspective the corner slots
        // foreshorten differently from the middle ones, which both looks wrong
        // and makes drag targeting feel inconsistent across the pane.
        camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100);
        camera.position.set(0, 0, 10);
        camera.lookAt(0, 0, 0);

        renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setPixelRatio(window.devicePixelRatio || 1);
        element.appendChild(renderer.domElement);

        // Labels are DOM, not three.js text: crisp at any DPI, no font atlas,
        // no geometry, and they inherit the client's own font.
        labelLayer = document.createElement("div");
        labelLayer.style.position = "absolute";
        labelLayer.style.left = "0";
        labelLayer.style.top = "0";
        labelLayer.style.width = "100%";
        labelLayer.style.height = "100%";
        // The canvas underneath must keep receiving every pointer event.
        labelLayer.style.pointerEvents = "none";
        labelLayer.style.overflow = "hidden";
        element.style.position = "relative";
        element.appendChild(labelLayer);

        scene.add(new THREE.AmbientLight(0xffffff, 0.62));
        const key = new THREE.DirectionalLight(0xffffff, 0.85);
        key.position.set(3, 6, 8);
        scene.add(key);
        const rim = new THREE.DirectionalLight(0x88aaff, 0.35);
        rim.position.set(-5, -2, 4);
        scene.add(rim);

        frameGroup = new THREE.Group();
        itemGroup = new THREE.Group();
        scene.add(frameGroup);
        scene.add(itemGroup);

        bindInput(renderer.domElement);
    };

    const resizeToContainer = function () {
        if (!renderer || !container || !camera) {
            return;
        }
        const width = container.clientWidth || 1;
        const height = container.clientHeight || 1;

        // setSize with updateStyle left at its default, deliberately. Passing
        // false sets only the width/height ATTRIBUTES, which are
        // size * devicePixelRatio, and with no CSS size to override them the
        // canvas lays out that many CSS pixels wide — larger than its pane on
        // any scaled display. The world pane documents the same trap; it is
        // invisible on a DPR-1 monitor and fatal to picking everywhere else.
        renderer.setSize(width, height);

        // Frame a fixed world height; let width follow the aspect ratio, so
        // the grid never distorts as the pane is dragged narrower.
        const halfHeight = (layoutHeight() / 2) + VIEW_MARGIN;
        const halfWidth = halfHeight * (width / height);
        const neededWidth = (layoutWidth() / 2) + VIEW_MARGIN;

        // A very tall, narrow pane would clip the grid horizontally. Widen the
        // frustum (zooming out) rather than letting the layout run off-screen.
        const finalWidth = Math.max(halfWidth, neededWidth);
        const finalHeight = finalWidth / (width / height);

        camera.left = -finalWidth;
        camera.right = finalWidth;
        camera.top = finalHeight;
        camera.bottom = -finalHeight;
        camera.updateProjectionMatrix();
    };

    // ─── Frames ─────────────────────────────────────────────────────────────

    const makeFrame = function (key, position, color, payload) {
        const geo = new THREE.BoxGeometry(FRAME_SIZE, FRAME_SIZE, FRAME_DEPTH);
        const mat = new THREE.MeshStandardMaterial({
            color: color, metalness: 0.1, roughness: 0.9
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.copy(position);
        mesh.position.z = -FRAME_DEPTH;
        mesh.userData.frame = payload;
        mesh.userData.key = key;
        frameGroup.add(mesh);
        frameMeshes[key] = mesh;

        return mesh;
    };

    const buildFrames = function () {
        if (!snapshot) {
            return;
        }
        const backGeo = new THREE.PlaneGeometry(
            layoutWidth() + VIEW_MARGIN, layoutHeight() + VIEW_MARGIN);
        const backMat = new THREE.MeshStandardMaterial({
            color: COLOR_BACKPLATE, metalness: 0.0, roughness: 1.0
        });
        const backplate = new THREE.Mesh(backGeo, backMat);
        backplate.position.z = -(FRAME_DEPTH * 3);
        frameGroup.add(backplate);

        const frames = snapshot.equip_slots || [];

        frames.forEach(function (entry, index) {
            makeFrame(
                equipKey(entry.slot),
                equipCellPos(index),
                COLOR_FRAME_EQUIP,
                { kind: "equip", slot: entry.slot, label: entry.label }
            );
        });

        for (let i = 0; i < snapshot.slots_total; i++) {
            makeFrame(
                invKey(i),
                gridCellPos(i),
                COLOR_FRAME,
                { kind: "inventory", index: i }
            );
        }
    };

    // ─── Items ──────────────────────────────────────────────────────────────

    const disposeMesh = function (mesh) {
        mesh.traverse(function (child) {
            if (child.geometry) {
                child.geometry.dispose();
            }
            if (child.material) {
                child.material.dispose();
            }
        });
    };

    const clearScene = function () {
        setHover(null);
        closeContextMenu();

        Object.keys(itemMeshes).forEach(function (key) {
            const mesh = itemMeshes[key];
            itemGroup.remove(mesh);
            disposeMesh(mesh);
            delete itemMeshes[key];
        });
        Object.keys(frameMeshes).forEach(function (key) {
            delete frameMeshes[key];
        });
        Object.keys(labels).forEach(function (key) {
            if (labels[key].parentNode) {
                labels[key].parentNode.removeChild(labels[key]);
            }
            delete labels[key];
        });

        while (frameGroup.children.length) {
            const child = frameGroup.children[0];
            frameGroup.remove(child);
            disposeMesh(child);
        }
    };

    const makeLabel = function (key, row) {
        const div = document.createElement("div");
        div.style.position = "absolute";
        div.style.transform = "translate(-50%, 0)";
        div.style.fontSize = "10px";
        div.style.lineHeight = "1.1";
        div.style.textAlign = "center";
        div.style.color = "#cfe0ee";
        div.style.textShadow = "0 1px 2px #000";
        div.style.pointerEvents = "none";
        div.style.whiteSpace = "nowrap";
        div.style.overflow = "hidden";
        div.style.textOverflow = "ellipsis";
        div.style.maxWidth = "70px";

        let text = row.name;

        if (row.stackable && row.quantity > 1) {
            text = text + " x" + row.quantity;
        }
        div.textContent = text;
        labelLayer.appendChild(div);
        labels[key] = div;
    };

    // Place one item row into its frame. Asynchronous because the mesh
    // resolver is; `generation` is what stops a mesh from a superseded
    // snapshot landing in the current scene.
    const placeItem = function (key, row, generation) {
        const frame = frameMeshes[key];

        if (!frame) {
            return;
        }
        blackoutMeshes.resolve(row.asset, row.family).then(function (mesh) {
            if (generation !== renderGeneration || !itemGroup) {
                disposeMesh(mesh);
                return;
            }
            mesh.scale.setScalar(ITEM_SCALE);
            mesh.position.copy(frame.position);
            mesh.position.z = ITEM_LIFT;
            mesh.rotation.x = ITEM_TILT_X;
            mesh.userData.row = row;
            mesh.userData.key = key;
            mesh.userData.home = mesh.position.clone();
            itemGroup.add(mesh);
            itemMeshes[key] = mesh;
            makeLabel(key, row);
        });
    };

    const rebuild = function () {
        if (!scene || !snapshot) {
            return;
        }
        renderGeneration += 1;
        const generation = renderGeneration;

        // A snapshot arriving mid-drag CANCELS the drag rather than being
        // deferred. A real inventory change during a gesture is rare, and
        // cancelling is one branch where deferring would be a state machine
        // that has to decide what a half-applied move means.
        if (drag) {
            log("snapshot arrived mid-drag; cancelling the drag");
            drag = null;
        }
        clearScene();
        buildFrames();

        const carried = snapshot.items || [];
        const worn = snapshot.equipped || [];

        carried.forEach(function (row) {
            placeItem(invKey(row.slot), row, generation);
        });
        worn.forEach(function (row) {
            placeItem(equipKey(row.slot), row, generation);
        });
        resizeToContainer();
    };

    // ─── Picking ────────────────────────────────────────────────────────────

    // A real raycast, unlike the world pane's screen-distance comparison.
    // That trick exists there because entities are ENTITY_SIZE spheres a few
    // pixels across and an honest intersection would be a test of aim. Frames
    // here are large, square and adjacent, so an exact hit is both achievable
    // and what the player expects — a cursor one pixel inside a frame should
    // pick that frame, not its neighbour.
    const pickFrame = function (event) {
        if (!renderer || !camera || !frameGroup) {
            return null;
        }
        if (!raycaster) {
            raycaster = new THREE.Raycaster();
        }
        const element = event.currentTarget || renderer.domElement;
        const rect = element.getBoundingClientRect();

        if (!rect.width || !rect.height) {
            return null;
        }
        const ndc = new THREE.Vector2(
            ((event.clientX - rect.left) / rect.width) * 2 - 1,
            -((event.clientY - rect.top) / rect.height) * 2 + 1
        );
        raycaster.setFromCamera(ndc, camera);

        const hits = raycaster.intersectObjects(frameGroup.children, false);

        for (let i = 0; i < hits.length; i++) {
            if (hits[i].object.userData.frame) {
                return hits[i].object;
            }
        }
        return null;
    };

    const rowAt = function (key) {
        const mesh = itemMeshes[key];

        if (!mesh) {
            return null;
        }
        return mesh.userData.row;
    };

    // ─── What a drag means ──────────────────────────────────────────────────

    // The command for dropping the item held from `sourceKey` onto `targetKey`,
    // or null when that is not a legal move. Both the target glow and the
    // command go through here, so what lights up is by construction what will
    // happen — the same contract blackout3d.js's tileAction keeps.
    const dropAction = function (sourceKey, targetKey) {
        const sourceRow = rowAt(sourceKey);

        if (!sourceRow || sourceKey === targetKey) {
            return null;
        }
        const target = frameMeshes[targetKey];

        if (!target) {
            return null;
        }
        const frame = target.userData.frame;
        const fromInventory = sourceKey.indexOf("inv:") === 0;

        if (fromInventory && frame.kind === "inventory") {
            // Slot numbers are 1-based for the player; the payload's are array
            // indices. serialize_inventory does the same conversion when it
            // builds the action commands, so both agree.
            const from = sourceRow.slot + 1;
            const to = frame.index + 1;
            return "swap " + from + " " + to;
        }

        if (fromInventory && frame.kind === "equip") {
            // Only the slot the item actually fits is a legal target, and the
            // server already said which that is. An item with no equip_slot
            // lights nothing on the paper doll at all.
            if (!sourceRow.equip_slot || sourceRow.equip_slot !== frame.slot) {
                return null;
            }
            return namedAction(sourceRow, "equip");
        }

        if (!fromInventory && frame.kind === "inventory") {
            // Note that `unequip` places the item in the first free slot, not
            // the frame the player dropped it on. The pane does not pretend
            // otherwise: it sends one command and redraws from the snapshot
            // that answers it. Chaining a `swap` behind it would be two
            // commands racing one gesture.
            return namedAction(sourceRow, "unequip");
        }
        return null;
    };

    // Pull a command out of the row's server-named action list by verb.
    //
    // There is deliberately no verb table in this file. The server names the
    // whole command — "equip 7", "unequip main_hand" — and this only picks
    // which of the offered ones a given gesture means.
    //
    // REFUSES A ROW THAT HAS BEEN MOVED OPTIMISTICALLY. The action strings
    // were built by the server against the slot the item was in when the
    // snapshot was taken, and an optimistic swap changes where it is without
    // being able to rewrite them. Swapping slot 1 to slot 6 and immediately
    // dragging onto the paper doll would otherwise send the stale "equip 1" —
    // equipping whatever is NOW in slot 1, which is the wrong item.
    //
    // Refusing for the one tick until the snapshot lands is the honest answer:
    // the frame does not light up, nothing is sent, and the gesture works on
    // the next try. Rebuilding the command here from row.slot would be this
    // file inventing a verb, which is the thing the world pane's deleted verb
    // table proved not to do.
    const namedAction = function (row, verb) {
        if (row.pendingMove) {
            return null;
        }
        const actions = row.actions || [];

        for (let i = 0; i < actions.length; i++) {
            if (actions[i].command.indexOf(verb + " ") === 0) {
                return actions[i].command;
            }
        }
        return null;
    };

    // ─── Optimistic application ─────────────────────────────────────────────

    // Move a mesh and its label from one slot key to another, keeping the two
    // caches and the mesh's own idea of where it is in step. Everything here
    // is undone by the next snapshot, which is the authority.
    const reseat = function (mesh, label, key) {
        const frame = frameMeshes[key];

        itemMeshes[key] = mesh;
        mesh.userData.key = key;

        if (label) {
            labels[key] = label;
        }
        if (frame) {
            mesh.position.copy(frame.position);
            mesh.position.z = ITEM_LIFT;
            mesh.userData.home = mesh.position.clone();
        }
    };

    const forget = function (key) {
        const mesh = itemMeshes[key];
        const label = labels[key];

        delete itemMeshes[key];
        delete labels[key];

        if (mesh) {
            itemGroup.remove(mesh);
            disposeMesh(mesh);
        }
        if (label && label.parentNode) {
            label.parentNode.removeChild(label);
        }
    };

    // Show the outcome of a drop before the server has answered.
    //
    // Waiting a full tick for the snapshot makes the pane feel dead, so the
    // prediction is drawn immediately — but it has to be a WHOLE prediction.
    // Moving only the dragged mesh on a swap leaves the displaced item sitting
    // under it, which reads as a bug for the tick it lasts.
    //
    // Each case predicts exactly as much as it honestly can:
    //
    //   swap    — fully predictable. Both meshes move, both rows have their
    //             slot updated so a second drag in the same tick still names
    //             the right numbers.
    //   equip   — the destination is the frame the player dropped on, so the
    //             mesh moves there.
    //   unequip — the destination is NOT knowable here. `unequip` puts the
    //             item in the first free slot, which is the server's decision
    //             and depends on state this pane does not track. So the mesh
    //             is removed rather than guessed at: "it has left your gear"
    //             is true, and the snapshot places it a tick later.
    const applyOptimistic = function (sourceKey, targetKey) {
        const target = frameMeshes[targetKey];

        if (!target) {
            return;
        }
        const frame = target.userData.frame;
        const fromInventory = sourceKey.indexOf("inv:") === 0;

        if (!fromInventory && frame.kind === "inventory") {
            forget(sourceKey);
            return;
        }

        const sourceMesh = itemMeshes[sourceKey];
        const sourceLabel = labels[sourceKey];
        const targetMesh = itemMeshes[targetKey];
        const targetLabel = labels[targetKey];

        delete itemMeshes[sourceKey];
        delete labels[sourceKey];
        delete itemMeshes[targetKey];
        delete labels[targetKey];

        if (sourceMesh) {
            reseat(sourceMesh, sourceLabel, targetKey);
        }
        if (targetMesh) {
            reseat(targetMesh, targetLabel, sourceKey);
        }

        if (frame.kind !== "inventory") {
            return;
        }
        // Keep the rows' slot numbers honest, so a drag that happens before
        // the snapshot lands still builds a correct `swap` — and mark them
        // moved, so namedAction refuses to reuse action strings the server
        // built against the slot they were in a moment ago.
        const sourceIndex = parseInt(sourceKey.split(":")[1], 10);

        if (sourceMesh && sourceMesh.userData.row) {
            sourceMesh.userData.row.slot = frame.index;
            sourceMesh.userData.row.pendingMove = true;
        }
        if (targetMesh && targetMesh.userData.row) {
            targetMesh.userData.row.slot = sourceIndex;
            targetMesh.userData.row.pendingMove = true;
        }
    };

    // ─── Control ────────────────────────────────────────────────────────────

    // The only way a command leaves this pane, deliberately. What goes down
    // the wire is the same ["text", [...]] a player typing in the input box
    // sends, so there is one code path on the server for both.
    //
    // Returns true when the command actually went, and CANNOT THROW. That is
    // load-bearing, not defensive habit:
    //
    // Evennia.msg reaches WebSocket.send, which throws InvalidStateError while
    // the socket is still CONNECTING. buildPane runs inside myLayout.init()
    // when the pane is restored from a SAVED LAYOUT, which is early enough for
    // that to be true — and an exception escaping buildPane propagates out of
    // GoldenLayout's component construction, which it does not survive. It
    // aborts AFTER goldenlayout's init() has already removed the HTML-defined
    // prompt and input divs, so the entire webclient renders as a blank page.
    // Not this pane: all of it.
    //
    // It presents as "the client works when I open the pane by hand, and is
    // blank on every page load afterwards", because opening it by hand happens
    // long after the socket is up. Clearing the saved layout appears to fix it,
    // which sends you looking in the wrong place.
    const sendCommand = function (command) {
        try {
            Evennia.msg("text", [command], {});
            log("sent", command);
            return true;
        } catch (err) {
            log("could not send", command, err.message);
            return false;
        }
    };

    // Ask the server for a snapshot, if we have none and the wire is up.
    //
    // `inventory` is an ordinary command that publishes a snapshot as a side
    // effect — and prints the text grid too, which is honest about what was
    // asked for. When the socket is not ready the request is REMEMBERED rather
    // than dropped, and onLoggedIn retries it.
    const requestSnapshot = function () {
        if (snapshot) {
            wantSnapshot = false;
            return;
        }
        if (!window.Evennia || !Evennia.isConnected || !Evennia.isConnected()) {
            wantSnapshot = true;
            return;
        }
        wantSnapshot = !sendCommand("inventory");
    };

    // ─── Hover and glow ─────────────────────────────────────────────────────

    const setGlow = function (key, color) {
        const mesh = frameMeshes[key];

        if (mesh && mesh.material) {
            mesh.material.emissive.setHex(color);
        }
    };

    const setHover = function (key) {
        if (hoverKey === key) {
            return;
        }
        if (hoverKey) {
            setGlow(hoverKey, COLOR_NO_GLOW);
        }
        hoverKey = key;

        if (hoverKey) {
            setGlow(hoverKey, COLOR_HOVER_GLOW);
        }
    };

    const setDragTarget = function (key) {
        if (!drag) {
            return;
        }
        if (drag.targetKey && drag.targetKey !== key) {
            setGlow(drag.targetKey, COLOR_NO_GLOW);
        }
        drag.targetKey = key;

        if (!key) {
            return;
        }
        const action = dropAction(drag.key, key);

        // An illegal target gets NO glow rather than a red one. Absence of
        // feedback is the same refusal the world pane uses for a wall, and it
        // never has to be un-learned as "red means something else here".
        setGlow(key, action ? COLOR_TARGET_GLOW : COLOR_REFUSE_GLOW);
    };

    // ─── Tooltip ────────────────────────────────────────────────────────────

    const hideTooltip = function () {
        if (tooltip && tooltip.parentNode) {
            tooltip.parentNode.removeChild(tooltip);
        }
        tooltip = null;
    };

    // Name, stack size and slot only.
    //
    // Deliberately not the item's description: serialize_entity omits `desc`
    // from the feed on purpose, because the text channel already carries the
    // prose and duplicating it is how the two drift. A player who wants the
    // description uses the Inspect action and reads it where it lives.
    const showTooltip = function (row, event) {
        hideTooltip();

        if (!container) {
            return;
        }
        tooltip = document.createElement("div");
        tooltip.style.position = "absolute";
        tooltip.style.padding = "3px 6px";
        tooltip.style.background = "rgba(10,14,20,0.94)";
        tooltip.style.border = "1px solid #35e0c0";
        tooltip.style.borderRadius = "3px";
        tooltip.style.color = "#e6f2ff";
        tooltip.style.fontSize = "11px";
        tooltip.style.pointerEvents = "none";
        tooltip.style.whiteSpace = "nowrap";
        tooltip.style.zIndex = "20";

        let text = row.name;

        if (row.stackable && row.quantity > 1) {
            text = text + " (x" + row.quantity + ")";
        }
        if (row.equip_slot) {
            text = text + " — " + row.equip_slot.replace(/_/g, " ");
        }
        tooltip.textContent = text;

        const rect = container.getBoundingClientRect();
        tooltip.style.left = (event.clientX - rect.left + 12) + "px";
        tooltip.style.top = (event.clientY - rect.top + 12) + "px";
        labelLayer.appendChild(tooltip);
    };

    // ─── Context menu ───────────────────────────────────────────────────────

    const closeContextMenu = function () {
        if (contextMenu && contextMenu.parentNode) {
            contextMenu.parentNode.removeChild(contextMenu);
        }
        contextMenu = null;
    };

    // Built entirely from the row's `actions`, which is why a new verb on an
    // item needs no client change at all.
    const openContextMenu = function (row, event) {
        closeContextMenu();

        const actions = row.actions || [];

        if (!actions.length || !container) {
            return;
        }
        contextMenu = document.createElement("div");
        contextMenu.style.position = "absolute";
        contextMenu.style.background = "rgba(10,14,20,0.97)";
        contextMenu.style.border = "1px solid #35e0c0";
        contextMenu.style.borderRadius = "3px";
        contextMenu.style.zIndex = "30";
        contextMenu.style.minWidth = "96px";
        contextMenu.style.pointerEvents = "auto";

        const title = document.createElement("div");
        title.textContent = row.name;
        title.style.padding = "4px 8px";
        title.style.borderBottom = "1px solid #22303d";
        title.style.color = "#8fa6b8";
        title.style.fontSize = "10px";
        contextMenu.appendChild(title);

        actions.forEach(function (action) {
            const entry = document.createElement("div");
            entry.textContent = action.label;
            entry.style.padding = "4px 8px";
            entry.style.cursor = "pointer";
            entry.style.color = "#e6f2ff";
            entry.style.fontSize = "11px";
            entry.addEventListener("mouseenter", function () {
                entry.style.background = "#1d3a44";
            });
            entry.addEventListener("mouseleave", function () {
                entry.style.background = "";
            });
            entry.addEventListener("click", function () {
                sendCommand(action.command);
                closeContextMenu();
            });
            contextMenu.appendChild(entry);
        });

        const rect = container.getBoundingClientRect();
        contextMenu.style.left = (event.clientX - rect.left) + "px";
        contextMenu.style.top = (event.clientY - rect.top) + "px";
        // The menu itself must take clicks, so it goes in the container rather
        // than in the pointer-events:none label layer.
        container.appendChild(contextMenu);
    };

    // ─── Pointer handling ───────────────────────────────────────────────────

    const onPointerDown = function (event) {
        closeContextMenu();
        hideTooltip();

        const frame = pickFrame(event);

        if (!frame) {
            return;
        }
        const key = frame.userData.key;

        if (event.button === MOUSE_BUTTON_RIGHT) {
            const row = rowAt(key);

            if (row) {
                openContextMenu(row, event);
            }
            event.preventDefault();
            return;
        }
        if (event.button !== MOUSE_BUTTON_LEFT) {
            return;
        }
        if (!itemMeshes[key]) {
            return;
        }
        pressStart = { x: event.clientX, y: event.clientY, key: key };

        // Capture so a drag that leaves the canvas keeps tracking instead of
        // sticking with an item held mid-air. Guarded for the same reason the
        // release below is: capturing a pointer the browser does not consider
        // active throws, and an exception here would abort the gesture before
        // it started rather than merely losing the capture.
        if (event.target.setPointerCapture) {
            try {
                event.target.setPointerCapture(event.pointerId);
            } catch (err) {
                // No capture. A drag that leaves the canvas ends at the edge,
                // which is a degraded gesture rather than a broken one.
            }
        }
    };

    const beginDrag = function () {
        const mesh = itemMeshes[pressStart.key];

        if (!mesh) {
            pressStart = null;
            return;
        }
        drag = {
            key: pressStart.key,
            mesh: mesh,
            home: mesh.position.clone(),
            targetKey: null
        };
        mesh.scale.setScalar(ITEM_SCALE * DRAG_SCALE);
        pressStart = null;
    };

    const onPointerMove = function (event) {
        if (pressStart) {
            const travel = Math.sqrt(
                Math.pow(event.clientX - pressStart.x, 2) +
                Math.pow(event.clientY - pressStart.y, 2));

            if (travel > DRAG_SLOP_PX) {
                beginDrag();
            }
        }
        const frame = pickFrame(event);
        const key = frame ? frame.userData.key : null;

        if (drag) {
            setHover(null);
            setDragTarget(key);
            followCursor(event);
            return;
        }
        setHover(key);

        const row = key ? rowAt(key) : null;

        if (row) {
            showTooltip(row, event);
            renderer.domElement.style.cursor = "pointer";
        } else {
            hideTooltip();
            renderer.domElement.style.cursor = "";
        }
    };

    // Move the held mesh to the cursor, on the plane it already sits in.
    // Orthographic unprojection is exact here — no ray/plane intersection is
    // needed, because every point on the near plane maps straight through.
    const followCursor = function (event) {
        const element = event.currentTarget || renderer.domElement;
        const rect = element.getBoundingClientRect();

        if (!rect.width || !rect.height) {
            return;
        }
        const ndc = new THREE.Vector3(
            ((event.clientX - rect.left) / rect.width) * 2 - 1,
            -((event.clientY - rect.top) / rect.height) * 2 + 1,
            0
        );
        ndc.unproject(camera);
        drag.mesh.position.set(ndc.x, ndc.y, DRAG_LIFT);
    };

    const cancelDrag = function () {
        if (!drag) {
            return;
        }
        if (drag.targetKey) {
            setGlow(drag.targetKey, COLOR_NO_GLOW);
        }
        drag.mesh.position.copy(drag.home);
        drag.mesh.scale.setScalar(ITEM_SCALE);
        drag = null;
    };

    const onPointerUp = function (event) {
        if (event.target.releasePointerCapture) {
            try {
                event.target.releasePointerCapture(event.pointerId);
            } catch (err) {
                // Capture may already have been released; nothing to undo.
            }
        }
        if (pressStart) {
            // Never moved far enough to be a drag. A plain left click on an
            // item does nothing on its own — every verb is in the right-click
            // menu, where it is named rather than guessed at.
            pressStart = null;
            return;
        }
        if (!drag) {
            return;
        }
        const frame = pickFrame(event);
        const targetKey = frame ? frame.userData.key : null;
        const action = targetKey ? dropAction(drag.key, targetKey) : null;

        if (!action) {
            cancelDrag();
            return;
        }

        // Optimistic: draw the outcome now, and let the snapshot that answers
        // this command be the truth. Waiting a full tick for the server would
        // make the pane feel dead; if the server refuses, the next
        // char_items_list corrects it and the text pane says why.
        setGlow(targetKey, COLOR_NO_GLOW);
        drag.mesh.scale.setScalar(ITEM_SCALE);

        const sourceKey = drag.key;
        drag = null;
        applyOptimistic(sourceKey, targetKey);

        sendCommand(action);
    };

    const onPointerLeave = function () {
        setHover(null);
        hideTooltip();
        pressStart = null;
        cancelDrag();
    };

    const bindInput = function (element) {
        element.addEventListener("pointerdown", onPointerDown);
        element.addEventListener("pointermove", onPointerMove);
        element.addEventListener("pointerup", onPointerUp);
        element.addEventListener("pointercancel", onPointerLeave);
        element.addEventListener("pointerleave", onPointerLeave);
        // Without this the browser menu opens on mouse-DOWN on some platforms
        // and swallows our own.
        element.addEventListener("contextmenu", function (event) {
            event.preventDefault();
        });
    };

    // ─── The frame loop ─────────────────────────────────────────────────────

    const positionLabels = function () {
        const rect = renderer.domElement.getBoundingClientRect();

        if (!rect.width || !rect.height) {
            return;
        }
        Object.keys(labels).forEach(function (key) {
            const mesh = itemMeshes[key];
            const div = labels[key];

            if (!mesh) {
                div.style.display = "none";
                return;
            }
            const frame = frameMeshes[key];
            // Anchor the label to the FRAME, not to the item: an item that is
            // spinning, bobbing or being dragged would otherwise drag its
            // caption around with it.
            const anchor = frame ? frame.position : mesh.position;
            const ndc = anchor.clone().project(camera);
            const x = (ndc.x + 1) * 0.5 * rect.width;
            const y = (1 - ndc.y) * 0.5 * rect.height;

            div.style.display = "";
            div.style.left = x + "px";
            div.style.top = (y + (rect.height * 0.018)) + "px";
        });
    };

    const animate = function () {
        animationHandle = requestAnimationFrame(animate);

        if (!renderer || !scene || !camera) {
            return;
        }
        const clock = performance.now() / 1000;

        Object.keys(itemMeshes).forEach(function (key) {
            const mesh = itemMeshes[key];

            mesh.rotation.y = clock * Math.PI * 2 * ITEM_SPIN_HZ;

            // The held item does not bob: its position is the cursor's, and
            // adding an offset to that would make it lag the pointer.
            if (drag && drag.mesh === mesh) {
                return;
            }
            const bob = Math.sin(clock * Math.PI * 2 * ITEM_BOB_HZ);
            mesh.position.z = ITEM_LIFT + (bob * ITEM_BOB_AMP);
        });

        positionLabels();
        renderer.render(scene, camera);
    };

    // ─── Channel handling ───────────────────────────────────────────────────

    const onItems = function (data) {
        snapshot = data;
        // Whatever we were waiting for has arrived — usually the server's own
        // resync, which beats a cold-start request in the normal case.
        wantSnapshot = false;
        rebuild();
    };

    // ─── GoldenLayout wiring ────────────────────────────────────────────────

    const resetRenderState = function () {
        Object.keys(frameMeshes).forEach(function (k) { delete frameMeshes[k]; });
        Object.keys(itemMeshes).forEach(function (k) { delete itemMeshes[k]; });
        Object.keys(labels).forEach(function (k) { delete labels[k]; });
        renderGeneration += 1;
        drag = null;
        pressStart = null;
        hoverKey = null;
        contextMenu = null;
        tooltip = null;
        raycaster = null;

        if (animationHandle && typeof cancelAnimationFrame === "function") {
            cancelAnimationFrame(animationHandle);
            animationHandle = null;
        }

        // Throw away the previous canvas and the GPU context behind it.
        //
        // buildPane appends a canvas per call and GoldenLayout calls it more
        // than once — on a saved-layout activation and on re-parenting. The
        // world pane documents what happens without this: canvases accumulate,
        // the module points at the newest, and pointer events arrive on a
        // canvas that is not the one being measured, so every click resolves
        // against a stale rect.
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
        if (labelLayer && labelLayer.parentNode) {
            labelLayer.parentNode.removeChild(labelLayer);
        }
        labelLayer = null;
    };

    const buildPane = function (glContainer) {
        const element = glContainer.getElement()[0];
        element.style.width = "100%";
        element.style.height = "100%";
        container = element;

        if (!window.THREE) {
            element.innerHTML =
                "<p style='padding:1em'>three.js is not loaded — the 3D " +
                "inventory is unavailable. Type `inventory` for the text " +
                "grid, which is unaffected.</p>";
            return;
        }
        if (!window.blackoutMeshes) {
            element.innerHTML =
                "<p style='padding:1em'>blackout_meshes.js is not loaded — " +
                "the 3D inventory is unavailable. Type `inventory` for the " +
                "text grid, which is unaffected.</p>";
            return;
        }

        resetRenderState();
        buildScene(element);
        resizeToContainer();
        glContainer.on("resize", resizeToContainer);
        animate();

        if (snapshot) {
            // Replay. A pane opened ten minutes into a session must show the
            // inventory, not wait for the next pickup.
            rebuild();
            return;
        }

        // Cold start: the feed has never sent one, which happens when the
        // player opens this pane in a session where nothing has touched their
        // inventory since login.
        //
        // Routed through requestSnapshot rather than sending here, because
        // this function runs inside myLayout.init() when the pane comes back
        // from a saved layout — before the websocket is open. See sendCommand
        // for what a throw at this exact point does to the whole client.
        requestSnapshot();
    };

    const createComponent = function () {
        const goldenlayout = window.plugins["goldenlayout"];

        if (!goldenlayout) {
            return false;
        }
        const myLayout = goldenlayout.getGL();

        if (!myLayout) {
            return false;
        }
        myLayout.registerComponent("blackout_inventory", buildPane);
        return true;
    };

    const registerSafely = function (where) {
        try {
            return createComponent();
        } catch (err) {
            console.log("[blackout_inventory] component registration failed in "
                + where + ": " + err.message);
            return false;
        }
    };

    const onLayoutChanged = function () {
        registerSafely("onLayoutChanged");
    };

    // There can only be ONE, for the reason the world pane spells out: the
    // scene, renderer and mesh caches are module state, so a second pane does
    // not get a second inventory — it takes this one's, and buildPane's reset
    // then disposes the canvas the first was drawing on.
    const openPane = function () {
        const myLayout = window.plugins["goldenlayout"].getGL();
        const existing = myLayout.root.getItemsByType("component").filter(
            function (item) {
                return item.config.componentName === "blackout_inventory";
            });

        if (existing.length) {
            const pane = existing[0];

            if (pane.parent && pane.parent.setActiveContentItem) {
                pane.parent.setActiveContentItem(pane);
            }
            return;
        }
        const component = {
            title: "Inventory",
            type: "component",
            componentName: "blackout_inventory",
            componentState: {}
        };
        const main = myLayout.root.getItemsByType("stack")[0].getActiveContentItem();
        main.parent.addChild(component);
    };

    // ─── Plugin interface ───────────────────────────────────────────────────

    const boundChannels = {};

    const route = function (cmdname, kwargs) {
        log(cmdname, kwargs);
        const data = kwargs || {};

        if (cmdname === CH_CHAR_ITEMS) {
            onItems(data);
        }
    };

    // Bind by name straight onto Evennia's emitter, NOT through the
    // onUnknownCmd plugin hook. DefaultEmitter dispatches to listeners[cmdname]
    // when one exists and only otherwise falls back to onDefault — whose first
    // taker is default_out.js, which claims every unknown command and prints it
    // as "Error or Unhandled event". This plugin necessarily loads after that
    // one, so a named listener is the only thing that can see the message.
    //
    // A CHANNEL HAS EXACTLY ONE LISTENER. DefaultEmitter.on does
    // `listeners[cmdname] = listener` — it REPLACES rather than appends — so
    // two plugins binding the same name is not two subscribers, it is the
    // second one silently taking the channel off the first. claimChannel is
    // what makes that impossible; see blackout_channels.js.
    const bindChannel = function (channel) {
        if (!channel || boundChannels[channel]) {
            return;
        }
        if (!window.blackoutChannels.claim(channel, PLUGIN_NAME)) {
            return;
        }
        boundChannels[channel] = true;
        Evennia.emitter.on(channel, function (args, kwargs) {
            route(channel, kwargs);
        });
    };

    // This pane binds ONE channel, and never the acknowledgement.
    //
    // It used to bind every channel the server acknowledged, copying what
    // blackout3d.js does — and that was a bug that blanked the world pane.
    // blackout3d binds from the acknowledgement because it needs to CLAIM AND
    // DROP channels it has never heard of, so a server-side addition cannot
    // reach default_out.js and get printed at the player as raw JSON. Copying
    // that policy into a second plugin meant this one claimed room_info,
    // blackout_map, room_players and the rest, then dropped them — leaving the
    // world pane with no data at all.
    //
    // blackout_subscribed is deliberately absent too. blackout3d owns it, and
    // that ownership is load-bearing: an EMPTY acknowledged set is the server
    // saying "I have forgotten you", which at_sync sends after every reload,
    // and blackout3d's handler is what re-subscribes. Taking that channel
    // meant nothing ever re-subscribed. This pane does not need it — it knows
    // its one channel name at authoring time.
    const bindListeners = function () {
        if (!window.Evennia || !Evennia.emitter) {
            return false;
        }
        if (!window.blackoutChannels) {
            return false;
        }
        bindChannel(CH_CHAR_ITEMS);
        return true;
    };

    const onUnknownCmd = function (cmdname, args, kwargs) {
        if (!boundChannels[cmdname]) {
            return false;
        }
        route(cmdname, kwargs);
        return true;
    };

    const onOptionsUI = function (parentdiv) {
        const openButton = $('<input type="button" value="Open Inventory" />');
        openButton.on("click", openPane);

        const debugBox = $('<input type="checkbox" id="blackout-inventory-debug" />');
        debugBox.on("change", function () {
            debug = this.checked;
            console.log("[blackout_inventory] debug logging "
                + (debug ? "on" : "off"));
        });

        parentdiv.append('<div style="font-weight: bold">Blackout Inventory:</div>');
        parentdiv.append(openButton);
        parentdiv.append('<div>Drag an item onto another slot to rearrange, ' +
                         'onto its matching gear slot to equip it, or off ' +
                         'your gear back into the grid to take it off. ' +
                         'Unequipping puts an item in the first free slot, ' +
                         'not the one you dropped it on.</div>');
        parentdiv.append('<div>Right-click an item for everything else it ' +
                         'can do. A slot that does not light up is not a ' +
                         'legal move.</div>');
        parentdiv.append('<div><label>Log feed messages </label></div>');
        parentdiv.append(debugBox);
    };

    // Must register BEFORE GoldenLayout instantiates anything. init() is the
    // only hook early enough: goldenlayout's own init() constructs myLayout
    // from the layout saved in localStorage, and its postInit() is what calls
    // myLayout.init(). Registering in postInit() is a page-BLANKING bug for
    // any player who has ever opened this pane — GoldenLayout throws on the
    // unknown component type after the prompt and input divs have already been
    // removed, so the whole client renders blank, not just this pane.
    const init = function () {
        registerSafely("init");
    };

    const postInit = function () {
        registerSafely("postInit");

        const bound = bindListeners();
        console.log("Blackout Inventory plugin loaded." +
            (bound ? "" : " WARNING: emitter unavailable, feed will not route."));
    };

    // The socket is reliably up by the time this fires, which is what makes it
    // the right place to retry a cold-start request that buildPane could not
    // send. A pane restored from a saved layout is built before the connection
    // exists, so this is the normal path for it, not an error path.
    //
    // The server's own resync usually beats us to it — at_sync pushes a full
    // snapshot on connect — in which case requestSnapshot sees one and stays
    // quiet rather than making the player's text pane echo an `inventory` they
    // did not type.
    const onLoggedIn = function () {
        if (wantSnapshot) {
            requestSnapshot();
        }
    };

    return {
        init: init,
        postInit: postInit,
        onLayoutChanged: onLayoutChanged,
        onLoggedIn: onLoggedIn,
        onUnknownCmd: onUnknownCmd,
        onOptionsUI: onOptionsUI,
        getSnapshot: function () { return snapshot; }
    };
})();

window.plugin_handler.add("blackout_inventory", blackoutInventory);
