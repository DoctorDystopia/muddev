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
