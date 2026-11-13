"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The dialogue vocabulary (DESIGN-0017): the names that a dialogue
             script can call, and the decorators that register one.

             A NEW NAME IS ONE DECORATED FUNCTION in a module under
             `vocab_defs/`. The function gets the DialogueContext first, and
             then the arguments that the script wrote:

                 @query("quest.is_active", "True while the quest runs.")
                 def _is_active(context, quest_key):
                     ...

             THREE KINDS. A value reads one fact with no brackets
             (`player.name`). A query reads one fact from its arguments. An
             action changes the game, and only a `do` line can call it.

             NO SCRIPT RUNS CODE. An expression in a script is a tree of
             tokens. The runner resolves each name in this table and nowhere
             else. A name that is not here is a content error, not a lookup
             on a game object.

             This module imports no game system, so a module under
             `vocab_defs/` can import it with no import ring. `vocabulary()`
             loads the definitions at the first call, not at import.
"""

import importlib
import inspect
import pkgutil
from dataclasses import dataclass

from evennia.utils import logger

from systems.gameplay.dialogue import constants as dialogue_const


# ─── Private constant definitions ────────────────────────────────────────────

_DEFS_PACKAGE: str = "systems.gameplay.dialogue.vocab_defs"


# ─── Module globals ──────────────────────────────────────────────────────────

# Each registered entry, by its name. The decorators write it.
_entries: dict = {}

# True after the first load of the definition modules.
_loaded: bool = False

# One (module path, error text) for each definition module that did not load.
_load_errors: list = []


# ─── Public classes ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class VocabularyEntry:
    """
    Purpose: Describe one name that a dialogue script can call.

    Entry:
        name is "<namespace>.<member>", for example "quest.accept".
        kind is one of VOCABULARY_KINDS.
        handler is the function. It gets the DialogueContext, and then one
        positional argument for each name in argument_names.
        summary is one line for an author. The editor stub shows it.
        argument_names come from the signature of the handler.
        argument_check is None, or a function (arguments) -> text or None.
        It gets one entry for each argument: the literal that the script
        wrote, or None for an argument that is not a literal. It returns the
        text of a problem, or None.

    Exit/Returns:
        Not applicable. A dataclass.

    Module Globals:
        None.

    Methodology:
        The argument check runs in the content check, not in a conversation.
        Thus, a quest key with a typing error fails a test and the editor
        check, and no player meets it.

    Notes/References:
        checks.py runs each argument_check.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """

    name: str
    kind: str
    handler: object
    summary: str
    argument_names: tuple = ()
    argument_check: object = None


# ─── Private helper routines ─────────────────────────────────────────────────

def _argument_names_of(handler: object) -> tuple:
    """The names of the parameters of a handler after the context."""
    parameters = inspect.signature(handler).parameters
    names = tuple(parameters)

    return names[1:]


def _register(name: str, kind: str, summary: str,
              argument_check: object) -> object:
    """
    Purpose: Build the decorator that files one handler under a name.

    Entry:
        name is "<namespace>.<member>".
        kind is one of VOCABULARY_KINDS.

    Exit/Returns:
        Returns a decorator. It returns the handler unchanged.
        The decorator raises ValueError for a name with no namespace, for a
        name that is already in use, and for a value that takes arguments.

    Module Globals:
        _entries written.

    Methodology:
        The errors raise at import. `_load_definitions` records them, and
        `tests/test_vocabulary.py` fails on a record.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    def decorator(handler: object) -> object:
        argument_names = _argument_names_of(handler)

        if dialogue_const.NAME_SEPARATOR not in name:
            raise ValueError(f"the vocabulary name '{name}' has no namespace")

        if name in _entries:
            raise ValueError(f"the vocabulary name '{name}' is already in use")

        if kind == dialogue_const.KIND_VALUE and argument_names:
            raise ValueError(f"the value '{name}' cannot take an argument")

        _entries[name] = VocabularyEntry(
            name=name,
            kind=kind,
            handler=handler,
            summary=summary,
            argument_names=argument_names,
            argument_check=argument_check,
        )

        return handler

    return decorator


def _load_definitions() -> None:
    """
    Purpose: Import each module under vocab_defs/ one time.

    Entry:
        No conditions.

    Exit/Returns:
        No return value. Each decorator in each module registers its entry.

    Module Globals:
        _loaded written. _load_errors written.

    Methodology:
        1. Walk the definition package with pkgutil, as the skill registry
           does. A new namespace is one new file.
        2. Import each module. Record a module that raises, and continue.

    Notes/References:
        The walk covers `vocab_defs/` only. It is not a walk over `blackout/`.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    global _loaded

    _loaded = True
    package = importlib.import_module(_DEFS_PACKAGE)

    for _finder, module_name, _is_package in pkgutil.iter_modules(
            package.__path__, prefix=f"{_DEFS_PACKAGE}."):
        try:
            importlib.import_module(module_name)
        except Exception as error:  # noqa: BLE001 - one bad file must not hide the rest
            _load_errors.append((module_name, repr(error)))
            logger.log_trace(
                f"{dialogue_const.LOG_TAG} cannot load {module_name}: {error}")


# ─── Public routines ─────────────────────────────────────────────────────────

def value(name: str, summary: str) -> object:
    """Register a value: one fact that a script reads with no brackets."""
    return _register(name, dialogue_const.KIND_VALUE, summary, None)


def query(name: str, summary: str, argument_check: object = None) -> object:
    """Register a query: one fact that a script reads from its arguments."""
    return _register(name, dialogue_const.KIND_QUERY, summary, argument_check)


def action(name: str, summary: str, argument_check: object = None) -> object:
    """Register an action: a change to the game that a `do` line calls."""
    return _register(name, dialogue_const.KIND_ACTION, summary, argument_check)


def vocabulary() -> dict:
    """
    Purpose: Give the whole dialogue vocabulary.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a dict of name -> VocabularyEntry. Do not change it.

    Module Globals:
        _entries read. _loaded read.

    Methodology:
        Load the definition modules at the first call. A definition imports
        the quest loader, and an import of this module must not start that.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    if not _loaded:
        _load_definitions()

    return _entries


def load_errors() -> list:
    """Each (module path, error text) of a definition module that failed."""
    if not _loaded:
        _load_definitions()

    return list(_load_errors)
