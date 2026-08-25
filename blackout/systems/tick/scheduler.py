"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: TickScheduler — deferred work keyed on absolute tick number, so a
             system can say "in 100 ticks" without owning a timer.

Why buckets and not a heap
--------------------------
The usual answer for deferred work is a binary min-heap ordered on expiry, at
O(log N) per insert. That is the right structure when deadlines are continuous
floats. Blackout's are not: the tick is discrete, so every deadline is an
INTEGER tick number, and a dict keyed on that integer is O(1) to insert, O(1)
to fire, needs no ordering at all, and is about thirty lines.

This is the degenerate case of a hashed timing wheel, minus the wheel: the
bucket space is sparse and unbounded rather than a fixed ring, so a deadline
144,000 ticks out (a daily shop restock) is one dict entry rather than a
cascade through hierarchical wheels. Nothing here needs the wheel's bounded
memory, and CPython's interpreter overhead dwarfs the difference between O(1)
and O(log N) at the handful-to-hundreds of pending entries this will hold.

Exact-bucket popping is sound because ``tick_number`` is a COUNTER, not a
clock: BlackoutTickEngine._tick increments it by exactly one per pass, so a
tick number is never skipped even when real time drifts. A slow tick makes the
wall-clock gap longer; it does not lose a bucket.

What this is NOT for
--------------------
Anything whose deadline must survive the server being DOWN. Ticks do not
advance while the process is stopped, and this scheduler lives on ndb -- it is
wiped by a reload and its users re-arm themselves at boot. A mechanic that has
to fire "30 seconds after the NPC died" including across a two-hour outage
needs an absolute wall-clock deadline instead; systems/spawning/respawn.py
explains that requirement and deliberately keeps its own queue.

The rule of thumb: if the mechanic's meaning is "in N ticks" (a swing cooldown,
an aura pulse, a buff duration, a paced craft), it belongs here. If its meaning
is "at this moment in real time" (a respawn window, a daily restock), it does
not.
"""

from evennia.utils import logger

from . import constants as const

# ─── Public constant definitions ────────────────────────────────────────────

# Handle returned for a call that could not be scheduled. Never valid input to
# cancel(), which ignores it.
NO_HANDLE: int = 0


# ─── Private constant definitions ───────────────────────────────────────────

# The first handle handed out. Starting above NO_HANDLE keeps "did I get a
# handle?" a truthiness test.
_FIRST_HANDLE: int = 1

# Smallest delay schedule_in accepts. Zero would mean "this tick", which is
# already in progress when a callback schedules more work, so the floor is the
# next one.
_MINIMUM_DELAY_TICKS: int = 1


# ─── Public routines ────────────────────────────────────────────────────────

def seconds_to_ticks(seconds: float) -> int:
    """
    Purpose: Convert a duration in seconds to whole ticks.

    Entry:
        seconds is a non-negative duration.

    Exit/Returns:
        Returns the number of ticks, rounded to nearest and never below
        _MINIMUM_DELAY_TICKS for a positive input.

    Module Globals:
        _MINIMUM_DELAY_TICKS read.
        const.TICK_SECONDS read.

    Methodology:
        Rounds rather than truncates so a 2-second interval becomes 3 ticks
        (1.8s) rather than 3.33 truncated to 3 by accident -- the caller can
        see the quantisation either way, but rounding keeps the error
        symmetric.

        Exists so callers can keep expressing design intent in seconds (the
        Obsidian vault states regen as "1 HP per minute") while the engine
        works in ticks.

    Notes/References:
        A duration that is not a whole number of ticks is quantised, which is
        the point: everything on the tick shares one rhythm.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    if seconds <= 0:
        return _MINIMUM_DELAY_TICKS

    raw = seconds / const.TICK_SECONDS
    ticks = int(round(raw))

    return max(_MINIMUM_DELAY_TICKS, ticks)


# ─── The scheduler ──────────────────────────────────────────────────────────

class TickScheduler:
    """Callbacks filed under the absolute tick number they are due on.

    Owned by BlackoutTickEngine and advanced once per tick. Not persistent:
    see this module's header for what that rules out.
    """

    def __init__(self) -> None:
        # due tick -> [handle, ...], insertion-ordered within a tick so two
        # callbacks due together fire in the order they were scheduled.
        self._buckets: dict = {}

        # handle -> callback, for cancellation and for firing.
        self._entries: dict = {}

        self._next_handle = _FIRST_HANDLE

    # ── scheduling ───────────────────────────────────────────────────────

    def schedule_at(self, due_tick: int, callback) -> int:
        """
        Purpose: Run `callback` on an absolute tick number.

        Entry:
            due_tick is the tick to fire on. callback takes no arguments.

        Exit/Returns:
            Returns a handle usable with cancel(), or NO_HANDLE if callback
            was None.

        Module Globals:
            NO_HANDLE read.

        Methodology:
            A due_tick already in the past cannot fire, because run_due only
            ever asks for the tick it is currently on. Callers are not
            expected to compute past deadlines, so this does not silently
            clamp -- schedule_in is the routine that does the arithmetic.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/18/2026
        """
        if callback is None:
            return NO_HANDLE

        handle = self._next_handle
        self._next_handle += 1

        self._entries[handle] = callback
        self._buckets.setdefault(due_tick, []).append(handle)

        return handle

    def schedule_in(self, delay_ticks: int, callback, now: int) -> int:
        """
        Purpose: Run `callback` a number of ticks from now.

        Entry:
            delay_ticks is how many ticks to wait; values below
            _MINIMUM_DELAY_TICKS are raised to it.
            now is the engine's current tick number.

        Exit/Returns:
            Returns a handle usable with cancel().

        Module Globals:
            _MINIMUM_DELAY_TICKS read.

        Methodology:
            The floor matters: a callback that schedules more work runs DURING
            the tick whose bucket has already been popped, so scheduling
            "zero ticks from now" would file into a bucket that will never be
            examined again.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/18/2026
        """
        delay = max(_MINIMUM_DELAY_TICKS, delay_ticks)
        due_tick = now + delay

        handle = self.schedule_at(due_tick, callback)

        return handle

    def cancel(self, handle: int) -> bool:
        """
        Purpose: Stop a scheduled callback from firing.

        Entry:
            handle came from schedule_at or schedule_in.

        Exit/Returns:
            Returns True if a pending call was cancelled, False if the handle
            was unknown, already fired, or NO_HANDLE.

        Module Globals:
            None

        Methodology:
            Tombstoned rather than unfiled: the entry is dropped from
            `_entries` and its bucket keeps a handle that resolves to nothing.
            run_due skips those. Removing it from the bucket list instead
            would be an O(n) scan for no benefit at these sizes.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/18/2026
        """
        existed = handle in self._entries

        self._entries.pop(handle, None)

        return existed

    # ── firing ───────────────────────────────────────────────────────────

    def run_due(self, now: int) -> int:
        """
        Purpose: Fire everything due on tick `now`.

        Entry:
            now is the engine's current tick number.

        Exit/Returns:
            Returns how many callbacks actually ran.

        Module Globals:
            None

        Methodology:
            Pops the bucket for exactly this tick -- see the module header for
            why exact matching is sound when the tick is a counter rather than
            a clock. Each callback is isolated: one raising must not stop the
            others, and must not escape into _tick, which would errback the
            LoopingCall and stop the tick for the whole server.

        Notes/References:
            A callback may schedule more work while running. It lands in a
            future bucket, never this one, because schedule_in floors its
            delay at one tick.

        Author: Nick Hobar
        Creation date: 08/18/2026
        """
        handles = self._buckets.pop(now, None)

        if not handles:
            return 0

        fired = 0

        for handle in handles:
            callback = self._entries.pop(handle, None)

            if callback is None:
                # Cancelled since it was scheduled.
                continue

            try:
                callback()
                fired += 1
            except Exception:
                logger.log_trace()

        return fired

    # ── introspection ────────────────────────────────────────────────────

    def pending_count(self) -> int:
        """Return how many callbacks are scheduled and not yet fired."""
        return len(self._entries)

    def next_due_tick(self):
        """Return the earliest tick holding work, or None when idle.

        For diagnostics only -- run_due never needs it, because it asks for
        the tick it is on rather than searching for the nearest deadline.
        """
        live = [tick for tick, handles in self._buckets.items()
                if any(h in self._entries for h in handles)]

        if not live:
            return None

        return min(live)
