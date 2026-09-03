"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: Every tunable the profiling harness reads, and nothing else.

             This module is the one owner of the facts the rest of the package
             asks about: what counts as slow, how much of a profile is worth
             printing, where a report is written, and which environment
             variable turns the test-suite instrument on. It imports nothing
             from the game, so a scenario module, the report renderer and the
             test runner can all read the same threshold without any of them
             importing each other.

             The severity bands are the reason this file exists rather than
             the numbers living beside their one reader. An audit that calls a
             1.2s scenario "critical" in the harness and "high" in the report
             is an audit nobody trusts twice, and the two renderers are in
             different modules.
"""

# ─── Public constant definitions ─────────────────────────────────────────────

# The environment variable that arms the per-test instrument. Absent or empty
# means the test suite runs exactly as it did before this package existed --
# see testrunner.py for why the toggle is an env var rather than a setting.
PROFILE_TESTS_ENV = "BLACKOUT_PROFILE_TESTS"

# The environment variable that names where per-test results are written. When
# unset the runner prints to stdout only, which is what a developer wants and
# what CI does not.
PROFILE_TESTS_OUTPUT_ENV = "BLACKOUT_PROFILE_TESTS_OUTPUT"

# Severity bands for a measured wall-clock duration, in seconds. Read by
# report.py to label a row and by the harness to decide an exit code. Ordered
# worst-first so a lookup can return on its first match.
SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"
SEVERITY_OK = "ok"

# A scenario slower than this is a latency spike a player would feel. The
# anchor is the tick: TICK_SECONDS is 0.6, so anything at or past half a tick
# has no room left to also do the work the tick exists for.
DURATION_CRITICAL_SECONDS: float = 0.300
DURATION_HIGH_SECONDS: float = 0.100
DURATION_MEDIUM_SECONDS: float = 0.030
DURATION_LOW_SECONDS: float = 0.010

# Query-count bands. A query count is judged separately from duration because
# the two fail differently: a slow scenario with three queries is CPU work to
# optimise, while a fast scenario with three hundred queries is an N+1 that is
# fast only because the test database is a local file.
QUERIES_CRITICAL: int = 200
QUERIES_HIGH: int = 60
QUERIES_MEDIUM: int = 20
QUERIES_LOW: int = 8

# How many cProfile rows a report prints per scenario. Twenty is the point
# past which a caller reads the raw .prof instead, and the harness writes one
# of those for every scenario anyway.
PROFILE_ROWS: int = 20

# Sort key handed to pstats. Cumulative time answers "what is this scenario
# spending its time inside", which is the question an audit asks; total time
# answers "which single function is hot", which is the question a fix asks.
PROFILE_SORT_CUMULATIVE = "cumulative"
PROFILE_SORT_INTERNAL = "tottime"

# Default repetitions for a scenario. One pass measures import cost and cold
# caches as though they were steady-state; enough passes to amortise that is
# the difference between a profile that names the game and one that names
# Django's app registry.
DEFAULT_REPEAT: int = 20

# Passes run and discarded before measurement starts, for the same reason.
DEFAULT_WARMUP: int = 3

# Where the harness writes its artefacts, relative to the game directory.
REPORT_DIRECTORY = "profiling_out"

# Filenames inside REPORT_DIRECTORY. The .prof files are keyed per scenario at
# write time; these two are the aggregates.
REPORT_TEXT_NAME = "audit_report.txt"
REPORT_JSON_NAME = "audit_report.json"

# Column widths for the rendered table. Held here so report.py and testrunner.py
# print tables that line up with each other.
NAME_COLUMN_WIDTH: int = 38
NUMBER_COLUMN_WIDTH: int = 11
SEVERITY_COLUMN_WIDTH: int = 9

# Seconds-to-milliseconds, named because style.md forbids the bare literal and
# because it appears in three renderers.
MILLISECONDS_PER_SECOND: int = 1000

# The pipeline layers a scenario may declare. A report groups by these, and the
# audit's whole claim is that it covers the stack end to end -- so the set is
# closed, and registering a scenario against an unlisted layer raises rather
# than quietly creating a one-row group nobody reads.
LAYER_DATABASE = "database"
LAYER_ENGINE = "engine"
LAYER_STATEFEED = "statefeed"
LAYER_PROTOCOL = "protocol"
LAYER_WEB = "web"

PIPELINE_LAYERS = (
    LAYER_DATABASE,
    LAYER_ENGINE,
    LAYER_STATEFEED,
    LAYER_PROTOCOL,
    LAYER_WEB,
)

# Human labels for the layers, for the report's group headings.
LAYER_LABELS = {
    LAYER_DATABASE: "Database (Django ORM / Evennia models)",
    LAYER_ENGINE: "Evennia engine (tick, combat, commands)",
    LAYER_STATEFEED: "Statefeed (serialisation and emit)",
    LAYER_PROTOCOL: "Protocol (websocket payload encoding)",
    LAYER_WEB: "Web layer (Django views and static assets)",
}
