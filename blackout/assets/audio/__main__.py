"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/26/2026
Description: The command line of the sound wizard. Run it from blackout/:

                 ../evenv/Scripts/python.exe -m assets.audio <command>

             Each command is one routine in _COMMANDS, and the routine calls a
             module that does the work. Nothing here decides anything.
"""

import sys

from assets.audio import check, credits, cue_table, wizard


# ─── Private constant definitions ────────────────────────────────────────────

_USAGE: str = """python -m assets.audio <command>

  add      answer questions to add one sound clip: the copy, its .import
           file, its cue, and its credits row. Then import it in Godot
  check    check the cue table, the sound clips and the credits

godot/README.md, "Sound is the client's", is the procedure."""

_EXIT_OK: int = 0
_EXIT_FAILED: int = 1
_EXIT_USAGE: int = 2


# ─── Private helper routines ─────────────────────────────────────────────────

def _command_add(_arguments: list) -> int:
    """
    Purpose: Run the sound wizard, and show the steps after it.

    Entry:
        No conditions. The wizard reads the terminal.

    Exit/Returns:
        Returns failed when the person stops.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    result = wizard.run()

    if result is None:
        return _EXIT_FAILED

    lines = wizard.next_steps(result)

    for line in lines:
        print(line)

    return _EXIT_OK


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
    Creation date: 10/26/2026
    """
    report = check.run_check()

    for line in report.warnings:
        print("  WARNING %s" % line)

    for line in report.problems:
        print("  PROBLEM %s" % line)

    if report.ok:
        print("  the sound clips are consistent")

    return _EXIT_OK if report.ok else _EXIT_FAILED


_COMMANDS: dict = {
    "add": _command_add,
    "check": _command_check,
}


# ─── Public routines ─────────────────────────────────────────────────────────

def main(argv: list) -> int:
    """
    Purpose: Run one command of the sound wizard.

    Entry:
        argv is sys.argv.

    Exit/Returns:
        Returns the process exit status.

    Module Globals:
        _COMMANDS, _USAGE read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    arguments = argv[1:]

    if not arguments or arguments[0] not in _COMMANDS:
        print(_USAGE)
        return _EXIT_USAGE

    command = _COMMANDS[arguments[0]]

    try:
        status = command(arguments[1:])
    except (cue_table.CueTableError, credits.CreditsError,
            OSError) as problem:
        print("  %s" % problem)
        status = _EXIT_FAILED

    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
