"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/26/2026
Description: The Godot import of a new sound clip.

             The sound wizard writes the .import file of a new sound clip
             itself, from its sound kind (kinds.render_import). Then one
             headless run of Godot imports it:

                 godot --headless --path godot --import

             Godot keeps each line of [params], and it adds the uid and the
             path of the imported file. This was tested on 10/26/2026 with
             Godot 4.7.2. Thus, the wizard needs no second import to set
             Force Mono, as the hand procedure did.

             Set GODOT_BIN when Godot is in an unusual place. The deploy
             scripts read the same variable.

             Import-safe. Only run_import starts a process.
"""

import glob
import os
import shutil
import subprocess

from assets.audio import paths


# ─── Private constant definitions ────────────────────────────────────────────

_GODOT_ENV_VAR: str = "GODOT_BIN"

# Where Godot is on this machine, as deploy/full_deploy.sh names it.
# Globbed, not pinned to a version. The newest match wins.
_GODOT_SEARCH_GLOBS: tuple = (
    os.path.join("~", "Games", "Projects", "Godot", "Godot_v4*",
                 "Godot_v4*_console.exe"),
    os.path.join("~", "Games", "Projects", "Godot", "Godot_v4*_console.exe"),
)
_GODOT_COMMAND: str = "godot"
_IMPORT_FLAGS: tuple = ("--headless", "--path")
_IMPORT_FLAG: str = "--import"
_TIMEOUT_SECONDS: int = 600
_TAIL_LINES: int = 8

# The line that the import adds to a .import file.
_UID_PREFIX: str = "uid="


# ─── Public routines ─────────────────────────────────────────────────────────

def find_godot() -> str:
    """
    Purpose: Find the Godot executable.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the path of the executable, or "" when neither GODOT_BIN,
        the folder of deploy/full_deploy.sh, nor the PATH gives one.

    Module Globals:
        _GODOT_ENV_VAR, _GODOT_SEARCH_GLOBS, _GODOT_COMMAND read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    configured = os.environ.get(_GODOT_ENV_VAR, "")

    if configured and os.path.isfile(configured):
        return configured

    found = []

    for pattern in _GODOT_SEARCH_GLOBS:
        matches = glob.glob(os.path.expanduser(pattern))
        found.extend(matches)

    if found:
        return sorted(found)[-1]

    on_path = shutil.which(_GODOT_COMMAND)

    return on_path or ""


def import_command(executable: str) -> list:
    """Give the command line of the headless import of the project."""
    return [executable, *_IMPORT_FLAGS, paths.GODOT_PROJECT_DIR, _IMPORT_FLAG]


def run_import(executable: str) -> str:
    """
    Purpose: Import each new file of the Godot project.

    Entry:
        executable came from find_godot.

    Exit/Returns:
        Returns "" when Godot ends with no error. Returns the last lines of
        its output when it fails or runs past the time limit.

    Module Globals:
        _TIMEOUT_SECONDS, _TAIL_LINES read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    command = import_command(executable)

    try:
        finished = subprocess.run(command, capture_output=True, text=True,
                                  timeout=_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as problem:
        return str(problem)

    if finished.returncode == 0:
        return ""

    output = (finished.stdout or "") + (finished.stderr or "")
    tail = output.strip().splitlines()[-_TAIL_LINES:]

    return "Godot ended with code %d:\n  %s" % (finished.returncode,
                                                "\n  ".join(tail))


def is_imported(import_file: str) -> bool:
    """
    Purpose: Tell whether Godot imported one sound clip.

    Entry:
        import_file names the .import file of the sound clip.

    Exit/Returns:
        Returns True when the file holds the uid line that the import adds.

    Module Globals:
        _UID_PREFIX read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    try:
        with open(import_file, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return False

    return any(line.startswith(_UID_PREFIX) for line in lines)
