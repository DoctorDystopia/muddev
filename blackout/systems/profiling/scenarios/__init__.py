"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: The scenario registry -- what the harness knows how to profile.

             Adding a profiling target is adding one decorated function to one
             module in this package. Nothing dispatches on a scenario's name
             and nothing holds a list of them, which is the same arrangement
             `@register_spawner` makes in typeclasses/spawners.py and for the
             same reason: a hand-maintained list is a thing that goes stale
             silently, and a profiling target that silently stopped running is
             worse than one that was never written.

Why a scenario is a factory rather than the work itself
-------------------------------------------------------
A decorated function receives the world fixture and RETURNS the zero-argument
callable to be measured. Everything the function does before that return --
finding rooms, spawning an NPC, resolving a handler -- is setup, and setup is
not measured. Handing the harness the work directly would have folded fixture
construction into every reported number, which is precisely the mistake that
makes a profile blame whichever scenario has the most expensive setup.

Why the layer is declared and not inferred
------------------------------------------
A statefeed scenario that happens to issue queries is still a statefeed
scenario. Grouping by what the code touches would put it under `database` and
lose the question the audit is asking, so the author says which layer the
scenario is a measurement OF, and constants.PIPELINE_LAYERS closes the set.
"""

import importlib
import pkgutil
from dataclasses import dataclass

from .. import constants as const


# ─── Public data structures ──────────────────────────────────────────────────

@dataclass
class Scenario:
    """One registered profiling target."""

    name: str
    layer: str
    factory: object
    repeat: int
    warmup: int
    notes: str


# ─── Module globals ──────────────────────────────────────────────────────────

# Insertion-ordered, and the order IS the report's order within a layer. A
# scenario registered after another is one whose result reads as a refinement
# of it, so the coarse measurement is meant to come first.
SCENARIO_REGISTRY: dict = {}

# Set once by discover(), so that a second call from a second entry point does
# not re-import every module and double-register every scenario.
_discovered = False


# ─── Public routines ─────────────────────────────────────────────────────────

def scenario(name: str,
             layer: str,
             repeat: int = const.DEFAULT_REPEAT,
             warmup: int = const.DEFAULT_WARMUP,
             notes: str = ""):
    """
    Purpose: Register a scenario factory under a name and a pipeline layer.

    Entry:
        name   - unique across the whole registry. A duplicate raises, because
                 the alternative is one scenario silently replacing another and
                 the report showing the right number of rows with the wrong
                 content.
        layer  - one of constants.PIPELINE_LAYERS.
        repeat - measured passes. Lower it for a scenario whose single pass is
                 already slow; the report divides by it either way.
        warmup - discarded passes before measurement.
        notes  - free text shown beside the result, for saying what a number
                 means when the name cannot.

    Exit/Returns:
        Returns the decorator, which returns the factory unchanged so that the
        function stays directly callable from a test.

    Module Globals:
        SCENARIO_REGISTRY written.

    Methodology:
        Validation happens at decoration time -- which is import time -- so a
        typo in a layer name is an ImportError during discovery rather than a
        KeyError halfway through a ten-minute profiling run.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    if layer not in const.PIPELINE_LAYERS:
        raise ValueError(f"unknown pipeline layer {layer!r} for scenario {name!r}")

    def register(factory):
        if name in SCENARIO_REGISTRY:
            raise ValueError(f"duplicate profiling scenario: {name!r}")

        SCENARIO_REGISTRY[name] = Scenario(name=name,
                                           layer=layer,
                                           factory=factory,
                                           repeat=repeat,
                                           warmup=warmup,
                                           notes=notes)
        return factory

    return register


def discover() -> dict:
    """
    Purpose: Import every scenario module in this package so its decorators run.

    Entry:
        No conditions.

    Exit/Returns:
        Returns SCENARIO_REGISTRY, populated. Safe to call repeatedly; the
        second call is a no-op that returns the same dict.

    Module Globals:
        _discovered read and written; SCENARIO_REGISTRY written indirectly by
        the decorators the imports run.

    Methodology:
        pkgutil over this package's own path, skipping private modules. This is
        the arrangement systems/progression/skills/registry.py uses, chosen
        over a settings-driven list because a profiling scenario has no reason
        to be switchable per deployment.

        An import failure is NOT swallowed. The quest loader's `except
        Exception` around content imports is exactly how GLOBAL_QUEST_REGISTRY
        came up empty for weeks (see CLAUDE.md), and a profiling harness that
        quietly measures four of its nine scenarios would report an audit with
        no bottlenecks in the layers whose module failed to import.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    global _discovered

    if _discovered:
        return SCENARIO_REGISTRY

    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue

        importlib.import_module(f"{__name__}.{module_info.name}")

    _discovered = True

    return SCENARIO_REGISTRY


def scenarios_for(layers=()) -> list:
    """
    Purpose: List the registered scenarios, optionally narrowed to some layers.

    Entry:
        layers - an iterable of layer names. Empty means every layer.

    Exit/Returns:
        Returns a list of Scenario objects in registration order, grouped by
        the declared order of constants.PIPELINE_LAYERS so a report walks the
        pipeline front to back.

    Module Globals:
        SCENARIO_REGISTRY read.

    Methodology:
        Discovery is triggered here rather than at module import, so that
        importing the registry to read its decorator does not drag in every
        game system a scenario touches.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    registry = discover()
    wanted = set(layers) if layers else set(const.PIPELINE_LAYERS)
    ordered = []

    for layer in const.PIPELINE_LAYERS:
        if layer not in wanted:
            continue

        for entry in registry.values():
            if entry.layer == layer:
                ordered.append(entry)

    return ordered
