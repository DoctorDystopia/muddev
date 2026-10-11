"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: BUFF_REGISTRY, found from the buff_defs package, and the one
             collector that combat calls for the buffs of an action.

             The discovery is the idiom of combat/rules/registry.py. Each
             buff instance carries the same seam stamp that a rules
             instance carries, so the combat pipeline treats the two the
             same. DESIGN-0012, Phase 3.
"""

import importlib
import inspect
import pkgutil

from evennia.utils import logger

from systems.gameplay.combat.rules.registry import OVERRIDDEN_SEAMS_ATTR, overridden_seams

from . import buff_defs as buff_defs_package
from .preceptors import pool_entry
from .buff_defs.base_buff import BASE_BUFF_KEY, BaseExterminatorBuff



# Modules under buff_defs/ that hold no concrete buff.
_EXCLUDED_MODULE_NAMES = frozenset({"base_buff"})



# ─── Private helper routines ────────────────────────────────────────────────

def _iter_buff_modules():
    """Yield the dotted path of every module under buff_defs/."""
    package_path = buff_defs_package.__path__
    package_name = buff_defs_package.__name__

    for _finder, module_name, is_pkg in pkgutil.walk_packages(
        package_path, prefix=f"{package_name}."
    ):
        leaf_name = module_name.rsplit(".", 1)[-1]

        if is_pkg or leaf_name in _EXCLUDED_MODULE_NAMES:
            continue

        yield module_name


def _buff_classes(module, module_path: str) -> list:
    """Every buff class DEFINED in one module, with its own key."""
    found = []

    for _name, obj in inspect.getmembers(module, inspect.isclass):
        is_buff = issubclass(obj, BaseExterminatorBuff) and obj is not BaseExterminatorBuff

        if not is_buff or obj.__module__ != module_path:
            continue

        if not obj.key or obj.key == BASE_BUFF_KEY:
            logger.log_err(f"[BUFF REGISTRY] {obj.__name__} has no unique `key`; skipped.")
            continue

        found.append(obj)

    return found


def _discover_buffs() -> dict:
    """
    Purpose: Build the buff registry by importing every buff module.

    Entry:
        No conditions.

    Exit/Returns:
        Returns {buff key: stamped buff instance}. A duplicate key is logged,
        and the first one stays.

    Module Globals:
        None.

    Methodology:
        1. Import each module under buff_defs/. Log and skip one that fails.
        2. Take each buff class that the module defines.
        3. Make one instance, and stamp its overridden seams.

    Notes/References:
        _discover_rules in combat/rules/registry.py is the model.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    registry = {}

    for module_path in _iter_buff_modules():
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            logger.log_trace(f"[BUFF REGISTRY] Failed to import {module_path}: {exc}")
            continue

        for buff_class in _buff_classes(module, module_path):
            if buff_class.key in registry:
                logger.log_err(f"[BUFF REGISTRY] Duplicate buff key {buff_class.key!r}.")
                continue

            registry[buff_class.key] = instantiate(buff_class)

    return registry



# ─── Public routines ────────────────────────────────────────────────────────

def instantiate(buff_class) -> BaseExterminatorBuff:
    """
    Purpose: Make one buff instance that the combat pipeline can read.

    Entry:
        buff_class is a BaseExterminatorBuff subclass.

    Exit/Returns:
        Returns an instance, stamped with its overridden seams.

    Module Globals:
        OVERRIDDEN_SEAMS_ATTR read.

    Methodology:
        The pipeline reads the stamp to pick a winner for each seam. A test
        buff goes through this routine too, so it is stamped the same way.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    instance = buff_class()
    seams = overridden_seams(buff_class)
    setattr(instance, OVERRIDDEN_SEAMS_ATTR, seams)

    return instance


def active_buffs(holder, opponent) -> tuple:
    """
    Purpose: Give the held buffs of one entity that work in one action.

    Entry:
        holder is one side of the action. opponent is the other side.

    Exit/Returns:
        Returns a tuple of buff instances. Empty for an NPC, for a player
        with no buff, and against a creature of another type. Never raises.

    Module Globals:
        BUFF_REGISTRY read.

    Methodology:
        1. If the holder has no Exterminator handler or no held buff, stop.
        2. Find each held key in BUFF_REGISTRY. Log and skip an unknown key.
        3. Keep each buff whose applies_to passes for this opponent.

    Notes/References:
        _build_context in combat.py calls this for the attacker against the
        defender, and for the defender against the attacker. The result goes
        through merge_contributors, never into handler.ndb.active_rules.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    handler = getattr(holder, "exterminator", None)

    if handler is None:
        return ()

    try:
        held = handler.held_buffs()
        found = []

        for buff_key in held:
            buff = BUFF_REGISTRY.get(buff_key)

            if buff is None:
                logger.log_err(f"active_buffs: {holder} holds unknown buff {buff_key!r}.")
                continue

            if buff.applies_to(holder, opponent):
                found.append(buff)

        return tuple(found)
    except Exception as exc:
        logger.log_err(f"active_buffs: {holder} against {opponent} failed: {exc!r}")
        return ()


def buff_name(buff, preceptor_key) -> str:
    """
    Purpose: Give the display name of one buff, as one Preceptor names it.

    Entry:
        buff is a buff instance. preceptor_key is a key of PRECEPTOR_DB, or
        None.

    Exit/Returns:
        Returns the `name` of the PoolEntry of the buff in the pool of that
        Preceptor. Returns the plain `name` of the buff class when the entry
        has no name, or the Preceptor does not list the buff.

    Module Globals:
        None.

    Methodology:
        The vault note: a pool gives each archetype its own name, so two
        Preceptors can name one buff two ways. Every reader of a buff name
        calls this routine: the cards, the held buffs line, and the pick
        message.

    Notes/References:
        No entry of Quin has a name yet, so his buffs show the plain names
        (Nick, 10/07/2026).

    Author: Nick Hobar
    Creation date: 10/07/2026
    """
    entry = pool_entry(preceptor_key, buff.key)

    if entry is None or not entry.name:
        return buff.name

    return entry.name


BUFF_REGISTRY: dict = _discover_buffs()
