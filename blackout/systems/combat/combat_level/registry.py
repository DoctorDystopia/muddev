"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Master catalog of all combat-level branches, discovered
             automatically from the branch_defs package tree.

Shape is deliberately identical to systems/progression/skills/registry.py and
systems/combat/auras/registry.py. The repo already has enough registry
idioms; this is not a new one.
"""



import importlib
import inspect
import pkgutil

from evennia.utils import logger

from . import branch_defs as branch_defs_package
from .branch_defs.base_branch import CombatBranch, BASE_BRANCH_KEY



# Public constant definitions

# Modules under branch_defs/ that hold no concrete branch classes. base_branch
# defines the interface itself.
_EXCLUDED_MODULE_NAMES = frozenset({"base_branch"})



def _iter_branch_modules():
    """
    Purpose: Yield the dotted path of every module under branch_defs/.

    Entry:
        No conditions.

    Exit/Returns:
        Yields fully-qualified module path strings.

    Module Globals:
        _EXCLUDED_MODULE_NAMES read.

    Methodology:
        pkgutil.walk_packages recurses the whole branch_defs tree, so a new
        Combat Specialty's branch needs no registration -- dropping a file
        in is enough.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    package_path = branch_defs_package.__path__
    package_name = branch_defs_package.__name__

    for _finder, module_name, is_pkg in pkgutil.walk_packages(
        package_path, prefix=f"{package_name}."
    ):
        if is_pkg:
            continue

        leaf_name = module_name.rsplit(".", 1)[-1]
        if leaf_name in _EXCLUDED_MODULE_NAMES:
            continue

        yield module_name


def _discover_branches() -> dict:
    """
    Purpose: Build the master combat-branch registry by importing every
    branch module.

    Entry:
        No conditions.

    Exit/Returns:
        Returns dict mapping branch key -> branch INSTANCE. Duplicate keys
        are logged and the first definition wins.

    Module Globals:
        None

    Methodology:
        Import each module, then collect every CombatBranch subclass DEFINED
        in that module (inspect the class's __module__ so a class merely
        imported into another module is not counted twice). A class without
        its own `key`, or one still carrying CombatBranch's placeholder key,
        is skipped.

        Stores INSTANCES rather than classes: a branch is stateless data plus
        one hook, so one shared instance per key is enough. Matches
        AURA_REGISTRY, the same shape for the same reason.

    Notes/References:
        Import failures are logged and skipped rather than raised -- one
        broken branch file must not stop combat_level from importing at
        startup.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    registry = {}

    for module_path in _iter_branch_modules():
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            logger.log_trace(f"[COMBAT BRANCH REGISTRY] Failed to import {module_path}: {exc}")
            continue

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, CombatBranch) or obj is CombatBranch:
                continue

            # Only count a class in the module that actually defines it.
            if obj.__module__ != module_path:
                continue

            branch_key = getattr(obj, "key", None)
            if not branch_key or branch_key == BASE_BRANCH_KEY:
                logger.log_err(
                    f"[COMBAT BRANCH REGISTRY] {obj.__name__} in {module_path} has no "
                    f"unique `key`; skipped."
                )
                continue

            if branch_key in registry:
                logger.log_err(
                    f"[COMBAT BRANCH REGISTRY] Duplicate branch key '{branch_key}' in "
                    f"{module_path}; keeping {type(registry[branch_key]).__name__}."
                )
                continue

            registry[branch_key] = obj()

    return registry


COMBAT_BRANCH_REGISTRY: dict = _discover_branches()
