"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The augment registry. Auto-discovers every BaseAugment subclass
             under augment_defs/, the arrangement of auras/registry.py. A
             new augment is one file there, and it is in the registry at
             the next import.
"""

import importlib
import inspect
import pkgutil

from evennia.utils import logger

from . import augment_defs as augment_defs_package
from .augment_defs.base_augment import BASE_AUGMENT_KEY, BaseAugment


# Private constant definitions

# Modules under augment_defs/ that hold no concrete augment classes.
_EXCLUDED_MODULE_NAMES = frozenset({"base_augment"})


# Private helper routines

def _iter_augment_modules():
    """
    Purpose: Yield the dotted path of every module under augment_defs/.

    Entry:
        No conditions.

    Exit/Returns:
        Yields fully-qualified module path strings.

    Module Globals:
        _EXCLUDED_MODULE_NAMES read.

    Methodology:
        pkgutil.walk_packages recurses the whole tree, so a new category
        directory needs no registration.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    package_path = augment_defs_package.__path__
    package_name = augment_defs_package.__name__

    for _finder, module_name, is_pkg in pkgutil.walk_packages(
        package_path, prefix=f"{package_name}."
    ):
        if is_pkg:
            continue

        leaf_name = module_name.rsplit(".", 1)[-1]

        if leaf_name in _EXCLUDED_MODULE_NAMES:
            continue

        yield module_name


def _augment_classes(module, module_path: str) -> list:
    """Every augment class DEFINED in one module, with its own key."""
    found = []

    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if not issubclass(obj, BaseAugment) or obj is BaseAugment:
            continue

        if obj.__module__ != module_path:
            continue

        # A shape that several augments share, such as the guard base.
        # `abstract` is read off the class __dict__, so a subclass that
        # does not set it is a real augment.
        if obj.__dict__.get("abstract", False):
            continue

        if not obj.key or obj.key == BASE_AUGMENT_KEY:
            logger.log_err(
                f"[AUGMENT REGISTRY] {obj.__name__} in {module_path} has no "
                f"unique `key`; skipped.")
            continue

        found.append(obj)

    return found


def _discover_augments() -> dict:
    """
    Purpose: Build the augment registry by importing every augment module.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a dict of augment key to augment INSTANCE. A duplicate key
        is logged, and the first definition wins.

    Module Globals:
        None.

    Methodology:
        1. Import each module. Log and skip one that fails.
        2. File each augment class that the module defines, as an instance.
           An augment is data plus three routines, so one instance for each
           key is enough.

    Notes/References:
        The shape of auras/registry.py.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    registry = {}

    for module_path in _iter_augment_modules():
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            logger.log_trace(f"[AUGMENT REGISTRY] Failed to import {module_path}: {exc}")
            continue

        for augment_class in _augment_classes(module, module_path):
            if augment_class.key in registry:
                logger.log_err(
                    f"[AUGMENT REGISTRY] Duplicate augment key "
                    f"{augment_class.key!r} in {module_path}; skipped.")
                continue

            registry[augment_class.key] = augment_class()

    return registry


# Module globals

AUGMENT_REGISTRY: dict = _discover_augments()


# Public routines

def find_augment(name: str):
    """
    Purpose: Resolve a typed name to an augment.

    Entry:
        name is any string. May be empty.

    Exit/Returns:
        Returns the augment instance, or None.

    Module Globals:
        AUGMENT_REGISTRY read.

    Methodology:
        1. An exact match on the key (with spaces as underscores) or on the
           lower-case name wins.
        2. Else, one unique prefix of a name wins. A prefix that matches
           two augments returns None rather than a guess.

    Notes/References:
        The shape of find_aura.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    if not name:
        return None

    needle = name.strip().lower()
    underscored = needle.replace(" ", "_")

    for augment_key, augment in AUGMENT_REGISTRY.items():
        if underscored == augment_key or needle == augment.name.lower():
            return augment

    prefix_matches = [
        augment
        for augment in AUGMENT_REGISTRY.values()
        if augment.name.lower().startswith(needle)
    ]

    if len(prefix_matches) == 1:
        return prefix_matches[0]

    return None


def get_augments_for_skill(skill_key: str) -> list:
    """
    Purpose: Every augment that the Augmentation skill unlocks at a level.

    Entry:
        skill_key is a skill key string.

    Exit/Returns:
        Returns a list of augment instances, sorted by (unlock_level, name),
        for the Augmentation key. An augment with NO_UNLOCK_LEVEL is left
        out: it gates nothing. Any other key returns [].

    Module Globals:
        AUGMENT_REGISTRY read.

    Methodology:
        The shape of auras.registry.get_auras_for_skill. Every augment
        scales with one skill, so the key test is one comparison. The
        skills constants are imported inside the routine, as pool.py does.

    Notes/References:
        skills/detail.py reads this for the Skills pane.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    from systems.gameplay.augmentation import constants as aug_const
    from systems.gameplay.progression.skills.constants import SKILL_KEY_AUGMENTATION

    if skill_key != SKILL_KEY_AUGMENTATION:
        return []

    matches = [
        augment
        for augment in AUGMENT_REGISTRY.values()
        if augment.unlock_level > aug_const.NO_UNLOCK_LEVEL
    ]

    matches.sort(key=lambda entry: (entry.unlock_level, entry.name))

    return matches


def augments_in_order() -> list:
    """
    Purpose: Every augment, in the order of the rail and the listing.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a list of augment instances, sorted by (unlock_level, name).

    Module Globals:
        AUGMENT_REGISTRY read.

    Methodology:
        One sort. The order is the server's. The client draws the rows in
        the order it gets them.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    ordered = sorted(AUGMENT_REGISTRY.values(),
                     key=lambda augment: (augment.unlock_level, augment.name))

    return ordered
