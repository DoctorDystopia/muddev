"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The expressions of a compiled script (DESIGN-0017): the
             condition of an `if`, the call of a `do` line, and the
             `{{...}}` in a text.

             AN EXPRESSION IS A TREE OF TOKENS. The addon compiler makes the
             tree. This module reads it, and it never runs a text as code.
             Each name resolves in the dialogue vocabulary and nowhere else.

             A SUBSET, ON PURPOSE. The module reads these tokens: a
             vocabulary name, a text, a number, true and false, brackets,
             `not`, a comparison, and `and` / `or`. It refuses arithmetic,
             an assignment, an array, and a dictionary. The content check
             (checks.py) gives the refusal to the author.

             THE ORDER IS THE ADDON'S ORDER. The test run in the Godot
             editor uses the resolver of the addon
             (`DialogueManager._resolve`). A script must give the same
             result here. Thus, this module copies its order:
               1. Split at the LAST `and` / `or`. The left side decides
                  first.
               2. Resolve each bracket and each name.
               3. Apply each `not` to the value after it.
               4. Apply each comparison, from the left.
             `a or b and c` is `(a or b) and c`, as in the addon. Brackets
             remove the doubt.
"""

import operator
from dataclasses import dataclass

from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue.script import DialogueScriptError
from systems.gameplay.dialogue.vocabulary import vocabulary


# ─── Private constant definitions ────────────────────────────────────────────

def _contains(member: object, container: object) -> bool:
    """The `in` comparison. A None on either side is False, as in the addon."""
    if member is None or container is None:
        return False

    return member in container


# Each comparison that a script can write, and the function that applies it.
_COMPARISONS: dict = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "in": _contains,
}

# Tokens that carry their own value.
_LITERAL_TOKENS: frozenset = frozenset({
    dialogue_const.TOKEN_STRING,
    dialogue_const.TOKEN_NUMBER,
    dialogue_const.TOKEN_BOOL,
    dialogue_const.TOKEN_RESOLVED,
})

# Tokens that the reduction in _reduce keeps as operators.
_OPERATOR_TOKENS: frozenset = frozenset({
    dialogue_const.TOKEN_NOT,
    dialogue_const.TOKEN_COMPARISON,
})

# Each token type that this module reads.
_SUPPORTED_TOKENS: frozenset = _LITERAL_TOKENS | _OPERATOR_TOKENS | frozenset({
    dialogue_const.TOKEN_VARIABLE,
    dialogue_const.TOKEN_DOT,
    dialogue_const.TOKEN_FUNCTION,
    dialogue_const.TOKEN_GROUP,
    dialogue_const.TOKEN_AND_OR,
    dialogue_const.TOKEN_PARENS_CLOSE,
})

# How many tokens one vocabulary name takes: namespace, dot, member.
_REFERENCE_LENGTH: int = 3

# The two forms of an item in _reduce: a value, or an operator.
_ITEM_VALUE: str = "value"


# ─── Public classes ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Reference:
    """
    Purpose: Describe one use of a vocabulary name in an expression.

    Entry:
        name is "<namespace>.<member>".
        is_call is True if the script wrote brackets after the name.
        arguments holds one token list for each argument.

    Exit/Returns:
        Not applicable. A dataclass.

    Module Globals:
        None.

    Methodology:
        The evaluation and the content check read a name through the same
        routine, `_read_reference`. Thus, the two cannot read a name
        differently.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """

    name: str
    is_call: bool
    arguments: tuple = ()


    def literal_arguments(self) -> list:
        """One entry for each argument: its literal, or None if it has none."""
        literals = []

        for argument in self.arguments:
            literals.append(_literal_of(argument))

        return literals


# ─── Private helper routines ─────────────────────────────────────────────────

def _type_of(token: dict) -> str:
    """The type of one token."""
    return token.get(dialogue_const.TOKEN_TYPE, "")


def _without_brackets(tokens: list) -> list:
    """The tokens with no closing bracket. The addon leaves one in the last
    argument of each call."""
    return [token for token in tokens
            if _type_of(token) != dialogue_const.TOKEN_PARENS_CLOSE]


def _literal_of(tokens: list) -> object:
    """The value of an argument that is one literal, or None."""
    cleaned = _without_brackets(tokens)

    if len(cleaned) != 1:
        return None

    only = cleaned[0]

    if _type_of(only) not in _LITERAL_TOKENS:
        return None

    return only.get(dialogue_const.TOKEN_VALUE)


def _arguments_of(function_token: dict) -> tuple:
    """The token list of each argument of a call. A call with empty brackets
    has no argument."""
    raw_arguments = function_token.get(dialogue_const.TOKEN_VALUE) or []
    arguments = []

    for raw_argument in raw_arguments:
        cleaned = _without_brackets(raw_argument)

        if cleaned:
            arguments.append(cleaned)

    return tuple(arguments)


def _read_reference(tokens: list, index: int) -> Reference:
    """
    Purpose: Read the vocabulary name that starts at one token.

    Entry:
        tokens[index] is a variable token, the namespace.

    Exit/Returns:
        Returns the Reference. It covers _REFERENCE_LENGTH tokens.
        Raises DialogueScriptError if no dot and member follow the namespace.

    Module Globals:
        None.

    Methodology:
        The addon writes `quest.accept("x")` as three tokens: the variable
        `quest`, a dot, and the function `accept` with its arguments. It
        writes `player.name` as a variable, a dot, and a variable.

    Notes/References:
        A name with no namespace, for example `gold`, is not in the
        vocabulary. The same error refuses it.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    namespace = tokens[index].get(dialogue_const.TOKEN_VALUE)
    has_member = len(tokens) >= index + _REFERENCE_LENGTH

    if not has_member or _type_of(tokens[index + 1]) != dialogue_const.TOKEN_DOT:
        raise DialogueScriptError(
            f"'{namespace}' is not a vocabulary name. A name is "
            f"'<namespace>.<member>'")

    member_token = tokens[index + 2]
    member_type = _type_of(member_token)

    if member_type == dialogue_const.TOKEN_FUNCTION:
        member = member_token.get(dialogue_const.TOKEN_FUNCTION_NAME)
        name = f"{namespace}{dialogue_const.NAME_SEPARATOR}{member}"

        return Reference(name, True, _arguments_of(member_token))

    if member_type == dialogue_const.TOKEN_VARIABLE:
        member = member_token.get(dialogue_const.TOKEN_VALUE)
        name = f"{namespace}{dialogue_const.NAME_SEPARATOR}{member}"

        return Reference(name, False)

    raise DialogueScriptError(f"no member name follows '{namespace}.'")


def _call(reference: Reference, context: object, actions_allowed: bool) -> object:
    """
    Purpose: Resolve one vocabulary name to its value.

    Entry:
        reference names the entry and holds the argument tokens.
        actions_allowed is True only for a `do` line.

    Exit/Returns:
        Returns what the handler returns.
        Raises DialogueScriptError for an unknown name, for an action
        outside a `do` line, and for a wrong number of arguments.

    Module Globals:
        The dialogue vocabulary read.

    Methodology:
        1. Find the entry.
        2. Refuse an action where a script only reads.
        3. Resolve each argument. An argument never calls an action.
        4. Call the handler with the context and the arguments.

    Notes/References:
        The content check finds each of these errors before a player does.
        These guards are for a script that went past the check.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    entry = vocabulary().get(reference.name)

    if entry is None:
        raise DialogueScriptError(
            f"'{reference.name}' is not in the dialogue vocabulary")

    if entry.kind == dialogue_const.KIND_ACTION and not actions_allowed:
        raise DialogueScriptError(
            f"the action '{reference.name}' can run only in a `do` line")

    if len(reference.arguments) != len(entry.argument_names):
        raise DialogueScriptError(
            f"'{reference.name}' takes {len(entry.argument_names)} "
            f"argument(s), and the script gives {len(reference.arguments)}")

    values = [_resolve(argument, context, False)
              for argument in reference.arguments]
    result = entry.handler(context, *values)

    return result


def _last_and_or(tokens: list) -> int | None:
    """The index of the last `and` / `or` that has a token on each side."""
    found = None

    for index, token in enumerate(tokens):
        if _type_of(token) == dialogue_const.TOKEN_AND_OR:
            found = index

    if found is None or found == 0 or found == len(tokens) - 1:
        return None

    return found


def _reduce(tokens: list, context: object, actions_allowed: bool) -> list:
    """
    Purpose: Resolve each bracket, literal, and name of a token list.

    Entry:
        tokens holds no `and` / `or` at its top level.

    Exit/Returns:
        Returns a list of (kind, payload) items. A value item is
        (_ITEM_VALUE, value). An operator item is (token type, operator).
        Raises DialogueScriptError for a token that this module does not
        read.

    Module Globals:
        _LITERAL_TOKENS, _OPERATOR_TOKENS read.

    Methodology:
        Read the tokens from the left. A name takes three tokens. Each other
        token is one item.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    items = []
    index = 0

    while index < len(tokens):
        token = tokens[index]
        token_type = _type_of(token)
        token_value = token.get(dialogue_const.TOKEN_VALUE)

        if token_type in _LITERAL_TOKENS:
            items.append((_ITEM_VALUE, token_value))
        elif token_type == dialogue_const.TOKEN_GROUP:
            group_value = _resolve(token_value, context, actions_allowed)
            items.append((_ITEM_VALUE, group_value))
        elif token_type == dialogue_const.TOKEN_VARIABLE:
            reference = _read_reference(tokens, index)
            name_value = _call(reference, context, actions_allowed)
            items.append((_ITEM_VALUE, name_value))
            index += _REFERENCE_LENGTH - 1
        elif token_type in _OPERATOR_TOKENS:
            items.append((token_type, token_value))
        else:
            raise DialogueScriptError(
                f"the server does not read a '{token_type}' in an expression")

        index += 1

    return items


def _apply_nots(items: list) -> list:
    """Apply each `not` to the value after it, from the left."""
    applied = []
    negate = False

    for kind, payload in items:
        if kind == dialogue_const.TOKEN_NOT:
            negate = not negate
            continue

        if kind == _ITEM_VALUE and negate:
            payload = not is_true(payload)
            negate = False

        applied.append((kind, payload))

    if negate:
        raise DialogueScriptError("a `not` has no value after it")

    return applied


def _apply_comparisons(items: list) -> object:
    """
    Purpose: Apply each comparison of a reduced token list, from the left.

    Entry:
        items holds value items, with one comparison item between two values.

    Exit/Returns:
        Returns the one value that is left.
        Raises DialogueScriptError if the items are not in that order.

    Module Globals:
        _COMPARISONS read.

    Methodology:
        1. Take the first value.
        2. For each comparison and the value after it, compare and keep the
           result as the new first value.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    if not items or items[0][0] != _ITEM_VALUE:
        raise DialogueScriptError("an expression has no value at its start")

    result = items[0][1]
    remaining = items[1:]

    if len(remaining) % 2 != 0:
        raise DialogueScriptError("an expression has a value or a comparison too many")

    for position in range(0, len(remaining), 2):
        operator_kind, symbol = remaining[position]
        value_kind, right_value = remaining[position + 1]
        compare = _COMPARISONS.get(str(symbol).strip())

        if operator_kind != dialogue_const.TOKEN_COMPARISON or compare is None:
            raise DialogueScriptError(f"'{symbol}' is not a comparison")

        if value_kind != _ITEM_VALUE:
            raise DialogueScriptError(f"no value follows the comparison '{symbol}'")

        result = compare(result, right_value)

    return result


def _resolve(tokens: list, context: object, actions_allowed: bool) -> object:
    """
    Purpose: Give the value of one token list.

    Entry:
        tokens is an expression as the addon compiler wrote it.

    Exit/Returns:
        Returns the value. Raises DialogueScriptError for an expression that
        this module does not read.

    Module Globals:
        None.

    Methodology:
        The four steps of the module header, in that order. The left side of
        an `and` / `or` decides alone when it can, so the right side does
        not run.

    Notes/References:
        `DialogueManager._resolve` in the addon is the model.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    cleaned = _without_brackets(tokens)
    split_at = _last_and_or(cleaned)

    if split_at is not None:
        symbol = cleaned[split_at].get(dialogue_const.TOKEN_VALUE)
        left_value = _resolve(cleaned[:split_at], context, actions_allowed)
        left_is_true = is_true(left_value)

        if symbol == dialogue_const.OPERATOR_AND and not left_is_true:
            return False

        if symbol == dialogue_const.OPERATOR_OR and left_is_true:
            return True

        right_value = _resolve(cleaned[split_at + 1:], context, actions_allowed)

        return is_true(right_value)

    items = _reduce(cleaned, context, actions_allowed)
    items = _apply_nots(items)
    result = _apply_comparisons(items)

    return result


def _collect(tokens: list, references: list, refused: set) -> None:
    """
    Purpose: Walk one token list for the content check.

    Entry:
        references and refused are the two collections to fill.

    Exit/Returns:
        No return value. Appends each Reference, and adds each token type
        that this module does not read.

    Module Globals:
        _SUPPORTED_TOKENS read.

    Methodology:
        Read the tokens from the left, as _reduce does. Walk into each
        bracket and each argument. A name that does not read is a refused
        variable.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    index = 0

    while index < len(tokens):
        token = tokens[index]
        token_type = _type_of(token)

        if token_type not in _SUPPORTED_TOKENS:
            refused.add(token_type)
        elif token_type == dialogue_const.TOKEN_GROUP:
            _collect(token.get(dialogue_const.TOKEN_VALUE) or [], references, refused)
        elif token_type == dialogue_const.TOKEN_VARIABLE:
            try:
                reference = _read_reference(tokens, index)
            except DialogueScriptError:
                refused.add(str(token.get(dialogue_const.TOKEN_VALUE)))
            else:
                references.append(reference)
                index += _REFERENCE_LENGTH - 1

                for argument in reference.arguments:
                    _collect(argument, references, refused)

        index += 1


# ─── Public routines ─────────────────────────────────────────────────────────

def is_true(value: object) -> bool:
    """True if a script takes this value as true. An empty text, an empty
    list, zero, and None are false, as in the addon."""
    return bool(value)


def evaluate(tokens: list, context: object, actions_allowed: bool = False) -> object:
    """
    Purpose: Give the value of one expression of a compiled script.

    Entry:
        tokens is the `expression` list of a condition, a mutation, or a
        replacement.
        context is the DialogueContext of the conversation.
        actions_allowed is True only for the expression of a `do` line.

    Exit/Returns:
        Returns the value. Raises DialogueScriptError for an expression that
        the server does not read, or for a name outside the vocabulary.

    Module Globals:
        None.

    Methodology:
        See the module header for the order.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    result = _resolve(tokens, context, actions_allowed)

    return result


def split_cases(tokens: list) -> list:
    """The values of one `when` line. `when "a", "b"` gives two token lists."""
    cases = []
    current = []

    for token in _without_brackets(tokens):
        if _type_of(token) == dialogue_const.TOKEN_COMMA:
            cases.append(current)
            current = []
        else:
            current.append(token)

    cases.append(current)

    return [case for case in cases if case]


def matches_case(match_value: object, tokens: list, context: object) -> bool:
    """
    Purpose: Decide if the value of a `match` line fits one `when` line.

    Entry:
        match_value is the value of the `match` expression.
        tokens is the expression of the `when` line.

    Exit/Returns:
        Returns True if one value of the `when` line fits.

    Module Globals:
        None.

    Methodology:
        1. Split the `when` line at each comma.
        2. If a value starts with a comparison, for example `when > 5`, put
           the match value in front and take the result.
        3. Else, compare the value with the match value for equality.

    Notes/References:
        `DialogueManager._check_case_value` in the addon is the model.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    for case in split_cases(tokens):
        if _type_of(case[0]) == dialogue_const.TOKEN_COMPARISON:
            resolved_token = {
                dialogue_const.TOKEN_TYPE: dialogue_const.TOKEN_RESOLVED,
                dialogue_const.TOKEN_VALUE: match_value,
            }
            compared = _resolve([resolved_token] + case, context, False)

            if is_true(compared):
                return True
        else:
            case_value = _resolve(case, context, False)

            if case_value == match_value:
                return True

    return False


def inspect_tokens(tokens: list) -> tuple:
    """
    Purpose: List what one expression uses, for the content check.

    Entry:
        tokens is an expression as the addon compiler wrote it.

    Exit/Returns:
        Returns (references, refused). references is a list of Reference, in
        the order of the script. refused is a sorted list of the token types
        and the bare names that the server does not read.

    Module Globals:
        None.

    Methodology:
        Walk the tree and call nothing. The check must not run an action.

    Notes/References:
        A `when` line that starts with a comparison is a valid expression
        with no first value. The comparison token is a supported token, so
        this walk accepts it.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    references = []
    refused = set()
    _collect(tokens, references, refused)

    return references, sorted(refused)
