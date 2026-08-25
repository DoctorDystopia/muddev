/*
 * tileAction — what clicking a tile means.
 *
 * WHY THIS ONE. Every click a player makes in the world pane goes through
 * tileAction, and the rules it used to hold were wrong once already in a way no
 * screenshot showed: diagonal neighbours with no diagonal link were refused,
 * which left the eight tiles nearest the player the only ones in the pane that
 * could not be clicked. Those rules now live in Python and are tested there
 * (systems/statefeed/tests/test_tile_actions.py); this is the other half —
 * that the CLIENT reads the server's answer correctly.
 *
 * It is pure: a tile in, an action or null out, reading only feed state the
 * module has already recorded. No DOM, no canvas, no browser.
 *
 * HOW THE PANE IS LOADED. blackout3d.js is an ES module that registers itself
 * with `window.plugin_handler` on evaluation, and reads `window.Evennia` when
 * binding. Node has neither, so the globals are stubbed BEFORE the dynamic
 * import — a static import would be hoisted above the stubs and the module
 * would throw on `window` being undefined.
 *
 * Run from blackout/web/jstests/:
 *     node --import ./register.mjs --test .
 *
 * Author: Nick Hobar
 * Creation date: 08/23/2026
 */

import test from "node:test";
import assert from "node:assert/strict";

// ─── Test doubles ────────────────────────────────────────────────────────────

const registered = {};
const listeners = {};

// The classic globals Evennia's webclient_gui.js defines. The pane reads these
// off `window` rather than importing them, because there is nothing to import
// them from — see the note at the bottom of blackout3d.js.
globalThis.window = globalThis;
globalThis.plugin_handler = {
    add: (name, plugin) => { registered[name] = plugin; },
};
globalThis.Evennia = {
    emitter: { on: (channel, fn) => { listeners[channel] = fn; } },
    msg: () => {},
};
globalThis.plugins = {};

// Evaluating the pane registers it. Dynamic, so the stubs above are in place.
const K = await import("../static/webclient/js/generated/blackout_constants.js");
await import("../static/webclient/js/plugins/blackout3d.js");

const pane = registered.blackout3d;

// postInit binds the feed channels through the shell. It also tries to register
// a GoldenLayout component, which fails harmlessly here and is caught by the
// shell's own try/catch — that tolerance is itself part of the contract.
pane.postInit();

// ─── Fixtures ────────────────────────────────────────────────────────────────

// Exactly what serializers.tile_actions produces for an observer standing at
// (4,6) on `oasis` with one real exit north. Kept in this shape deliberately:
// if the payload changes, this fixture is what has to change with it, and the
// Python tests are the source of truth for what the server actually sends.
const ROOM_INFO = {
    num: 1,
    name: "Oasis",
    room_kind: "Oasis",
    coords: [4, 6, "oasis"],
    exits: { north: 2 },
    tile_actions: {
        "4:6": { command: "look", kind: K.KIND_LOOK },
        "4:7": { command: "north", kind: K.KIND_STEP },
        "5:6": { command: "", kind: K.KIND_NONE },
        "3:6": { command: "", kind: K.KIND_NONE },
        "4:5": { command: "", kind: K.KIND_NONE },
    },
    cancel_action: { command: "goto", kind: K.KIND_CANCEL },
};

// A map node's own action: the walk to itself, stamped once per session.
const walk = (x, y) => ({ command: `goto (${x},${y})`, kind: K.KIND_WALK });
const tile = (x, y, z = "oasis") => ({ z, x, y, action: walk(x, y) });

const feed = (payload) => listeners[K.CH_ROOM_INFO]([], payload);

// ─── Tests ───────────────────────────────────────────────────────────────────

test("the pane binds every channel it declares", () => {
    for (const channel of [K.CH_ROOM_INFO, K.CH_MAP, K.CH_COMBAT,
                           K.CH_SUBSCRIBED]) {
        assert.ok(listeners[channel],
            `${channel} was never bound; the shell's postInit did not run`);
    }
});

test("the pane refuses everything before it knows where it is", () => {
    // No room_info yet. A tile carrying a perfectly good action must still be
    // refused, because "which map am I on" is unanswerable.
    assert.equal(pane.getTileAction(tile(4, 7)), null);
});

test("tileAction reads the server's answer", async (t) => {
    feed(ROOM_INFO);

    await t.test("own tile -> look", () => {
        assert.deepEqual(pane.getTileAction(tile(4, 6)),
            { command: "look", kind: K.KIND_LOOK });
    });

    await t.test("real exit -> the step the exit is named", () => {
        assert.deepEqual(pane.getTileAction(tile(4, 7)),
            { command: "north", kind: K.KIND_STEP });
    });

    await t.test("cardinal neighbour with no exit -> refused", () => {
        // An EMPTY command, not an absent entry. This is the wall rule: a
        // click on a visible barrier must not walk the player the long way
        // around it.
        assert.equal(pane.getTileAction(tile(5, 6)), null);
        assert.equal(pane.getTileAction(tile(4, 5)), null);
    });

    await t.test("diagonal neighbour with no link -> walk", () => {
        // ABSENT from tile_actions, so it falls through to the node's own
        // goto. This is the case the old client got wrong.
        assert.deepEqual(pane.getTileAction(tile(5, 7)), walk(5, 7));
    });

    await t.test("distant tile -> walk", () => {
        assert.deepEqual(pane.getTileAction(tile(10, 0)), walk(10, 0));
    });

    await t.test("tile on another map -> refused", () => {
        // `goto` does not cross maps; the islands are joined by transition
        // NODES you walk onto, not by coordinates that relate.
        assert.equal(pane.getTileAction(tile(4, 7, "oasis_outskirts")), null);
    });

    await t.test("tile the server gave no action -> refused", () => {
        assert.equal(
            pane.getTileAction({ z: "oasis", x: 9, y: 9, action: null }), null);
    });
});

test("an empty command is not the same as an absent entry", () => {
    // The distinction the whole design rests on, asserted directly rather than
    // inferred from the two cases above: absent means "fall through to the
    // node's goto", empty means "the server says no".
    feed(ROOM_INFO);

    const absent = pane.getTileAction(tile(7, 7));
    const empty = pane.getTileAction(tile(5, 6));

    assert.deepEqual(absent, walk(7, 7));
    assert.equal(empty, null);
});

test("a room with no coordinates refuses everything", () => {
    feed({ ...ROOM_INFO, coords: [] });

    assert.equal(pane.getTileAction(tile(4, 7)), null);
});

test("a room_info with no tile_actions still walks", () => {
    // Forward compatibility in the honest direction: an older server, or one
    // that sends the field empty, must not break the pane. Every tile falls
    // through to the map node's own action.
    feed({ ...ROOM_INFO, tile_actions: {} });

    assert.deepEqual(pane.getTileAction(tile(4, 7)), walk(4, 7));
});
