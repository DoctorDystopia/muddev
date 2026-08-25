"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: The registry of global manager Scripts that must be brought up at
             server start, and the one call that brings them all up.

Why this exists
---------------
server/conf/at_server_startstop.py carried three hand-listed calls:

    bootstrap_tick()
    bootstrap_respawns()
    bootstrap_regen()

so adding a fourth global system meant editing a server conf file, and
forgetting to meant the system simply never started -- with nothing raised and
nothing logged. That is a dispatch list, which CLAUDE.md forbids, and it is the
same OCP hole ``_tickable_handler_keys()`` had on the per-entity side.

``@register_manager`` records a bootstrap routine; ``bootstrap_all()`` runs
every registered one, isolating failures so a broken respawn manager cannot
stop combat from starting. at_server_startstop never needs editing again.

On ordering
-----------
Managers are bootstrapped in the order their modules appear in
``_MANAGER_MODULES``, which preserves the original combat -> respawns -> regen
sequence. The order is not currently load-bearing -- each manager is
self-contained and creates its own Script -- but it is fixed rather than
arbitrary so that if one ever does depend on another, the dependency is
expressible somewhere visible instead of falling out of import timing.

Relationship to the tick scheduler
----------------------------------
This is deliberately thin. The regen and respawn managers are candidates to
stop being Scripts at all and become deadline entries on the tick engine's
scheduler, at which point most of what they share dissolves rather than moving
into a base class. Registering their bootstraps costs almost nothing and
survives that change; a SingletonManagerScript base class would not.
"""

import importlib

from evennia.scripts.models import ScriptDB
from evennia.utils import logger

# ─── Public constant definitions ────────────────────────────────────────────

# bootstrap routine name -> callable. Insertion-ordered, which is the order
# bootstrap_all runs them in.
MANAGER_REGISTRY: dict = {}


# ─── Private constant definitions ───────────────────────────────────────────

# Modules to import so their @register_manager decorators run, in bootstrap
# order. Mirrors tickable._TICKABLE_MODULES and typeclasses/spawners.py's
# _SPAWNER_MODULES. Imported lazily to avoid a cycle through the game systems
# at module scope.
_MANAGER_MODULES = (
    "systems.tick.engine",
    "systems.spawning.respawn",
    "systems.combat.hp_regen",
)


# ─── Module globals ─────────────────────────────────────────────────────────

_loaded = False


# ─── Public routines ────────────────────────────────────────────────────────

def register_manager(bootstrap_fn):
    """
    Purpose: Record a global manager's bootstrap routine.

    Entry:
        bootstrap_fn takes no arguments and brings one global manager up. It
        must be idempotent -- bootstrap_all may run after a reload as well as
        a cold start.

    Exit/Returns:
        Returns bootstrap_fn unchanged, so this reads as a decorator.

    Module Globals:
        MANAGER_REGISTRY written.

    Methodology:
        Keyed on the function's qualified name so re-importing a module cannot
        register the same bootstrap twice under different identities.

    Notes/References:
        Matches @register_spawner in typeclasses/spawners.py and
        @register_tickable in systems/combat/tickable.py.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    name = f"{bootstrap_fn.__module__}.{bootstrap_fn.__name__}"

    MANAGER_REGISTRY[name] = bootstrap_fn

    return bootstrap_fn


def get_singleton_script(key, script_cls):
    """
    Purpose: Return the one global Script stored under ``key``, creating it if
             absent and repairing it if the stored typeclass no longer loads.

    Entry:
        key is the Script's db_key; script_cls is the typeclass it must be.
        Safe to call repeatedly and from any point after Django is up.

    Exit/Returns:
        Returns a live instance of script_cls. Raises RuntimeError if Evennia
        refuses to create one.

    Module Globals:
        None.

    Methodology:
        A Script row records its typeclass as an import path. Move or rename
        the module and that path stops resolving, at which point Evennia hands
        back a plain DefaultScript instead of raising -- so the caller gets an
        object that is missing every method it was about to call. Looking up
        by key alone cannot see that; isinstance can, so every manager goes
        through this one check rather than trusting the key.

        A stale row is replaced rather than swapped in place: swap_typeclass
        refuses outright on any Script with interval > 0, which all three
        managers have.

    Notes/References:
        Written after systems/combat/tick_engine.py moved to
        systems/tick/engine.py and the persisted engine row kept pointing at
        the old path -- every attack then died on
        ``'DefaultScript' object has no attribute '_ensure_loop'``.

    Author: Nick Hobar
    Creation date: 08/19/2026
    """
    script = ScriptDB.objects.filter(db_key=key).first()
    saved = None

    if script is not None and not isinstance(script, script_cls):
        saved = _discard_stale_script(script, key, script_cls)
        script = None

    if script is None:
        script = _create_singleton(key, script_cls)
        _restore_attributes(script, saved)

    return script


def load_all_managers() -> None:
    """
    Purpose: Import every module holding a manager so its decorator runs.

    Entry:
        No conditions. Safe to call repeatedly.

    Exit/Returns:
        No return value.

    Module Globals:
        _MANAGER_MODULES read. _loaded read and written.

    Methodology:
        Lazy import, in declared order, so MANAGER_REGISTRY's insertion order
        is the bootstrap order.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    global _loaded

    if _loaded:
        return

    for module_name in _MANAGER_MODULES:
        importlib.import_module(module_name)

    _loaded = True


def bootstrap_all() -> dict:
    """
    Purpose: Bring every registered global manager up. Called once, from
             at_server_startstop.at_server_start.

    Entry:
        Called after Django and Evennia are initialised.

    Exit/Returns:
        Returns {manager name: the object its bootstrap returned}, with a
        failed manager mapped to None. The return exists for tests and
        diagnostics; the server ignores it.

    Module Globals:
        MANAGER_REGISTRY read.

    Methodology:
        Per-manager try/except, matching the isolation the tick engine already
        applies to handlers: one system failing to start must not stop the
        rest of the server coming up, and the traceback must reach the log
        rather than the boot sequence.

    Notes/References:
        Replaces three hand-listed calls in server/conf/at_server_startstop.py.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    load_all_managers()

    started = {}

    for name, bootstrap_fn in MANAGER_REGISTRY.items():
        try:
            started[name] = bootstrap_fn()
        except Exception:
            logger.log_trace()
            logger.log_err(f"bootstrap_all: {name} failed to start.")
            started[name] = None

    return started


# ─── Private routines ───────────────────────────────────────────────────────

def _discard_stale_script(stale, key, script_cls) -> dict:
    """Delete a Script whose typeclass no longer resolves, returning its
    persistent Attributes so the replacement can inherit them.

    The Attributes are worth carrying: the respawn manager's pending queue and
    the regen manager's registry both live there, and dropping them would turn
    a cosmetic path change into lost gameplay state.
    """
    logger.log_err(
        f"get_singleton_script: '{key}' is stored as "
        f"'{stale.db_typeclass_path}', which no longer loads as "
        f"{script_cls.__name__}. Recreating it."
    )

    saved = {attr.key: attr.value for attr in stale.attributes.all()}
    stale.delete()

    return saved


def _create_singleton(key, script_cls):
    """Create the global Script, turning Evennia's error list into a raise."""
    script, errors = script_cls.create(key=key)

    if errors:
        raise RuntimeError(f"Could not create the '{key}' script: {errors}")

    return script


def _restore_attributes(script, saved) -> None:
    """Copy Attributes rescued from a stale row onto its replacement."""
    if not saved:
        return

    for attr_key, value in saved.items():
        script.attributes.add(attr_key, value)
