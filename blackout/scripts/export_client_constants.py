"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: Write the generated client constant modules to disk.

             A thin CLI over systems.statefeed.clientexport, which owns the
             rendering and is pure. Everything that touches the filesystem is
             here, and nothing here decides what a constant is.

             SAFE, unlike its neighbours in this directory. It bootstraps
             Django for settings only, touches no database, and writes exactly
             the paths in _OUTPUTS below -- all of them generated files that
             are rebuilt from Python on every run. It is still behind the
             `if __name__ == "__main__"` guard every script here carries,
             because CLAUDE.md marks this whole directory import-unsafe and one
             safe file does not change how the directory should be treated.

             Run it after changing any exported name in
             systems/statefeed/constants.py:

                 python scripts/export_client_constants.py

             `--check` writes nothing and exits non-zero when a committed file
             is stale, which is what CI and the test suite want.

             THE GENERATED FILES ARE COMMITTED. Deliberately: the webclient has
             no build step and must not acquire one just to load. The committed
             copy is the artifact the client actually reads, and
             tests/test_client_constants.py asserts it matches a fresh render,
             so a stale copy fails the suite rather than shipping.
"""

import os
import sys


# ─── Private constant definitions ────────────────────────────────────────────

# The game dir (blackout/), two levels up from scripts/export_client_constants.py.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The repo root. The Godot client is a sibling of the game dir, not inside it.
_REPO_ROOT = os.path.dirname(_GAME_DIR)

_SETTINGS_MODULE = "server.conf.settings"
_SETTINGS_ENV_VAR = "DJANGO_SETTINGS_MODULE"

# Where each rendered module is written is NOT decided here. It lives on
# clientexport._OUTPUT_PATHS, because the test that asserts the committed files
# are current needs the same table and cannot import this directory --
# CLAUDE.md marks blackout/scripts/ import-unsafe. This script reads it through
# clientexport.output_paths().

_CHECK_FLAG = "--check"

# Newline written explicitly rather than left to the platform. A generated file
# whose line endings depend on which machine rendered it is a file that shows
# up in every diff, and --check would fail on Windows against a copy committed
# from Linux.
_NEWLINE = "\n"


# ─── Private helper routines ─────────────────────────────────────────────────

def _bootstrap_django():
    """
    Purpose: Make `systems.statefeed` importable.

    Entry:
        None.

    Exit/Returns:
        None. Configures Django in-process.

    Module Globals:
        _GAME_DIR, _SETTINGS_MODULE, _SETTINGS_ENV_VAR read.

    Methodology:
        Put the game dir on sys.path, point Django at the real settings, and
        call django.setup(). Settings are needed because constants.py sits in a
        package whose siblings import Evennia; no database connection is opened
        and none is used.

    Notes/References:
        The real settings rather than test_settings, because this writes files
        a running client will read.
    """
    if _GAME_DIR not in sys.path:
        sys.path.insert(0, _GAME_DIR)

    os.environ.setdefault(_SETTINGS_ENV_VAR, _SETTINGS_MODULE)

    import django

    django.setup()


def _read_existing(path) -> str:
    """
    Purpose: Read a previously generated file, if there is one.

    Entry:
        path - absolute path to the generated file.

    Exit/Returns:
        The file's contents, or "" when it does not exist.

    Module Globals:
        None

    Methodology:
        Read with newline="" so existing line endings survive the round trip
        and a comparison against freshly rendered text is honest.

    Notes/References:
        None
    """
    if not os.path.isfile(path):
        return ""

    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _write(path, text):
    """
    Purpose: Write one generated file, creating its directory if needed.

    Entry:
        path - absolute destination path.
        text - the rendered module.

    Exit/Returns:
        None.

    Module Globals:
        _NEWLINE read.

    Methodology:
        Create the parent directory, then write with an explicit newline so the
        output is byte-identical whichever platform rendered it.

    Notes/References:
        None
    """
    directory = os.path.dirname(path)

    if directory and not os.path.isdir(directory):
        os.makedirs(directory)

    with open(path, "w", encoding="utf-8", newline=_NEWLINE) as handle:
        handle.write(text)


def _relative(path) -> str:
    """
    Purpose: Shorten a path for printing.

    Entry:
        path - absolute path.

    Exit/Returns:
        The path relative to the repo root, or the original when it lies
        outside.

    Module Globals:
        _REPO_ROOT read.

    Methodology:
        os.path.relpath, guarded: on Windows a path on another drive raises
        rather than returning something useless.

    Notes/References:
        Cosmetic only.
    """
    try:
        return os.path.relpath(path, _REPO_ROOT)
    except ValueError:
        return path


def _export(check_only) -> int:
    """
    Purpose: Render every language and either write it or compare it.

    Entry:
        check_only - True to compare and report without writing.

    Exit/Returns:
        The process exit code: 0 when everything is current or was written,
        1 when --check found a stale file.

    Module Globals:
        None

    Methodology:
        Render each language clientexport declares, look up its destination,
        and compare against what is on disk. A language with no destination is
        a loud failure rather than a skip, because it means a client was added
        to the renderer and nobody said where its file goes.

    Notes/References:
        Iterates clientexport.languages() rather than the path table, so the
        renderer stays the authority on what can be rendered.
    """
    from systems.statefeed import clientexport

    outputs = clientexport.output_paths()
    stale = []

    for language in clientexport.languages():
        path = outputs.get(language)

        if path is None:
            print("No output path for language %r; add one to _OUTPUTS."
                  % language)
            return 1

        rendered = clientexport.render(language)

        if _read_existing(path) == rendered:
            print("  current  %s" % _relative(path))
            continue

        if check_only:
            stale.append(path)
            print("  STALE    %s" % _relative(path))
            continue

        _write(path, rendered)
        print("  written  %s" % _relative(path))

    if stale:
        print("\n%d generated file(s) are out of date. Run:\n"
              "    python scripts/export_client_constants.py" % len(stale))
        return 1

    return 0


def main(argv) -> int:
    """
    Purpose: Entry point.

    Entry:
        argv - the argument list, without the program name.

    Exit/Returns:
        A process exit code.

    Module Globals:
        _CHECK_FLAG read.

    Methodology:
        Bootstrap Django, then export. Only one flag, so no argparse.

    Notes/References:
        None
    """
    check_only = _CHECK_FLAG in argv

    _bootstrap_django()

    print("Exporting client constants%s:"
          % (" (check only)" if check_only else ""))

    return _export(check_only)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
