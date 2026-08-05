"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Master catalog of all action rules classes, discovered
             automatically from the rule_defs package tree.

Shape is deliberately identical to systems/combat/auras/registry.py, which is
itself identical to systems/progression/skills/registry.py. Same idiom, third
noun.
"""



import importlib
import inspect
import pkgutil

from evennia.utils import logger

from . import rule_defs as rule_defs_package
from .rule_defs.base_rules import ACTION_SEAM_NAMES, BaseActionRules



# Public constant definitions

# Modules under rule_defs/ that hold no concrete rules classes. base_rules
# defines the interface itself and is also the default implementation.
_EXCLUDED_MODULE_NAMES = frozenset({"base_rules"})

# Attribute the registry stamps on every discovered class, naming the seams it
# actually overrides. Read by the pipeline to pick a winner per seam.
OVERRIDDEN_SEAMS_ATTR = "_overridden_seams"



def _overridden_seams(rules_class) -> frozenset:
    """
    Purpose: Work out which of the nine seams a rules class actually replaces.

    Entry:
        rules_class - a BaseActionRules subclass.

    Exit/Returns:
        frozenset of seam names from ACTION_SEAM_NAMES that the class defines
        differently from BaseActionRules.

    Module Globals:
        ACTION_SEAM_NAMES read.

    Methodology:
        Compares the resolved function object against BaseActionRules's. This
        is deliberately STRUCTURAL rather than declared: the obvious
        alternative is an `overrides = ("roll_damage",)` tuple on each
        definition, which goes stale the first time someone adds a method and
        forgets to list it -- and the failure mode is silent, because the
        pipeline would simply never dispatch to the new override.

        Inheritance is handled for free: a subclass of a subclass reports both
        its own overrides and its parent's, because attribute lookup already
        resolved through the MRO.

    Notes/References:
        Computed once here, at discovery time, rather than per action -- this
        runs on a 0.6s tick for every combatant.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    overridden = set()

    for seam_name in ACTION_SEAM_NAMES:
        own = getattr(rules_class, seam_name, None)
        base = getattr(BaseActionRules, seam_name, None)

        if own is not base:
            overridden.add(seam_name)

    return frozenset(overridden)


def _iter_rules_modules():
    """
    Purpose: Yield the dotted path of every module under rule_defs/.

    Entry:
        No conditions.

    Exit/Returns:
        Yields fully-qualified module path strings.

    Module Globals:
        _EXCLUDED_MODULE_NAMES read.

    Methodology:
        pkgutil.walk_packages recurses the whole rule_defs tree, so a new
        category directory needs no registration -- dropping a file in is
        enough.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    package_path = rule_defs_package.__path__
    package_name = rule_defs_package.__name__

    for _finder, module_name, is_pkg in pkgutil.walk_packages(
        package_path, prefix=f"{package_name}."
    ):
        if is_pkg:
            continue

        leaf_name = module_name.rsplit(".", 1)[-1]
        if leaf_name in _EXCLUDED_MODULE_NAMES:
            continue

        yield module_name


def _discover_rules() -> dict:
    """
    Purpose: Build the master rules registry by importing every rules module.

    Entry:
        No conditions.

    Exit/Returns:
        Returns dict mapping rules key -> rules INSTANCE, each stamped with an
        _overridden_seams frozenset. Duplicate keys are logged and the first
        definition wins.

    Module Globals:
        OVERRIDDEN_SEAMS_ATTR read.

    Methodology:
        Import each module, then collect every BaseActionRules subclass DEFINED
        in that module (inspect the class's __module__ so a class merely
        imported into another module is not counted twice). A class without
        its own `key`, or one still carrying BaseActionRules's placeholder key,
        is skipped.

        Stores INSTANCES rather than classes, matching AURA_REGISTRY: a rules
        definition is stateless data plus overrides, so one shared instance per
        key is enough and every call site is spared a `()`.

        Each instance is stamped with its overridden-seam set here rather than
        on first use, because the pipeline consults it on every action.

    Notes/References:
        Import failures are logged and skipped rather than raised -- one broken
        rules file must not stop the combat package from importing at startup.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    registry = {}

    for module_path in _iter_rules_modules():
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            logger.log_trace(f"[RULES REGISTRY] Failed to import {module_path}: {exc}")
            continue

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BaseActionRules) or obj is BaseActionRules:
                continue

            # Only count a class in the module that actually defines it.
            if obj.__module__ != module_path:
                continue

            rules_key = getattr(obj, "key", None)
            if not rules_key or rules_key == BaseActionRules.key:
                logger.log_err(
                    f"[RULES REGISTRY] {obj.__name__} in {module_path} has no unique "
                    f"`key`; skipped."
                )
                continue

            if rules_key in registry:
                logger.log_err(
                    f"[RULES REGISTRY] Duplicate rules key '{rules_key}' in "
                    f"{module_path}; keeping {type(registry[rules_key]).__name__}."
                )
                continue

            instance = obj()
            seams = _overridden_seams(obj)
            setattr(instance, OVERRIDDEN_SEAMS_ATTR, seams)

            if not seams:
                logger.log_err(
                    f"[RULES REGISTRY] {obj.__name__} in {module_path} overrides no "
                    f"seam and contributes no modifiers; it will have no effect."
                )

            registry[rules_key] = instance

    return registry


def find_rules(key: str):
    """
    Purpose: Resolve a rules key to its registered instance.

    Entry:
        key - a registry key as stamped on an item's combat_rules list.

    Exit/Returns:
        Returns the matching rules instance, or None if nothing matches.

    Module Globals:
        RULES_REGISTRY read.

    Methodology:
        Exact key match only. Unlike find_aura there is no display-name or
        prefix fallback: rules keys are written by a developer in an ItemDef,
        never typed by a player, so a near-miss is a bug to surface rather
        than a guess to make.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    if not key:
        return None

    return RULES_REGISTRY.get(key)


RULES_REGISTRY: dict = _discover_rules()
