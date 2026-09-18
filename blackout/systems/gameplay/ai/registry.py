"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: Decorator registry for NPC combat behaviours.

Modelled on typeclasses/spawners.py (SPAWNER_REGISTRY / @register_spawner):
an explicit module list, a decorator that files a callable under a key, and a
one-shot loader. Adding a behaviour is adding one decorated function, never
editing a dispatch chain.

The module list is EXPLICIT and hand-maintained. It is not a directory walk and
must never become one: CLAUDE.md records that bulk-importing modules under
blackout/ once executed an operator script and deleted 347 grid rooms.
"""



import importlib

from evennia.utils import logger

from .constants import AI_BEHAVIOR_ATTR



# key -> callable(handler) -> action dict | None
BEHAVIOR_REGISTRY = {}

# Modules to import so their @register_behavior decorators run.
# Add new behaviour modules here as they are created.
_BEHAVIOR_MODULES = [
    "systems.gameplay.ai.behaviors",
]

_LOADED = False



def load_all_behaviors() -> None:
    """
    Purpose: Import every behaviour module once, so the decorators have run
    before the first registry lookup.

    Entry:
        None.

    Exit/Returns:
        No return value. Idempotent — the second call is a no-op.

    Module Globals:
        _BEHAVIOR_MODULES read; _LOADED written; BEHAVIOR_REGISTRY populated
        as a side effect of the imports.

    Methodology:
        The _LOADED latch is set BEFORE the imports rather than after. A
        behaviour module importing something that reaches back into the
        registry would otherwise re-enter this function and import the same
        modules a second time; setting the latch first makes that re-entry a
        no-op instead of a loop.

    Notes/References:
        Same shape as typeclasses/spawners.load_all_spawners.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    global _LOADED

    if _LOADED:
        return

    _LOADED = True

    for module_name in _BEHAVIOR_MODULES:
        importlib.import_module(module_name)



def register_behavior(behavior_key: str):
    """
    Purpose: Decorator filing a behaviour callable under its key.

    Entry:
        behavior_key - the string an NpcDef's ai_behavior field carries. Use a
                       constant from systems/gameplay/ai/constants.py, not a literal.

    Exit/Returns:
        Returns the decorator, which returns the function unchanged so the
        behaviour stays directly callable and directly testable.

    Module Globals:
        BEHAVIOR_REGISTRY written.

    Methodology:
        A duplicate key is logged rather than raised. This runs at import time,
        and an exception here would take down whatever imported the module --
        for a name collision that leaves the game perfectly playable with one
        behaviour shadowed.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    def decorator(func):
        if behavior_key in BEHAVIOR_REGISTRY:
            logger.log_err(
                f"register_behavior: duplicate key {behavior_key!r}; "
                f"{func!r} shadows {BEHAVIOR_REGISTRY[behavior_key]!r}"
            )

        BEHAVIOR_REGISTRY[behavior_key] = func

        return func

    return decorator



def get_behavior(behavior_key: str):
    """
    Purpose: Look a behaviour up by key, loading the registry if needed.

    Entry:
        behavior_key - the key to resolve. None or "" resolves to None.

    Exit/Returns:
        The behaviour callable, or None if the key names nothing.

    Module Globals:
        BEHAVIOR_REGISTRY read.

    Methodology:
        Returns None instead of raising KeyError. The caller is the combat
        tick, where an exception is swallowed by the engine and the only
        visible symptom is an NPC that quietly stopped fighting; a None the
        caller can log is strictly more debuggable than a traceback nobody
        sees.

    Notes/References:
        docs/2026-08-23-DESIGN-0003 §5, first risk row.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    if not behavior_key:
        return None

    load_all_behaviors()

    behavior = BEHAVIOR_REGISTRY.get(behavior_key)

    return behavior



def behavior_key_for(npc) -> str:
    """
    Purpose: Name the behaviour this NPC runs, from its DEFINITION.

    Entry:
        npc - the NPC being asked for an action.

    Exit/Returns:
        Returns a key into BEHAVIOR_REGISTRY, or "" for an NPC that acts on
        nothing -- which is every player Character, and is not an error.

    Module Globals:
        AI_BEHAVIOR_ATTR read.

    Methodology:
        THE DEF IS READ BEFORE THE ROW, AND THE ORDER IS THE POINT. NpcDef
        stamps ai_behavior onto every NPC it spawns, so a changed default
        reaches new NPCs and no others: the raiders already standing in the
        world keep the key their spawn wrote, forever, and a retune of the AI
        looks like a retune that did nothing. Reading the def first means the
        fix to one line of content corrects every instance already in the
        database, with no migration and no map rebuild.

        This is TalkativeNPC._dialogue_module_for's arrangement, applied to
        the other fact NpcDef stamps. CLAUDE.md records both halves of the
        lesson under "An import path belongs in the code, never in a database
        row".

        The row is still the answer for an NPC that names no def -- a
        hand-built one, or a test fixture -- which is why it stays a fallback
        rather than being deleted.

    Notes/References:
        The NPC_DB import is deferred. This module is reached from
        systems/gameplay/combat/combat.py, which typeclass modules import at
        startup, and world/npc_database.py pulls in every NpcDef module.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    from world.npc_database import NPC_DB, NPC_KEY_ATTR

    npc_key = getattr(npc.db, NPC_KEY_ATTR, None)
    definition = NPC_DB.get(npc_key) if npc_key else None

    if definition is not None:
        return definition.ai_behavior or ""

    return getattr(npc.db, AI_BEHAVIOR_ATTR, None) or ""
