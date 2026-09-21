"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: The command line of the model pipeline. Run it from blackout/:

                 ../evenv/Scripts/python.exe -m assets.pipeline <command>

             Each command is one routine in _COMMANDS, and the routine calls a
             module that does the work. Nothing here decides anything.
"""

import sys

from assets.pipeline import (budgets, build, check, fetch, glb, outputs,
                             paths, picocad, records, sources)


# ─── Private constant definitions ────────────────────────────────────────────

_USAGE: str = """python -m assets.pipeline <command>

  build [asset_key ...] [--force]   build models (default: every record)
  check                             check records, sources and served tree
  seal <source_id ...> | --all      record the hash of every file in a source
  new <family> <asset_key> <source_id> <file>
                                    write a new model record
  fetch polyhaven <asset_id>        download a Poly Haven model as a source
  fetch file <path> <source_id>     copy a downloaded file or folder as a source
  inspect <asset_key>               print what one served model holds
  budgets                           print the family budgets

assets/README.md is the procedure."""

_EXIT_OK: int = 0
_EXIT_FAILED: int = 1
_EXIT_USAGE: int = 2
_FORCE_FLAG: str = "--force"
_ALL_FLAG: str = "--all"
_BYTES_PER_KIB: int = 1024


# ─── Private helper routines ─────────────────────────────────────────────────

def _print_result(result: build.BuildResult) -> None:
    """
    Purpose: Print one line for one built model.

    Entry:
        result came from build.build_one.

    Exit/Returns:
        Returns None. Writes to stdout.

    Module Globals:
        _BYTES_PER_KIB read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    summary = result.summary
    state = "fresh " if result.skipped else "built "
    edges = ",".join(str(edge) for edge in summary.texture_edges) or "-"

    print("  %s %-38s %6d KiB %7d tris  textures %s"
          % (state, result.record.asset_key,
             summary.size_bytes // _BYTES_PER_KIB, summary.triangles, edges))


def _command_build(arguments: list) -> int:
    """
    Purpose: Build the named models, or every model, and the outputs.

    Entry:
        arguments holds asset keys and, optionally, --force.

    Exit/Returns:
        Returns the exit status: failed when any model failed.

    Module Globals:
        _FORCE_FLAG read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    force = _FORCE_FLAG in arguments
    wanted = {name for name in arguments if name != _FORCE_FLAG}
    all_records = records.load_all()
    chosen = [record for record in all_records
              if not wanted or wanted & set(record.keys)]
    lock = build.read_lock()
    failures = 0

    for record in chosen:
        try:
            result = build.build_one(record, force)
        except (build.BuildError, sources.SourceError, picocad.PicoCADError,
                OSError, ValueError) as problem:
            print("  FAILED %s: %s" % (record.asset_key, problem))
            failures += 1
            continue

        lock[record.asset_key] = {"inputs": result.inputs_digest,
                                  "output": result.output_digest}
        _print_result(result)

    known = {record.asset_key for record in all_records}
    lock = {key: value for key, value in lock.items() if key in known}
    build.write_lock(lock)

    for path in outputs.write_all():
        print("  wrote %s" % path)

    return _EXIT_FAILED if failures else _EXIT_OK


def _command_check(_arguments: list) -> int:
    """
    Purpose: Run the check and print its report.

    Entry:
        No conditions.

    Exit/Returns:
        Returns failed when the check found a problem.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    report = check.run_check()

    for line in report.warnings:
        print("  WARNING %s" % line)

    for line in report.problems:
        print("  PROBLEM %s" % line)

    if report.ok:
        print("  the model pipeline is consistent")

    return _EXIT_OK if report.ok else _EXIT_FAILED


def _command_seal(arguments: list) -> int:
    """
    Purpose: Record the current file hashes of the named sources.

    Entry:
        arguments holds source ids, or --all.

    Exit/Returns:
        Returns the exit status.

    Module Globals:
        _ALL_FLAG read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    chosen = arguments

    if _ALL_FLAG in arguments:
        chosen = sources.list_source_ids()

    if not chosen:
        print(_USAGE)
        return _EXIT_USAGE

    for source_id in chosen:
        source = sources.load_source(source_id)
        count = sources.seal(source)
        print("  sealed %s (%d files)" % (source_id, count))

    return _EXIT_OK


def _command_new(arguments: list) -> int:
    """
    Purpose: Write a new model record.

    Entry:
        arguments is [family, asset_key, source_id, file].

    Exit/Returns:
        Returns the exit status. Refuses to overwrite a record.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    if len(arguments) != 4:
        print(_USAGE)
        return _EXIT_USAGE

    family, asset_key, source_id, filename = arguments
    written = fetch.write_model_record(family, asset_key, source_id, filename)
    print("  wrote %s" % written)
    print("  next: python -m assets.pipeline build %s" % asset_key)

    return _EXIT_OK


def _command_fetch(arguments: list) -> int:
    """
    Purpose: Download or copy a new source, and write its source record.

    Entry:
        arguments is ["polyhaven", asset_id] or ["file", path, source_id].

    Exit/Returns:
        Returns the exit status.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    if arguments[:1] == ["polyhaven"] and len(arguments) == 2:
        directory = fetch.fetch_polyhaven(arguments[1])
    elif arguments[:1] == ["file"] and len(arguments) == 3:
        directory = fetch.fetch_file(arguments[1], arguments[2])
    else:
        print(_USAGE)
        return _EXIT_USAGE

    print("  wrote %s" % directory)
    print("  next: fill in every TODO in its source.toml, then run "
          "`python -m assets.pipeline new`")

    return _EXIT_OK


def _command_inspect(arguments: list) -> int:
    """
    Purpose: Print what one served model holds.

    Entry:
        arguments is [asset_key].

    Exit/Returns:
        Returns the exit status.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    matches = [record for record in records.load_all()
               if arguments and arguments[0] in record.keys]

    if not matches:
        print("  no model record answers to %s" % arguments)
        return _EXIT_FAILED

    record = matches[0]
    served = paths.served_path(record.family, record.asset_key)
    summary = glb.summarize(served)
    print("  %s -> %s" % (arguments[0], served))
    print("  %r" % (summary,))
    print("  " + budgets.describe_budget(record.family))

    return _EXIT_OK


def _command_budgets(_arguments: list) -> int:
    """
    Purpose: Print every family budget.

    Entry:
        No conditions.

    Exit/Returns:
        Returns ok.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    for family in sorted(budgets.FAMILY_BUDGETS):
        print("  " + budgets.describe_budget(family))

    print("  " + budgets.describe_budget("<anything else>"))

    return _EXIT_OK


_COMMANDS: dict = {
    "build": _command_build,
    "check": _command_check,
    "seal": _command_seal,
    "new": _command_new,
    "fetch": _command_fetch,
    "inspect": _command_inspect,
    "budgets": _command_budgets,
}


# ─── Public routines ─────────────────────────────────────────────────────────

def main(argv: list) -> int:
    """
    Purpose: Run one pipeline command.

    Entry:
        argv is sys.argv.

    Exit/Returns:
        Returns the process exit status.

    Module Globals:
        _COMMANDS, _USAGE read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    arguments = argv[1:]

    if not arguments or arguments[0] not in _COMMANDS:
        print(_USAGE)
        return _EXIT_USAGE

    command = _COMMANDS[arguments[0]]

    try:
        status = command(arguments[1:])
    except (records.RecordError, sources.SourceError,
            fetch.FetchError) as problem:
        print("  %s" % problem)
        status = _EXIT_FAILED

    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
