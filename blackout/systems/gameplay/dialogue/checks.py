"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The content rules of a compiled script (DESIGN-0017).

             THE EDITOR ACCEPTS MORE THAN THE SERVER RUNS. The Dialogue
             Manager compiler accepts a `while` loop, a random line, a
             pause tag, and each name that an author types. The dialogue
             runner reads a subset, and a name must be in the dialogue
             vocabulary. This module finds each difference. Without it, the
             editor shows no error and the server ignores the line.

             The check calls nothing. It reads the token trees, so no action
             runs and no player is necessary.

             Three callers: the loader refuses a script with a problem, the
             test of the script files checks each script, and
             `python -m systems.gameplay.dialogue` prints the problems for
             the Godot editor.

             A NEW RULE is one function in _RULES and one RULE_* name in
             constants.py.

             ONE RULE READS EACH SCRIPT OF THE GAME. `memory_problems` finds
             a recall of a memory key that no script remembers. A memory key
             can go from one script to a different script. Thus, that rule
             is not in _RULES. files.check_game runs it.
"""

from dataclasses import dataclass

from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue import expressions
from systems.gameplay.dialogue.script import CompiledScript
from systems.gameplay.dialogue.vocabulary import vocabulary


# ─── Private constant definitions ────────────────────────────────────────────

# The id fields of a line that name one other line.
_TARGET_FIELDS: tuple = (
    dialogue_const.FIELD_NEXT,
    dialogue_const.FIELD_NEXT_AFTER,
    dialogue_const.FIELD_NEXT_SIBLING,
)

# The line types that name their target: a `=>` line, and a response.
_JUMP_TYPES: frozenset = frozenset({
    dialogue_const.TYPE_GOTO, dialogue_const.TYPE_RESPONSE})

# The line types with no content of their own.
_FILLER_TYPES: frozenset = frozenset({
    dialogue_const.TYPE_BLANK, dialogue_const.TYPE_COMMENT})

# The tokens of a `do` line: a namespace, a dot, and one call.
_MUTATION_TOKEN_COUNT: int = 3

# The kinds that each usage accepts.
_KINDS_OF_USAGE: dict = {
    dialogue_const.USAGE_CONDITION: (
        dialogue_const.KIND_VALUE, dialogue_const.KIND_QUERY),
    dialogue_const.USAGE_TEXT: (
        dialogue_const.KIND_VALUE, dialogue_const.KIND_QUERY),
    dialogue_const.USAGE_MUTATION: (dialogue_const.KIND_ACTION,),
}


# ─── Public classes ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Problem:
    """One fault of a compiled script. rule is a RULE_* name. line_id is the
    id of the line, or an empty text for a fault of the whole script."""

    rule: str
    line_id: str
    message: str


    def source_line(self) -> int | None:
        """The line number in the dialogue script, from 1. None for a fault
        of the whole script. The addon makes each line id from the index of
        its source line."""
        head = self.line_id.split(dialogue_const.NAME_SEPARATOR)[0]

        if not head.isdigit():
            return None

        return int(head) + 1


    def describe(self) -> str:
        """The problem as one line for an author."""
        line_number = self.source_line()

        if line_number is None:
            return f"{self.message} [{self.rule}]"

        return f"line {line_number}: {self.message} [{self.rule}]"


# ─── Private helper routines ─────────────────────────────────────────────────

def _expression_of(holder: dict, field_name: str) -> list:
    """The token list under one field of a line, or an empty list."""
    block = holder.get(field_name) or {}

    return block.get(dialogue_const.FIELD_EXPRESSION) or []


def _line_expressions(line: dict) -> list:
    """
    Purpose: List each expression of one line, with how the line uses it.

    Entry:
        line is one line of a compiled script.

    Exit/Returns:
        Returns a list of (usage, tokens). usage is a USAGE_* name.

    Module Globals:
        None.

    Methodology:
        1. The condition of an `if`, a `match`, or a response.
        2. Each value of each `when` line, split at its commas.
        3. The call of a `do` line.
        4. Each `{{...}}` in the text and in the speaker.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    found = []
    condition = _expression_of(line, dialogue_const.FIELD_CONDITION)

    if condition:
        found.append((dialogue_const.USAGE_CONDITION, condition))

    for case in line.get(dialogue_const.FIELD_CASES) or []:
        case_tokens = _expression_of(case, dialogue_const.FIELD_CONDITION)

        for value_tokens in expressions.split_cases(case_tokens):
            found.append((dialogue_const.USAGE_CONDITION, value_tokens))

    mutation = _expression_of(line, dialogue_const.FIELD_MUTATION)

    if mutation:
        found.append((dialogue_const.USAGE_MUTATION, mutation))

    for field_name in (dialogue_const.FIELD_TEXT_REPLACEMENTS,
                       dialogue_const.FIELD_CHARACTER_REPLACEMENTS):
        for replacement in line.get(field_name) or []:
            tokens = replacement.get(dialogue_const.FIELD_EXPRESSION) or []
            found.append((dialogue_const.USAGE_TEXT, tokens))

    return found


def _reference_problems(reference: object, usage: str, line_id: str) -> list:
    """
    Purpose: Check one use of a vocabulary name.

    Entry:
        reference is an expressions.Reference.
        usage is the USAGE_* name of the expression that holds it.

    Exit/Returns:
        Returns a list of Problem. Empty for a correct use.

    Module Globals:
        The dialogue vocabulary read. _KINDS_OF_USAGE read.

    Methodology:
        1. The name must be in the vocabulary.
        2. The kind must fit the usage: only a `do` line calls an action,
           and a `do` line calls nothing else.
        3. A value has no brackets. A query and an action have brackets.
        4. The number of arguments must be that of the handler.
        5. The argument check of the entry must accept the literals.

    Notes/References:
        An argument of a call is a reading, so a name in it must not be an
        action. _expression_problems gives each argument the text usage.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    entry = vocabulary().get(reference.name)

    if entry is None:
        return [Problem(dialogue_const.RULE_NAME, line_id,
                        f"'{reference.name}' is not in the dialogue vocabulary")]

    problems = []

    if entry.kind not in _KINDS_OF_USAGE[usage]:
        problems.append(Problem(
            dialogue_const.RULE_KIND, line_id,
            f"'{reference.name}' is a {entry.kind}, and a {usage} cannot use one"))

    is_value = entry.kind == dialogue_const.KIND_VALUE

    if is_value == reference.is_call:
        form = "no brackets" if is_value else "brackets"
        problems.append(Problem(
            dialogue_const.RULE_KIND, line_id,
            f"'{reference.name}' is a {entry.kind}. Write it with {form}"))

    if len(reference.arguments) != len(entry.argument_names):
        expected = ", ".join(entry.argument_names) or "no argument"
        problems.append(Problem(
            dialogue_const.RULE_ARITY, line_id,
            f"'{reference.name}' takes ({expected}), and the script gives "
            f"{len(reference.arguments)} argument(s)"))
    elif entry.argument_check is not None:
        complaint = entry.argument_check(reference.literal_arguments())

        if complaint:
            problems.append(Problem(
                dialogue_const.RULE_ARGUMENT, line_id,
                f"'{reference.name}': {complaint}"))

    return problems


def _expression_problems(usage: str, tokens: list, line_id: str) -> list:
    """
    Purpose: Check one expression of one line.

    Entry:
        usage is a USAGE_* name. tokens is the expression.

    Exit/Returns:
        Returns a list of Problem.

    Module Globals:
        None.

    Methodology:
        1. Refuse each token type that the server does not read.
        2. A `do` line must be exactly one call.
        3. Check the first name against the usage of the line. Check each
           other name as a reading, because it is an argument or an operand.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    references, refused = expressions.inspect_tokens(tokens)
    problems = []

    for token_type in refused:
        problems.append(Problem(
            dialogue_const.RULE_EXPRESSION, line_id,
            f"the server does not read '{token_type}' in a {usage}"))

    is_mutation = usage == dialogue_const.USAGE_MUTATION

    if is_mutation and len(tokens) != _MUTATION_TOKEN_COUNT:
        problems.append(Problem(
            dialogue_const.RULE_EXPRESSION, line_id,
            "a `do` line must be one call of an action, for example "
            "`do quest.accept(\"key\")`"))

    for position, reference in enumerate(references):
        reference_usage = usage

        if is_mutation and position > 0:
            reference_usage = dialogue_const.USAGE_TEXT

        problems.extend(_reference_problems(reference, reference_usage, line_id))

    return problems


# ─── The rules ───────────────────────────────────────────────────────────────

def _check_version(script: CompiledScript) -> list:
    """The compiler version must be the one that this package reads."""
    if script.compiler_version == dialogue_const.SUPPORTED_COMPILER_VERSION:
        return []

    return [Problem(
        dialogue_const.RULE_VERSION, "",
        f"compiler version {script.compiler_version}, and the server reads "
        f"version {dialogue_const.SUPPORTED_COMPILER_VERSION}. Run the script "
        f"export again, or update the server for the new addon")]


def _check_start_cue(script: CompiledScript) -> list:
    """Each script starts at the start cue."""
    if script.cue_line(dialogue_const.CUE_START) is not None:
        return []

    return [Problem(
        dialogue_const.RULE_START_CUE, "",
        f"the script has no '~ {dialogue_const.CUE_START}' cue")]


def _check_line_types(script: CompiledScript) -> list:
    """Each line has a type that the runner reads."""
    problems = []

    for line_id, line in script.lines.items():
        line_type = line.get(dialogue_const.FIELD_TYPE, "")

        if line_type not in dialogue_const.SUPPORTED_LINE_TYPES:
            problems.append(Problem(
                dialogue_const.RULE_LINE_TYPE, line_id,
                f"the server does not run a '{line_type}' line"))

    return problems


def _check_features(script: CompiledScript) -> list:
    """No line uses a feature of the addon that the runner does not read."""
    problems = []

    for line_id, line in script.lines.items():
        for field_name, feature in dialogue_const.REFUSED_FIELDS.items():
            if line.get(field_name):
                problems.append(Problem(
                    dialogue_const.RULE_FEATURE, line_id,
                    f"the server does not run {feature}"))

    return problems


def _check_markup(script: CompiledScript) -> list:
    """No text holds inline markup of the addon that the runner does not
    read. The player would see the markup as text."""
    problems = []

    for line_id, line in script.lines.items():
        text = line.get(dialogue_const.FIELD_TEXT, "")

        for feature, pattern in dialogue_const.REFUSED_MARKUP:
            if pattern.search(text):
                problems.append(Problem(
                    dialogue_const.RULE_MARKUP, line_id,
                    f"the server does not run {feature}"))

    return problems


def _target_ids(line: dict) -> list:
    """Each line id that one line names, and that the runner can read. The
    `next_id` of a `match` line names its first `when` line. The compiler
    keeps no `when` line, and the runner reads the cases."""
    is_match = line.get(dialogue_const.FIELD_TYPE) == dialogue_const.TYPE_MATCH
    targets = [line.get(field_name) for field_name in _TARGET_FIELDS
               if not (is_match and field_name == dialogue_const.FIELD_NEXT)]
    targets.extend(line.get(dialogue_const.FIELD_RESPONSES) or [])

    for case in line.get(dialogue_const.FIELD_CASES) or []:
        targets.append(case.get(dialogue_const.FIELD_NEXT))

    return [target for target in targets if target is not None]


def _check_targets(script: CompiledScript) -> list:
    """Each id that a line or a cue names is a line of this script, or an
    end id. An id from an imported file is not."""
    problems = []

    for cue, line_id in script.cues.items():
        if line_id not in script.lines:
            problems.append(Problem(
                dialogue_const.RULE_TARGET, "",
                f"the cue '{cue}' names a line outside this script. The "
                f"server does not run an import"))

    for line_id, line in script.lines.items():
        for target in _target_ids(line):
            if target in dialogue_const.END_IDS or target in script.lines:
                continue

            problems.append(Problem(
                dialogue_const.RULE_TARGET, line_id,
                f"the line jumps to '{target}', and this script has no such "
                f"line"))

    return problems


def _successors(line: dict) -> list:
    """
    Purpose: List each line that the runner can read after one line.

    Entry:
        line is one line of a compiled script.

    Exit/Returns:
        Returns a list of line ids. An end id can be in it.

    Module Globals:
        None.

    Methodology:
        The same routes as the handlers of runner.py:
        1. A response group continues at each of its responses.
        2. An `if` continues in its block, or at the next branch, or past
           the group. An `else` has no condition, so it has one route.
        3. A `match` continues at each `when`, and past the group only if
           it has no `else`.
        4. A `=><` jump also continues at the line after it.
        5. Each other line continues at its next line.

    Notes/References:
        _check_fall_through walks these routes. A route that the runner
        never takes gives a false fault, so the list must stay exact.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    line_type = line.get(dialogue_const.FIELD_TYPE, "")
    routes = [line.get(dialogue_const.FIELD_NEXT)]
    after = line.get(dialogue_const.FIELD_NEXT_AFTER)

    if line_type == dialogue_const.TYPE_RESPONSE:
        routes.extend(line.get(dialogue_const.FIELD_RESPONSES) or [])
    elif line_type == dialogue_const.TYPE_CONDITION:
        if _expression_of(line, dialogue_const.FIELD_CONDITION):
            routes.append(line.get(dialogue_const.FIELD_NEXT_SIBLING) or after)
    elif line_type == dialogue_const.TYPE_MATCH:
        cases = line.get(dialogue_const.FIELD_CASES) or []
        routes = [case.get(dialogue_const.FIELD_NEXT) for case in cases]
        has_else = any(case.get(dialogue_const.FIELD_IS_ELSE) for case in cases)

        if not has_else:
            routes.append(after)
    elif line_type == dialogue_const.TYPE_GOTO:
        if line.get(dialogue_const.FIELD_IS_SNIPPET):
            routes.append(after)

    return [route for route in routes if route is not None]


def _reachable_lines(script: CompiledScript) -> set:
    """The id of each line that the runner can reach from some cue."""
    waiting = [line_id for line_id in script.cues.values()
               if line_id in script.lines]
    reached = set()

    while waiting:
        line_id = waiting.pop()

        if line_id in reached or line_id not in script.lines:
            continue

        reached.add(line_id)
        waiting.extend(_successors(script.lines[line_id]))

    return reached


def _falls_into_cue(line_id: str, line: dict, cue_names: dict) -> str | None:
    """
    Purpose: Name the cue that one line continues into with no jump.

    Entry:
        cue_names maps the line id of each cue to its name.

    Exit/Returns:
        Returns the name of the cue, or None.

    Module Globals:
        _JUMP_TYPES, _FILLER_TYPES read.

    Methodology:
        1. A `=>` line and a response name their target. They are jumps.
        2. A blank line or a comment that continues at a cue is a fall.
        3. Each other line is a fall only if the cue is the next line of
           the dialogue script. `Guard: Bye. => next` names a cue that is
           further away.

    Notes/References:
        The compiled script does not say if a line had a `=>`. Step 3 is
        the test for that.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    line_type = line.get(dialogue_const.FIELD_TYPE, "")

    if line_type in _JUMP_TYPES:
        return None

    for target in _successors(line):
        cue = cue_names.get(target)

        if cue is None:
            continue

        is_next_line = (line_id.isdigit() and target.isdigit()
                        and int(target) == int(line_id) + 1)

        if line_type in _FILLER_TYPES or is_next_line:
            return cue

    return None


def _check_fall_through(script: CompiledScript) -> list:
    """No cue continues into the cue below it. The addon reads on past a
    cue line, so a cue with no `=> END` at its end also shows the next cue."""
    cue_names = {line_id: cue for cue, line_id in script.cues.items()}
    problems = []

    for line_id in sorted(_reachable_lines(script), key=_line_order):
        cue = _falls_into_cue(line_id, script.lines[line_id], cue_names)

        if cue is not None:
            problems.append(Problem(
                dialogue_const.RULE_FALL_THROUGH, line_id,
                f"the lines above the cue '{cue}' continue into it. End "
                f"them with `=> END` or with a jump"))

    return problems


def _line_order(line_id: str) -> float:
    """The place of a line in the dialogue script, for a sorted report."""
    try:
        return float(line_id)
    except ValueError:
        return 0.0


def _check_expressions(script: CompiledScript) -> list:
    """Each expression uses only tokens that the server reads, and only
    names of the dialogue vocabulary, in the correct form."""
    problems = []

    for line_id, line in script.lines.items():
        for usage, tokens in _line_expressions(line):
            problems.extend(_expression_problems(usage, tokens, line_id))

    return problems


# Each rule, in the order of the report. A rule is (script) -> list of Problem.
_RULES: tuple = (
    _check_version,
    _check_start_cue,
    _check_line_types,
    _check_features,
    _check_markup,
    _check_targets,
    _check_fall_through,
    _check_expressions,
)


# ─── Public routines ─────────────────────────────────────────────────────────

def script_problems(script: CompiledScript) -> list:
    """
    Purpose: Check one compiled script against each content rule.

    Entry:
        script is a CompiledScript, as load_script returns it.

    Exit/Returns:
        Returns a list of Problem, in the order of the rules. Empty for a
        script that the server can run.

    Module Globals:
        _RULES read.

    Methodology:
        Run each rule and join the results. Each rule checks the whole
        script, so one fault does not hide a second fault.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    problems = []

    for rule in _RULES:
        found = rule(script)
        problems.extend(found)

    return problems


def memory_uses(script: CompiledScript) -> tuple:
    """
    Purpose: List the memory keys that one script remembers and recalls.

    Entry:
        script is a CompiledScript.

    Exit/Returns:
        Returns (remembered, recalls). remembered is a set of keys. recalls
        is a list of (line id, key), in the order of the script.

    Module Globals:
        None.

    Methodology:
        1. Read each expression of each line, as _check_expressions does.
        2. Keep the literal key of each `memory.remember` and of each
           `memory.recall`, also inside an argument of a different call.

    Notes/References:
        A call with no literal key is skipped. The argument check of the
        name already refuses it.

    Author: Nick Hobar
    Creation date: 11/19/2026
    """
    remembered = set()
    recalls = []

    for line_id in sorted(script.lines, key=_line_order):
        for _usage, tokens in _line_expressions(script.lines[line_id]):
            references, _refused = expressions.inspect_tokens(tokens)

            for reference in references:
                arguments = reference.literal_arguments()

                if not arguments:
                    continue

                key = arguments[dialogue_const.MEMORY_KEY_ARGUMENT]

                if not isinstance(key, str):
                    continue

                if reference.name == dialogue_const.MEMORY_REMEMBER:
                    remembered.add(key)
                elif reference.name == dialogue_const.MEMORY_RECALL:
                    recalls.append((line_id, key))

    return remembered, recalls


def memory_problems(scripts: list) -> list:
    """
    Purpose: Find each recall of a memory key that no script remembers.

    Entry:
        scripts is a list of CompiledScript: each script of the game.

    Exit/Returns:
        Returns a list of (script key, Problem), in the order of the
        scripts. Empty if each recall has a remember.

    Module Globals:
        None.

    Methodology:
        1. Collect each key that some script of the game remembers.
        2. A recall of a key outside that set is a problem.

    Notes/References:
        A recall of such a key always gives its default, and the server
        shows no error. This is the only rule that reads more than one
        script, so script_problems does not run it, and the loader does
        not either. files.check_game and a test of the game run it.

    Author: Nick Hobar
    Creation date: 11/19/2026
    """
    uses = [(script.key, memory_uses(script)) for script in scripts]
    remembered = set()
    problems = []

    for _key, (script_remembered, _recalls) in uses:
        remembered.update(script_remembered)

    for script_key, (_remembered, recalls) in uses:
        for line_id, memory_key in recalls:
            if memory_key in remembered:
                continue

            problems.append((script_key, Problem(
                dialogue_const.RULE_MEMORY, line_id,
                f"no script remembers the memory key '{memory_key}'. Add "
                f"`do {dialogue_const.MEMORY_REMEMBER}(\"{memory_key}\", ...)`")))

    return problems
