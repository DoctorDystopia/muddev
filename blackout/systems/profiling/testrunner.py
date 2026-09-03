"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: An opt-in per-test instrument for the suite itself.

             Wraps the project's configured test runner and records, for every
             test method, its wall-clock duration and the number of database
             queries it issued. Off unless BLACKOUT_PROFILE_TESTS is set in the
             environment, and when it is off this class does nothing at all
             beyond one `if` at startup.

Why an environment variable and not a setting
----------------------------------------------
test_settings.py is loaded by every developer on every run, and a profiling
flag living there is one somebody commits as True and nobody notices for a
month. An environment variable is scoped to the invocation that asked for it
and cannot be committed.

Why this extends Evennia's runner rather than replacing it
-----------------------------------------------------------
Evennia's EvenniaTestSuiteRunner.setup_test_environment calls `evennia._init()`
and sets settings.TEST_ENVIRONMENT -- and without that step no object #1 or #2
exists, so every create_object in the suite dies on "settings.DEFAULT_HOME
(= '#2') does not exist". Subclassing it means this instrument cannot be the
reason that stops happening. The first draft of harness.py used a bare
DiscoverRunner and failed in exactly that way, which is also the failure
CLAUDE.md records against `--parallel`.

Why the timing is taken by a result class and not a decorator
--------------------------------------------------------------
unittest hands a TestResult startTest/stopTest around every method, including
setUp and tearDown. That bracket is the number that matters here -- CLAUDE.md's
whole point about EvenniaTest is that the fixtures cost more than the bodies --
and a decorator on the test method would measure only the part that is already
cheap.

Enabling it
-----------
    BLACKOUT_PROFILE_TESTS=1 ../evenv/Scripts/evennia.exe test \\
        --settings test_settings.py systems.banking

    BLACKOUT_PROFILE_TESTS=1 BLACKOUT_PROFILE_TESTS_OUTPUT=out.csv ...

The CSV is written only when the output variable names a path; otherwise the
summary prints to stderr and nothing touches the filesystem.
"""

import os
import time
import unittest

from django.db import connection
from evennia.server.tests.testrunner import EvenniaTestSuiteRunner

from . import constants as const


# ─── Private helper routines ─────────────────────────────────────────────────

def _profiling_enabled() -> bool:
    """
    Purpose: Report whether the instrument is armed for this invocation.

    Entry:
        No conditions.

    Exit/Returns:
        True when BLACKOUT_PROFILE_TESTS is set to anything non-empty other
        than a recognised falsehood.

    Module Globals:
        constants.PROFILE_TESTS_ENV read.

    Methodology:
        "0", "false" and "no" are treated as off so that a developer who
        exports the variable in a shell profile can turn it off without
        unsetting it.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    raw = os.environ.get(const.PROFILE_TESTS_ENV, "")
    lowered = raw.strip().lower()

    if lowered in ("", "0", "false", "no"):
        return False

    return True


def _output_path() -> str:
    """Return the CSV destination, or "" when none was named."""
    return os.environ.get(const.PROFILE_TESTS_OUTPUT_ENV, "").strip()


# ─── Public routines / Classes ───────────────────────────────────────────────

class TimingTestResult(unittest.TextTestResult):
    """A TestResult that records how long each test took and what it queried.

    The timing brackets setUp and tearDown as well as the test body, because
    that is the cost that actually multiplies across the suite.

    The query count is read from `connection.queries_log`, which Django keeps
    as a bounded deque and populates only while DEBUG is on. Under a normal
    test run DEBUG is off, so the count reads zero -- and that is deliberately
    NOT worked around here. Forcing DEBUG on for the whole suite would change
    what is being measured (every query gains a wrapper) and would slow the
    run this instrument exists to speed up. A caller who wants query counts
    asks for them per scenario through the harness, which turns DEBUG on for
    one block at a time.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timings = []
        self._started_at = 0.0
        self._queries_at_start = 0


    def startTest(self, test):
        """Record the clock and the query log's depth before setUp runs."""
        self._queries_at_start = len(connection.queries_log)
        self._started_at = time.perf_counter()

        super().startTest(test)


    def stopTest(self, test):
        """Record the elapsed time once tearDown has finished."""
        elapsed = time.perf_counter() - self._started_at
        queries = len(connection.queries_log) - self._queries_at_start

        super().stopTest(test)

        identifier = test.id()
        class_name = type(test).__name__
        bases = []

        for base in type(test).__mro__[1:]:
            bases.append(base.__name__)

            if base.__name__ in ("EvenniaTest", "EvenniaTestCase",
                                 "EvenniaCommandTest", "TestCase"):
                break

        self.timings.append({"id": identifier,
                             "class": class_name,
                             "base": bases[-1] if bases else "",
                             "seconds": elapsed,
                             "queries": queries})


class ProfilingRunnerMixin:
    """The opt-in per-test instrument, as a mixin over a real test runner.

    A MIXIN and not a runner. The distinction is the interface-segregation one:
    measuring a suite and configuring how a suite runs are two jobs, and the
    project's runner needs the second whether or not anybody asked for the
    first. server/conf/testrunner.py composes this over Evennia's runner; a
    caller wanting only the instrument can use ProfilingTestRunner below.

    Everything here is inert unless BLACKOUT_PROFILE_TESTS is set: get_resultclass
    defers to the inherited one, and suite_result finds no timings to report.
    """

    def get_resultclass(self):
        """Return the timing result class, or the inherited one when off."""
        if not _profiling_enabled():
            return super().get_resultclass()

        return TimingTestResult


    def suite_result(self, suite, result, **kwargs):
        """Print the timing summary, then defer to the normal result handling."""
        timings = getattr(result, "timings", None)

        if timings:
            self._report(timings)

        return super().suite_result(suite, result, **kwargs)


    def _report(self, timings) -> None:
        """
        Purpose: Summarise a profiled run by test, by class and by base class.

        Entry:
            timings - the list TimingTestResult accumulated.

        Exit/Returns:
            None. Prints to stderr and optionally writes a CSV.

        Module Globals:
            constants.PROFILE_ROWS and the column widths read.

        Methodology:
            Three views, because the three answer different questions. The
            per-test view finds one pathological test. The per-CLASS view finds
            an expensive setUp shared by a dozen cheap tests, which the
            per-test view spreads too thin to see. The per-BASE view is the one
            that says what the suite's floor costs -- it is how a claim like
            "the fixtures are most of the runtime" is made checkable rather
            than asserted.

        Notes/References:
            Written to stderr so that a caller piping stdout to a file for the
            CSV still sees the summary.

        Author: Nick Hobar
        Creation date: 09/03/2026
        """
        import sys

        by_class = {}
        by_base = {}
        total = 0.0

        for entry in timings:
            total += entry["seconds"]

            class_row = by_class.setdefault(entry["class"], [0, 0.0])
            class_row[0] += 1
            class_row[1] += entry["seconds"]

            base_row = by_base.setdefault(entry["base"], [0, 0.0])
            base_row[0] += 1
            base_row[1] += entry["seconds"]

        stream = sys.stderr
        slowest = sorted(timings, key=lambda row: -row["seconds"])

        stream.write(f"\n\nProfiled {len(timings)} test(s), "
                     f"{total:.2f}s of measured test time.\n")

        stream.write("\nSlowest tests\n")
        for entry in slowest[:const.PROFILE_ROWS]:
            stream.write(f"  {entry['seconds'] * 1000:>9.1f} ms  "
                         f"{entry['id']}\n")

        stream.write("\nCostliest classes (total seconds)\n")
        ranked = sorted(by_class.items(), key=lambda row: -row[1][1])
        for name, (count, seconds) in ranked[:const.PROFILE_ROWS]:
            stream.write(f"  {seconds:>8.2f}s  {count:>4} test(s)  "
                         f"{seconds / count * 1000:>8.1f} ms each  {name}\n")

        stream.write("\nBy base class -- the suite's floor\n")
        ranked = sorted(by_base.items(), key=lambda row: -row[1][1])
        for name, (count, seconds) in ranked:
            share = seconds / total * 100 if total else 0
            stream.write(f"  {seconds:>8.2f}s  {share:>5.1f}%  {count:>5} "
                         f"test(s)  {seconds / count * 1000:>8.1f} ms each  "
                         f"{name}\n")

        destination = _output_path()

        if not destination:
            return

        self._write_csv(timings, destination)
        stream.write(f"\nPer-test CSV written to {destination}\n")


    def _write_csv(self, timings, destination: str) -> None:
        """Write every per-test row as CSV, for analysis outside this process."""
        import csv

        with open(destination, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle,
                                    fieldnames=["id", "class", "base",
                                                "seconds", "queries"])
            writer.writeheader()

            for entry in timings:
                writer.writerow(entry)


class ProfilingTestRunner(ProfilingRunnerMixin, EvenniaTestSuiteRunner):
    """Evennia's runner plus the instrument, for use on its own.

    The base is named directly rather than resolved through
    `get_runner(settings)`. That is not a style choice: a settings file
    pointing TEST_RUNNER at this class would make the class its own parent and
    recurse at import time, which is exactly what the first draft did.

    EvenniaTestSuiteRunner specifically, because its setup_test_environment is
    the step that calls `evennia._init()` and puts object #2 in place. A runner
    that skipped it fails every create_object in the suite with
    "settings.DEFAULT_HOME (= '#2') does not exist".
    """
