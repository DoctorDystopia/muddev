"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: The per-tick coalescing buffer — the "trailing send" mechanism
             constants.py's cap discussion asks for and says emit.py lacks.

What this fixes
---------------
The rate cap in emit.py DROPS. That is safe for a channel whose next message
tells the whole truth anyway, and wrong for every other kind, which is why the
cap table is such a short list guarded by such a long comment.

Coalescing is the alternative the comment names: hold a channel's messages for
the duration of a tick, keep only the newest, and send that one at the end.
Nothing is dropped -- the client gets one message per tick instead of several,
and the message it gets is the current truth rather than a stale one.

What is buffered, and what is not
---------------------------------
Two conditions, both required:

  1. The emission happened DURING a tick. Anything a player typed flushes
     immediately, because making `get sword` wait up to 600ms for its inventory
     update would trade a real problem for a worse one. The engine tells this
     module when a tick begins and ends; everything outside that window is
     untouched.
  2. The channel is in const.COALESCABLE_CHANNELS -- it carries whole
     snapshots, so keeping only the newest loses nothing. Event and delta
     channels (combat swings, entity add/remove, chunked map payloads) are
     never held, because coalescing them would lose information rather than
     compress it. See that constant for the full argument.

A future experiment
-------------------
Buffering EVERY emission -- including the ones a command produced -- would be
truer to OSRS, which builds one update block per player per tick and flushes it
at the end of the loop. It would give a graphical client strictly coherent
per-tick snapshots to interpolate across, which is worth something to the 3D
webclient specifically. The cost is up to one tick of latency on every
command-driven update, paid by telnet players who gain nothing from it. That
trade is worth measuring rather than assuming; this module is deliberately
shaped so the change would be to _should_hold, not to its callers.
"""

from evennia.utils import logger

from . import constants as const

# ─── Module globals ─────────────────────────────────────────────────────────

# True only between begin_tick and flush. Module state rather than engine ndb
# because emit() is called from everywhere and must answer "am I inside a
# tick?" without holding a reference to the engine.
_holding = False

# (observer id, channel) -> (observer, payload). Insertion-ordered, so a flush
# sends channels in the order they were first written this tick.
_pending: dict = {}


# ─── Private helper routines ────────────────────────────────────────────────

def _should_hold(payload) -> bool:
    """
    Purpose: Decide whether this payload waits for the end of the tick.

    Entry:
        payload is a payloads._Payload subclass instance.

    Exit/Returns:
        True to hold, False to send now.

    Module Globals:
        _holding read. const.COALESCABLE_CHANNELS read.

    Methodology:
        Both conditions in the module header, in the cheap order: the tick
        flag is a bare boolean and rules out every command-driven emission
        before the channel is even looked at.

    Notes/References:
        The single place to change if full per-tick buffering is ever tried.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    if not _holding:
        return False

    coalescable = payload.channel in const.COALESCABLE_CHANNELS

    return coalescable


def _key_for(obj, payload):
    """Return the coalescing key: one entry per observer per channel."""
    return (obj.id, payload.channel)


# ─── Public routines ────────────────────────────────────────────────────────

def begin_tick() -> None:
    """
    Purpose: Start holding coalescable emissions. Called by the tick engine at
             the top of a tick.

    Entry:
        No conditions. Safe to call when already holding.

    Exit/Returns:
        No return value.

    Module Globals:
        _holding written. _pending read.

    Methodology:
        Idempotent, and does not touch _pending -- which flush leaves empty
        anyway. Calling it twice without an intervening flush is harmless.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    global _holding

    _holding = True


def is_holding() -> bool:
    """Return True while a tick is in progress. For tests and diagnostics."""
    return _holding


def pending_count() -> int:
    """Return how many coalesced payloads are waiting to be sent."""
    return len(_pending)


def hold(obj, payload) -> bool:
    """
    Purpose: Take custody of a payload if it should be coalesced.

    Entry:
        obj is the observer. payload is a payloads._Payload subclass instance.

    Exit/Returns:
        True if this module has taken responsibility for sending it, in which
        case the caller must NOT send. False to send immediately.

    Module Globals:
        _pending written.

    Methodology:
        Last write wins for a given observer and channel, which is the whole
        point: three inventory snapshots produced by one tick's worth of
        gathering collapse to the one that is actually true at the end of it.

    Notes/References:
        Never raises. emit() calls this on a gameplay path and the module
        contract there is that a cosmetic side-channel cannot break a swing.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    try:
        should = _should_hold(payload)

        if not should:
            return False

        key = _key_for(obj, payload)
        _pending[key] = (obj, payload)

        return True
    except Exception:
        logger.log_trace()
        return False


def flush() -> int:
    """
    Purpose: Send every held payload and stop holding. Called by the tick
             engine at the end of a tick.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the number of sessions reached across all payloads.

    Module Globals:
        _holding written. _pending read and written.

    Methodology:
        Sends with force=True, bypassing the wall-clock rate cap. One message
        per channel per tick is already a stronger and simpler guarantee than
        the cap -- and applying the cap here would reintroduce the dropping
        behaviour this module exists to replace.

        _holding is cleared FIRST so the emits below take the immediate path
        rather than re-entering the buffer they are draining.

        _pending is emptied unconditionally. An entry whose send fails is
        NOT retried: the next tick that touches the same observer and channel
        produces a fresher snapshot anyway, and retrying stale ones forever
        would let a permanently-failing observer accumulate them.

        An observer deleted since its payload was held is skipped, since
        nothing will ever deliver to it.

    Notes/References:
        Failures are contained per payload: one bad observer must not strand
        everybody else's update.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    global _holding

    _holding = False

    if not _pending:
        return 0

    from . import emit as emit_module

    draining = list(_pending.values())
    _pending.clear()

    sent = 0

    for obj, payload in draining:
        try:
            if getattr(obj, "pk", None) is None:
                continue

            reached = emit_module.emit(obj, payload, force=True)
            sent += reached
        except Exception:
            logger.log_trace()

    return sent


def reset() -> None:
    """Drop all held state. For tests, and for a clean start after a reload."""
    global _holding

    _holding = False
    _pending.clear()


# ─── Registration ───────────────────────────────────────────────────────────
# Attached at import. systems/statefeed/__init__.py imports this module, and
# statefeed itself is imported by combat well before the first tick, so the
# hooks are always in place by the time the engine runs.
#
# Imported lazily inside the function for the usual reason: the engine must not
# depend on a game system, and this file is the one that knows the dependency
# exists.

def _register_phase_hooks() -> None:
    """Bracket every tick with begin_tick / flush."""
    from systems.tick.engine import PHASE_FEED, PHASE_START, register_phase_hook

    register_phase_hook(PHASE_START, begin_tick)
    register_phase_hook(PHASE_FEED, flush)


_register_phase_hooks()
