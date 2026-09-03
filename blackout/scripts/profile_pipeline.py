"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: Run the end-to-end profiling harness and write its report.

             A thin CLI over systems.profiling, which owns every measurement
             and every judgement. Everything that parses an argument or writes
             to stdout is here, and nothing here decides what is slow.

             SAFE, like export_client_constants.py and unlike the rest of this
             directory -- but for a different and stronger reason. That script
             is safe because it opens no database. This one opens a database
             constantly; it is safe because the database it opens is a TEST
             database that Django creates for the run and destroys after it.
             The live development data is never connected to, never queried,
             and never written. See systems/profiling/harness.py for why that
             was made structural rather than left to care.

             It is still behind the `if __name__ == "__main__"` guard every
             script here carries, because CLAUDE.md marks this whole directory
             import-unsafe and two safe files do not change how the directory
             should be treated.

             Run from blackout/:

                 python scripts/profile_pipeline.py
                 python scripts/profile_pipeline.py --layer statefeed
                 python scripts/profile_pipeline.py --only serialize_area
                 python scripts/profile_pipeline.py --show-profile

             Artifacts land in blackout/profiling_out/ -- a text report, the
             same run as JSON, and one .prof per scenario for snakeviz or
             pstats. The directory is gitignored: a profiling run's numbers
             are machine-specific and committing them would invite a diff
             nobody can review.
"""

import os
import sys


# ─── Private constant definitions ────────────────────────────────────────────

# The game dir (blackout/), two levels up from scripts/profile_pipeline.py.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The TEST settings, deliberately, not the real ones. The harness creates a
# database and the MD5 hasher this overlay installs is the difference between
# a fixture build measured in seconds and one measured in minutes -- which
# would otherwise be charged to whichever scenario ran first.
_SETTINGS_MODULE = "server.conf.test_settings"
_SETTINGS_ENV_VAR = "DJANGO_SETTINGS_MODULE"

_LAYER_FLAG = "--layer"
_ONLY_FLAG = "--only"
_SHOW_PROFILE_FLAG = "--show-profile"
_LIST_FLAG = "--list"

# Exit codes. A run whose worst row is CRITICAL exits non-zero so that a CI job
# can gate on it, the way --check does for the generated constants.
_EXIT_OK = 0
_EXIT_CRITICAL = 1


# ─── Private helper routines ─────────────────────────────────────────────────

def _bootstrap_django() -> None:
    """
    Purpose: Make `systems.profiling` importable and Django usable.

    Entry:
        No conditions.

    Exit/Returns:
        None. Configures Django in-process.

    Module Globals:
        _GAME_DIR, _SETTINGS_MODULE, _SETTINGS_ENV_VAR read.

    Methodology:
        Identical to export_client_constants._bootstrap_django, except for the
        settings module. The duplication is two lines and the alternative is a
        shared helper in a directory CLAUDE.md forbids importing from.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    if _GAME_DIR not in sys.path:
        sys.path.insert(0, _GAME_DIR)

    os.environ[_SETTINGS_ENV_VAR] = _SETTINGS_MODULE

    import django

    django.setup()


def _values_after(argv, flag) -> tuple:
    """
    Purpose: Collect every value given to a repeatable flag.

    Entry:
        argv - the argument list without the program name.
        flag - the flag to look for.

    Exit/Returns:
        Returns a tuple of the values that followed each occurrence. Empty when
        the flag is absent.

    Module Globals:
        None.

    Methodology:
        A flag at the very end of argv with nothing after it contributes
        nothing rather than raising -- the run is still meaningful, and an
        argument parser that dies on a trailing typo is one people stop using.

    Notes/References:
        Hand-rolled rather than argparse, matching the neighbouring script.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    found = []
    index = 0

    while index < len(argv):
        if argv[index] == flag and index + 1 < len(argv):
            found.append(argv[index + 1])
            index += 2
            continue

        index += 1

    return tuple(found)


def _print_listing() -> int:
    """
    Purpose: Print every registered scenario without measuring anything.

    Entry:
        Django must already be bootstrapped.

    Exit/Returns:
        Always _EXIT_OK.

    Module Globals:
        None.

    Methodology:
        Discovery is the whole point: the listing is what proves a newly added
        scenario module was picked up, without paying for a full run to find
        out.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    from systems.profiling import scenarios_for

    entries = scenarios_for()

    print(f"{len(entries)} registered scenario(s):\n")

    for entry in entries:
        print(f"  [{entry.layer:<10}] {entry.name}")

    return _EXIT_OK


def _print_report(measurements, show_profiles: bool) -> None:
    """
    Purpose: Print the run's table, and optionally each cProfile breakdown.

    Entry:
        measurements  - the list harness.run returned.
        show_profiles - True to print the per-scenario function breakdowns.

    Exit/Returns:
        None.

    Module Globals:
        None.

    Methodology:
        The table always prints; the breakdowns are opt-in because twenty rows
        times a dozen scenarios is more than a terminal is useful for, and the
        .prof files on disk are the better way to read them anyway.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    from systems.profiling import render_profile, render_table

    table = render_table(measurements)

    print(table)

    if not show_profiles:
        return

    for measurement in measurements:
        breakdown = render_profile(measurement)

        print("")
        print(breakdown)


def main(argv) -> int:
    """
    Purpose: Entry point.

    Entry:
        argv - the argument list, without the program name.

    Exit/Returns:
        A process exit code: _EXIT_CRITICAL when the run's worst row is
        critical, _EXIT_OK otherwise.

    Module Globals:
        Every _*_FLAG read.

    Methodology:
        Bootstrap, then either list or run. The exit code is derived from the
        report's own severity fold rather than recomputed here, so the CLI and
        the report cannot disagree about whether a run passed.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    _bootstrap_django()

    if _LIST_FLAG in argv:
        return _print_listing()

    from systems.profiling import constants as const
    from systems.profiling import run, write_artifacts
    from systems.profiling.report import worst_severity

    layers = _values_after(argv, _LAYER_FLAG)
    only = _values_after(argv, _ONLY_FLAG)
    show_profiles = _SHOW_PROFILE_FLAG in argv

    print("Profiling the Blackout pipeline (test database, live data "
          "untouched)...")

    measurements = run(layers=layers, only=only)

    if not measurements:
        print("No scenarios ran. Check --layer and --only against --list.")
        return _EXIT_CRITICAL

    _print_report(measurements, show_profiles)

    written = write_artifacts(measurements)
    overall = worst_severity(measurements)

    print("")
    print(f"Worst severity: {overall}")
    print(f"Report:   {written['text']}")
    print(f"JSON:     {written['json']}")
    print(f"Profiles: {len(written['profiles'])} .prof file(s) in "
          f"{const.REPORT_DIRECTORY}/")

    if overall == const.SEVERITY_CRITICAL:
        return _EXIT_CRITICAL

    return _EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
