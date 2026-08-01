"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/30/2026
Description: BlackoutTickEngine — the single server-wide 0.6s OSRS tick that
             advances every active combat handler.

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

from evennia.scripts.models import ScriptDB
from evennia.scripts.scripts import DefaultScript
from evennia.utils import logger
from twisted.internet.task import LoopingCall

from . import constants as const

# ─── module constants ──────────────────────────────────────────────────────

TICK_ENGINE_KEY = "blackout_tick_engine"


# ─── the engine ────────────────────────────────────────────────────────────


class BlackoutTickEngine(DefaultScript):
    """Global script owning the 0.6s combat LoopingCall.

    Combat handlers register themselves here on creation and unregister on
    ``end_combat``. Every 0.6s the engine calls ``handler.tick()`` on each
    registered handler, isolating failures so one broken combatant cannot
    take down the loop for everyone.
    """

    def at_script_creation(self) -> None:
        self.key = TICK_ENGINE_KEY
        self.desc = "Global 0.6s Blackout combat tick"
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
        self.ndb._tick_loop.start(const.COMBAT_TICK_SECONDS, now=False)

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
        purge_stale_combat_handlers()
        self._ensure_loop()

    def at_repeat(self, **kwargs) -> None:
        """Watchdog. Re-arms the LoopingCall if something killed it."""
        self._ensure_loop()

    def at_stop(self, **kwargs) -> None:
        self._stop_loop()

    # ── registry ─────────────────────────────────────────────────────────

    def _registry(self) -> set:
        """The live set of registered handler ids.

        Lives on ndb, so it is empty after a reload — seed it from the active
        handler scripts, which are the source of truth.
        """
        from .combat import COMBAT_HANDLER_KEY

        registry = self.ndb._handler_ids
        if registry is None:
            registry = set(
                ScriptDB.objects.filter(
                    db_key=COMBAT_HANDLER_KEY, db_is_active=True
                ).values_list("id", flat=True)
            )
            self.ndb._handler_ids = registry
        return registry

    def register(self, handler) -> None:
        """Add a combat handler to the tick rotation."""
        if handler is None or handler.pk is None:
            return
        self._registry().add(handler.id)
        self._ensure_loop()

    def unregister(self, handler) -> None:
        """Remove a combat handler from the tick rotation."""
        if handler is None:
            return
        self._registry().discard(handler.id)

    # ── the tick ─────────────────────────────────────────────────────────

    def _tick(self) -> None:
        """Advance every registered combat handler by one tick."""
        registry = self._registry()
        if not registry:
            return

        for handler_id in list(registry):
            try:
                handler = ScriptDB.objects.filter(id=handler_id).first()
            except Exception:
                logger.log_trace()
                registry.discard(handler_id)
                continue

            if handler is None or not hasattr(handler, "tick"):
                registry.discard(handler_id)
                continue

            try:
                handler.tick()
            except Exception:
                # One bad combatant must never stop the server-wide tick.
                logger.log_trace()
                registry.discard(handler_id)


# ─── module helpers ────────────────────────────────────────────────────────


def get_tick_engine() -> BlackoutTickEngine:
    """Return the global tick engine, creating and starting it if absent.

    Lazily created from ``ensure_combat_handler`` so no settings.py change is
    needed to bootstrap combat.
    """
    engine = ScriptDB.objects.filter(db_key=TICK_ENGINE_KEY).first()

    if engine is None:
        engine, errors = BlackoutTickEngine.create(key=TICK_ENGINE_KEY)
        if errors:
            raise RuntimeError(f"Could not create the Blackout tick engine: {errors}")

    if not engine.is_active:
        engine.start()

    # start() is a no-op if the Script was already active, so re-arm explicitly.
    engine._ensure_loop()
    return engine


def bootstrap_combat() -> BlackoutTickEngine:
    """Bring combat up at server start. Called from at_server_startstop.

    Purging first and creating the engine second matters: on the very first
    boot after this change no engine row exists yet, so the engine's own
    ``at_server_start`` will not have run and the leftovers from the old
    (timerless) handlers would otherwise survive until someone attacked.
    """
    purge_stale_combat_handlers()
    return get_tick_engine()


def purge_stale_combat_handlers() -> int:
    """Delete every leftover per-combatant handler and clear its owner's flag.

    Twitch combat does not meaningfully survive a server restart, and handlers
    are cheap to recreate on the next ``attack``. Sweeping them at server start
    means a handler that was persisted in a broken state (e.g. the historical
    ``db_interval=0`` rows) can no longer wedge combat permanently.

    Returns the number of handlers deleted.
    """
    from .combat import COMBAT_HANDLER_KEY

    count = 0
    for handler in ScriptDB.objects.filter(db_key=COMBAT_HANDLER_KEY):
        owner = handler.obj
        if owner is not None:
            try:
                owner.db.in_combat = False
                owner.__dict__.pop("combat", None)
            except Exception:
                logger.log_trace()
        try:
            handler.delete()
            count += 1
        except Exception:
            logger.log_trace()

    if count:
        logger.log_info(f"BlackoutTickEngine: purged {count} stale combat handler(s).")
    return count
