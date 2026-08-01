"""
Registry for room-spawner functions.

Each spawner is a callable ``(room) -> None`` registered under a
room prototype key (e.g. "Pole clearing").  GridTile reads the key
from its prototype and dispatches to the matching spawner at
post-spawn time, keeping GridTile itself open for extension.
"""

import importlib

SPAWNER_REGISTRY = {}

# Modules to import so their @register_spawner decorators run.
# Add new spawner modules here as they are created.
_SPAWNER_MODULES = [
    "typeclasses.gathering_nodes",
    "typeclasses.skill_facilities",
    "typeclasses.bank_nodes",
    "typeclasses.npcs",
    "typeclasses.npc_combat",
]

_LOADED = False

def load_all_spawners():
    global _LOADED
    if _LOADED:
        return
    for mod_name in _SPAWNER_MODULES:
        importlib.import_module(mod_name)
    _LOADED = True

def register_spawner(room_key):
    def decorator(f):
        SPAWNER_REGISTRY[room_key] = f
        return f
    return decorator


def spawn_once(room, typeclass_path, key, **kwargs):
    """
    Purpose: Create one object of `typeclass_path` in `room`, unless the room
    already holds one.

    Entry:
        room is an Evennia Room.
        typeclass_path is a full dotted typeclass path.
        key is the object key to create with.
        kwargs are forwarded to create_object.

    Exit/Returns:
        Returns the existing object if one was already present, the newly
        created object otherwise.

    Module Globals:
        None

    Methodology:
        Scan room.contents for an exact typeclass match; create only when
        absent. Spawners run every time a map tile is (re)spawned, so this
        guard is what keeps a rebuild from stacking duplicates.

    Notes/References:
        Every spawner previously carried its own copy of this
        `if not any(obj.is_typeclass(..., exact=True) ...)` block -- five
        identical guards that had to be written correctly each time.

    Author: Nick Hobar
    Creation date: 08/01/2026
    """
    from evennia import create_object

    for obj in room.contents:
        if obj.is_typeclass(typeclass_path, exact=True):
            return obj

    return create_object(typeclass_path, key=key, location=room, **kwargs)
