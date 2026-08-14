"""
Input functions

Input functions are always called from the client (they handle server
input, hence the name).

This module is loaded by being included in the
`settings.INPUT_FUNC_MODULES` tuple.

All *global functions* included in this module are considered
input-handler functions and can be called by the client to handle
input.

An input function must have the following call signature:

    cmdname(session, *args, **kwargs)

Where session will be the active session and *args, **kwargs are extra
incoming arguments and keyword properties.

A special command is the "default" command, which is will be called
when no other cmdname matches. It also receives the non-found cmdname
as argument.

    default(session, cmdname, *args, **kwargs)

────────────────────────────────────────────────────────────────────────────

Blackout adds the state-feed subscription handshake here. A graphical client
opts in to the structured channels it wants; a telnet client never calls these
and never pays for the feed.

Imports in this module are safe: Evennia's callables_from_module only treats
callables DEFINED here as inputfuncs, so an imported helper cannot accidentally
become client-callable.

Wire format, over the websocket:

    ["blackout_subscribe",   [], {"channels": "all"}]
    ["blackout_subscribe",   [], {"channels": ["room_info", "blackout_combat"]}]
    ["blackout_unsubscribe", [], {"channels": "all"}]

The server replies on "blackout_subscribed" with the set that was actually
accepted, so a client can tell a typo from a channel that is merely quiet.

Author: Nick Hobar
Creation date: 08/07/2026
"""

from evennia.utils import logger

from systems.statefeed import constants as feed_const
from systems.statefeed import resync, subscriptions


# ─── Private helper routines ─────────────────────────────────────────────────

def _requested_channels(args, kwargs):
    """Pull the channel argument out of either calling convention.

    A client may send channels as the `channels` kwarg or as the first
    positional argument. Accepting both costs one branch and removes the most
    likely reason a hand-written client's first subscribe silently does
    nothing.
    """
    if "channels" in kwargs:
        return kwargs["channels"]

    if args:
        return args[0]

    return feed_const.SUBSCRIBE_ALL


# ─── Public routines (inputfuncs) ────────────────────────────────────────────

def blackout_subscribe(session, *args, **kwargs):
    """
    Purpose: Subscribe a client session to structured state-feed channels and
    immediately send it a full snapshot of the world.

    Entry:
        session - the calling ServerSession.
        args    - optionally the channel list as the first positional value.
        kwargs  - optionally {"channels": [...]} or {"channels": "all"}.
                  Omitting both subscribes to every channel.

    Exit/Returns:
        Returns nothing. Sends "blackout_subscribed" with the accepted channel
        set, followed by the full state snapshot.

    Module Globals:
        feed_const.SUBSCRIBE_ALL read.

    Methodology:
        Subscribe THEN snapshot, in that order: the snapshot is delivered
        through the ordinary emit path, which filters on the subscription that
        must therefore already exist.

        Wrapped, because an exception raised inside an inputfunc is swallowed
        and logged by Evennia without the client learning anything -- catching
        it here means a broken subscribe at least leaves a trace naming this
        function.

    Notes/References:
        Unknown channel names are dropped rather than accepted; the
        acknowledgement is what makes that visible to the client.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    try:
        requested = _requested_channels(args, kwargs)
        subscriptions.subscribe(session, requested)

        subscriptions.announce(session)
        resync.send_full_state(session.puppet)
    except Exception:
        logger.log_trace()


def blackout_unsubscribe(session, *args, **kwargs):
    """
    Purpose: Stop sending a client one or more state-feed channels.

    Entry:
        session - the calling ServerSession.
        args    - optionally the channel list as the first positional value.
        kwargs  - optionally {"channels": [...]}. Omitting both unsubscribes
                  from everything.

    Exit/Returns:
        Returns nothing. Sends "blackout_subscribed" with whatever remains.

    Module Globals:
        feed_const.SUBSCRIBE_ALL read.

    Methodology:
        Acknowledges with the REMAINING set rather than the removed one, so a
        client only ever has to track a single authoritative value from the
        server regardless of which call it made.

    Notes/References:
        A disconnect clears subscriptions on its own -- they live on Session
        ndb. This exists for a client that wants to quiet a channel while
        staying connected.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    try:
        requested = _requested_channels(args, kwargs)
        subscriptions.unsubscribe(session, requested)

        subscriptions.announce(session)
    except Exception:
        logger.log_trace()


def blackout_resync(session, *args, **kwargs):
    """
    Purpose: Re-send the full state snapshot on client request.

    Entry:
        session - the calling ServerSession. Must already be subscribed;
                  a snapshot is filtered by subscription like anything else.

    Exit/Returns:
        Returns nothing. Sends the full snapshot.

    Module Globals:
        None.

    Methodology:
        The client-driven counterpart to the server-driven resync in
        ServerSession.at_sync. A client that has lost its place -- a dropped
        frame, a truncated chunk, a tab that slept -- can ask for the world
        again rather than reconnecting.

    Notes/References:
        Forced past the rate caps by send_full_state, so this cannot be used to
        bypass them for a channel: it sends one snapshot, not a stream.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    try:
        resync.send_full_state(session.puppet)
    except Exception:
        logger.log_trace()
