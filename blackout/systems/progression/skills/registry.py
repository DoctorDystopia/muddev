"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Master catalog of all playable skill classes, discovered
             automatically from the skill_defs package tree.
"""



import importlib
import inspect
import pkgutil

from evennia.utils import logger

from . import skill_defs as skill_defs_package
from .skill_defs.base_skill import BaseSkill



# Public constant definitions

# Modules under skill_defs/ that hold no skill classes. base_skill defines the
# interface itself; the *_skills.py container modules are the hand-maintained
# dicts this auto-discovery replaces and are kept only as import shims.
_EXCLUDED_MODULE_NAMES = frozenset({"base_skill"})



def _iter_skill_modules():
    """
    Purpose: Yield the dotted path of every module under skill_defs/.

    Entry:
        No conditions.

    Exit/Returns:
        Yields fully-qualified module path strings.

    Module Globals:
        _EXCLUDED_MODULE_NAMES read.

    Methodology:
        pkgutil.walk_packages recurses the whole skill_defs tree, so a new
        category directory needs no registration -- dropping a file in is
        enough. Mirrors systems/quests/loader.py's content-package walk.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    package_path = skill_defs_package.__path__
    package_name = skill_defs_package.__name__

    for _finder, module_name, is_pkg in pkgutil.walk_packages(
        package_path, prefix=f"{package_name}."
    ):
        if is_pkg:
            continue

        leaf_name = module_name.rsplit(".", 1)[-1]
        if leaf_name in _EXCLUDED_MODULE_NAMES:
            continue

        yield module_name


def _discover_skills() -> dict:
    """
    Purpose: Build the master skill registry by importing every skill module.

    Entry:
        No conditions.

    Exit/Returns:
        Returns dict mapping skill key -> skill class. Duplicate keys are
        logged and the first definition wins.

    Module Globals:
        None

    Methodology:
        Import each module, then collect every BaseSkill subclass DEFINED in
        that module (inspect the class's __module__ so a class merely imported
        into a container module is not counted twice). A class without its own
        `key`, or one still carrying BaseSkill's placeholder key, is skipped.

    Notes/References:
        Replaces the previous chain of per-category *_skills.py container
        dicts plus a hand-edited merge, which required three edits to add one
        skill and silently dropped any category whose import line was
        commented out.

    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    registry = {}

    for module_path in _iter_skill_modules():
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            logger.log_trace(f"[SKILL REGISTRY] Failed to import {module_path}: {exc}")
            continue

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BaseSkill) or obj is BaseSkill:
                continue

            # Only count a class in the module that actually defines it.
            if obj.__module__ != module_path:
                continue

            skill_key = getattr(obj, "key", None)
            if not skill_key or skill_key == BaseSkill.key:
                logger.log_err(
                    f"[SKILL REGISTRY] {obj.__name__} in {module_path} has no unique "
                    f"`key`; skipped."
                )
                continue

            if skill_key in registry:
                logger.log_err(
                    f"[SKILL REGISTRY] Duplicate skill key '{skill_key}' in "
                    f"{module_path}; keeping {registry[skill_key].__name__}."
                )
                continue

            registry[skill_key] = obj

    return registry


SKILL_REGISTRY: dict = _discover_skills()
