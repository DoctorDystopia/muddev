"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: TickableHandler — the shared base for every per-entity script the
             BlackoutTickEngine drives, plus the registry that tells the engine
             which ones exist.

Why this exists
---------------
BlackoutCombatHandler and BlackoutAuraHandler were siblings that had
independently grown the same four pieces of machinery:

  * an ``at_script_creation`` setting key / desc / timerless interval /
    non-persistent, then seeding ndb
  * ``mark_running`` — Evennia will not flag a timerless script active, so the
    handler owns its own liveness
  * ``get_X_handler_for`` — scan ``obj.scripts`` for an ACTIVE handler
  * ``ensure_X_handler`` — ~50 lines of find-or-create, including a
    delete-and-recreate branch for handlers written under an older interval,
    and the ``obj.__dict__.pop(accessor, None)`` dance that clears a
    ``lazy_property`` cache

Every one of those was written twice and had to be kept in step by hand. They
had already drifted once: the aura version cleared the accessor cache on EVERY
path while the combat version only did so when it created or discarded a
handler, so a combat handler reused after a reload could leave a stale cached
value behind. The unified version takes the aura behaviour, which is the
correct one.

The registry
------------
The engine used to ask a hand-maintained ``_tickable_handler_keys()`` for the
keys it may drive, carrying this warning:

    Any new tickable handler must be added HERE as well as registering itself,
    or it will work until the first reload and then silently stop forever.

That is a dispatch list, which CLAUDE.md forbids. ``@register_tickable`` now
records a subclass by its own ``HANDLER_KEY``, matching the
``@register_spawner`` pattern in typeclasses/spawners.py.

``_TICKABLE_MODULES`` still names the modules to import so the decorators run
-- the same shape as ``_SPAWNER_MODULES`` -- because both handler modules
import from this one and resolving them at import time would close the cycle.
The difference that matters is that forgetting an entry is no longer silent:
tests/test_tickable.py walks the tree and fails if any TickableHandler
subclass is missing from the registry.
"""

import importlib

from evennia.scripts.scripts import DefaultScript
from evennia.utils import logger

from . import states

# ─── Public constant definitions ────────────────────────────────────────────

# Evennia interval meaning "this script owns no timer of its own". ScriptDB's
# db_interval is a Django IntegerField and cannot express the 0.6s tick, so
# every tickable is timerless and the engine's LoopingCall calls tick().
# ScriptBase._start_task refuses to start a task at an interval <= 0, which is
# exactly what is wanted here.
HANDLER_NO_TIMER_INTERVAL: int = -1

# handler key -> TickableHandler subclass.
TICKABLE_REGISTRY: dict = {}


# ─── Private constant definitions ───────────────────────────────────────────

# Modules to import so their @register_tickable decorators run. Mirrors
# _SPAWNER_MODULES in typeclasses/spawners.py. A missing entry is caught by
# tests/test_tickable.py rather than surfacing as combat that stops after a
# reload.
_TICKABLE_MODULES = (
    "systems.combat.combat",
    "systems.combat.auras.aura_handler",
)


# ─── Module globals ─────────────────────────────────────────────────────────

_loaded = False


# ─── Private helper routines ────────────────────────────────────────────────

def _find_handler_script(owner, handler_key: str, active_only: bool):
    """
    Purpose: Scan an owner's scripts for one carrying `handler_key`.

    Entry:
        owner is an Evennia Object with a `scripts` handler.
        handler_key is the canonical key of the handler wanted.
        active_only limits the search to scripts Evennia flags active.

    Exit/Returns:
        Returns the first matching script, or None.

    Module Globals:
        None

    Methodology:
        Two callers want different things from the same scan. Lookups treat a
        stopped leftover as "not in combat", so they pass active_only=True;
        ensure_handler has to SEE a leftover in order to discard it, so it
        passes False.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    for script in owner.scripts.all():
        if getattr(script, "key", "") != handler_key:
            continue

        if active_only and not script.is_active:
            continue

        return script

    return None


# ─── Public routines ────────────────────────────────────────────────────────

def register_tickable(handler_cls):
    """
    Purpose: Record a TickableHandler subclass so the engine can find it.

    Entry:
        handler_cls defines a non-empty HANDLER_KEY.

    Exit/Returns:
        Returns handler_cls unchanged, so this reads as a class decorator.

    Module Globals:
        TICKABLE_REGISTRY written.

    Methodology:
        Keyed on the class's own HANDLER_KEY rather than a string passed to
        the decorator, so the key cannot be registered under one name and
        created under another.

    Notes/References:
        Matches @register_spawner in typeclasses/spawners.py.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    key = getattr(handler_cls, "HANDLER_KEY", "")

    if not key:
        raise ValueError(
            f"{handler_cls.__name__} must define HANDLER_KEY to be registered."
        )

    TICKABLE_REGISTRY[key] = handler_cls

    return handler_cls


def load_all_tickables() -> None:
    """
    Purpose: Import every module holding a tickable so its decorator runs.

    Entry:
        No conditions. Safe to call repeatedly.

    Exit/Returns:
        No return value.

    Module Globals:
        _TICKABLE_MODULES read. _loaded read and written.

    Methodology:
        Imported lazily rather than at module scope because both handler
        modules import from this one; resolving them eagerly would close the
        cycle. Mirrors load_all_spawners.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    global _loaded

    if _loaded:
        return

    for module_name in _TICKABLE_MODULES:
        importlib.import_module(module_name)

    _loaded = True


def tickable_keys() -> tuple:
    """
    Purpose: Return every script key the tick engine is allowed to drive.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a tuple of handler keys, in registration order.

    Module Globals:
        TICKABLE_REGISTRY read.

    Methodology:
        Replaces the hand-maintained _tickable_handler_keys(). The engine's
        registry reseed and its boot sweep are both key-driven, so this is the
        one list that decides which handlers survive a reload.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    load_all_tickables()

    return tuple(TICKABLE_REGISTRY)


def get_handler_for(owner, handler_cls):
    """
    Purpose: Return an owner's ACTIVE handler of the given class, or None.

    Entry:
        owner is an Evennia Object. handler_cls is a TickableHandler subclass.

    Exit/Returns:
        Returns the live handler script, or None.

    Module Globals:
        None

    Methodology:
        Gated on is_active deliberately: an entity is considered to be running
        this handler iff the handler is live. A leftover stopped script must
        not read as live combat, or the `combat` accessor hands back a parked
        script and the "you aren't in combat" guards behave inconsistently.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    handler = _find_handler_script(owner, handler_cls.HANDLER_KEY, active_only=True)

    return handler


def ensure_handler(owner, handler_cls):
    """
    Purpose: Return the owner's handler of this class, creating and arming one
             if absent, and register it with the tick engine.

    Entry:
        owner is an Evennia Object. handler_cls is a TickableHandler subclass
        with HANDLER_KEY and ACCESSOR_NAME set.

    Exit/Returns:
        Returns the live, registered handler. Raises RuntimeError if Evennia
        refuses to create one, after messaging the owner.

    Module Globals:
        HANDLER_NO_TIMER_INTERVAL read.

    Methodology:
        Either a handler already exists and is reused, or one is created.
        There is no third case: every tickable is non-persistent and the
        engine purges the lot at server start, so a handler written under an
        older configuration cannot outlive the process that made it.

        The accessor cache is cleared on EVERY path, not just creation.
        get_handler_for is gated on is_active, so reviving a stopped leftover
        otherwise leaves a cached None behind and the caller keeps seeing no
        handler at all.

    Notes/References:
        Replaces ensure_combat_handler and ensure_aura_handler, which were
        ~50 near-identical lines each. Per-class extra work belongs in
        on_ensured, not here.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    from .engine import get_tick_engine

    existing = _find_handler_script(owner, handler_cls.HANDLER_KEY, active_only=False)

    if existing is None:
        existing, errors = handler_cls.create(
            key=handler_cls.HANDLER_KEY,
            obj=owner,
        )

        if errors:
            for err in errors:
                owner.msg(f"|r{err}|n")
            raise RuntimeError(
                f"Could not create {handler_cls.__name__} for {owner}: {errors}"
            )

    owner.__dict__.pop(handler_cls.ACCESSOR_NAME, None)

    # Evennia will not flag a timerless script active, so we own liveness.
    existing.mark_running()

    # A reused handler may have had its ndb wiped by a reload since it was
    # created, so reseed before anything reads the per-tick fields.
    existing.init_runtime_state()

    existing.on_ensured()

    get_tick_engine().register(existing)

    return existing


# ─── The base class ─────────────────────────────────────────────────────────

class TickableHandler(DefaultScript):
    """A per-entity script advanced by the global BlackoutTickEngine.

    Subclasses set HANDLER_KEY, ACCESSOR_NAME and HANDLER_DESC, decorate
    themselves with @register_tickable, and implement tick(). Everything else
    below is shared.

    Every tickable is timerless and non-persistent: the engine owns the 0.6s
    LoopingCall, and per-tick state does not meaningfully survive a restart --
    the engine sweeps leftovers at server start and the handler is recreated
    on the next action.
    """

    # Canonical script key. Also what @register_tickable files the class under
    # and what the engine's reseed and boot sweep query on.
    HANDLER_KEY: str = ""

    # The lazy_property name on the OWNER that caches this handler.
    # lazy_property stores into obj.__dict__ under its own __name__ and its
    # deleter raises (CLAUDE.md gotcha 7), so invalidation is a dict pop.
    ACCESSOR_NAME: str = ""

    # Script.desc, shown by Evennia's script listings.
    HANDLER_DESC: str = ""

    def at_script_creation(self) -> None:
        """Set up a timerless, non-persistent script and seed its ndb state."""
        self.key = self.HANDLER_KEY
        self.desc = self.HANDLER_DESC
        self.interval = HANDLER_NO_TIMER_INTERVAL
        self.persistent = False

        self.init_runtime_state()

    # ── activity state ───────────────────────────────────────────────────

    @property
    def state(self):
        """This handler's ActivityState.

        Lives on ndb alongside every other per-tick field. That is not a
        compromise: a reload wipes the state a handler was mid-way through,
        and the engine sweeps every handler at boot anyway, so the only
        correct value after a restart is the initial one.
        """
        current = self.ndb.activity_state

        if current is None:
            current = states.INITIAL_STATE
            self.ndb.activity_state = current

        return current

    def dispatch(self, event) -> bool:
        """
        Purpose: Apply an ActivityEvent to this handler's state.

        Entry:
            event is an ActivityEvent.

        Exit/Returns:
            Returns True if the state changed, False if the event was not
            legal from the current state.

        Module Globals:
            None

        Methodology:
            The transition table decides; this routine only applies. An
            illegal pair is LOGGED rather than silently ignored, because the
            failure it replaces -- a handler wedged in a state nothing could
            move it out of -- was invisible, and diagnosing it is what
            tick_debug had to be written for.

            Illegal is not the same as fatal: a TARGET_INVALID arriving twice
            in one tick is an ordinary race, so this returns False rather than
            raising and lets the caller carry on.

        Notes/References:
            The last transition is recorded so `tickdebug` can report how a
            handler reached the state it is stuck in, rather than only that it
            is stuck.

        Author: Nick Hobar
        Creation date: 08/18/2026
        """
        current = self.state
        resulting = states.next_state(current, event)

        if resulting is None:
            logger.log_info(
                f"{type(self).__name__} on {self.obj}: ignoring illegal "
                f"transition {current.name} --{event.name}-->"
            )
            return False

        self.ndb.activity_state = resulting
        self.ndb.last_transition = (current, event, resulting)

        return True

    def is_busy(self) -> bool:
        """Whether this handler's owner is occupied by the activity it drives.

        The single fact `db.in_combat` used to be stored as, in five places
        that nothing kept in agreement.
        """
        busy = states.is_busy(self.state)

        return busy

    def init_runtime_state(self) -> None:
        """(Re)initialise the ndb fields tick() depends on.

        ndb does not survive a reload, and a non-persistent script can still
        be reached once before the engine sweeps it, so every entry point that
        reads per-tick state calls this first rather than trusting
        at_script_creation to have run in this process.

        The base has nothing to seed; subclasses override.
        """
        return None

    def on_ensured(self) -> None:
        """Hook run by ensure_handler after the handler is armed.

        Exists so ensure_handler stays one function: combat refreshes its
        weapon data here, auras need nothing. Failures are the subclass's to
        contain -- ensure_handler does not guard this.
        """
        return None

    def mark_running(self) -> None:
        """Flag this handler live.

        With a negative interval Evennia never sets db_is_active for us
        (ScriptBase._start_task bails out at interval <= 0), yet
        get_handler_for, the owner's accessor and the tick engine's registry
        rebuild all key off that flag. Since the engine -- not Evennia -- owns
        our timer, we set it ourselves. stop() clears it again on the way out.
        """
        if self.is_active:
            return

        self.db_is_active = True
        self.save(update_fields=["db_is_active"])

    def invalidate_accessor(self) -> None:
        """Clear the owner's cached reference to this handler.

        Called on teardown. lazy_property caches into obj.__dict__ rather than
        ndb, so `del obj.ndb.combat` was a silently swallowed no-op and the
        accessor kept handing back a deleted script for the rest of the
        session.
        """
        owner = self.obj

        if owner is None:
            return

        owner.__dict__.pop(self.ACCESSOR_NAME, None)

    def tick(self) -> None:
        """Advance this handler by one TICK_SECONDS tick.

        Called by the global BlackoutTickEngine's LoopingCall, not by an
        Evennia Script timer -- see engine.py for why.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement tick()."
        )
