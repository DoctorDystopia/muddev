"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The files of the dialogue scripts (DESIGN-0017): where the
             dialogue scripts and the compiled scripts are, and the check
             that each pair agrees.

             A COMPILED SCRIPT IS A GENERATED FILE IN GIT. Only the Godot
             editor has the compiler. Thus, the server reads a file that the
             script export wrote, and a compiled script can go out of date:
             an author edits a dialogue script outside the editor, or
             commits one file of the pair. Each compiled script carries the
             digest of its source. `pair_problems` compares the two, and a
             test fails on a difference.

             `check_game` is the whole check of the game: the pairs, and
             then the content rules of each compiled script. The test and
             `python -m systems.gameplay.dialogue` both call it.
"""

import os

from django.conf import settings

from systems.gameplay.dialogue import checks
from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue import loader
from systems.gameplay.dialogue.script import (
    DialogueScriptError,
    load_script,
    read_source,
    source_digest,
)


# ─── Private constant definitions ────────────────────────────────────────────

# The dialogue scripts of the game, from the root of the repository. The
# Godot editor shows only files of its project.
_SOURCE_FROM_REPO: tuple = ("godot", "dialogue")

# What an author runs to make each compiled script current.
_EXPORT_HINT: str = (
    "Save the script in the Godot editor, or run the script export "
    "(godot/addons/blackout_dialogue/export_cli.gd)")


# ─── Private helper routines ─────────────────────────────────────────────────

def _keys_with_suffix(directory: str, suffix: str) -> list:
    """The file names of one directory with one suffix, without it, sorted."""
    if not os.path.isdir(directory):
        return []

    keys = []

    for file_name in sorted(os.listdir(directory)):
        key, file_suffix = os.path.splitext(file_name)

        if file_suffix == suffix:
            keys.append(key)

    return keys


def _pair_problem(key: str, source_directory_path: str, compiled_directory: str) -> str | None:
    """The fault of the compiled script of one dialogue script, or None."""
    source_path = os.path.join(
        source_directory_path, f"{key}{dialogue_const.SOURCE_SUFFIX}")
    compiled_path = os.path.join(
        compiled_directory, f"{key}{dialogue_const.COMPILED_SUFFIX}")

    if not os.path.isfile(compiled_path):
        return f"{key}: the dialogue script has no compiled script. {_EXPORT_HINT}"

    try:
        script = load_script(compiled_path)
    except DialogueScriptError as error:
        return f"{key}: {error}"

    digest = source_digest(read_source(source_path))

    if script.source_sha256 != digest:
        return f"{key}: the compiled script is out of date. {_EXPORT_HINT}"

    return None


# ─── Public routines ─────────────────────────────────────────────────────────

def source_directory() -> str:
    """The directory of the dialogue scripts of the game: godot/dialogue/."""
    repository = os.path.dirname(settings.GAME_DIR)

    return os.path.join(repository, *_SOURCE_FROM_REPO)


def pair_problems(source_directory_path: str, compiled_directory: str) -> list:
    """
    Purpose: Check that each dialogue script has a current compiled script.

    Entry:
        source_directory_path holds `.dialogue` files.
        compiled_directory holds the `.json` files of the script export.
        The two can be one directory.

    Exit/Returns:
        Returns a list of texts, one for each fault. Empty if each pair
        agrees.

    Module Globals:
        None.

    Methodology:
        1. For each dialogue script, the compiled script must exist, and
           its digest must be the digest of the dialogue script.
        2. For each compiled script, the dialogue script must exist.

    Notes/References:
        The digest ignores the line ends. See source_digest.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    problems = []
    source_keys = _keys_with_suffix(
        source_directory_path, dialogue_const.SOURCE_SUFFIX)
    compiled_keys = _keys_with_suffix(
        compiled_directory, dialogue_const.COMPILED_SUFFIX)

    for key in source_keys:
        problem = _pair_problem(key, source_directory_path, compiled_directory)

        if problem is not None:
            problems.append(problem)

    for key in compiled_keys:
        if key not in source_keys:
            problems.append(
                f"{key}: the compiled script has no dialogue script. {_EXPORT_HINT}")

    return problems


def content_problems(key: str) -> list:
    """Each fault of the content of one compiled script of the game, as
    texts that start with the key."""
    try:
        script = load_script(loader.script_path(key))
    except DialogueScriptError as error:
        return [f"{key}: {error}"]

    found = checks.script_problems(script)

    return [f"{key}: {problem.describe()}" for problem in found]


def check_game() -> list:
    """
    Purpose: Check each dialogue script of the game.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a list of texts, one for each fault. Empty for a game with
        no fault.

    Module Globals:
        None.

    Methodology:
        1. Check each pair of a dialogue script and a compiled script.
        2. Check the content of each compiled script.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    problems = pair_problems(source_directory(), loader.compiled_directory())

    for key in loader.script_keys():
        problems.extend(content_problems(key))

    return problems
