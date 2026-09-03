"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: The runner. Builds a throwaway database, fills it with the
             fixture world, measures every registered scenario against it, and
             hands back the results.

Why the run happens inside a TestCase
--------------------------------------
Two reasons, and the first is the one that matters.

CLAUDE.md opens with a warning that blackout/scripts/ acts on the live
development database and that a loop over the game's modules once deleted 347
grid rooms. A profiling harness is that same shape of tool -- it spawns
characters, arms combat handlers and issues writes, hundreds of times over --
and pointing it at the dev database would put the next 347 rooms one typo away.
Running inside Django's test machinery means the database is created for the
run, thrown away after it, and rolled back between phases. There is no code
path from here to the live data at all, which is a stronger guarantee than
being careful.

The second reason is that Evennia's world does not exist until somebody builds
it. `settings.DEFAULT_HOME` names #2, a Character cannot be created without a
home to fall back to, and `EvenniaTestMixin` is the code that puts those rows
in place. Re-implementing that here would be a second owner of a fact Evennia
already owns, and it would drift.

Why the scenarios all run in ONE test method
---------------------------------------------
A TestCase rolls back after every method, so a method per scenario would
rebuild the 81-tile fixture every time -- turning a fixture cost into the
dominant term of a run that exists to measure something else. One method builds
the world once and measures every scenario against it.

The trade is that scenarios share state: one that leaves a combat handler armed
is observed by every scenario after it. That is accepted deliberately and is
why registration order is documented as report order -- a scenario is measured
against a world the ones before it have already touched, which is also the
world a real server is in.
"""

import os

from evennia.utils.test_resources import EvenniaTest

from . import constants as const
from . import instruments, report
from .scenarios import scenarios_for
from .world_fixture import ProfilingWorld


# ─── Module globals ──────────────────────────────────────────────────────────

# The runner cannot pass arguments into a TestCase, and it cannot read a return
# value out of one -- unittest owns both ends. These three carry the selection
# in and the results out. Module state rather than class attributes so that the
# case class stays a plain TestCase that a developer can also run by hand.
_selected_layers: tuple = ()
_selected_names: tuple = ()
_results: list = []


# ─── Private helper routines ─────────────────────────────────────────────────

def _wanted(entry) -> bool:
    """
    Purpose: Decide whether one registered scenario is in this run.

    Entry:
        entry - a scenarios.Scenario.

    Exit/Returns:
        True when the scenario should be measured.

    Module Globals:
        _selected_names read.

    Methodology:
        Layer filtering already happened in scenarios_for; this is the
        by-name narrowing, matched as a case-insensitive SUBSTRING so that a
        caller can say `--only serialize_area` and get both radii rather than
        having to type a full name with its parenthetical.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    if not _selected_names:
        return True

    lowered = entry.name.lower()

    for fragment in _selected_names:
        if fragment.lower() in lowered:
            return True

    return False


def _measure_all(world) -> list:
    """
    Purpose: Run every selected scenario against a built world.

    Entry:
        world - a built ProfilingWorld.

    Exit/Returns:
        Returns a list of Measurement objects, in report order.

    Module Globals:
        _selected_layers read.

    Methodology:
        A factory that raises is recorded as a failed Measurement rather than
        aborting the run. The factory is setup, and setup failing is exactly
        the case where the OTHER scenarios' numbers are still worth having --
        an audit that reports eight layers and one broken row is useful, one
        that reports a traceback is not.

    Notes/References:
        See instruments.measure for the four-phase measurement itself.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    entries = scenarios_for(_selected_layers)
    measured = []

    for entry in entries:
        if not _wanted(entry):
            continue

        try:
            work = entry.factory(world)
        except Exception as failure:
            measured.append(instruments.Measurement(
                name=entry.name,
                layer=entry.layer,
                repeat=0,
                total_seconds=0.0,
                query_count=0,
                duplicate_queries=0,
                call_count=0,
                error=f"setup {type(failure).__name__}: {failure}",
                notes=entry.notes))
            continue

        result = instruments.measure(name=entry.name,
                                     layer=entry.layer,
                                     work=work,
                                     repeat=entry.repeat,
                                     warmup=entry.warmup,
                                     notes=entry.notes)
        measured.append(result)

    return measured


# ─── Public routines / Classes ───────────────────────────────────────────────

class ProfilingHarnessCase(EvenniaTest):
    """The single TestCase the whole run happens inside.

    Named without a `test_`-prefixed module so Django's discovery never picks
    it up as part of the ordinary suite: this class takes minutes and writes
    files, which is not something `evennia test systems` should ever do.
    The harness builds a suite naming it explicitly instead.
    """

    def test_profile_pipeline(self):
        """Build the fixture world and measure every selected scenario."""
        global _results

        world = ProfilingWorld()
        world.build()

        _results = _measure_all(world)


def run(layers=(), only=(), verbosity: int = 0) -> list:
    """
    Purpose: Execute a profiling run and return its measurements.

    Entry:
        layers    - layer names to restrict to; empty means every layer.
        only      - name fragments to restrict to; empty means every scenario.
        verbosity - passed to the Django test runner. 0 keeps its chatter out
                    of the report.

    Exit/Returns:
        Returns a list of Measurement objects. Returns an empty list if the
        run produced nothing, which a caller should treat as a failure rather
        than as a clean bill of health.

    Module Globals:
        _selected_layers, _selected_names and _results written.

    Methodology:
        The runner comes from get_runner(settings) -- the class the project's
        own TEST_RUNNER names -- rather than from a hardcoded DiscoverRunner.
        That is not tidiness. Evennia points TEST_RUNNER at
        EvenniaTestSuiteRunner, whose setup_test_environment calls
        `evennia._init()` and sets settings.TEST_ENVIRONMENT, and WITHOUT that
        step no object #1 or #2 exists -- so every create_object dies on
        "settings.DEFAULT_HOME (= '#2') does not exist". A bare DiscoverRunner
        here failed in exactly the way CLAUDE.md records --parallel failing,
        which is the same root cause seen from a different angle.

        The full lifecycle is driven by hand rather than through run_tests()
        because run_tests builds its own suite by discovery, and this run must
        execute one named test and no others.

        Django's settings must already be configured before this is called --
        the caller is either the test runner or scripts/profile_pipeline.py,
        and both arrange that. This module deliberately does not call
        django.setup() itself, so that importing it can never have a side
        effect on a server process.

    Notes/References:
        See the module header for why the run is inside a TestCase at all.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    global _selected_layers, _selected_names, _results

    import unittest

    from django.conf import settings
    from django.test.utils import get_runner

    _selected_layers = tuple(layers)
    _selected_names = tuple(only)
    _results = []

    runner_class = get_runner(settings)
    runner = runner_class(verbosity=verbosity, interactive=False)

    suite = unittest.TestSuite()
    suite.addTest(ProfilingHarnessCase("test_profile_pipeline"))

    runner.setup_test_environment()
    old_config = runner.setup_databases()

    try:
        runner.run_suite(suite)
    finally:
        runner.teardown_databases(old_config)
        runner.teardown_test_environment()

    return _results


def write_artifacts(measurements, directory: str = const.REPORT_DIRECTORY) -> dict:
    """
    Purpose: Write the run's report and per-scenario .prof files to disk.

    Entry:
        measurements - the list run() returned.
        directory    - where to write, created if absent.

    Exit/Returns:
        Returns {"text": path, "json": path, "profiles": [paths]}.

    Module Globals:
        constants.REPORT_* read.

    Methodology:
        A .prof per scenario, dumped in pstats' own binary format, so that a
        reader can open one in snakeviz or pstats' interactive browser rather
        than being limited to the twenty rows the text report prints. The text
        and JSON reports are the summary; the .prof files are the evidence.

        A scenario that failed has no stats and is skipped rather than writing
        an empty file that looks like a measurement.

    Notes/References:
        https://www.evennia.com/docs/latest/Coding/Profiling.html for reading
        the dumps.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    os.makedirs(directory, exist_ok=True)

    text_path = os.path.join(directory, const.REPORT_TEXT_NAME)
    json_path = os.path.join(directory, const.REPORT_JSON_NAME)

    table = report.render_table(measurements)
    document = report.to_json(measurements)

    with open(text_path, "w", encoding="utf-8") as handle:
        handle.write(table)
        handle.write("\n")

    with open(json_path, "w", encoding="utf-8") as handle:
        handle.write(document)
        handle.write("\n")

    written = []

    for measurement in measurements:
        if measurement.stats is None:
            continue

        safe = measurement.name.replace(" ", "_").replace("/", "_")
        safe = "".join(char for char in safe if char.isalnum() or char in "_-.")
        profile_path = os.path.join(directory, f"{safe}.prof")

        measurement.stats.dump_stats(profile_path)
        written.append(profile_path)

    return {"text": text_path, "json": json_path, "profiles": written}
