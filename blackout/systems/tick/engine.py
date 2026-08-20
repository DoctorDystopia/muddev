"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/30/2026
Description: BlackoutTickEngine — the single server-wide 0.6s OSRS tick that
             advances every registered tickable handler and runs deferred work.

Why this exists
---------------
Evennia cannot drive a sub-second repeat on its own:

  * ``ScriptDB.db_interval`` is a Django ``IntegerField`` (evennia/scripts/models.py),
    so assigning 0.6 silently truncates to 0, and ``ScriptBase._start_task`` refuses
    to start a task when ``db_interval <= 0``.
  * ``TICKER_HANDLER._store_key`` (evennia/scripts/tickerhandler.py) raises
    ``RuntimeError`` outright for any interval below 1 second, so ``utils.repeat``
    is unavailable too.

So the real tick is a twisted ``LoopingCall`` (which happily takes a float), owned
by one global Script. The Script's own Evennia ``interval`` is an integer watchdog
that only re-arms the LoopingCall if it ever dies; it is NOT the combat tick.

One authoritative tick — rather than a timer per combatant — is also what OSRS
actually does, and it is the prerequisite for augmentation-flicking (see
``constants.py``, "Augmentation"), where a swing must resolve against the buff
state at the exact tick it lands.
"""

import time
from collections import deque

from evennia.scripts.models import ScriptDB
from evennia.scripts.scripts import DefaultScript
from evennia.utils import logger
from twisted.internet.task import LoopingCall

from . import constants as const
from . import debug as tick_debug
from . import tickable
from .scheduler import TickScheduler
from systems.managers import get_singleton_script, register_manager

# ─── module constants ──────────────────────────────────────────────────────

TICK_ENGINE_KEY = "blackout_tick_engine"

# ─── Tick phases ───────────────────────────────────────────────────────────
# Named points other systems can attach to without the engine importing them.
# The engine drives the game's heartbeat; it must not know which systems care
# that a tick started, or it stops being infrastructure and becomes a hub.
#
# START fires after inbound actions are applied and before any handler runs;
# FEED fires last, once everything that could change state has.
PHASE_START = "start"
PHASE_FEED = "feed"

_PHASE_HOOKS: dict = {PHASE_START: [], PHASE_FEED: []}


def register_phase_hook(phase: str, hook) -> None:
    """Attach a zero-argument callable to a tick phase.

    Registered at import time by the system that cares -- see
    systems/statefeed/buffer.py, which uses START and FEED to bracket its
    per-tick coalescing window.

    Raises KeyError on an unknown phase rather than silently never running,
    which is the failure mode the old hand-maintained handler-key list had.
    """
    _PHASE_HOOKS[phase].append(hook)


def _run_phase_hooks(phase: str) -> None:
    """Run every hook on a phase, containing failures.

    A hook is a bystander to the tick, exactly like a handler: one raising
    must not stop the others, and must never escape into _tick, which would
    errback the LoopingCall and stop the server-wide tick.
    """
    for hook in _PHASE_HOOKS[phase]:
        try:
            hook()
        except Exception:
            logger.log_trace()


# ─── the engine ────────────────────────────────────────────────────────────

class BlackoutTickEngine(DefaultScript):
    """Global script owning the 0.6s LoopingCall — the game's heartbeat.

    Handlers register themselves here on creation and unregister on teardown.
    Every 0.6s the engine calls ``handler.tick()`` on each registered handler,
    then runs any deferred work due this tick, isolating failures so one
    broken subscriber cannot take down the loop for everyone.

    The engine knows nothing about what it is driving. Combat, auras and
    anything added later are all just TickableHandlers to it.
    """

    def at_script_creation(self) -> None:
        self.key = TICK_ENGINE_KEY
        self.desc = "Global 0.6s Blackout game tick"
        # Integer watchdog only — the real tick is the LoopingCall below.
        self.interval = const.TICK_ENGINE_WATCHDOG_SECONDS
        self.persistent = True


    # ── LoopingCall lifecycle ────────────────────────────────────────────

    def _ensure_loop(self) -> None:
        """Create/start the 0.6s LoopingCall if it isn't already running.

        Safe to call repeatedly — from at_start, at_server_start and the
        watchdog at_repeat.
        """
        loop = self.ndb._tick_loop
        if loop is not None and loop.running:
            return

        # ndb (never pickled) — a LoopingCall must not be persisted.
        self.ndb._tick_loop = LoopingCall(self._tick)
        self.ndb._tick_loop.start(const.TICK_SECONDS, now=False)


    def _stop_loop(self) -> None:
        loop = self.ndb._tick_loop
        if loop is not None and loop.running:
            try:
                loop.stop()
            except Exception as exc:
                logger.log_err(f"BlackoutTickEngine._stop_loop failed: {exc!r}")
        self.ndb._tick_loop = None


    def at_start(self, **kwargs) -> None:
        self._ensure_loop()


    def at_server_start(self) -> None:
        """Reliable post-reload hook.

        ``ScriptDB.objects.update_scripts_after_server_start`` calls this on
        every script, active or not, so it is the one place guaranteed to run
        after a reload/restart.
        """
        purge_stale_handlers()
        self._ensure_loop()


    def at_repeat(self, **kwargs) -> None:
        """Watchdog. Re-arms the LoopingCall if something killed it."""
        self._ensure_loop()


    def at_stop(self, **kwargs) -> None:
        self._stop_loop()


    # ── registry ─────────────────────────────────────────────────────────

    def _registry(self) -> dict:
        """The live, ORDERED registry of handler ids.

        A dict keyed by handler id with unused values — Python dicts preserve
        insertion order, so this is an ordered set with O(1) add, remove and
        membership. It was a plain `set`, and that made tick order arbitrary:
        two combatants who would each kill the other on the same tick had the
        winner decided by CPython's set internals. Resolution order is
        gameplay in an OSRS-derived engine, so it has to be a fact rather than
        an implementation detail.

        Lives on ndb, so it is empty after a reload — seed it from the active
        handler scripts, which are the source of truth. The reseed is ordered
        by id so the order after a reload is the order handlers were created
        in, rather than whatever the database felt like returning.

        Seeded from EVERY registered tickable key, not just combat's. _tick
        itself is key-agnostic — it only needs a `tick()` method — but this
        reseed is not, which is why the key list must be complete. It used to
        be hand-maintained; it is now whatever @register_tickable has recorded,
        and systems/combat/tests/test_tickable.py fails if a subclass is
        missing from it.
        """
        registry = self.ndb._handler_ids

        if registry is None:
            ordered_ids = (
                ScriptDB.objects.filter(
                    db_key__in=tickable.tickable_keys(), db_is_active=True
                )
                .order_by("id")
                .values_list("id", flat=True)
            )
            registry = dict.fromkeys(ordered_ids)
            self.ndb._handler_ids = registry

        return registry


    def _strikes(self) -> dict:
        """Consecutive-failure counts, keyed by handler id.

        Also ndb: a strike record is only meaningful within one process's
        rotation, and a reload rebuilds the registry from scratch anyway.
        """
        strikes = self.ndb._handler_strikes

        if strikes is None:
            strikes = {}
            self.ndb._handler_strikes = strikes

        return strikes


    def register(self, handler) -> None:
        """Add a handler to the tick rotation."""
        if handler is None or handler.pk is None:
            return

        registry = self._registry()

        # Assigning an existing key leaves its position alone, so re-arming a
        # handler mid-fight must not shuffle it to the back of the rotation.
        registry[handler.id] = None

        self._ensure_loop()


    def unregister(self, handler) -> None:
        """Remove a handler from the tick rotation."""
        if handler is None:
            return

        self._drop(handler.id)


    def is_registered(self, handler) -> bool:
        """Return True if `handler` is currently in the tick rotation.

        Public because a handler CAN still leave the rotation on its own — it
        now takes TICK_HANDLER_MAX_STRIKES consecutive failures rather than a
        single one, but the end state is the same and the only symptom is
        combat quietly stopping. The diagnostics in tick_debug read this to
        tell a stalled fight apart from a handler that has fallen out of the
        loop; strike_count says how close a still-registered handler is to
        that fate.
        """
        if handler is None or handler.pk is None:
            return False

        registry = self._registry()

        return handler.id in registry


    def registered_count(self) -> int:
        """Return how many handlers are in the tick rotation."""
        registry = self._registry()

        return len(registry)


    def strike_count(self, handler) -> int:
        """Return how many CONSECUTIVE failures `handler` has logged.

        Zero for a healthy handler, and reset to zero by any successful tick.
        Public so `tickdebug` can report a handler that is failing but has not
        yet been evicted — the window in which the old drop-on-first-exception
        policy gave no warning at all.
        """
        if handler is None or handler.pk is None:
            return 0

        strikes = self._strikes()
        count = strikes.get(handler.id, 0)

        return count


    def failing_count(self) -> int:
        """Return how many registered handlers currently carry any strikes.

        The number a diagnostic wants: zero is healthy, and anything else is
        a handler that is failing but has not yet been evicted -- the window
        the old drop-on-first-exception policy skipped straight past.
        """
        strikes = self._strikes()

        return len(strikes)


    # ── inbound actions (the INPUT phase) ────────────────────────────────

    def _inbound(self) -> list:
        """The queue of actions waiting to be applied at the top of a tick.

        On ndb: an intention that did not survive to the next tick is not worth
        replaying after a reload, and the handlers it names are swept at boot
        anyway.
        """
        queue = self.ndb._inbound_actions

        if queue is None:
            queue = []
            self.ndb._inbound_actions = queue

        return queue

    def enqueue_action(self, handler, action_dict: dict) -> None:
        """Record an action to apply at the START of the next tick.

        Entry:
            handler is a live TickableHandler. action_dict is whatever that
            handler's apply_action understands.

        Exit/Returns:
            No return value.

        Methodology:
            Commands arrive whenever their packet does -- from the Portal, over
            AMP, at an arbitrary point relative to the LoopingCall. Applying
            them on arrival meant a command landing DURING _tick was seen by
            that tick or the next depending on where its handler sat in the
            rotation, which is not a decision that should be made by iteration
            order.

            Draining at a fixed point instead makes the answer always "the next
            tick", for every command, regardless of when in the tick it
            arrived. This is what OSRS does: inbound packets are buffered and
            processed in one phase rather than as they land.

        Notes/References:
            Last write wins for a given handler, matching the previous
            behaviour of queue_action -- a second intention replaces the first
            rather than queueing behind it.

        Author: Nick Hobar
        Creation date: 08/18/2026
        """
        if handler is None or handler.pk is None:
            return

        self._inbound().append((handler, action_dict))

    def _drain_inbound(self) -> int:
        """Apply every queued action. The first phase of a tick.

        Returns how many were applied. A handler deleted between enqueue and
        drain is skipped; one whose apply_action raises is isolated, for the
        same reason _advance_one isolates a failing tick.
        """
        queue = self._inbound()

        if not queue:
            return 0

        # Swap the list out before applying: an action may enqueue more work,
        # and that belongs to the NEXT tick rather than extending this drain.
        pending = list(queue)
        queue.clear()

        applied = 0

        for handler, action_dict in pending:
            if handler.pk is None:
                continue

            try:
                handler.apply_action(action_dict)
                applied += 1
            except Exception:
                logger.log_trace()

        return applied

    def pending_action_count(self) -> int:
        """Return how many inbound actions are waiting. For diagnostics."""
        return len(self._inbound())


    # ── deferred work ────────────────────────────────────────────────────

    def scheduler(self) -> TickScheduler:
        """Return the tick scheduler, creating it if this process has none.

        On ndb, so it is empty after a reload and its users re-arm themselves
        at boot -- see scheduler.py's header for what that deliberately rules
        out.
        """
        existing = self.ndb._scheduler

        if existing is None:
            existing = TickScheduler()
            self.ndb._scheduler = existing

        return existing

    def schedule_in(self, delay_ticks: int, callback) -> int:
        """Run `callback` `delay_ticks` ticks from now. Returns a handle."""
        scheduler = self.scheduler()
        now = self.current_tick()

        return scheduler.schedule_in(delay_ticks, callback, now)

    def schedule_at(self, due_tick: int, callback) -> int:
        """Run `callback` on an absolute tick number. Returns a handle."""
        scheduler = self.scheduler()

        return scheduler.schedule_at(due_tick, callback)

    def cancel_scheduled(self, handle: int) -> bool:
        """Stop a scheduled callback. Returns True if one was pending."""
        scheduler = self.scheduler()

        return scheduler.cancel(handle)

    def current_tick(self) -> int:
        """Return the engine's tick counter -- the game's notion of now.

        Monotonic within a process and reset by a reload. NOT wall-clock:
        anything whose deadline must survive the server being down needs an
        absolute time instead (systems/spawning/respawn.py explains why).
        """
        number = self.ndb.tick_number or 0

        return number


    # ── rotation membership ──────────────────────────────────────────────

    def _drop(self, handler_id: int) -> None:
        """Remove a handler id from the rotation and forget its strikes.

        The quiet exit, for a handler that is simply gone (deleted row, or a
        script that carries no tick()). Not a failure, so nothing is logged.
        """
        registry = self._registry()
        strikes = self._strikes()

        registry.pop(handler_id, None)
        strikes.pop(handler_id, None)


    def _record_success(self, handler_id: int) -> None:
        """Clear a handler's strike record after a clean tick.

        Strikes are CONSECUTIVE: one good tick forgives everything before it,
        so a combatant whose target briefly vanished mid-swing is not carried
        toward eviction by an unrelated failure ten minutes later.
        """
        strikes = self._strikes()

        strikes.pop(handler_id, None)


    def _record_failure(self, handler_id: int, stage: str) -> bool:
        """Charge a handler one strike, evicting it once it has too many.

        Entry:
            handler_id is a registered id. stage names what failed ("lookup"
            or "tick") and appears in the eviction log.

        Exit/Returns:
            Returns True if this strike evicted the handler.

        Methodology:
            The engine used to discard a handler on its FIRST exception, and
            the only symptom was combat stopping with nothing said. A single
            bad tick is now survivable; TICK_HANDLER_MAX_STRIKES consecutive
            ones are not, and the eviction is logged at error level rather
            than left as a bare traceback.
        """
        strikes = self._strikes()
        count = strikes.get(handler_id, 0) + 1
        strikes[handler_id] = count

        if count < const.TICK_HANDLER_MAX_STRIKES:
            return False

        self._drop(handler_id)

        logger.log_err(
            f"BlackoutTickEngine: evicted handler {handler_id} from the tick "
            f"rotation after {count} consecutive {stage} failures. Whatever it "
            f"was driving has stopped; see the tracebacks above."
        )

        return True


    # ── the tick ─────────────────────────────────────────────────────────

    def _record_tick_timing(self, started_at: float) -> None:
        """Advance the tick counter and measure the gap since the last tick.

        The engine had no notion of "now" at all before this: nothing counted
        ticks and nothing looked at the clock, so there was no fact for a
        diagnostic to report. All of it lives on ndb, per-process and reset by
        a reload, exactly like the handler counters it is measuring.

        Cheap enough to run unconditionally — two monotonic reads and a deque
        append — which is what makes `tickdebug status` a health check over a
        window rather than a single instantaneous reading.
        """
        last_at = self.ndb.last_tick_at

        if last_at is None:
            interval = const.TICK_SECONDS
        else:
            interval = started_at - last_at

        recorded = self.ndb.tick_intervals

        if recorded is None:
            recorded = deque(maxlen=const.TICK_DEBUG_SAMPLE_WINDOW)
            self.ndb.tick_intervals = recorded

        recorded.append(interval)

        number = self.ndb.tick_number or 0

        self.ndb.tick_number = number + 1
        self.ndb.tick_interval = interval
        self.ndb.last_tick_at = started_at


    def _advance_one(self, handler_id: int) -> None:
        """Drive one registered handler through a single tick.

        Entry:
            handler_id is an id drawn from the rotation. It may name a row
            that has since been deleted.

        Exit/Returns:
            No return value, and NOTHING is allowed to escape: an exception
            reaching _tick would errback the LoopingCall and stop the tick for
            the whole server.

        Methodology:
            A missing or non-tickable row is dropped quietly -- it is gone,
            not broken. A failure at either stage costs a strike instead of
            the handler's place in the rotation, and a clean pass clears the
            record. See _record_failure for why the old drop-on-first-failure
            rule had to go.

        Notes/References:
            The per-handler query here is deliberate for now; batching the
            whole rotation into one filter(id__in=...) is a separate change
            and wants the owner-map that comes with it.
        """
        try:
            handler = ScriptDB.objects.filter(id=handler_id).first()
        except Exception:
            logger.log_trace()
            self._record_failure(handler_id, "lookup")
            return

        if handler is None or not hasattr(handler, "tick"):
            self._drop(handler_id)
            return

        try:
            handler.tick()
        except Exception:
            # One bad subscriber must never stop the server-wide tick.
            logger.log_trace()
            self._record_failure(handler_id, "tick")
            return

        self._record_success(handler_id)


    def _tick(self) -> None:
        """Advance every registered handler by one tick, then run due work.

        The old "return early if the registry is empty" guard is gone. An empty
        registry makes the loop below a no-op anyway, so it bought nothing, and
        it also skipped the tick counter and the diagnostic hooks — meaning a
        player watching the tick saw nothing at all until someone attacked, and
        the interval window went stale exactly when a stalled server is most
        worth measuring.
        """
        started_at = time.monotonic()

        self._record_tick_timing(started_at)

        # Both hooks swallow their own exceptions; see tick_debug's header for
        # why that guarantee has to hold — anything raised here would errback
        # the LoopingCall and stop the tick for the whole server.
        tick_debug.before_tick(self)

        # INPUT first: every command that arrived since the last tick lands
        # now, so the handlers below all observe the same world.
        self._drain_inbound()

        _run_phase_hooks(PHASE_START)

        registry = self._registry()

        # Snapshot the ids first: _advance_one may drop entries, and a handler
        # ending combat mid-tick mutates the registry under us. Iteration order
        # is the registry's insertion order and IS gameplay -- see _registry.
        for handler_id in list(registry):
            self._advance_one(handler_id)

        # Deferred work runs AFTER the handlers, so a callback scheduled for
        # this tick observes the state the handlers just produced rather than
        # the state they are halfway through changing. run_due contains its own
        # failures for the same reason _advance_one does.
        self.scheduler().run_due(self.current_tick())

        # FEED last: everything that could have changed state this tick has
        # now run, so what the buffer holds is the tick's final answer rather
        # than a value something later in the pass would have overwritten.
        _run_phase_hooks(PHASE_FEED)

        self.ndb.tick_duration = time.monotonic() - started_at

        tick_debug.after_tick(self)


# ─── module helpers ────────────────────────────────────────────────────────

def get_tick_engine() -> BlackoutTickEngine:
    """Return the global tick engine, creating and starting it if absent.

    Lazily created from ``ensure_handler`` so no settings.py change is needed
    to bring the tick up. get_singleton_script owns the lookup, including
    rebuilding a row whose typeclass path no longer loads -- this module has
    moved once already, and the stale row silently degrades to DefaultScript.
    """
    engine = get_singleton_script(TICK_ENGINE_KEY, BlackoutTickEngine)

    if not engine.is_active:
        engine.start()

    # start() is a no-op if the Script was already active, so re-arm explicitly.
    engine._ensure_loop()
    return engine


@register_manager
def bootstrap_tick() -> BlackoutTickEngine:
    """Bring combat up at server start. Called from at_server_startstop.

    Purging first and creating the engine second matters: on the very first
    boot after this change no engine row exists yet, so the engine's own
    ``at_server_start`` will not have run and the leftovers from the old
    (timerless) handlers would otherwise survive until someone attacked.
    """
    purge_stale_handlers()
    return get_tick_engine()


def _reset_owner(owner) -> None:
    """Drop the owner's cached reference to every handler class.

    lazy_property caches into obj.__dict__, so a handler about to be deleted
    would otherwise keep being handed out. The accessor names come from the
    registry -- the engine used to hard-code two of them plus a combat flag,
    and the flag is gone entirely now that in_combat derives from the handler
    rather than being stamped on its owner.
    """
    for handler_cls in tickable.TICKABLE_REGISTRY.values():
        owner.__dict__.pop(handler_cls.ACCESSOR_NAME, None)


def purge_stale_handlers() -> int:
    """Delete every leftover per-entity handler and reset its owner.

    Per-tick state does not meaningfully survive a server restart -- it lives
    on ndb, which a reload wipes -- and handlers are cheap to recreate on the
    next action. Sweeping them at server start means a handler persisted in a
    broken state (e.g. the historical ``db_interval=0`` rows) can no longer
    wedge its system permanently.

    Applies to every registered tickable by the same rule: a combat handler is
    recreated on the next attack, an aura is re-toggled by the player.

    Returns the number of handlers deleted.
    """
    count = 0

    for handler in ScriptDB.objects.filter(db_key__in=tickable.tickable_keys()):
        owner = handler.obj

        if owner is not None:
            try:
                _reset_owner(owner)
            except Exception:
                logger.log_trace()

        try:
            handler.delete()
            count += 1
        except Exception:
            logger.log_trace()

    if count:
        logger.log_info(f"BlackoutTickEngine: purged {count} stale handler(s).")

    return count
