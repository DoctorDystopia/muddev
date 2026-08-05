"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/03/2026
Description: Master catalog of all damage aura classes, discovered
             automatically from the aura_defs package tree.

Shape is deliberately identical to systems/progression/skills/registry.py.
The repo already has four registry idioms; this is not a fifth.
"""



import importlib
import inspect
import pkgutil

from evennia.utils import logger

from . import aura_defs as aura_defs_package
from .aura_defs.base_aura import BaseAura



# Public constant definitions

# Modules under aura_defs/ that hold no concrete aura classes. base_aura
# defines the interface itself.
_EXCLUDED_MODULE_NAMES = frozenset({"base_aura"})



def _iter_aura_modules():
    """
    Purpose: Yield the dotted path of every module under aura_defs/.

    Entry:
        No conditions.

    Exit/Returns:
        Yields fully-qualified module path strings.

    Module Globals:
        _EXCLUDED_MODULE_NAMES read.

    Methodology:
        pkgutil.walk_packages recurses the whole aura_defs tree, so a new
        category directory needs no registration -- dropping a file in is
        enough.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    package_path = aura_defs_package.__path__
    package_name = aura_defs_package.__name__

    for _finder, module_name, is_pkg in pkgutil.walk_packages(
        package_path, prefix=f"{package_name}."
    ):
        if is_pkg:
            continue

        leaf_name = module_name.rsplit(".", 1)[-1]
        if leaf_name in _EXCLUDED_MODULE_NAMES:
            continue

        yield module_name


def _discover_auras() -> dict:
    """
    Purpose: Build the master aura registry by importing every aura module.

    Entry:
        No conditions.

    Exit/Returns:
        Returns dict mapping aura key -> aura INSTANCE. Duplicate keys are
        logged and the first definition wins.

    Module Globals:
        None

    Methodology:
        Import each module, then collect every BaseAura subclass DEFINED in that
        module (inspect the class's __module__ so a class merely imported into
        another module is not counted twice). A class without its own `key`, or
        one still carrying BaseAura's placeholder key, is skipped.

        Stores INSTANCES rather than classes: an aura is stateless data plus
        three hooks, so one shared instance per key is enough, and every call
        site is spared a `()`. This is the one intentional divergence from
        SKILL_REGISTRY, which stores classes because skills are instantiated
        per use.

    Notes/References:
        Import failures are logged and skipped rather than raised -- one broken
        aura file must not stop the combat package from importing at startup.

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    registry = {}

    for module_path in _iter_aura_modules():
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            logger.log_trace(f"[AURA REGISTRY] Failed to import {module_path}: {exc}")
            continue

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BaseAura) or obj is BaseAura:
                continue

            # Only count a class in the module that actually defines it.
            if obj.__module__ != module_path:
                continue

            aura_key = getattr(obj, "key", None)
            if not aura_key or aura_key == BaseAura.key:
                logger.log_err(
                    f"[AURA REGISTRY] {obj.__name__} in {module_path} has no unique "
                    f"`key`; skipped."
                )
                continue

            if aura_key in registry:
                logger.log_err(
                    f"[AURA REGISTRY] Duplicate aura key '{aura_key}' in "
                    f"{module_path}; keeping {type(registry[aura_key]).__name__}."
                )
                continue

            registry[aura_key] = obj()

    return registry


def find_aura(name: str):
    """
    Purpose: Resolve a player-typed aura name to a registered aura.

    Entry:
        name - raw player input, e.g. "righteous fire" or "righteous_fire".

    Exit/Returns:
        Returns the matching aura instance, or None if nothing matches.

    Module Globals:
        AURA_REGISTRY read.

    Methodology:
        Players type display names with spaces; keys use underscores. Match on
        the key first, then on the display name, both case-insensitively, then
        accept an unambiguous prefix of a display name so "right" works. A
        prefix matching more than one aura returns None rather than guessing.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    if not name:
        return None

    needle = name.strip().lower()
    underscored = needle.replace(" ", "_")

    for aura_key, aura in AURA_REGISTRY.items():
        if underscored == aura_key or needle == aura.name.lower():
            return aura

    prefix_matches = [
        aura
        for aura in AURA_REGISTRY.values()
        if aura.name.lower().startswith(needle)
    ]

    if len(prefix_matches) == 1:
        return prefix_matches[0]

    return None


AURA_REGISTRY: dict = _discover_auras()
