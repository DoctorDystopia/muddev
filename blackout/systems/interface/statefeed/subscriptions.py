"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: Who is listening to the state feed, and to what.

             The feed is opt-in per channel. That is not a nicety: every
             outputfunc sent to a session costs a clean_senddata validation
             pass, a pickle.dumps, and one AMP box, per session, and Evennia is
             a single-process Twisted server whose comfortable concurrency sits
             in the tens. A telnet player who will never render a mesh must pay
             nothing at all, and the check that guarantees that lives here.

             Subscriptions live on Session.ndb, deliberately. A subscription is
             meaningless across a disconnect, and Session ndb is cleared by a
             server reload anyway -- which is why the client re-subscribes on
             reconnect and why ServerSession.at_sync pushes a full resync.
"""

from . import constants as const


# ─── Private helper routines ─────────────────────────────────────────────────

def _normalise(channels) -> set:
    """Coerce a client's channel argument into a set of names.

    Accepts the SUBSCRIBE_ALL sentinel, a bare string, or any iterable. A
    client sending a single channel as a plain string is the common case and
    must not be iterated into characters.
    """
    if channels == const.SUBSCRIBE_ALL:
        return set(const.SUBSCRIBABLE_CHANNELS)

    if isinstance(channels, str):
        return {channels}

    if not channels:
        return set()

    names = set()

    for entry in channels:
        names.add(str(entry))

    return names


# ─── Public routines ─────────────────────────────────────────────────────────

def subscribe(session, channels) -> set:
    """
    Purpose: Add channels to a session's subscription set.

    Entry:
        session  - a ServerSession.
        channels - an iterable of channel-name strings, or the single string
                   constants.SUBSCRIBE_ALL to mean every known channel.

    Exit/Returns:
        Returns the session's full subscription set after the change. Names
        that are not in SUBSCRIBABLE_CHANNELS are ignored, not added.

    Module Globals:
        const.SUBSCRIBABLE_CHANNELS, const.SUBSCRIBE_ALL,
        const.SUBSCRIPTION_ATTR read.

    Methodology:
        Unknown names are dropped rather than accepted so that a typo in a
        client surfaces as "that channel never fires" at subscribe time, when
        the caller can still see the returned set, rather than as a silent
        no-op forever.

    Notes/References:
        The returned set is what the subscribe inputfunc echoes back to the
        client, so a client can confirm what it actually got.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    requested = _normalise(channels)
    current = subscribed_channels(session)
    accepted = requested & const.SUBSCRIBABLE_CHANNELS
    updated = current | accepted

    setattr(session.ndb, const.SUBSCRIPTION_ATTR, updated)

    return updated


def unsubscribe(session, channels) -> set:
    """
    Purpose: Remove channels from a session's subscription set.

    Entry:
        session  - a ServerSession.
        channels - an iterable of channel names, or constants.SUBSCRIBE_ALL to
                   clear every subscription.

    Exit/Returns:
        Returns the session's remaining subscription set.

    Module Globals:
        const.SUBSCRIPTION_ATTR read.

    Methodology:
        Difference rather than discard-in-a-loop, so an unknown name is a
        harmless no-op.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    requested = _normalise(channels)
    current = subscribed_channels(session)
    updated = current - requested

    setattr(session.ndb, const.SUBSCRIPTION_ATTR, updated)

    return updated


def subscribed_channels(session) -> set:
    """
    Purpose: Read a session's current subscription set.

    Entry:
        session - a ServerSession, or anything with an `ndb` holder.

    Exit/Returns:
        Returns a set of channel names. Empty set when the session has never
        subscribed, or when ndb was cleared by a reload.

    Module Globals:
        const.SUBSCRIPTION_ATTR read.

    Methodology:
        Returns a COPY. The caller in emit.py does set arithmetic on the
        result, and handing out the live object would let a read path mutate a
        session's subscriptions.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    holder = getattr(session, "ndb", None)

    if holder is None:
        return set()

    stored = getattr(holder, const.SUBSCRIPTION_ATTR, None)

    if not stored:
        return set()

    return set(stored)


def announce(session) -> None:
    """
    Purpose: Tell a client exactly what it is subscribed to right now.

    Entry:
        session - a ServerSession.

    Exit/Returns:
        Returns nothing. Sends the CHANNEL_SUBSCRIBED_ACK outputfunc carrying
        the full current set, which may legitimately be empty.

    Module Globals:
        const.CHANNEL_SUBSCRIBED_ACK read.

    Methodology:
        Always the WHOLE set, never a delta, so a client only ever tracks one
        authoritative value from the server no matter which call produced it.

        An empty set is a real answer and the load-bearing one: it is what a
        client is told at at_sync, and it means "I have forgotten you, ask
        again". That single message covers both ways a subscription goes
        missing -- a subscribe that raced the Portal-to-Server sync and was
        dropped, and a reload that wiped the ndb this set lives on.

    Notes/References:
        Sent from ServerSession.at_sync and from the subscribe/unsubscribe
        inputfuncs. Those are the only three moments the set can change.

        at_sync means this reaches EVERY session, telnet included, and that
        costs a telnet player nothing: telnet_oob.data_out writes only under a
        negotiated MSDP or GMCP, so a bare telnet client is sent no bytes at
        all and a Mudlet client gets a correct, harmless Blackout.Subscribed.

    Author: Nick Hobar
    Creation date: 08/11/2026
    """
    channels = subscribed_channels(session)
    ordered = sorted(channels)

    session.msg(**{const.CHANNEL_SUBSCRIBED_ACK: {"channels": ordered}})


def is_subscribed(session, channel: str) -> bool:
    """Return True if this session wants messages on `channel`."""
    channels = subscribed_channels(session)

    return channel in channels


def has_channel_subscribers(obj, channel: str) -> bool:
    """
    Purpose: Cheap "is anyone listening to THIS channel" test for an object's
    sessions.

    Entry:
        obj     - any object that may expose a `sessions` handler.
        channel - one of the constants.CHANNEL_* names.

    Exit/Returns:
        True if at least one of the object's sessions subscribes to `channel`.

    Module Globals:
        None.

    Methodology:
        Narrower than has_subscribers below, and needed for a different reason.
        has_subscribers answers "is it worth serialising anything at all";
        this answers "is it worth building THIS payload", which only matters
        for a payload expensive enough that building-then-discarding is a real
        cost. Today that is char_summary alone -- it reads every handler on the
        character and walks the XP curve once per skill.

        emit() re-checks per session on the way out. This is a pre-filter, not
        a replacement for that check.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    handler = getattr(obj, "sessions", None)

    if handler is None:
        return False

    for session in handler.all():
        wants = is_subscribed(session, channel)

        if wants:
            return True

    return False


def has_subscribers(obj) -> bool:
    """
    Purpose: Cheap "is anyone listening at all" test for an object's sessions.

    Entry:
        obj - any object that may expose a `sessions` handler.

    Exit/Returns:
        True if at least one of the object's sessions has any subscription.

    Module Globals:
        None.

    Methodology:
        Exists so a caller can skip building a payload entirely. Serialising a
        room's contents is a loop over contents with a tag read each; doing it
        for a player base that is entirely on telnet would be pure waste.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    handler = getattr(obj, "sessions", None)

    if handler is None:
        return False

    for session in handler.all():
        channels = subscribed_channels(session)

        if channels:
            return True

    return False
