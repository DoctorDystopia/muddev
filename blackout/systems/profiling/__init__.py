"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: The profiling harness -- the package's public surface.

             Nothing in the game imports this package. That is the design
             constraint it is built around, not an accident of it being new:
             profiling code that production logic depends on is profiling code
             that ships, and the seams this harness attaches to (the tick's
             register_phase_hook, Django's connection, cProfile) all already
             exist for other reasons.

             The dependency arrow points one way, always: profiling -> game.
             A test asserting that is in tests/test_isolation.py, because the
             rule is one a well-meaning future edit breaks by adding a single
             convenient import.

Public surface
--------------
    run(layers, only)      -- measure the pipeline, return Measurements
    write_artifacts(...)   -- persist a run's report and .prof files
    measure(...)           -- measure one callable, for ad-hoc use
    count_queries(...)     -- the narrow N+1 tool
    scenario(...)          -- the registration decorator

Usage is documented in README.md beside this file.
"""

from .harness import run, write_artifacts
from .instruments import Measurement, count_queries, measure
from .report import render_profile, render_table, severity_for, to_json
from .scenarios import scenario, scenarios_for

__all__ = [
    "Measurement",
    "count_queries",
    "measure",
    "render_profile",
    "render_table",
    "run",
    "scenario",
    "scenarios_for",
    "severity_for",
    "to_json",
    "write_artifacts",
]
