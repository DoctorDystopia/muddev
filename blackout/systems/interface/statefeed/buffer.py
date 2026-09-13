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

Stale marks: coalescing the BUILD, not only the send
----------------------------------------------------
Holding a payload collapses several sends into one, but every one of them was
still BUILT. For the cheap channels that costs nothing worth naming. For
char_summary and char_skills it is the whole cost: the dossier reads every
handler on the character and lists the bank, the roster walks four unlock
registries per skill, and either one rebuilt on every HP change or XP award
would be built several times a tick to have all but the last thrown away.

So those snapshots are not emitted where a fact changes. They are MARKED STALE
there, and built once, after the last change:

  - Inside a tick, flush() builds every stale snapshot before it sends
    anything, while the window is still open, so what the builds emit is held
    beside everything else and leaves in the same flush.
  - Outside a tick, the first mark schedules a drain for the end of the current
    reactor turn. A command runs to completion inside one turn, so `wear all`
    or a twenty-item `get all` rebuilds the dossier once rather than twenty
    times, and the player sees it no later than the text.

A builder is the channel's own emitter (events.emit_summary), handed in rather
than imported, so this module still depends on nothing above it.

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

# (observer id, builder) -> (observer, builder). Insertion-ordered, so a drain
# builds snapshots in the order they went stale.
_stale: dict = {}

# The reactor call that will drain _stale outside a tick, or None when none is
# scheduled. Kept so a tick that drains first can cancel it.
_drain_call = None


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


def _stale_key(obj, builder):
    """Return the stale-mark key: one entry per observer per snapshot."""
    return (getattr(obj, "id", None), builder)


def _schedule_drain() -> None:
    """
    Purpose: Make sure a drain runs at the end of this reactor turn.

    Entry:
        No conditions. Safe to call when a drain is already scheduled.

    Exit/Returns:
        No return value.

    Module Globals:
        _drain_call read and written.

    Methodology:
        callLater(0) rather than a drain here and now, because the caller is
        in the middle of changing something -- an item half-way through a
        move, the first of several hits -- and the whole point of a mark is to
        build after the LAST change, not after the first.

        The reactor is imported inside the routine. Importing
        twisted.internet.reactor installs the default reactor if none is
        installed yet, and this module is imported by the typeclasses at
        startup, before the server has necessarily chosen its own.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    global _drain_call

    if _drain_call is not None and _drain_call.active():
        return

    from twisted.internet import reactor

    _drain_call = reactor.callLater(0, drain_stale)


def _cancel_drain_call() -> None:
    """Forget the scheduled drain, cancelling it if it has not run yet.

    A call that is running right now is no longer active(), so a drain the
    reactor started does not try to cancel itself.
    """
    global _drain_call

    scheduled = _drain_call
    _drain_call = None

    if scheduled is not None and scheduled.active():
        scheduled.cancel()


def _build_one(obj, builder) -> int:
    """Run one builder. Returns 1 if it ran, 0 if skipped or it raised.

    An observer deleted since it was marked is skipped, since nothing will ever
    deliver to it; one builder raising costs that one snapshot, not everybody
    else's.
    """
    if getattr(obj, "pk", None) is None:
        return 0

    try:
        builder(obj)
    except Exception:
        logger.log_trace()
        return 0

    return 1


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


def stale_count() -> int:
    """Return how many snapshots are marked stale and not yet rebuilt."""
    return len(_stale)


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


def mark_stale(obj, builder, delay: float = 0.0) -> None:
    """
    Purpose: Record that one observer's snapshot must be rebuilt, and make sure
             something will rebuild it.

    Entry:
        obj     - the observer whose snapshot is out of date.
        builder - a callable taking the observer and emitting its snapshot; in
                  practice one of the events.emit_* routines.
        delay   - seconds from now at which the snapshot goes stale, for a fact
                  that changes on a clock rather than on an event (a cure
                  coming due). 0 means now.

    Exit/Returns:
        No return value. Never raises.

    Module Globals:
        _stale written. _holding read.

    Methodology:
        Keyed by observer AND builder, so marking the dossier stale three times
        collapses to one rebuild while the dossier and the roster stay two.

        Inside a tick nothing is scheduled: flush() is already certain to run.
        Outside one, a drain is scheduled for the end of the reactor turn
        unless one already is.

        A delayed mark is a reactor call back into this same routine, so when
        it lands it coalesces with whatever else went stale at that moment
        rather than building on its own.

    Notes/References:
        A delayed mark is lost on a reload. The resync every session gets after
        one sends each snapshot whole, so nothing is left wrong -- but a
        deadline still in the future then waits for the next change to mark
        its snapshot rather than for its own moment.

        Never raises, for the reason hold() does not.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    try:
        if delay > 0:
            from twisted.internet import reactor

            reactor.callLater(delay, mark_stale, obj, builder)
            return

        _stale[_stale_key(obj, builder)] = (obj, builder)

        if not _holding:
            _schedule_drain()
    except Exception:
        logger.log_trace()


def discard_stale(obj, builder) -> None:
    """Drop a mark that a build happening right now already satisfies.

    Called by an emitter that is building its snapshot on the spot -- the
    dossier opened from `score`, a resync -- so a change marked a moment
    earlier does not buy a second, identical build at the drain.
    """
    _stale.pop(_stale_key(obj, builder), None)


def drain_stale() -> int:
    """
    Purpose: Build every stale snapshot now.

    Entry:
        No conditions. Safe with nothing stale.

    Exit/Returns:
        Returns how many builders ran.

    Module Globals:
        _stale read and written. const.STALE_DRAIN_MAX_PASSES read.

    Methodology:
        Cancels any scheduled drain first. This call is doing that drain's job,
        and a tick that got here before the reactor turn did must not leave a
        second drain behind to find nothing.

        PASSES rather than one sweep, because building one snapshot can make
        another stale -- emit_status marks the dossier, which repeats
        in_combat -- and a mark made during a drain belongs to the change being
        drained. Each pass takes its entries OUT before building them, so a
        builder that marks its own snapshot again waits for the next pass
        instead of looping forever inside this one.

        Marks still standing after const.STALE_DRAIN_MAX_PASSES are a cycle
        between builders. They are left for the next drain rather than spun on
        here, and the next drain is never far: the tick engine flushes every
        0.6s whether or not anything is fighting.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    _cancel_drain_call()

    built = 0

    for _pass in range(const.STALE_DRAIN_MAX_PASSES):
        if not _stale:
            break

        draining = list(_stale.values())
        _stale.clear()

        for obj, builder in draining:
            built += _build_one(obj, builder)

    return built


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
        Stale snapshots are built FIRST, while _holding is still set, so what
        they emit is held beside this tick's other payloads and leaves in this
        same flush -- a dossier describing the tick's HP arrives with the
        vitals reading that carried it, not a reactor turn later.

        Sends with force=True, bypassing the wall-clock rate cap. One message
        per channel per tick is already a stronger and simpler guarantee than
        the cap -- and applying the cap here would reintroduce the dropping
        behaviour this module exists to replace.

        _holding is cleared before the payloads drain, so the emits below take
        the immediate path rather than re-entering the buffer they are
        draining.

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

    drain_stale()

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
    _stale.clear()
    _cancel_drain_call()


# ─── Registration ───────────────────────────────────────────────────────────
# Attached at import. systems/interface/statefeed/__init__.py imports this module, and
# statefeed itself is imported by combat well before the first tick, so the
# hooks are always in place by the time the engine runs.
#
# Imported lazily inside the function for the usual reason: the engine must not
# depend on a game system, and this file is the one that knows the dependency
# exists.

def _register_phase_hooks() -> None:
    """Bracket every tick with begin_tick / flush."""
    from systems.core.tick.engine import PHASE_FEED, PHASE_START, register_phase_hook

    register_phase_hook(PHASE_START, begin_tick)
    register_phase_hook(PHASE_FEED, flush)


_register_phase_hooks()
