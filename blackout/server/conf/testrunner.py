"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: The project's test runner. Owns how the suite RUNS, as distinct
             from what the suite tests.

             Three things are composed here and they are deliberately three:

               1. EvenniaTestSuiteRunner, which is not optional. Its
                  setup_test_environment calls `evennia._init()` and sets
                  settings.TEST_ENVIRONMENT, and without that step no object #1
                  or #2 exists -- so every create_object in the suite fails with
                  "settings.DEFAULT_HOME (= '#2') does not exist".
               2. A garbage-collection policy for the run. See below.
               3. systems.profiling's opt-in per-test instrument, inert unless
                  BLACKOUT_PROFILE_TESTS is set.

             The instrument is a MIXIN living in systems/profiling/ rather than
             a runner living here, because measuring a suite and configuring one
             are different jobs with different lifetimes. This module needs the
             configuration whether or not anybody ever asks for a measurement.

Why the suite freezes the garbage collector
--------------------------------------------
Evennia's idmapper `flush_cache()` ends with an unconditional `gc.collect()`,
and `EvenniaTestMixin.tearDown` calls it after EVERY test method. A full
collection walks every tracked object in the process -- measured at 259,410 of
them once Django and Evennia have finished importing, almost all of which are
loaded modules, classes, functions and code objects that can never be garbage
while the process lives. The suite was rescanning that same quarter-million
objects 1,857 times.

`gc.freeze()` moves everything currently tracked into a permanent generation
that `collect()` does not scan. Objects created AFTERWARDS -- which is every
fixture, every test object, every payload -- stay in the ordinary generations
and are collected exactly as before. The isolation guarantee is untouched:
`flush_cache` still clears the idmapper's instance caches, which is the half
that makes tests order-independent, and the collection still reclaims the
garbage the tests themselves produced.

Measured on this machine, over runs of 30 empty EvenniaTest methods:

    gc unfrozen      146.49 ms/test
    gc.freeze()      104.93 ms/test
    saving            41.56 ms/test  (28.4%)

Across 1,857 tests that is roughly 77 seconds of a 604-second suite.

Why the freeze happens after setup_test_environment and not at import
----------------------------------------------------------------------
The point is to freeze a heap that is FINISHED loading. At import time Django's
app registry, Evennia's `_init()` and the game's typeclass and cmdset modules
have not run yet, so most of what the freeze exists to exclude would not be
tracked yet and would stay in the scanned generations anyway.

A `gc.collect()` runs immediately before the freeze so that whatever genuinely
is garbage at that moment is reclaimed rather than made permanent.

Notes/References:
    The freeze is undone in teardown_test_environment. Nothing in a test
    process outlives that, so this is tidiness rather than necessity -- but a
    runner that leaves global interpreter state changed behind it is one whose
    effects turn up somewhere surprising later.
"""

import gc

from evennia.server.tests.testrunner import EvenniaTestSuiteRunner
from systems.profiling.testrunner import ProfilingRunnerMixin


class BlackoutTestSuiteRunner(ProfilingRunnerMixin, EvenniaTestSuiteRunner):
    """Evennia's runner, plus this project's gc policy and its instrument.

    The MRO order matters: the mixin must come first so that its
    get_resultclass and suite_result are the ones unittest reaches, with
    EvenniaTestSuiteRunner's behind them as the `super()` they defer to when
    profiling is off.
    """

    def setup_test_environment(self, **kwargs):
        """
        Purpose: Prepare the Evennia test environment, then freeze the heap.

        Entry:
            No conditions. Called once per test process by Django.

        Exit/Returns:
            None.

        Module Globals:
            None.

        Methodology:
            Evennia's setup runs FIRST and the freeze happens after it, so that
            everything `evennia._init()` imports is included in the permanent
            generation. Freezing first would leave the largest part of the heap
            in the scanned generations, which is the whole cost being removed.

        Notes/References:
            See the module header for the measurement.

        Author: Nick Hobar
        Creation date: 09/03/2026
        """
        super().setup_test_environment(**kwargs)

        gc.collect()
        gc.freeze()


    def teardown_test_environment(self, **kwargs):
        """
        Purpose: Unfreeze the heap, then tear the Evennia environment down.

        Entry:
            setup_test_environment must have run.

        Exit/Returns:
            None.

        Module Globals:
            None.

        Methodology:
            Mirror image of setup: the interpreter-level change is undone
            before the framework-level one, so that at no point is the
            environment torn down while global state this class set is still
            in place.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 09/03/2026
        """
        gc.unfreeze()

        super().teardown_test_environment(**kwargs)
