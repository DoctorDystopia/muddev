"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: The measurement primitives -- what it means to time a block of
             game code, count the queries it issues, and capture a cProfile of
             it.

Why timing and profiling are two separate passes
------------------------------------------------
cProfile costs a Python-level callback on every call and return, which inflates
a call-heavy routine far more than a loop-heavy one. Reporting a profiled
duration as though it were the real one therefore does not just add a constant
-- it REORDERS the audit, promoting whichever scenario happens to make the most
function calls. So `measure` runs the work twice: a clean pass that owns the
duration, and a profiled pass that owns the call breakdown and whose own
duration is thrown away.

Why the query count comes from its own pass too
-----------------------------------------------
`CaptureQueriesContext` holds every executed query as a dict for the life of
the block. Over DEFAULT_REPEAT passes of a scenario that issues hundreds, that
is a list big enough to perturb the timing it is sharing a pass with. It gets
the third pass, and it runs the work ONCE rather than `repeat` times, because a
query count is a property of one execution and multiplying it by the repeat
count would only make the number harder to compare against an assertNumQueries.

Why nothing here knows what a scenario is
-----------------------------------------
This module measures a zero-argument callable. It cannot name a room, a
serializer or a tick, which is what keeps it usable from the harness, from the
test runner and from a throwaway experiment in a shell without any of the three
growing a dependency on the others.
"""

import cProfile
import pstats
import time
from dataclasses import dataclass, field
from io import StringIO

from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext

from . import constants as const


# ─── Public data structures ──────────────────────────────────────────────────

@dataclass
class Measurement:
    """One scenario's measured cost.

    Every field is a fact about the run rather than a judgement about it: the
    severity band is derived by report.py, so that a caller re-rendering an
    older result cannot get a different verdict than the run that produced it
    would have.
    """

    name: str
    layer: str
    repeat: int
    total_seconds: float
    query_count: int
    duplicate_queries: int
    call_count: int
    stats: object = None
    error: str = ""
    notes: str = ""
    slowest_queries: list = field(default_factory=list)


    @property
    def per_pass_seconds(self) -> float:
        """Seconds for a single execution, which is the comparable number."""
        if self.repeat < 1:
            return self.total_seconds

        return self.total_seconds / self.repeat


    @property
    def per_pass_milliseconds(self) -> float:
        """per_pass_seconds in the unit the report prints."""
        seconds = self.per_pass_seconds

        return seconds * const.MILLISECONDS_PER_SECOND


    @property
    def failed(self) -> bool:
        """True when the scenario raised and its numbers mean nothing."""
        return bool(self.error)


# ─── Private helper routines ─────────────────────────────────────────────────

def _run_repeatedly(work, repeat: int) -> None:
    """
    Purpose: Call a zero-argument callable a fixed number of times.

    Entry:
        work   - a zero-argument callable. May return anything; the value is
                 discarded.
        repeat - how many times to call it. A value below 1 calls it once, so
                 that a caller passing 0 measures something rather than
                 reporting a zero duration for work that never ran.

    Exit/Returns:
        No return value. Any exception from `work` propagates -- containment is
        the caller's decision, and `measure` makes it.

    Module Globals:
        None.

    Methodology:
        The loop is deliberately bare. Anything else inside it -- a counter, a
        progress print, an accumulator -- is measured along with the work and
        shows up in the profile as though the game did it.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    passes = repeat

    if passes < 1:
        passes = 1

    for _ in range(passes):
        work()


def _count_duplicates(captured) -> int:
    """
    Purpose: Count how many captured queries repeat SQL already seen.

    Entry:
        captured - the list of {"sql": ..., "time": ...} dicts a
        CaptureQueriesContext leaves behind.

    Exit/Returns:
        Returns the number of queries whose exact SQL text appeared earlier in
        the list. Zero for an empty list.

    Module Globals:
        None.

    Methodology:
        Identical SQL executed twice in one logical operation is the signature
        of an N+1: the ORM re-fetching a row it already held, once per object
        in a loop. Distinguishing it from a legitimately repeated query needs
        judgement, so this reports the count and leaves the judgement to the
        reader -- but a scenario reporting 4 queries of which 0 are duplicates
        and one reporting 400 of which 397 are duplicates do not need the same
        amount of reading.

        Comparison is on the SQL string AFTER parameter substitution, which
        Django has already done. That understates the count when a loop varies
        its parameter, so the number is a floor rather than an estimate.

    Notes/References:
        The pattern this is built to catch is the one CLAUDE.md records in
        systems/tick/tests/test_query_cost.py -- an O(N*M) walk that is
        invisible at development scale.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    seen = set()
    duplicates = 0

    for entry in captured:
        sql = entry.get("sql", "")

        if sql in seen:
            duplicates += 1
            continue

        seen.add(sql)

    return duplicates


def _slowest(captured, limit: int) -> list:
    """
    Purpose: Name the individual queries that cost the most time.

    Entry:
        captured - the CaptureQueriesContext list.
        limit    - how many to keep.

    Exit/Returns:
        Returns a list of (seconds, sql) tuples, longest first, at most `limit`
        long. Empty when nothing was captured.

    Module Globals:
        None.

    Methodology:
        Django records a per-query duration only when DEBUG is on, which is the
        state CaptureQueriesContext forces for its own block. A missing or
        unparseable time is treated as zero rather than raising, because a
        diagnostic that dies on a backend quirk is worse than one that
        under-reports.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    timed = []

    for entry in captured:
        raw = entry.get("time", 0)

        try:
            seconds = float(raw)
        except (TypeError, ValueError):
            seconds = 0.0

        timed.append((seconds, entry.get("sql", "")))

    timed.sort(reverse=True)

    return timed[:limit]


def _profile_once(work):
    """
    Purpose: Run the work under cProfile and hand back the collected stats.

    Entry:
        work - a zero-argument callable.

    Exit/Returns:
        Returns a (pstats.Stats, total_calls) pair. The Stats object is bound
        to a throwaway StringIO so that printing it later cannot write to the
        caller's stdout by surprise.

    Module Globals:
        None.

    Methodology:
        One pass, not `repeat` passes. The profile's job is the SHAPE of the
        call tree, and that shape does not change with repetition -- while the
        stats object's memory does, linearly, for a scenario that touches
        thousands of distinct code objects.

    Notes/References:
        https://www.evennia.com/docs/latest/Coding/Profiling.html -- Evennia's
        own guidance is to drive cProfile around a known workload rather than
        to profile a whole running server, which is what a scenario is.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    profiler = cProfile.Profile()

    profiler.enable()

    try:
        work()
    finally:
        profiler.disable()

    sink = StringIO()
    stats = pstats.Stats(profiler, stream=sink)
    call_count = stats.total_calls

    return stats, call_count


# ─── Public routines ─────────────────────────────────────────────────────────

def measure(name: str,
            layer: str,
            work,
            repeat: int = const.DEFAULT_REPEAT,
            warmup: int = const.DEFAULT_WARMUP,
            notes: str = "") -> Measurement:
    """
    Purpose: Produce the full cost picture for one zero-argument callable.

    Entry:
        name   - the scenario's reported name.
        layer  - one of constants.PIPELINE_LAYERS.
        work   - a zero-argument callable that performs the workload. It is
                 called `warmup + repeat + 2` times in total, so it must be
                 safe to repeat and must not depend on being the first caller.
        repeat - measured passes for the timing number.
        warmup - discarded passes run first, to pay import and cache costs
                 outside the measurement.
        notes  - free text carried through to the report.

    Exit/Returns:
        Returns a Measurement. On an exception from `work`, returns one whose
        `error` is set and whose numbers are zero -- this routine does not
        raise, because a harness run must report the scenarios that worked
        rather than dying on the first that did not.

    Module Globals:
        constants.DEFAULT_REPEAT and DEFAULT_WARMUP read as defaults.

    Methodology:
        Four phases, in this order:
          1. warmup, discarded -- pays for lazy imports, idmapper population
             and Django's connection setup.
          2. timing, `repeat` passes, nothing else running.
          3. profiling, one pass, duration discarded.
          4. query capture, one pass.
        The order matters: query capture goes last because it forces DEBUG on
        for its block, and Django's DEBUG cursor wrapper would otherwise be
        measured as though it were the game's own cost.

    Notes/References:
        See the module header for why 2 and 3 cannot share a pass.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    if layer not in const.PIPELINE_LAYERS:
        raise ValueError(f"unknown pipeline layer: {layer}")

    try:
        _run_repeatedly(work, warmup)

        started_at = time.perf_counter()
        _run_repeatedly(work, repeat)
        elapsed = time.perf_counter() - started_at

        stats, call_count = _profile_once(work)

        reset_queries()

        with CaptureQueriesContext(connection) as captured:
            work()

        entries = list(captured.captured_queries)
        duplicates = _count_duplicates(entries)
        slowest = _slowest(entries, const.PROFILE_ROWS)

    except Exception as failure:
        return Measurement(name=name,
                           layer=layer,
                           repeat=0,
                           total_seconds=0.0,
                           query_count=0,
                           duplicate_queries=0,
                           call_count=0,
                           error=f"{type(failure).__name__}: {failure}",
                           notes=notes)

    return Measurement(name=name,
                       layer=layer,
                       repeat=repeat,
                       total_seconds=elapsed,
                       query_count=len(entries),
                       duplicate_queries=duplicates,
                       call_count=call_count,
                       stats=stats,
                       notes=notes,
                       slowest_queries=slowest)


def count_queries(work) -> int:
    """
    Purpose: Report how many queries a zero-argument callable issues.

    Entry:
        work - a zero-argument callable.

    Exit/Returns:
        Returns the query count for exactly one execution.

    Module Globals:
        None.

    Methodology:
        The narrow tool, for a caller that wants the N+1 number and not a
        profile. It exists so that a regression test can assert on the same
        measurement the audit reported without importing the whole harness.

    Notes/References:
        Django's own assertNumQueries is the right tool inside a TestCase; this
        is for the paths that are not one.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    reset_queries()

    with CaptureQueriesContext(connection) as captured:
        work()

    return len(captured.captured_queries)
