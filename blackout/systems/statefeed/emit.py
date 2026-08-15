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

def emit(obj, payload, force: bool = False) -> int:
    """
    Purpose: Send one payload to one observer's subscribed sessions.

    Entry:
        obj     - the observer. Any object; one with no sessions (an NPC) is a
                  supported and common case and costs one getattr.
        payload - a payloads._Payload subclass instance.
        force   - True to bypass the channel's rate cap. Reserved for resync,
                  where a dropped message would leave a client permanently
                  stale rather than merely a beat behind.

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
        now = time.monotonic()
        sessions = _eligible_sessions(obj, channel, now, force)

        if not sessions:
            return 0

        body = payload.to_dict()
        obj.msg(session=sessions, **{channel: body})

        return len(sessions)
    except Exception:
        logger.log_trace()
        return 0


def emit_to_room(room, payload, exclude=()) -> int:
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

    for occupant in occupants:
        if occupant in exclude:
            continue

        reached = emit(occupant, payload)
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

    Notes/References:
        This broadcast is WIDER than the text channel, which is exactly what
        raising STATEFEED_ENTITY_RADIUS above 0 means and why that constant
        documents itself as a balance decision rather than a rendering one.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    sent = 0

    for room in rooms:
        reached = emit_to_room(room, payload, exclude=exclude)
        sent += reached

    return sent
