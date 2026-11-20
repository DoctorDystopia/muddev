"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The constants of the dialogue scripts (DESIGN-0017): the format
             of a compiled script, the line types and the token types that
             the addon compiler writes, the kinds of a vocabulary entry, the
             rule names of the content check, and the line templates.

             THE ADDON OWNS THE FORMAT. The line types, the token types, and
             the field names here are the strings that Dialogue Manager
             writes (`godot/addons/dialogue_manager/constants.gd` and
             `compiler/compiled_line.gd`). The server only reads them.
             SUPPORTED_COMPILER_VERSION names the one compiler version that
             this package reads. `tests/test_script_files.py` compares it
             with the version in the addon, so an addon update fails a test.
"""

import re


# ─── The compiled script file ────────────────────────────────────────────────

# The format of the file that the script export writes. Increase it when the
# keys below change.
COMPILED_FORMAT: int = 1

# The COMPILER_VERSION of the addon (import_plugin.gd) that this package reads.
SUPPORTED_COMPILER_VERSION: int = 18

SOURCE_SUFFIX: str = ".dialogue"
COMPILED_SUFFIX: str = ".json"

# The directory of the compiled scripts, inside the dialogue package.
COMPILED_DIRECTORY: str = "compiled"

KEY_FORMAT: str = "format"
KEY_COMPILER_VERSION: str = "compiler_version"
KEY_SOURCE: str = "source"
KEY_SOURCE_SHA256: str = "source_sha256"
KEY_CUES: str = "cues"
KEY_LINES: str = "lines"

# The cue where each conversation starts, and the cue that holds the parting
# line. A script with no farewell cue gets the generic farewell.
CUE_START: str = "start"
CUE_FAREWELL: str = "farewell"


# ─── Line types and line ids (the addon's strings) ───────────────────────────

TYPE_BLANK: str = ""
TYPE_COMMENT: str = "comment"
TYPE_CUE: str = "cue"
TYPE_DIALOGUE: str = "dialogue"
TYPE_RESPONSE: str = "response"
TYPE_CONDITION: str = "condition"
TYPE_MATCH: str = "match"
TYPE_MUTATION: str = "mutation"
TYPE_GOTO: str = "goto"

# The line types that the runner reads. The addon also writes "while" and
# "random". The content check refuses them.
SUPPORTED_LINE_TYPES: frozenset = frozenset({
    TYPE_BLANK, TYPE_COMMENT, TYPE_CUE, TYPE_DIALOGUE, TYPE_RESPONSE,
    TYPE_CONDITION, TYPE_MATCH, TYPE_MUTATION, TYPE_GOTO,
})

ID_NULL: str = ""
ID_END: str = "end"
ID_END_CONVERSATION: str = "end!"
END_IDS: frozenset = frozenset({ID_NULL, ID_END, ID_END_CONVERSATION})

# A line id from a file that the script imports holds this mark.
IMPORT_MARK: str = "@"


# ─── Line fields (the addon's strings) ───────────────────────────────────────

FIELD_TYPE: str = "type"
FIELD_NEXT: str = "next_id"
FIELD_NEXT_AFTER: str = "next_id_after"
FIELD_NEXT_SIBLING: str = "next_sibling_id"
FIELD_TEXT: str = "text"
FIELD_CHARACTER: str = "character"
FIELD_TEXT_REPLACEMENTS: str = "text_replacements"
FIELD_CHARACTER_REPLACEMENTS: str = "character_replacements"
FIELD_VALUE_IN_TEXT: str = "value_in_text"
FIELD_RESPONSES: str = "responses"
FIELD_CONDITION: str = "condition"
FIELD_MUTATION: str = "mutation"
FIELD_EXPRESSION: str = "expression"
FIELD_CASES: str = "cases"
FIELD_IS_ELSE: str = "is_else"
FIELD_IS_SNIPPET: str = "is_snippet"

# Fields of a feature that the runner does not read. The content check
# refuses a line that fills one. The value is the name of the feature.
REFUSED_FIELDS: dict = {
    "siblings": "a random line (%)",
    "concurrent_lines": "a concurrent line (| )",
    "tags": "a tag ([#...])",
    "next_id_expression": "a jump to an expression (=> {{...}})",
}


# ─── Expression tokens (the addon's strings) ─────────────────────────────────

TOKEN_TYPE: str = "type"
TOKEN_VALUE: str = "value"
TOKEN_FUNCTION_NAME: str = "function"

TOKEN_VARIABLE: str = "variable"
TOKEN_DOT: str = "dot"
TOKEN_FUNCTION: str = "function"
TOKEN_STRING: str = "string"
TOKEN_NUMBER: str = "number"
TOKEN_BOOL: str = "bool"
TOKEN_GROUP: str = "group"
TOKEN_NOT: str = "not"
TOKEN_COMPARISON: str = "comparison"
TOKEN_AND_OR: str = "and_or"
TOKEN_COMMA: str = "comma"
TOKEN_PARENS_CLOSE: str = "parens_close"

# A value that the runner puts into an expression itself: the value of a
# `match` line, in front of a `when` case that starts with a comparison.
TOKEN_RESOLVED: str = "value"

OPERATOR_AND: str = "and"
OPERATOR_OR: str = "or"

# A vocabulary name is "<namespace>.<member>".
NAME_SEPARATOR: str = "."


# ─── Vocabulary entry kinds ──────────────────────────────────────────────────

# A value reads one fact, with no brackets: `player.name`.
KIND_VALUE: str = "value"
# A query reads one fact from its arguments: `quest.is_active("key")`.
KIND_QUERY: str = "query"
# An action changes the game. Only a `do` line can call it.
KIND_ACTION: str = "action"

VOCABULARY_KINDS: tuple = (KIND_VALUE, KIND_QUERY, KIND_ACTION)


# ─── Where a script uses an expression ───────────────────────────────────────

USAGE_CONDITION: str = "condition"
USAGE_MUTATION: str = "do line"
USAGE_TEXT: str = "text"


# ─── The runner ──────────────────────────────────────────────────────────────

# The most lines that the runner reads for one beat. A jump that goes in a
# circle with no response reaches it.
STEP_LIMIT: int = 500

# How the runner shows a spoken line of a speaker that is not the NPC of the
# conversation, and how it joins the lines of a beat. A line of the NPC
# itself shows with no name (runner._say_line).
SPEECH_TEMPLATE: str = "{speaker}: {line}"
LINE_SEPARATOR: str = "\n\n"

# The addon reads "Name: text" in a response as a speaker and a line. A
# response has no speaker in Blackout, so the runner joins the two again.
RESPONSE_TEMPLATE: str = "{speaker}: {line}"

# The name of an NPC that the runner cannot resolve.
UNKNOWN_NPC_NAME: str = "Someone"

# The line that asks the player to take a quest (`quest.accept_prompt`).
ACCEPT_PROMPT_TEMPLATE: str = "Accept the quest '{title}'?"

# The heading above the objective lines of a quest.
OBJECTIVES_HEADING: str = "Objectives:"
OBJECTIVE_INDENT: str = "  "

LOG_TAG: str = "[DIALOGUE]"


# ─── The dialogue memory ─────────────────────────────────────────────────────

# The Attribute on a player character that holds its dialogue memory: one
# dict of memory key -> value. memory.py is its one reader and writer.
MEMORY_ATTRIBUTE: str = "dialogue_memory"

# The two names of the memory vocabulary. The content check reads them to
# find each recall of a key that no script remembers.
MEMORY_REMEMBER: str = "memory.remember"
MEMORY_RECALL: str = "memory.recall"

# The position of the key in the arguments of the two names.
MEMORY_KEY_ARGUMENT: int = 0

# A memory key is snake_case, as a quest key is.
MEMORY_KEY_PATTERN: re.Pattern = re.compile(r"^[a-z][a-z0-9_]*$")

# The types of value that the memory keeps: the literals that a script can
# write. A game object is not a fact of a conversation.
MEMORY_VALUE_TYPES: tuple = (str, int, float, bool)


# ─── The content check ───────────────────────────────────────────────────────

RULE_VERSION: str = "compiler_version"
RULE_START_CUE: str = "start_cue"
RULE_LINE_TYPE: str = "line_type"
RULE_FEATURE: str = "feature"
RULE_MARKUP: str = "markup"
RULE_TARGET: str = "target"
RULE_FALL_THROUGH: str = "fall_through"
RULE_EXPRESSION: str = "expression"
RULE_NAME: str = "name"
RULE_KIND: str = "kind"
RULE_ARITY: str = "arity"
RULE_ARGUMENT: str = "argument"
# A recall of a memory key that no script of the game remembers. Only the
# check of the whole game finds it (checks.memory_problems).
RULE_MEMORY: str = "memory"

CHECK_RULES: tuple = (
    RULE_VERSION, RULE_START_CUE, RULE_LINE_TYPE, RULE_FEATURE, RULE_MARKUP,
    RULE_TARGET, RULE_FALL_THROUGH, RULE_EXPRESSION, RULE_NAME, RULE_KIND,
    RULE_ARITY, RULE_ARGUMENT, RULE_MEMORY,
)

# Inline markup of the addon that the runner does not read. Each entry is the
# name of the feature and the pattern that finds it in the text of a line.
REFUSED_MARKUP: tuple = (
    ("an inline random text ([[a|b]])", re.compile(r"\[\[.*?\]\]")),
    ("an inline condition ([if ...])", re.compile(r"\[/?if\b")),
    ("an inline mutation ([do ...])", re.compile(r"\[(do!?|set|\$>>?) ")),
    ("a pause, a speed, or an auto-advance tag",
     re.compile(r"\[/?(wait|speed|next)\b")),
)
