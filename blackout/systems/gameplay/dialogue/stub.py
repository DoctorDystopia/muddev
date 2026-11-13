"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The editor stub of the dialogue vocabulary (DESIGN-0017): the
             names that a dialogue script can call, as one generated
             GDScript file for the Godot editor.

             WHY A STUB. The Run button of the Dialogue tab uses the runtime
             of the Dialogue Manager addon, with no server behind it. That
             runtime stops at the first name that it cannot find. The stub
             gives it each name of the vocabulary, with an answer that the
             author sets in the test scene.

             THE SERVER OWNS THE NAMES. The vocabulary is Python. This
             module renders the stub from it, and a test fails if the file
             in git is not that text. Never edit the stub by hand.

             THE STUB READS NO GAME. A yes or no query gives False until the
             author sets it. A text gives its call in angle brackets, so the
             author sees where each text goes. An action only records its
             call.

             The templates here indent with four spaces, as each Python
             file does. `_to_tabs` changes the indent to tabs, because the
             Godot project indents with tabs.
"""

import inspect
import os

from django.conf import settings

from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue.vocabulary import vocabulary


# ─── Public constant definitions ─────────────────────────────────────────────

# How the stub answers one name. The stub file holds the same four words.
STUB_FLAG: str = "flag"
STUB_TEXT: str = "text"
STUB_OTHER: str = "other"
STUB_ACTION: str = "action"


# ─── Private constant definitions ────────────────────────────────────────────

# The stub file, from the root of the repository.
_STUB_FROM_REPO: tuple = ("godot", "addons", "blackout_dialogue", "dialogue_stub.gd")

# The answer of a name, from the return annotation of its handler.
_ANSWER_OF_ANNOTATION: dict = {bool: STUB_FLAG, str: STUB_TEXT}

# The helper of the stub that gives each answer, and the GDScript type that
# the generated member returns.
_HELPER_OF_ANSWER: dict = {
    STUB_FLAG: ("_flag", "bool"),
    STUB_TEXT: ("_text", "String"),
    STUB_OTHER: ("_other", "Variant"),
    STUB_ACTION: ("_do", "void"),
}

# One level of indent in the templates, and in the stub file.
_TEMPLATE_INDENT: str = "    "
_GDSCRIPT_INDENT: str = "\t"

_HEADER: str = '''@tool
class_name DialogueStub
extends RefCounted
## GENERATED FILE. Do not edit it. To write it again, run from blackout/:
##
##     python -m systems.gameplay.dialogue --write-stub
##
## The dialogue vocabulary of the server as GDScript, for the Godot editor
## (DESIGN-0017). The server owns each name
## (`blackout/systems/gameplay/dialogue/vocab_defs/`). This file only lets
## the editor use the names with no server:
##
## - The test scene of the Dialogue tab gives one DialogueStub to the runtime
##   of Dialogue Manager. Thus, the Run button works on a dialogue script.
## - The Dialogue tab reads this file for its list of names.
##
## No name here reads the game. A yes or no query gives the answer that the
## author set in the test scene, and false before that. A text gives its
## call in angle brackets. An action only records its call.

const KIND_FLAG := "flag"
const KIND_TEXT := "text"
const KIND_OTHER := "other"
const KIND_ACTION := "action"

## How the stub answers each name of the vocabulary.
const KINDS := {
%(kinds)s
}

## The answer that the author set for a call, by its call text. Change it in
## place. Each namespace holds this same Dictionary.
var answers: Dictionary = {}

## Each action that the script ran, as its call text, in order.
var actions: Array[String] = []

%(namespaces)s


## The text of one call, as an author writes it:
## `quest.on_step("a", "b")`.
static func call_text(name: String, arguments: Array) -> String:
    var parts: Array[String] = []

    for argument: Variant in arguments:
        parts.append(JSON.stringify(argument))

    return "%%s(%%s)" %% [name, ", ".join(parts)]


## The part that each namespace shares: the answers, and one helper for each
## kind of answer.
class Names extends RefCounted:
    var _answers: Dictionary
    var _actions: Array[String]


    func _init(answers: Dictionary, actions: Array[String]) -> void:
        _answers = answers
        _actions = actions


    func _flag(asked: String) -> bool:
        return bool(_answers.get(asked, false))


    func _text(asked: String) -> String:
        return str(_answers.get(asked, "<%%s>" %% asked))


    func _other(asked: String) -> Variant:
        return _answers.get(asked)


    func _do(asked: String) -> void:
        _actions.append(asked)
'''

_KIND_ROW: str = '    "%(name)s": "%(answer)s",'
_NAMESPACE_MEMBER: str = "var %(namespace)s := %(class_name)s.new(answers, actions)"
_CLASS_HEADER: str = "\n\nclass %(class_name)s extends Names:"
_VALUE_MEMBER: str = '''    ## %(summary)s
    var %(member)s: %(type)s:
        get:
            return %(helper)s("%(name)s")
'''
_CALL_MEMBER: str = '''    ## %(summary)s
    func %(member)s(%(parameters)s) -> %(type)s:
        %(keyword)s%(helper)s(DialogueStub.call_text("%(name)s", [%(arguments)s]))
'''
_CLASS_NAME_SUFFIX: str = "Names"


# ─── Private helper routines ─────────────────────────────────────────────────

def _to_tabs(text: str) -> str:
    """Change the indent of each line from four spaces to one tab."""
    lines = []

    for line in text.split("\n"):
        body = line.lstrip(" ")
        levels = (len(line) - len(body)) // len(_TEMPLATE_INDENT)
        lines.append(_GDSCRIPT_INDENT * levels + body)

    return "\n".join(lines)


def _answer_of(entry: object) -> str:
    """How the stub answers one entry: an action records, and each other
    entry answers from the return annotation of its handler."""
    if entry.kind == dialogue_const.KIND_ACTION:
        return STUB_ACTION

    annotation = inspect.signature(entry.handler).return_annotation
    answer = _ANSWER_OF_ANNOTATION.get(annotation, STUB_OTHER)

    return answer


def _split(name: str) -> tuple:
    """The namespace and the member of one vocabulary name."""
    namespace, member = name.split(dialogue_const.NAME_SEPARATOR, 1)

    return namespace, member


def _class_name_of(namespace: str) -> str:
    """The name of the stub class of one namespace: `quest` -> QuestNames."""
    return f"{namespace.capitalize()}{_CLASS_NAME_SUFFIX}"


def _render_member(entry: object) -> str:
    """
    Purpose: Render one vocabulary entry as a member of its namespace class.

    Entry:
        entry is a VocabularyEntry.

    Exit/Returns:
        Returns the GDScript text of the member, with its summary above it.

    Module Globals:
        _HELPER_OF_ANSWER, _VALUE_MEMBER, _CALL_MEMBER read.

    Methodology:
        1. A value is a property, so a script reads it with no brackets.
        2. A query and an action are functions. Each argument is a Variant,
           because the runtime of the addon gives what the script wrote.
        3. The body gives the call text to the helper of the answer.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    _namespace, member = _split(entry.name)
    answer = _answer_of(entry)
    helper, gdscript_type = _HELPER_OF_ANSWER[answer]
    fields = {
        "summary": entry.summary,
        "member": member,
        "name": entry.name,
        "helper": helper,
        "type": gdscript_type,
    }

    if entry.kind == dialogue_const.KIND_VALUE:
        return _VALUE_MEMBER % fields

    parameters = [f"{argument}: Variant" for argument in entry.argument_names]
    fields["parameters"] = ", ".join(parameters)
    fields["arguments"] = ", ".join(entry.argument_names)
    fields["keyword"] = "" if answer == STUB_ACTION else "return "

    return _CALL_MEMBER % fields


def _render_classes(entries: list) -> str:
    """One class for each namespace, in name order, with each member in
    name order."""
    blocks = []
    namespaces = sorted({_split(entry.name)[0] for entry in entries})

    for namespace in namespaces:
        members = [_render_member(entry) for entry in entries
                   if _split(entry.name)[0] == namespace]
        header = _CLASS_HEADER % {"class_name": _class_name_of(namespace)}
        blocks.append(header + "\n" + "\n\n".join(members).rstrip("\n"))

    return "\n".join(blocks)


# ─── Public routines ─────────────────────────────────────────────────────────

def stub_path() -> str:
    """The path of the stub file in the Godot project."""
    repository = os.path.dirname(settings.GAME_DIR)

    return os.path.join(repository, *_STUB_FROM_REPO)


def render_stub() -> str:
    """
    Purpose: Render the whole stub file from the dialogue vocabulary.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the GDScript text, with LF line ends and a tab indent.

    Module Globals:
        The dialogue vocabulary read. _HEADER read.

    Methodology:
        1. Sort the entries by name, so the text does not depend on the
           order of the imports.
        2. Render the table of answers, one variable for each namespace,
           and one class for each namespace.
        3. Change the indent to tabs.

    Notes/References:
        tests/test_stub.py compares this text with the file in git.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    entries = [entry for _name, entry in sorted(vocabulary().items())]
    namespaces = sorted({_split(entry.name)[0] for entry in entries})
    kind_rows = [_KIND_ROW % {"name": entry.name, "answer": _answer_of(entry)}
                 for entry in entries]
    namespace_rows = [
        _NAMESPACE_MEMBER % {"namespace": namespace,
                             "class_name": _class_name_of(namespace)}
        for namespace in namespaces]
    header = _HEADER % {
        "kinds": "\n".join(kind_rows),
        "namespaces": "\n".join(namespace_rows),
    }
    text = _to_tabs(header + _render_classes(entries) + "\n")

    return text


def write_stub() -> bool:
    """Write the stub file if its text changed. Returns True if it wrote."""
    path = stub_path()
    text = render_stub()

    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", newline="") as handle:
            current = handle.read().replace("\r\n", "\n")

        if current == text:
            return False

    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)

    return True
