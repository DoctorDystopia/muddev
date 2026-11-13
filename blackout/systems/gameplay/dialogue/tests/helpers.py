"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: Shared parts of the dialogue tests (DESIGN-0017): the fixture
             scripts, a test vocabulary, a stub talker, and the helpers
             that give a response by a keyword of its label.

             THE FIXTURES USE A TEST VOCABULARY. A fixture script calls
             `state.*` names, which read a StubTalker. Thus, the tests of
             the runner and of the content check need no database and no
             quest, and a change to the vocabulary of the game breaks none.
             `use_test_vocabulary` puts the test vocabulary in place for one
             test.

             A content test of the game, for example the playthrough of a
             quest, uses `talk` and `give` with the real vocabulary.
"""

import os
from unittest import mock

from systems.gameplay.dialogue import checks, expressions, loader
from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue.runner import Conversation, DialogueContext
from systems.gameplay.dialogue.script import load_script
from systems.gameplay.dialogue.vocabulary import VocabularyEntry


# ─── Public constant definitions ─────────────────────────────────────────────

FIXTURE_DIRECTORY: str = os.path.join(os.path.dirname(__file__), "fixtures")

FIXTURE_FLOW: str = "flow"
FIXTURE_REFUSED: str = "refused"
FIXTURE_NO_START: str = "no_start"

# The argument that `state.checked` refuses, in the refused fixture.
REFUSED_ARGUMENT: str = "bad"
REFUSED_ARGUMENT_TEXT: str = "the fixture refuses this argument"


# ─── Public classes ──────────────────────────────────────────────────────────

class StubTalker:
    """The player side of a fixture conversation. The `state.*` names read
    it, and `state.raise` writes it."""

    def __init__(self, name: str = "Tester"):
        self.key = name
        self.flags = set()
        self.counts = {}
        self.texts = {}
        self.raised = []


# ─── Private helper routines ─────────────────────────────────────────────────

def _flag(context: object, name: str) -> bool:
    return name in context.caller.flags


def _count(context: object, name: str) -> int:
    return context.caller.counts.get(name, 0)


def _text(context: object, name: str) -> str:
    return context.caller.texts.get(name, "")


def _name(context: object) -> str:
    return context.caller.key


def _raise(context: object, name: str) -> None:
    context.caller.raised.append(name)
    context.caller.flags.add(name)


def _checked(context: object, key: str) -> bool:
    return True


def _refuse_bad(arguments: list) -> str | None:
    if arguments[0] == REFUSED_ARGUMENT:
        return REFUSED_ARGUMENT_TEXT

    return None


# ─── Public routines ─────────────────────────────────────────────────────────

def fixture_vocabulary() -> dict:
    """The vocabulary that the fixture scripts call: name -> entry."""
    entries = (
        VocabularyEntry("state.flag", dialogue_const.KIND_QUERY, _flag,
                        "A flag of the stub talker.", ("name",)),
        VocabularyEntry("state.count", dialogue_const.KIND_QUERY, _count,
                        "A count of the stub talker.", ("name",)),
        VocabularyEntry("state.text", dialogue_const.KIND_QUERY, _text,
                        "A text of the stub talker.", ("name",)),
        VocabularyEntry("state.name", dialogue_const.KIND_VALUE, _name,
                        "The name of the stub talker."),
        VocabularyEntry("state.raise", dialogue_const.KIND_ACTION, _raise,
                        "Raise a flag of the stub talker.", ("name",)),
        VocabularyEntry("state.checked", dialogue_const.KIND_QUERY, _checked,
                        "A query with an argument check.", ("key",),
                        _refuse_bad),
    )

    return {entry.name: entry for entry in entries}


def use_test_vocabulary(test_case: object) -> None:
    """Put the test vocabulary in place of the game vocabulary, until the
    test ends. Call it in setUp."""
    entries = fixture_vocabulary()

    for module in (expressions, checks):
        patcher = mock.patch.object(module, "vocabulary", return_value=entries)
        patcher.start()
        test_case.addCleanup(patcher.stop)


def fixture_path(key: str, suffix: str = dialogue_const.COMPILED_SUFFIX) -> str:
    """The path of one fixture file."""
    return os.path.join(FIXTURE_DIRECTORY, f"{key}{suffix}")


def load_fixture(key: str) -> object:
    """The compiled script of one fixture."""
    return load_script(fixture_path(key))


def fixture_conversation(key: str, talker: object = None,
                         npc: object = None) -> Conversation:
    """A conversation from a fixture script, with a stub talker. A StubTalker
    also serves as the NPC: the runner reads only its `key`."""
    caller = talker or StubTalker()
    context = DialogueContext(caller=caller, npc=npc)

    return Conversation(load_fixture(key), context)


def talk(caller: object, script_key: str, npc: object = None,
         cue: str = dialogue_const.CUE_START) -> Conversation:
    """Open a conversation from a script of the game, as `talk` does, with
    no menu. Returns the Conversation at its first beat. A test can start
    at a different cue, for a beat that no response reaches in its state."""
    script = loader.get_script(script_key)
    conversation = Conversation(script, DialogueContext(caller=caller, npc=npc))
    conversation.open(cue)

    return conversation


def response_index(conversation: Conversation, keyword: str) -> int:
    """The index of the one response whose label holds a keyword. Raises
    AssertionError if no response or more than one response holds it."""
    labels = [response.label for response in conversation.beat.responses]
    found = [index for index, label in enumerate(labels)
             if keyword.lower() in label.lower()]

    if len(found) != 1:
        raise AssertionError(
            f"{len(found)} response(s) hold '{keyword}'. The beat offers: {labels}")

    return found[0]


def give(conversation: Conversation, keyword: str) -> object:
    """Give the response whose label holds a keyword. Returns the next beat."""
    index = response_index(conversation, keyword)

    return conversation.choose(index)
