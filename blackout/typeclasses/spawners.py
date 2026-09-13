"""
Registry for room-spawner functions.

TWO registries, because a tile answers two different questions.

WHAT THE TILE IS -- one answer. ``SPAWNER_REGISTRY`` is keyed on the room
prototype key ("Bank", "Foundry Furnace Facility"), and a tile has exactly one
key, so it stands up exactly one occupant. That is the right shape for the
thing the tile exists for.

WHAT ELSE IS ON IT -- as many answers as it declares.
``ATTRIBUTE_SPAWNER_REGISTRY`` is keyed on a room ATTRIBUTE name, and every
registered spawner whose attribute the room carries runs. A signpost labelling
the furnace is the case this was added for: the tile's key is already
"Foundry Furnace Facility" and cannot also be "Signpost", so signage keyed on
the room key could never share a tile with anything. Keyed on
``signpost_label`` it shares a tile with everything, and needs no edit to the
facility it is labelling.

Both are dispatched by ``GridTile.at_object_post_spawn``, which is handed the
prototype after its attributes have been applied -- so the key and the
attributes are both readable by the time a spawner runs.

The two differ in one more way, and it is deliberate: a failing ATTRIBUTE
spawner is contained and logged, a failing key spawner is not. See that hook.
"""

import importlib

SPAWNER_REGISTRY = {}

# room attribute name -> spawner callable. See the module docstring for why
# this is separate from SPAWNER_REGISTRY rather than a second entry in it.
ATTRIBUTE_SPAWNER_REGISTRY = {}

# Modules to import so their @register_spawner decorators run.
# Add new spawner modules here as they are created.
_SPAWNER_MODULES = [
    "typeclasses.gathering_nodes",
    "typeclasses.skill_facilities",
    "typeclasses.bank_nodes",
    "typeclasses.npcs",
    "typeclasses.npc_combat",
    "typeclasses.signs",
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


def register_attribute_spawner(attr_name):
    """
    Purpose: Record a spawner that runs on any tile declaring `attr_name`,
             whatever that tile's room key is.

    Entry:
        attr_name is the room attribute a map sets to ask for this. The
        decorated callable takes the room and returns whatever it likes; the
        return is ignored by the dispatcher and used by tests.

    Exit/Returns:
        Returns a decorator, so this reads like @register_spawner above.

    Module Globals:
        ATTRIBUTE_SPAWNER_REGISTRY written.

    Methodology:
        The decorated spawner must be IDEMPOTENT, because it runs on every
        rebuild of every tile carrying the attribute -- `spawn_once` is the
        guard written for exactly that.

        It must also tolerate the attribute being present and empty. A map
        author who deletes the text and leaves the key behind gets nothing
        spawned rather than a blank object, and the spawner is the only place
        that can tell the difference.

    Notes/References:
        Added 09/12/2026 so a signpost could share a tile with the facility it
        labels. The module docstring has the argument.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    def decorator(f):
        ATTRIBUTE_SPAWNER_REGISTRY[attr_name] = f

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
