"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The loader of the compiled scripts (DESIGN-0017): one compiled
             script by its key, from `world/npc_dialogues/compiled/`.

             A SAVE IN THE EDITOR REACHES THE GAME WITH NO RELOAD. The
             loader keeps each script with the change time of its file. If
             the script export wrote the file again, the next conversation
             reads the new file.

             A SCRIPT WITH A PROBLEM DOES NOT OPEN. The loader runs the
             content check on each file that it reads. A script that the
             server cannot run raises here, before the first line reaches a
             player.
"""

import os

import world.npc_dialogues as dialogue_package

from systems.gameplay.dialogue import checks
from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue.script import (
    CompiledScript,
    DialogueScriptError,
    load_script,
)


# ─── Private constant definitions ────────────────────────────────────────────

# How many problems the error of a refused script names.
_PROBLEMS_IN_ERROR: int = 3


# ─── Module globals ──────────────────────────────────────────────────────────

# key -> (change time of the file, CompiledScript). See get_script.
_cache: dict = {}


# ─── Public routines ─────────────────────────────────────────────────────────

def compiled_directory() -> str:
    """The directory of the compiled scripts of the game."""
    package_directory = os.path.dirname(dialogue_package.__file__)
    directory = os.path.join(package_directory, dialogue_const.COMPILED_DIRECTORY)

    return directory


def script_path(key: str) -> str:
    """The path of the compiled script with this key."""
    file_name = f"{key}{dialogue_const.COMPILED_SUFFIX}"

    return os.path.join(compiled_directory(), file_name)


def script_keys() -> list:
    """The key of each compiled script of the game, in name order."""
    directory = compiled_directory()

    if not os.path.isdir(directory):
        return []

    keys = []

    for file_name in sorted(os.listdir(directory)):
        key, suffix = os.path.splitext(file_name)

        if suffix == dialogue_const.COMPILED_SUFFIX:
            keys.append(key)

    return keys


def has_script(key: str) -> bool:
    """True if a compiled script with this key exists."""
    return os.path.isfile(script_path(key))


def get_script(key: str) -> CompiledScript:
    """
    Purpose: Give the compiled script with this key, ready to run.

    Entry:
        key is the name that an NpcDef gives in `dialogue_script`.

    Exit/Returns:
        Returns the CompiledScript.
        Raises DialogueScriptError if the file is missing, if it cannot be
        read, or if the content check finds a problem.

    Module Globals:
        _cache read and written.

    Methodology:
        1. Read the change time of the file.
        2. If the cache holds the script with that change time, return it.
        3. Else, read the file and run the content check.
        4. Keep only a script with no problem.

    Notes/References:
        A refused script is not kept. Thus, the next call reads the file
        again, and a corrected file opens with no reload.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    path = script_path(key)

    try:
        changed_at = os.stat(path).st_mtime_ns
    except OSError as error:
        raise DialogueScriptError(
            f"no compiled script has the key '{key}' ({path})") from error

    cached = _cache.get(key)

    if cached is not None and cached[0] == changed_at:
        return cached[1]

    script = load_script(path)
    problems = checks.script_problems(script)

    if problems:
        first = [problem.describe() for problem in problems[:_PROBLEMS_IN_ERROR]]
        listed = ", ".join(first)

        raise DialogueScriptError(
            f"the script '{key}' has {len(problems)} problem(s): {listed}")

    _cache[key] = (changed_at, script)

    return script


def forget_all() -> None:
    """Empty the cache. A test calls it."""
    _cache.clear()
