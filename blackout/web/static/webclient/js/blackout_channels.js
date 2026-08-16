/*
 * Blackout channel ownership — who is allowed to bind which feed channel.
 *
 * REQUIRES: nothing. Must load before any Blackout plugin.
 *
 * Not a plugin. A plain global, like blackout_meshes.js.
 *
 * THE PROBLEM THIS EXISTS FOR:
 *
 * Evennia's DefaultEmitter keeps ONE listener per command name. Its `on` does
 *
 *     listeners[cmdname] = listener;
 *
 * so a second plugin binding a name it already holds does not become a second
 * subscriber — it silently takes the channel away from the first, which then
 * stops receiving a channel it believes it is still handling.
 *
 * That is not hypothetical. blackout_inventory.js bound every channel the
 * server acknowledged, copying blackout3d.js's policy without copying its
 * reason, and took room_info, blackout_map, room_players and the rest off the
 * world pane. The world pane rendered a blank screen, threw no error, and
 * logged nothing: from its side, the feed had simply gone quiet. Worse, it
 * also took blackout_subscribed, whose empty-set message is the only signal
 * that says "the server has forgotten you, subscribe again" — so after a
 * reload nothing re-subscribed at all.
 *
 * A first-claim-wins registry makes the failure loud and local instead. A
 * plugin that asks for a channel someone else owns is refused and can say so,
 * rather than succeeding and breaking a pane it has never heard of.
 *
 * WHY FIRST CLAIM RATHER THAN LAST: the plugin that names a channel explicitly
 * at authoring time is always more specific than the one sweeping up whatever
 * the server happens to acknowledge, and the explicit ones bind during
 * postInit, before any acknowledgement can arrive. First-claim-wins is
 * therefore the same thing as most-specific-wins here, without needing a
 * priority to be declared and kept accurate.
 *
 * Author: Nick Hobar
 * Creation date: 08/15/2026
 */

let blackoutChannels = (function () {
    "use strict";

    // channel name -> the plugin name that holds it.
    const owners = {};

    // Try to take ownership of a channel.
    //
    // Returns true when the caller may bind it — either because it was
    // unclaimed, or because the caller already holds it and is re-binding,
    // which happens on a GoldenLayout layout change. Returns false when
    // another plugin owns it, and logs, because a refused claim always means
    // two panes disagree about who handles something.
    const claim = function (channel, pluginName) {
        const owner = owners[channel];

        if (owner && owner !== pluginName) {
            console.log("[blackout_channels] " + pluginName +
                " asked for '" + channel + "' but " + owner +
                " already owns it; not binding.");
            return false;
        }
        owners[channel] = pluginName;
        return true;
    };

    // Who owns a channel, or "" if nobody does. Diagnostic only.
    const ownerOf = function (channel) {
        return owners[channel] || "";
    };

    return {
        claim: claim,
        ownerOf: ownerOf
    };
})();

// Published on `window` explicitly. A top-level `let` creates a lexical
// binding in the global SCOPE but no property on the global OBJECT, so
// `window.blackoutChannels` would otherwise be undefined — and the window
// property is the only form a plugin can guard on without risking a
// ReferenceError when this file has failed to load.
window.blackoutChannels = blackoutChannels;
