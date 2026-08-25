/*
 * The pane shell — everything a Blackout GoldenLayout pane needs that is not
 * about what it draws.
 *
 * WHAT THIS IS FOR. blackout3d.js and blackout_inventory.js defined fifteen
 * identically-named routines between them. Eight of those are pure lifecycle
 * and wiring — component registration, the single-pane guard, opening and
 * surfacing, channel claiming, message routing — and the two copies were not
 * merely similar: they were the SAME code with a different plugin name, pane
 * title and build callback substituted. Those eight are here.
 *
 * That is not merely repetitive. It meant every bug found in one pane had to
 * be found again in the other, and the comments in both files record that
 * happening twice already — the orphaned-canvas bug and the second-pane guard
 * are each documented at length in two places, in two slightly different
 * wordings, having been fixed on two different days.
 *
 * A third pane — a map, a character sheet, a crafting UI — was a third copy.
 * It is now a call to createPaneShell.
 *
 * WHAT STAYS IN THE PANE. Everything about DRAWING: the scene, the camera, the
 * meshes, the picking, the frame loop, and the teardown of all of it. The
 * shell owns the pane's LIFECYCLE and its wiring to Evennia; it deliberately
 * knows nothing about three.js and never touches a renderer or a canvas.
 *
 * WHAT IS DELIBERATELY NOT HERE:
 *
 *   - The renderer, the canvas and their disposal. Two panes dispose very
 *     different things (one owns skinned-model clones and a skeleton, the
 *     other a flat grid of frames), and a shared "dispose everything" would
 *     have to know about both.
 *   - resizeToContainer. Both panes have one and they differ: the world pane
 *     drives a perspective camera, the inventory pane an orthographic one that
 *     rescales its layout to fit. Same name, genuinely different jobs.
 *   - Anything about what a click MEANS. That is the pane's, and increasingly
 *     the server's — see systems/statefeed/serializers.py.
 *   - onOptionsUI. It LOOKS shared: both panes add an "Open" button and a
 *     debug checkbox. But the world pane's block also carries six lines of
 *     help text about camera controls and what lights up, and the inventory
 *     pane's carries its own. A helper general enough to express both would
 *     take more parameters than the six lines it saved, and the pattern is
 *     shared while the CONTENT is not. Extracting it would have been
 *     extraction for its own sake.
 *
 * Author: Nick Hobar
 * Creation date: 08/23/2026
 */

import * as blackoutChannels from "../blackout_channels.js";

// GoldenLayout's own component config. `componentState` is required and empty
// for both panes; neither has any state worth persisting into a saved layout,
// because everything they draw is replayed from the feed on build.
const COMPONENT_TYPE = "component";
const STACK_TYPE = "stack";

/*
 * Build the lifecycle and wiring for one pane.
 *
 * Purpose: Give a pane everything that is not about drawing, so the two panes
 *          stop carrying two copies of it.
 *
 * Entry:
 *     spec.name     - the plugin name, and the GoldenLayout component name.
 *                     Must be unique across Blackout plugins; it is what
 *                     blackout_channels.js records as a channel's owner.
 *     spec.title    - the pane's tab title.
 *     spec.build    - build(glContainer). The pane's own constructor. Called
 *                     by GoldenLayout, possibly more than once in a session.
 *     spec.channels - () => [channel names] to bind at postInit. A function
 *                     rather than an array because blackout3d's list is not
 *                     final until the server has acknowledged a subscription.
 *     spec.route    - route(channel, kwargs). Called for every bound channel.
 *     spec.onOpen   - optional, called after the pane is opened from the
 *                     options UI.
 *
 * Exit/Returns:
 *     An object carrying the plugin_handler hooks (init, postInit,
 *     onLayoutChanged, onUnknownCmd) plus `bindChannel`, `openPane` and
 *     `isBound`, which panes need on their own behalf.
 *
 * Module Globals:
 *     blackoutChannels read.
 *
 * Methodology:
 *     Everything below was lifted verbatim from the two panes and
 *     parameterised on name/title/build. The comments came with it: each one
 *     records a specific bug, and they are the closest thing this layer has to
 *     a regression suite for the failures they describe.
 *
 * Notes/References:
 *     See docs/2026-08-23-ENG-0004-webclient-architecture.md, F3.
 */
export const createPaneShell = function (spec) {
    "use strict";

    const name = spec.name;
    const boundChannels = {};

    // Teach GoldenLayout how to build our pane.
    //
    // This MUST happen before GoldenLayout itself starts, and the only hook
    // early enough is init(). The sequence is: plugin_handler.init() runs
    // every plugin's init(), during which goldenlayout's init() constructs
    // myLayout from the layout saved in localStorage; only afterwards does
    // plugin_handler.postInit() run, and goldenlayout's postInit() is what
    // calls myLayout.init() and actually instantiates the panes.
    //
    // A player who has ever opened a Blackout pane has its name written into
    // that saved layout. Registering in postInit() is a page-blanking bug for
    // exactly those players: Blackout loads last, so goldenlayout's postInit
    // reaches myLayout.init() first, GoldenLayout throws on the component type
    // it has never heard of, and it throws AFTER goldenlayout's init() has
    // already removed the HTML-defined prompt and input divs — so the whole
    // client renders as a blank page, not just the pane.
    const createComponent = function () {
        const goldenlayout = window.plugins["goldenlayout"];

        if (!goldenlayout) {
            return false;
        }
        const myLayout = goldenlayout.getGL();

        if (!myLayout) {
            return false;
        }
        myLayout.registerComponent(name, spec.build);
        return true;
    };

    const registerSafely = function (where) {
        try {
            return createComponent();
        } catch (err) {
            console.log("[" + name + "] component registration failed in "
                + where + ": " + err.message);
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

    // Bring the pane up, or surface the one that already exists.
    //
    // There can only be ONE of each. A pane's scene, camera, renderer and mesh
    // caches are its module state, so a second pane does not get a second
    // world — it takes the first one's, and the build's own reset then disposes
    // the canvas the first was drawing on. Before this guard, clicking "Open"
    // twice (or once in a session whose layout GoldenLayout had already saved)
    // left a pane that looked fine and was not the one the module pointed at:
    // rendering carried on in one canvas while pointer events arrived on
    // another, and every click silently resolved to nothing.
    //
    // Making a second pane impossible is a smaller fix than making a pane
    // multi-instance, and multi-instance buys nothing — two views of one
    // diorama, from one camera the player steers in one place.
    const openPane = function () {
        const myLayout = window.plugins["goldenlayout"].getGL();
        const existing = myLayout.root.getItemsByType(COMPONENT_TYPE).filter(
            function (item) {
                return item.config.componentName === name;
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
            title: spec.title,
            type: COMPONENT_TYPE,
            componentName: name,
            componentState: {}
        };
        const main = myLayout.root.getItemsByType(
            STACK_TYPE)[0].getActiveContentItem();

        main.parent.addChild(component);

        if (spec.onOpen) {
            spec.onOpen();
        }
    };

    // Claim a channel and subscribe to it.
    //
    // The claim is what stops two panes silently taking a channel off each
    // other: Evennia's emitter keeps ONE listener per name, so a second bind is
    // a theft rather than a second subscription. See blackout_channels.js for
    // the bug that cost.
    const bindChannel = function (channel) {
        if (!channel || boundChannels[channel]) {
            return;
        }
        if (!blackoutChannels.claim(channel, name)) {
            return;
        }
        boundChannels[channel] = true;
        Evennia.emitter.on(channel, function (args, kwargs) {
            spec.route(channel, kwargs);
        });
    };

    const isBound = function (channel) {
        return Boolean(boundChannels[channel]);
    };

    const bindListeners = function () {
        if (!window.Evennia || !Evennia.emitter) {
            return false;
        }
        spec.channels().forEach(bindChannel);
        return true;
    };

    // A channel the server sent that nothing else claimed. Only ours if we
    // bound it; returning true stops default_out.js printing the raw JSON at
    // the player.
    const onUnknownCmd = function (cmdname, args, kwargs) {
        if (!boundChannels[cmdname]) {
            return false;
        }
        spec.route(cmdname, kwargs);
        return true;
    };

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
        return bindListeners();
    };

    return {
        init: init,
        postInit: postInit,
        onLayoutChanged: onLayoutChanged,
        onUnknownCmd: onUnknownCmd,
        bindChannel: bindChannel,
        isBound: isBound,
        openPane: openPane,
        registerSafely: registerSafely
    };
};
