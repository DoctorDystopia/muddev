"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/16/2026
Description: The tick performance feed. One reading of the server tick goes
             to each session that subscribes to CHANNEL_TICK_PERF, after
             each tick.

             The engine records the timing of each tick on its ndb
             (`_record_tick_timing`, and `tick_duration` at the end of
             `_tick`). This module reads those numbers and sends them. It
             measures nothing itself.

             WHY A PHASE HOOK. The engine is infrastructure, and it imports
             no feed. `register_phase_hook` is the seam that CLAUDE.md names
             for a bystander to the tick. This module attaches to PHASE_END,
             which fires after the engine records the duration. Thus, the
             cost of the send is not in the duration that the send reports.

             WHY SESSIONS, NOT OBSERVERS. Every other emitter sends to the
             sessions of one character. The tick is a fact of the server.
             A session at the connection screen can draw it too. Thus, the
             hook walks every connected session and sends to the ones that
             subscribe. A session that does not subscribe costs one set
             lookup. See emit.emit_to_sessions.

             WHY NOTHING HERE MAY RAISE. The hook runs inside `_tick`. The
             engine contains a hook that raises, but a hook that raises on
             every tick fills the log at 100 lines a minute. The send is in
             emit_to_sessions, which swallows and logs.
"""

from evennia.utils import logger

from . import constants as const
from .emit import emit_to_sessions
from .payloads import TickPerfPayload

# No import from systems/core/tick at module scope. The tick package imports
# this package. Its debug.py reads the message types. For the same reason,
# buffer.py keeps its engine import inside a function.


# ─── Module globals ─────────────────────────────────────────────────────────

# True after attach() registered the hook. One hook for each process.
_attached: bool = False


# ─── Private helper routines ─────────────────────────────────────────────────

def _subscribed_sessions() -> list:
    """Return every connected session that subscribes to the channel."""
    from evennia import SESSION_HANDLER

    from . import subscriptions

    found = []

    for session in SESSION_HANDLER.get_sessions():
        wants = subscriptions.is_subscribed(session, const.CHANNEL_TICK_PERF)

        if wants:
            found.append(session)

    return found


def _find_engine():
    """Return the tick engine of this process, or None before its first tick.

    The hook runs inside `_tick`, so the engine exists. The lookup goes
    through get_tick_engine, which caches the row for each process.
    """
    from systems.core.tick.engine import get_tick_engine

    return get_tick_engine()


# ─── Public routines ─────────────────────────────────────────────────────────

def build_payload(engine) -> TickPerfPayload:
    """
    Purpose: Read the timing of the last tick off the engine.

    Entry:
        engine - a BlackoutTickEngine that ticked at least one time.

    Exit/Returns:
        A TickPerfPayload. A missing number reads as zero, so a payload
        built before the first tick is valid and says nothing.

    Module Globals:
        None. TICK_SECONDS is read through tick_debug.late_threshold.

    Methodology:
        `late` comes from tick_debug.late_threshold, the rule that
        `tickdebug` uses. One owner for "what counts as late".

    Notes/References:
        The engine records `tick_interval` in `_record_tick_timing` and
        `tick_duration` at the end of `_tick`.

    Author: Nick Hobar
    Creation date: 10/16/2026
    """
    from systems.core.tick import debug as tick_debug

    interval = float(engine.ndb.tick_interval or 0.0)
    duration = float(engine.ndb.tick_duration or 0.0)
    threshold = tick_debug.late_threshold()

    return TickPerfPayload(
        tick=int(engine.ndb.tick_number or 0),
        interval=interval,
        duration=duration,
        handlers=engine.registered_count(),
        failing=engine.failing_count(),
        late=interval > threshold,
    )


def emit_tick_perf(engine=None) -> int:
    """
    Purpose: Send the reading of the last tick to every session that asked.

    Entry:
        engine - the tick engine, or None to look it up.

    Exit/Returns:
        The number of sessions that got the reading. Zero when no session
        subscribes, and then nothing is built. Never raises.

    Module Globals:
        None.

    Methodology:
        The subscriber walk comes first. A server with no graphical client
        pays one loop over its sessions and builds no payload.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/16/2026
    """
    try:
        sessions = _subscribed_sessions()

        if not sessions:
            return 0

        if engine is None:
            engine = _find_engine()

        payload = build_payload(engine)

        return emit_to_sessions(sessions, payload)
    except Exception:
        logger.log_trace()
        return 0


def on_tick_end() -> None:
    """The PHASE_END hook. Zero arguments, as every phase hook is."""
    emit_tick_perf()


def attach() -> None:
    """
    Attach `on_tick_end` to the tick, one time for each process. The engine
    import is here, not at module scope, so that the feed loads with no
    engine.
    """
    global _attached

    if _attached:
        return

    from systems.core.tick.engine import PHASE_END, register_phase_hook

    register_phase_hook(PHASE_END, on_tick_end)
    _attached = True


# The feed package imports this module for this side effect. See __init__.
attach()
