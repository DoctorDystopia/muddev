"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: The rule that keeps the profiling harness out of the game.

             The dependency arrow points one way: profiling -> game, never the
             reverse. Nothing under blackout/ outside systems/profiling/ may
             import it, and nothing may import it at server start.

             This is asserted rather than trusted because it is a rule a
             well-meaning edit breaks with a single convenient import -- a
             serializer that wants a timing decorator, a command that wants a
             query counter -- and the damage from that is not obvious. The
             harness imports cProfile, django.test and Evennia's test
             resources; dragging those into a running server is how a
             production process ends up with the test framework loaded.

             The precedent is systems/statefeed/tests/test_client_constants.py,
             which guards a rule about generated files the same way: a
             convention nobody can violate silently.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.profiling
"""

import ast
import os
import unittest


# ─── Private constant definitions ────────────────────────────────────────────

# The game directory, four levels up from
# systems/profiling/tests/test_isolation.py.
_HERE = os.path.dirname(os.path.abspath(__file__))
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))

# The package that may not be imported from outside itself.
_PACKAGE = "systems.profiling"

# The one legitimate exception, and the reason it is legitimate: test_settings
# names the runner as a STRING for Django to import, and server/conf/testrunner
# composes the instrument. Neither is loaded by a running server -- settings.py
# does not import test_settings, and the runner module is only reached through
# the TEST_RUNNER setting.
_ALLOWED_IMPORTERS = {
    os.path.join("server", "conf", "testrunner.py"),
}

# Directories that hold no game code and are not walked. scripts/ is excluded
# because CLAUDE.md marks it import-unsafe -- reading it is fine, but the
# profiling CLI legitimately lives there and is not a game module.
_SKIPPED_DIRECTORIES = ("__pycache__", "profiling_out", "backups", "assets")


# ─── Private helper routines ─────────────────────────────────────────────────

def _game_modules():
    """
    Purpose: Yield every game .py file that is not part of the harness.

    Entry:
        No conditions.

    Exit/Returns:
        Yields (absolute_path, relative_path) pairs.

    Module Globals:
        _GAME_DIR and _SKIPPED_DIRECTORIES read.

    Methodology:
        The harness's own tree is skipped -- it is allowed to import itself --
        and so is scripts/, which holds the CLI. The CLI naming the package is
        the intended direction of the arrow.

    Notes/References:
        The files are READ and parsed, never imported. CLAUDE.md's first
        warning is that bulk-importing modules under blackout/ once deleted 347
        grid rooms; a test that enforced an import rule by importing everything
        would be that same loop.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    harness_root = os.path.join(_GAME_DIR, "systems", "profiling")
    scripts_root = os.path.join(_GAME_DIR, "scripts")

    for base, directories, files in os.walk(_GAME_DIR):
        directories[:] = [name for name in directories
                          if name not in _SKIPPED_DIRECTORIES]

        if base.startswith(harness_root) or base.startswith(scripts_root):
            continue

        for name in files:
            if not name.endswith(".py"):
                continue

            absolute = os.path.join(base, name)
            relative = os.path.relpath(absolute, _GAME_DIR)

            yield absolute, relative


def _imported_names(path) -> list:
    """
    Purpose: List every module name a file imports.

    Entry:
        path - absolute path to a .py file.

    Exit/Returns:
        Returns a list of dotted module names. A file that will not parse
        contributes nothing rather than raising -- a syntax error is a
        different test's business.

    Module Globals:
        None.

    Methodology:
        ast rather than a regex, so that the word "systems.profiling" appearing
        in a docstring or a comment -- which it does, in several modules that
        reference this harness in prose -- is not mistaken for an import.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    names = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
            continue

        if isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)

    return names


# ─── Public routines / Classes ───────────────────────────────────────────────

class TestProfilingIsNotImportedByTheGame(unittest.TestCase):
    """Nothing under blackout/ may import the profiling harness.

    Plain unittest.TestCase: this reads files off disk and needs no database,
    no fixtures and no Evennia. Inheriting anything heavier would be paying
    ~130ms per method for nothing -- which is the exact waste the audit this
    package produced went looking for.
    """

    def test_no_game_module_imports_the_harness(self):
        """The dependency arrow points profiling -> game, never the reverse."""
        offenders = []

        for absolute, relative in _game_modules():
            if relative in _ALLOWED_IMPORTERS:
                continue

            imported = _imported_names(absolute)

            for name in imported:
                if name == _PACKAGE or name.startswith(_PACKAGE + "."):
                    offenders.append(f"{relative} imports {name}")

        self.assertEqual(offenders, [],
                         "Profiling code must stay decoupled from production "
                         "logic. Move what is needed into the harness, or "
                         "profile from outside through an existing seam "
                         "(systems/tick/engine.py's register_phase_hook is "
                         "the one built for this).")


    def test_the_allowed_importer_actually_exists(self):
        """A stale exemption is worse than none -- it silently permits a path.

        If server/conf/testrunner.py is ever renamed, this fails rather than
        leaving an entry that would quietly excuse some future file that
        happens to land on the same path.
        """
        for relative in _ALLOWED_IMPORTERS:
            path = os.path.join(_GAME_DIR, relative)

            self.assertTrue(os.path.isfile(path),
                            f"exempted importer {relative} no longer exists; "
                            "remove it from _ALLOWED_IMPORTERS")
