/*
 * Blackout channel ownership — who is allowed to bind which feed channel.
 *
 * An ES MODULE. Not a plugin -- it registers nothing with plugin_handler.
 *
 * It used to be a plain global that "must load before any Blackout plugin",
 * which was a requirement nothing could enforce. It is now imported by the
 * panes that use it, so the ordering is the import graph.
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



// channel name -> the plugin name that holds it. Module-scoped, so this is
// exactly one registry no matter how many modules import it -- which is the
// property the whole thing depends on. A second copy would let two panes each
// believe they own a channel.
const owners = {};



// Try to take ownership of a channel.
//
// Returns true when the caller may bind it — either because it was
// unclaimed, or because the caller already holds it and is re-binding,
// which happens on a GoldenLayout layout change. Returns false when
// another plugin owns it, and logs, because a refused claim always means
// two panes disagree about who handles something.
export const claim = function (channel, pluginName) {
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
export const ownerOf = function (channel) {
    return owners[channel] || "";
};
