"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: Rendering only. This module changes nothing and measures nothing.

             The read/write split is the one systems/devtools/dossier.py makes
             against actions.py, and for the same reason: a reader looking at a
             profiling run wants to be able to tell at a glance which module
             could have perturbed the numbers, and the answer has to be "not
             this one". Everything here takes Measurements and returns strings
             or plain dicts.

             It is also where severity lives. instruments.py records facts and
             report.py judges them, so that re-rendering a stored run cannot
             produce a different verdict than the run that measured it would
             have -- the numbers are on disk, the thresholds are in
             constants.py, and neither is re-derived from the other.
"""

import json

from . import constants as const


# ─── Private helper routines ─────────────────────────────────────────────────

def _duration_severity(seconds: float) -> str:
    """
    Purpose: Band a per-pass duration.

    Entry:
        seconds - a non-negative per-pass duration.

    Exit/Returns:
        Returns one of the constants.SEVERITY_* names.

    Module Globals:
        constants.DURATION_*_SECONDS read.

    Methodology:
        Worst-first, returning on the first match, so the bands cannot overlap
        into an ambiguous answer.

    Notes/References:
        The anchor is TICK_SECONDS -- see constants.py.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    if seconds >= const.DURATION_CRITICAL_SECONDS:
        return const.SEVERITY_CRITICAL

    if seconds >= const.DURATION_HIGH_SECONDS:
        return const.SEVERITY_HIGH

    if seconds >= const.DURATION_MEDIUM_SECONDS:
        return const.SEVERITY_MEDIUM

    if seconds >= const.DURATION_LOW_SECONDS:
        return const.SEVERITY_LOW

    return const.SEVERITY_OK


def _query_severity(count: int) -> str:
    """
    Purpose: Band a per-pass query count.

    Entry:
        count - a non-negative query count for one execution.

    Exit/Returns:
        Returns one of the constants.SEVERITY_* names.

    Module Globals:
        constants.QUERIES_* read.

    Methodology:
        Judged separately from duration, because the two fail differently: a
        fast scenario issuing hundreds of queries is fast only because the test
        database is a local file with no network between it and the process.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    if count >= const.QUERIES_CRITICAL:
        return const.SEVERITY_CRITICAL

    if count >= const.QUERIES_HIGH:
        return const.SEVERITY_HIGH

    if count >= const.QUERIES_MEDIUM:
        return const.SEVERITY_MEDIUM

    if count >= const.QUERIES_LOW:
        return const.SEVERITY_LOW

    return const.SEVERITY_OK


def _worst(first: str, second: str) -> str:
    """Return whichever of two severity names is the more serious."""
    order = (const.SEVERITY_CRITICAL,
             const.SEVERITY_HIGH,
             const.SEVERITY_MEDIUM,
             const.SEVERITY_LOW,
             const.SEVERITY_OK)

    for name in order:
        if first == name or second == name:
            return name

    return const.SEVERITY_OK


def _header_row() -> str:
    """Render the table's column headings."""
    name = "scenario".ljust(const.NAME_COLUMN_WIDTH)
    milliseconds = "ms/pass".rjust(const.NUMBER_COLUMN_WIDTH)
    queries = "queries".rjust(const.NUMBER_COLUMN_WIDTH)
    duplicates = "dup".rjust(const.NUMBER_COLUMN_WIDTH)
    calls = "calls".rjust(const.NUMBER_COLUMN_WIDTH)
    severity = "severity".rjust(const.SEVERITY_COLUMN_WIDTH)

    return f"{name} {milliseconds} {queries} {duplicates} {calls} {severity}"


def _measurement_row(measurement) -> str:
    """Render one Measurement as a table row."""
    name = measurement.name[:const.NAME_COLUMN_WIDTH]
    name = name.ljust(const.NAME_COLUMN_WIDTH)

    if measurement.failed:
        return f"{name} {'ERROR':>{const.NUMBER_COLUMN_WIDTH}}  {measurement.error}"

    milliseconds = measurement.per_pass_milliseconds
    severity = severity_for(measurement)

    return (f"{name} "
            f"{milliseconds:>{const.NUMBER_COLUMN_WIDTH}.3f} "
            f"{measurement.query_count:>{const.NUMBER_COLUMN_WIDTH}} "
            f"{measurement.duplicate_queries:>{const.NUMBER_COLUMN_WIDTH}} "
            f"{measurement.call_count:>{const.NUMBER_COLUMN_WIDTH}} "
            f"{severity:>{const.SEVERITY_COLUMN_WIDTH}}")


# ─── Public routines ─────────────────────────────────────────────────────────

def severity_for(measurement) -> str:
    """
    Purpose: Give one Measurement its overall severity band.

    Entry:
        measurement - a Measurement. A failed one is CRITICAL: a scenario that
        raised is a broken audit row, not a fast one.

    Exit/Returns:
        Returns one of the constants.SEVERITY_* names.

    Module Globals:
        None directly; the two banding helpers read constants.

    Methodology:
        The worse of the duration band and the query band. A scenario is as
        bad as its worst dimension, because fixing only the other one leaves
        the symptom in place.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    if measurement.failed:
        return const.SEVERITY_CRITICAL

    by_duration = _duration_severity(measurement.per_pass_seconds)
    by_queries = _query_severity(measurement.query_count)

    return _worst(by_duration, by_queries)


def render_table(measurements) -> str:
    """
    Purpose: Render every measurement as a table, grouped by pipeline layer.

    Entry:
        measurements - an iterable of Measurement objects, in any order.

    Exit/Returns:
        Returns the whole report as one string. A layer with no measurements
        is omitted rather than printed empty.

    Module Globals:
        constants.PIPELINE_LAYERS and LAYER_LABELS read.

    Methodology:
        Grouped by the DECLARED layer order, so the report reads front to back
        along the pipeline the audit claims to cover, rather than in whatever
        order the scenarios were registered.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    by_layer = {}

    for measurement in measurements:
        by_layer.setdefault(measurement.layer, []).append(measurement)

    lines = []

    for layer in const.PIPELINE_LAYERS:
        rows = by_layer.get(layer)

        if not rows:
            continue

        label = const.LAYER_LABELS[layer]

        lines.append("")
        lines.append(label)
        lines.append("-" * len(label))
        lines.append(_header_row())

        for measurement in rows:
            row = _measurement_row(measurement)
            lines.append(row)

    return "\n".join(lines)


def render_profile(measurement, rows: int = const.PROFILE_ROWS,
                   sort_key: str = const.PROFILE_SORT_CUMULATIVE) -> str:
    """
    Purpose: Render one measurement's cProfile breakdown.

    Entry:
        measurement - a Measurement carrying a pstats.Stats. One without
                      stats (a failed scenario) renders as a short note.
        rows        - how many functions to print.
        sort_key    - a pstats sort key; see constants.PROFILE_SORT_*.

    Exit/Returns:
        Returns the breakdown as a string.

    Module Globals:
        constants.PROFILE_ROWS and PROFILE_SORT_CUMULATIVE read as defaults.

    Methodology:
        The Stats object was built against a StringIO in instruments.py
        precisely so that this can rewind and read that buffer rather than
        letting pstats print to the process's stdout.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    stats = measurement.stats

    if stats is None:
        return f"{measurement.name}: no profile ({measurement.error or 'not collected'})"

    stream = stats.stream

    stream.seek(0)
    stream.truncate(0)

    stats.sort_stats(sort_key)
    stats.print_stats(rows)

    body = stream.getvalue()

    return f"{measurement.name} (sorted by {sort_key})\n{body}"


def to_json(measurements) -> str:
    """
    Purpose: Render the run as machine-readable JSON.

    Entry:
        measurements - an iterable of Measurement objects.

    Exit/Returns:
        Returns a JSON document as a string. The pstats object is deliberately
        absent: it is not JSON-safe, and the harness writes a .prof file per
        scenario for anyone who wants it.

    Module Globals:
        None.

    Methodology:
        Every field is a measured fact plus the derived severity. Storing the
        severity rather than only the raw numbers is what lets a later
        comparison say "this got worse" without having to re-implement the
        bands.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    rows = []

    for measurement in measurements:
        severity = severity_for(measurement)

        rows.append({"name": measurement.name,
                     "layer": measurement.layer,
                     "repeat": measurement.repeat,
                     "milliseconds_per_pass": measurement.per_pass_milliseconds,
                     "queries": measurement.query_count,
                     "duplicate_queries": measurement.duplicate_queries,
                     "calls": measurement.call_count,
                     "severity": severity,
                     "notes": measurement.notes,
                     "error": measurement.error})

    return json.dumps(rows, indent=2)


def worst_severity(measurements) -> str:
    """
    Purpose: Give the whole run one severity, for an exit code.

    Entry:
        measurements - an iterable of Measurement objects. An empty run is OK.

    Exit/Returns:
        Returns the most serious severity present.

    Module Globals:
        None.

    Methodology:
        Folded with the same _worst used per measurement, so a run cannot be
        graded on a scale the rows were not.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    overall = const.SEVERITY_OK

    for measurement in measurements:
        severity = severity_for(measurement)
        overall = _worst(overall, severity)

    return overall
