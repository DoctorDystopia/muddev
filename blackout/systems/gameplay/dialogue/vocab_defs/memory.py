"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/19/2026
Description: The `memory.*` names of the dialogue vocabulary (DESIGN-0017):
             a value that a script keeps for the player, and reads back in a
             later cue or a later talk.

                 do memory.remember("human_reading", 72)
                 {{memory.recall("human_reading", 82)}}

             `systems/gameplay/dialogue/memory.py` holds the value. This
             module only gives the two names to the scripts.

             EACH ARGUMENT IS A LITERAL. The argument checks refuse a key
             that is not a snake_case text. They also refuse a value or a
             default that is not a literal. Thus, the content check can
             match each recall with a remember (checks.memory_problems).
"""

from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue import memory
from systems.gameplay.dialogue.vocabulary import action, query


# ─── Private constant definitions ────────────────────────────────────────────

# The position of the value of a remember, and of the default of a recall.
_VALUE_ARGUMENT: int = 1

_KEY_EXAMPLE: str = '"human_reading"'


# ─── Private helper routines ─────────────────────────────────────────────────

def _check_key(arguments: list) -> str | None:
    """The problem with the memory key of a call, or None."""
    key = arguments[dialogue_const.MEMORY_KEY_ARGUMENT]

    if not isinstance(key, str):
        return f"the key must be a literal text, for example {_KEY_EXAMPLE}"

    if not dialogue_const.MEMORY_KEY_PATTERN.match(key):
        return (f"the key '{key}' must be snake_case, for example "
                f"{_KEY_EXAMPLE}")

    return None


def _check_literal(arguments: list, role: str) -> str | None:
    """The problem with the key or with the literal after it, or None. role
    is the name of the second argument in the problem text."""
    key_problem = _check_key(arguments)
    second = arguments[_VALUE_ARGUMENT]

    if key_problem is not None:
        return key_problem

    if not isinstance(second, dialogue_const.MEMORY_VALUE_TYPES):
        return f"the {role} must be a literal: a text, a number, or true or false"

    return None


def _check_remember(arguments: list) -> str | None:
    """The problem with the arguments of `memory.remember`, or None."""
    return _check_literal(arguments, "value")


def _check_recall(arguments: list) -> str | None:
    """The problem with the arguments of `memory.recall`, or None."""
    return _check_literal(arguments, "default")


# ─── The names ───────────────────────────────────────────────────────────────

@action(dialogue_const.MEMORY_REMEMBER,
        "Keep a value for the player under a key. A later cue or talk recalls it.",
        argument_check=_check_remember)
def _remember(context: object, key: str, value: object) -> None:
    memory.remember(context.caller, key, value)


@query(dialogue_const.MEMORY_RECALL,
       "The value that the player keeps under a key, or the default if none.",
       argument_check=_check_recall)
def _recall(context: object, key: str, default: object) -> object:
    recalled = memory.recall(context.caller, key, default)

    return recalled
