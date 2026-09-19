"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Every pop-up definition, found automatically in popup_defs/.

             The skill registry's arrangement (progression/skills/registry.py):
             walk the package, import each module, and keep every BasePopup
             subclass that the module itself defines. A new pop-up is one
             file, and a dispatch chain here would be the edit that someone
             forgets.

             Import this module LAZILY from anything a typeclass imports. A
             pop-up definition imports its own game system, and the bank's
             imports typeclasses/bank_nodes.py, which is where CmdBank lives.
"""

import importlib
import inspect
import pkgutil

from evennia.utils import logger

from . import popup_defs as popup_defs_package
from .popup_defs.base_popup import BasePopup


# ─── Private constant definitions ────────────────────────────────────────────

# Modules under popup_defs/ that hold no pop-up of their own.
_EXCLUDED_MODULE_NAMES: frozenset = frozenset({"base_popup"})


# ─── Module globals ──────────────────────────────────────────────────────────

# One line for each module or class that did not load. Empty when all is well.
# Filled by _discover_popups, which builds POPUP_REGISTRY at the end of this
# module.
LOAD_ERRORS: list = []


# ─── Private helper routines ─────────────────────────────────────────────────

def _iter_popup_modules():
    """Yield the dotted path of every module under popup_defs/."""
    package_path = popup_defs_package.__path__
    package_name = popup_defs_package.__name__

    for _finder, module_name, is_pkg in pkgutil.walk_packages(
        package_path, prefix=f"{package_name}."
    ):
        if is_pkg:
            continue

        leaf_name = module_name.rsplit(".", 1)[-1]

        if leaf_name in _EXCLUDED_MODULE_NAMES:
            continue

        yield module_name


def _popups_in(module) -> list:
    """Return the BasePopup subclasses that `module` itself defines."""
    found = []

    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if not issubclass(obj, BasePopup) or obj is BasePopup:
            continue

        if obj.__module__ != module.__name__:
            continue

        found.append(obj)

    return found


def _discover_popups() -> dict:
    """
    Purpose: Build the registry by importing every pop-up module.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a dict of pop-up key -> one instance of its class.

    Module Globals:
        LOAD_ERRORS written.

    Methodology:
        1. Import each module under popup_defs/.
        2. If an import fails, log it and go on to the next module.
        3. Skip a class with no key, and keep the first class for a duplicate.

    Notes/References:
        LOAD_ERRORS keeps each failure, so a test makes a broken pop-up loud.
        The quest loader learned that from an empty registry.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    registry = {}

    for module_path in _iter_popup_modules():
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            LOAD_ERRORS.append(f"{module_path}: {exc}")
            logger.log_trace(f"[POPUP REGISTRY] Failed to import {module_path}")
            continue

        for popup_class in _popups_in(module):
            popup_key = popup_class.key

            if not popup_key or popup_key in registry:
                LOAD_ERRORS.append(f"{popup_class.__name__}: bad or duplicate key")
                continue

            registry[popup_key] = popup_class()

    return registry


# ─── The registry ────────────────────────────────────────────────────────────

POPUP_REGISTRY: dict = _discover_popups()


# ─── Public routines ─────────────────────────────────────────────────────────

def get_popup(popup_key: str):
    """Return the pop-up registered under `popup_key`, or None."""
    return POPUP_REGISTRY.get(popup_key)
