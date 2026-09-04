"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: The one way a payload reaches a client.

             Everything routes through emit() so that the three rules that make
             this feed safe live in exactly one place:

               1. NOTHING HERE MAY RAISE. Every call site is a gameplay path --
                  a swing landing, a player walking through a door. A cosmetic
                  side-channel must never be able to break a fight or a move,
                  so the whole send is wrapped and a failure is logged and
                  swallowed. This mirrors the same decision in
                  typeclasses/rooms.py, where a failed map overlay falls back
                  rather than breaking `look`.
               2. Non-subscribed sessions cost nothing.
               3. A channel is rate-capped per session, not globally.

             No protocol work is involved in any of this. Any non-reserved
             kwarg to msg() becomes an Evennia outputfunc; the websocket
             protocol's send_default JSON-dumps unknown outputfuncs verbatim as
             [cmdname, [args], {kwargs}], and telnet clients get the same tuple
             re-encoded as GMCP or MSDP. The pipe already existed.
"""

import time

from evennia.utils import logger

from . import buffer
from . import constants as const
from . import subscriptions


# ─── Private helper routines ─────────────────────────────────────────────────

def _rate_state(session) -> dict:
    """Return the session's {channel: last_send_time} map, creating it once."""
    stored = getattr(session.ndb, const.RATE_STATE_ATTR, None)

    if stored is None:
        stored = {}
        setattr(session.ndb, const.RATE_STATE_ATTR, stored)

    return stored


def _passes_rate_cap(session, channel: str, now: float) -> bool:
    """
    Purpose: Decide whether this channel may send to this session right now,
    recording the send time when it may.

    Entry:
        session - a ServerSession.
        channel - one of the constants.CHANNEL_* names.
        now     - a time.monotonic() reading, taken once per emit so every
                  session in a room broadcast is judged against the same
                  instant.

    Exit/Returns:
        True if the send may proceed. Records `now` as the channel's last send
        time as a side effect, so a caller must not call this speculatively.

    Module Globals:
        const.CHANNEL_MIN_INTERVAL_SECONDS and
        const.DEFAULT_MIN_INTERVAL_SECONDS read.

    Methodology:
        monotonic rather than wall time: a clock adjustment mid-session must
        not be able to stall a channel for hours or open a flood.

        Channels with no configured interval fall through with zero cost --
        combat is deliberately uncapped, because at a 0.6s tick with a 4-tick
        weapon cycle it is already self-limiting and dropping a swing would
        desync the client's HP readout from the text log.

    Notes/References:
        Aardwolf caps its group channel at one send per second for the same
        reason this exists.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    interval = const.CHANNEL_MIN_INTERVAL_SECONDS.get(
        channel, const.DEFAULT_MIN_INTERVAL_SECONDS
    )

    if interval <= 0:
        return True

    state = _rate_state(session)
    last_sent = state.get(channel)

    if last_sent is not None and (now - last_sent) < interval:
        return False

    state[channel] = now

    return True


def _could_listen(obj) -> bool:
    """
    Purpose: Cheap "could this object possibly have a session" test, used to
             keep a room broadcast from asking every rock on the floor.

    Entry:
        obj - any object sitting in a room.

    Exit/Returns:
        True when the object might have a session. False is a promise that it
        has none.

    Module Globals:
        None.

    Methodology:
        Reads `db_sessid`, the raw column on the row that is already loaded,
        rather than going through the `sessions` handler. That handler is a
        lazy_property whose constructor splits the same column and then tests
        every id in it against the global session handler -- work worth doing
        for a player and pure waste for scenery.

        This is the same move the profiling harness measures under "Raw column
        obj.db_location_id" versus "FK traversal obj.location.id": read the
        fact off the row you already have.

        THE DIRECTION OF ERROR IS THE WHOLE ARGUMENT. The column can be stale
        in one direction only -- it may still name a session that has since
        gone away, because ObjectSessionHandler prunes those lazily when it is
        next built. A stale-NON-EMPTY column costs one wasted emit() call,
        which then does the real subscription check and sends nothing. A
        stale-EMPTY column cannot happen: a session is recorded by writing this
        column, so empty means no session has ever been attached.

        So a False here is safe and a True is merely not yet a decision, which
        is exactly the asymmetry a fast pre-filter needs.

    Notes/References:
        PERF-0002 measured 1,242 emit() calls for two moves, the overwhelming
        majority of them on scenery. This is that number's fix.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    return bool(getattr(obj, "db_sessid", None))


def _eligible_sessions(obj, channel: str, now: float, force: bool) -> list:
    """Return the object's sessions that want `channel` and are not capped.

    `force` skips the rate cap without recording a send time, so a forced
    resync neither gets dropped by a cap nor starves the next ordinary send.
    """
    handler = getattr(obj, "sessions", None)

    if handler is None:
        return []

    eligible = []

    for session in handler.all():
        wants = subscriptions.is_subscribed(session, channel)

        if not wants:
            continue

        if force:
            eligible.append(session)
            continue

        allowed = _passes_rate_cap(session, channel, now)

        if allowed:
            eligible.append(session)

    return eligible


# ─── Public routines ─────────────────────────────────────────────────────────

def emit(obj, payload, force: bool = False, body=None) -> int:
    """
    Purpose: Send one payload to one observer's subscribed sessions.

    Entry:
        obj     - the observer. Any object; one with no sessions (an NPC) is a
                  supported and common case and costs one getattr.
        payload - a payloads._Payload subclass instance.
        force   - True to bypass the channel's rate cap. Reserved for resync,
                  where a dropped message would leave a client permanently
                  stale rather than merely a beat behind.
        body    - a payload body already rendered by payload.to_dict(), for a
                  broadcast that is sending the SAME body to many observers.
                  None means render it here, which is the single-observer case
                  and the one every direct caller wants.

    Exit/Returns:
        Returns the number of sessions the payload was sent to. Zero is the
        normal result on a server with no graphical clients connected.

    Module Globals:
        const.RESERVED_CHANNEL_NAME read.

    Methodology:
        The whole body is wrapped. See the module docstring: every call site is
        a gameplay path and this must never be the reason a swing or a move
        fails.

        The payload is sent as the outputfunc's KWARGS -- msg(room_info={...})
        -- because clean_senddata normalises a bare dict to [[], {kwargs}],
        which is the shape a client can read by name rather than by position.

        `body` exists so a room broadcast renders one dict instead of one per
        observer; every observer of a broadcast is sent a byte-identical body,
        and to_dict was being called once each. Sharing the dict is safe
        because nothing downstream mutates it: clean_senddata's _validate
        BUILDS a new structure rather than editing the one it walks, and the
        `options` key msg() injects goes into the outer kwargs mapping, which
        is constructed fresh on the line below.

    Notes/References:
        The reserved-name guard is not paranoia: Evennia's websocket
        send_default silently DROPS an outputfunc named "options", and
        clean_senddata injects a key of that name into every outputfunc's
        kwargs. A channel named "options" would fail invisibly.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    channel = payload.channel

    if not channel or channel == const.RESERVED_CHANNEL_NAME:
        logger.log_err(f"statefeed: refusing to emit on channel {channel!r}.")
        return 0

    try:
        # Inside a tick, a coalescable channel is held and sent once at the
        # end -- the trailing send this module's rate cap could not offer. The
        # buffer's own flush calls back in with force=True and the holding
        # flag already cleared, so this cannot recurse.
        held = buffer.hold(obj, payload)

        if held:
            return 0

        now = time.monotonic()
        sessions = _eligible_sessions(obj, channel, now, force)

        if not sessions:
            return 0

        if body is None:
            body = payload.to_dict()

        obj.msg(session=sessions, **{channel: body})

        return len(sessions)
    except Exception:
        logger.log_trace()
        return 0


def emit_to_room(room, payload, exclude=(), body=None) -> int:
    """
    Purpose: Send one payload to every subscribed observer standing in a room.

    Entry:
        room    - a room object, or None (a no-op).
        payload - a payloads._Payload subclass instance.
        exclude - objects to skip, matching the `exclude` argument the text
                  broadcast beside this call site already uses.

    Exit/Returns:
        Returns the total number of sessions reached.

    Module Globals:
        None.

    Methodology:
        Iterates room.contents rather than taking a session list, so this
        mirrors msg_contents exactly: the feed reaches precisely the people the
        text reaches, and no one else. That equivalence is the whole reason the
        feed leaks no information the text channel does not already leak.

        _could_listen NARROWS HOW the occupants are found, never WHICH of them
        hear it. That distinction is the one thing to preserve if this loop is
        ever touched again: the filter is a promise about objects that have no
        session at all, and every object it lets through still goes through
        emit() and still faces the real subscription check and the rate cap.
        A room's contents are mostly scenery -- PERF-0002 measured 1,242
        emit() calls for two moves, nearly all on rocks.

        The body is rendered ONCE, here, and handed to every emit(). Each
        observer of a room broadcast receives the same bytes, and payload
        .to_dict() was being called once per observer to produce them.

    Notes/References:
        This is the room-sized broadcast, matching the text channel exactly.
        emit_to_area is the radius-sized one, used by the channels that report
        entities the observer is not standing with.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    if room is None:
        return 0

    sent = 0

    try:
        occupants = room.contents
    except Exception:
        logger.log_trace()
        return 0

    if body is None:
        try:
            body = payload.to_dict()
        except Exception:
            logger.log_trace()
            return 0

    for occupant in occupants:
        if occupant in exclude:
            continue

        if not _could_listen(occupant):
            continue

        reached = emit(occupant, payload, body=body)
        sent += reached

    return sent


def emit_to_area(rooms, payload, exclude=()) -> int:
    """
    Purpose: Send one payload to every subscribed observer in a group of rooms.

    Entry:
        rooms   - room objects, typically from targeting.rooms_within_radius.
        payload - a payloads._Payload subclass instance.
        exclude - objects to skip.

    Exit/Returns:
        Returns the total number of sessions reached.

    Module Globals:
        None.

    Methodology:
        The delta half of the radius contract. Once emit_room_contents reports
        entities from a neighbourhood rather than one room, the add/remove
        deltas have to travel the same distance or the two disagree: an
        observer would be sent the full list including an NPC three tiles away,
        then never hear that it died, and would render a corpse standing there
        until they walked far enough to trigger a fresh list.

        Reuses emit_to_room per room rather than flattening the occupant lists,
        so there is one implementation of "who in a room hears this".

        The body is rendered once for the WHOLE area and threaded down, so a
        radius-10 broadcast over 441 rooms renders one dict rather than one per
        reached observer. emit_to_room would otherwise render its own per room,
        which for a neighbourhood-sized broadcast is the same waste one level
        up.

    Notes/References:
        This broadcast is WIDER than the text channel, which is exactly what
        raising STATEFEED_ENTITY_RADIUS above 0 means and why that constant
        documents itself as a balance decision rather than a rendering one.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    sent = 0

    try:
        body = payload.to_dict()
    except Exception:
        logger.log_trace()
        return 0

    for room in rooms:
        reached = emit_to_room(room, payload, exclude=exclude, body=body)
        sent += reached

    return sent
