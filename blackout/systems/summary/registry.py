"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Auto-discovered catalog of summary-screen panels.
"""

import importlib
import inspect
import pkgutil

from evennia.utils import logger

from . import panel_defs as panel_defs_package
from .panel_defs.base_panel import BasePanel


# Public constant definitions

# Modules under panel_defs/ that hold no panel classes. base_panel defines the
# interface itself.
_EXCLUDED_MODULE_NAMES = frozenset({"base_panel"})


def _iter_panel_modules():
    """
    Purpose: Yield the dotted path of every module under panel_defs/.

    Entry:
        No conditions.

    Exit/Returns:
        Yields fully-qualified module path strings.

    Module Globals:
        _EXCLUDED_MODULE_NAMES read.

    Methodology:
        pkgutil.walk_packages recurses the whole tree, so a future
        sub-directory of panels (say panel_defs/social/) needs no registration.
        Mirrors systems/progression/skills/registry.py exactly.

    Notes/References:
        This walk is confined to systems/summary/panel_defs/. It must never be
        pointed at a wider path -- CLAUDE.md §"Danger: blackout/scripts/"
        records what a bulk module import across blackout/ once did.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    package_path = panel_defs_package.__path__
    package_name = panel_defs_package.__name__

    for _finder, module_name, is_pkg in pkgutil.walk_packages(
        package_path, prefix=f"{package_name}."
    ):
        if is_pkg:
            continue

        leaf_name = module_name.rsplit(".", 1)[-1]
        if leaf_name in _EXCLUDED_MODULE_NAMES:
            continue

        yield module_name


def _discover_panels() -> dict:
    """
    Purpose: Build the panel registry by importing every panel module.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a dict mapping panel key -> panel class, ordered by each
        class's `order` then its key. Python dicts preserve insertion order,
        so the caller iterates rather than re-sorting.

    Module Globals:
        None.

    Methodology:
        Import each module, then collect every BasePanel subclass DEFINED in
        that module -- inspect.__module__ so a class merely imported into
        another panel is not registered twice. A class without its own `key` is
        logged and skipped rather than silently absorbed under the empty
        placeholder, which would let one broken panel evict another.

        A module that fails to import is logged and skipped. A syntax error in
        one panel must cost the player that band, not the whole `score`
        command.

    Notes/References:
        Ordering by `order` and only then by key means two panels that forgot
        to set an order still render deterministically rather than in
        filesystem-walk order.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    discovered = []

    for module_path in _iter_panel_modules():
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            logger.log_trace(f"[SUMMARY REGISTRY] Failed to import {module_path}: {exc}")
            continue

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BasePanel) or obj is BasePanel:
                continue

            if obj.__module__ != module_path:
                continue

            panel_key = getattr(obj, "key", None)
            if not panel_key:
                logger.log_err(
                    f"[SUMMARY REGISTRY] {obj.__name__} in {module_path} has no "
                    f"`key`; skipped."
                )
                continue

            discovered.append(obj)

    discovered.sort(key=lambda panel: (panel.order, panel.key))

    registry = {}
    for panel in discovered:
        if panel.key in registry:
            logger.log_err(
                f"[SUMMARY REGISTRY] Duplicate panel key '{panel.key}'; keeping "
                f"{registry[panel.key].__name__}."
            )
            continue

        registry[panel.key] = panel

    return registry


PANEL_REGISTRY: dict = _discover_panels()
