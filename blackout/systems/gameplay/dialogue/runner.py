"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The dialogue runner (DESIGN-0017). It reads a compiled script
             and makes each beat: the text that the player reads now, and
             the responses that the player can give.

             THE RUNNER KNOWS NO MENU. A Conversation is callable from a
             test, a script, or a command, with no EvMenu anywhere.
             `systems/interface/menus/dialogue_script.py` shows a beat as an
             EvMenu node, and that module holds no rule.

             ONE BEAT IS THE LINES UP TO THE NEXT RESPONSES (Nick,
             11/11/2026). The runner joins each line that it reaches into
             one text. It stops when the script offers responses, or when
             the script ends.

             A `do` LINE RUNS WHEN THE RUNNER REACHES IT. A `do` line before
             the responses of a beat runs before the player reads that
             beat. To run an action after the player reads a scene, put the
             `do` line under a response.

             THE SERVER DECIDES EACH CONDITION. The client gets the text and
             the responses that passed. It gets no condition and no hidden
             response.
"""

from dataclasses import dataclass, field

from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue import expressions
from systems.gameplay.dialogue.script import CompiledScript, DialogueScriptError
from systems.interface.ui.colors import dialog, title


# ─── Public classes ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DialogueContext:
    """The two sides of one conversation. Each vocabulary handler gets it.

    caller is the player character. npc is the NPC, or None for a
    conversation with no NPC."""

    caller: object
    npc: object = None


    def npc_name(self) -> str:
        """The name of the NPC, or the unknown name for a conversation with
        no NPC. The `npc.name` value and the speech look both read it."""
        if self.npc is None:
            return dialogue_const.UNKNOWN_NPC_NAME

        return str(self.npc.key)


@dataclass(frozen=True)
class Response:
    """One answer of a beat. label is what the player reads. next_line and
    stack say where the script continues if the player gives it."""

    label: str
    next_line: str
    stack: tuple = ()


@dataclass(frozen=True)
class Beat:
    """The text and the responses that the player gets at one time. A beat
    with no response ends the conversation."""

    text: str = ""
    responses: tuple = ()


    def is_ending(self) -> bool:
        """True if the conversation stops after this beat."""
        return not self.responses


@dataclass
class _Walk:
    """The state of the runner while it makes one beat."""

    script: CompiledScript
    context: DialogueContext
    stack: list = field(default_factory=list)
    texts: list = field(default_factory=list)
    responses: list = field(default_factory=list)
    stopped: bool = False


# ─── Private helper routines ─────────────────────────────────────────────────

def _fill(text: str, replacements: list, context: DialogueContext) -> str:
    """Put the value of each `{{...}}` into a text."""
    filled = text

    for replacement in replacements or []:
        tokens = replacement.get(dialogue_const.FIELD_EXPRESSION, [])
        marker = replacement.get(dialogue_const.FIELD_VALUE_IN_TEXT, "")
        resolved = expressions.evaluate(tokens, context)
        filled = filled.replace(marker, str(resolved))

    return filled


def _speaker_of(line: dict, context: DialogueContext) -> str:
    """The speaker of a line, with each `{{...}}` filled. Empty for none."""
    speaker = line.get(dialogue_const.FIELD_CHARACTER, "")
    replacements = line.get(dialogue_const.FIELD_CHARACTER_REPLACEMENTS)

    return _fill(speaker, replacements, context)


def _text_of(line: dict, context: DialogueContext) -> str:
    """The text of a line, with each `{{...}}` filled."""
    text = line.get(dialogue_const.FIELD_TEXT, "")
    replacements = line.get(dialogue_const.FIELD_TEXT_REPLACEMENTS)

    return _fill(text, replacements, context)


def _passes(holder: dict, context: DialogueContext) -> bool:
    """True if the condition of a line or a response holds. A line with no
    condition, for example an `else`, always passes."""
    condition = holder.get(dialogue_const.FIELD_CONDITION) or {}
    tokens = condition.get(dialogue_const.FIELD_EXPRESSION)

    if not tokens:
        return True

    result = expressions.evaluate(tokens, context)

    return expressions.is_true(result)


# ─── The line handlers ───────────────────────────────────────────────────────
#
# Each handler gets the walk and one line. It returns the id of the next
# line. A handler that completes the beat sets walk.stopped.

def _pass_line(walk: _Walk, line: dict) -> str:
    """A cue, a comment, or a blank line. Continue."""
    return line.get(dialogue_const.FIELD_NEXT, dialogue_const.ID_NULL)


def _say_line(walk: _Walk, line: dict) -> str:
    """
    Purpose: Add one line of text to the beat.

    Entry:
        line is a dialogue line of the compiled script.

    Exit/Returns:
        Returns the id of the next line. Appends the text to walk.texts.

    Module Globals:
        None.

    Methodology:
        1. A line with no speaker is narration. It stays plain.
        2. A line with a speaker is speech. Each text line of it gets the
           speech colour.
        3. A line of the NPC of the conversation shows with no name. The
           pop-up title and the first beat already name that NPC.
        4. A line of each other speaker shows the name in front.

    Notes/References:
        The colour goes on each text line, not around the whole text. A
        colour code that spans a line break can colour the frame of the menu.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    text = _text_of(line, walk.context)
    speaker = _speaker_of(line, walk.context)

    if speaker:
        parts = [dialog(part) for part in text.split("\n")]
        text = "\n".join(parts)

        if speaker != walk.context.npc_name():
            text = dialogue_const.SPEECH_TEMPLATE.format(
                speaker=title(speaker), line=text)

    walk.texts.append(text)

    return line.get(dialogue_const.FIELD_NEXT, dialogue_const.ID_NULL)


def _offer_responses(walk: _Walk, line: dict) -> str:
    """
    Purpose: Complete the beat with the responses that the player can give.

    Entry:
        line is the first response of a group. Its `responses` field lists
        the id of each response of the group, itself included.

    Exit/Returns:
        Returns ID_NULL. Fills walk.responses and sets walk.stopped.

    Module Globals:
        None.

    Methodology:
        1. For each response of the group, check its condition.
        2. Keep each response that passes, with the line that follows it
           and a copy of the return stack.

    Notes/References:
        The addon reads "Name: text" in a response as a speaker and a line.
        A response has no speaker here, so the label joins the two again.
        If no response passes, the beat has none, and the conversation ends.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    response_ids = line.get(dialogue_const.FIELD_RESPONSES) or []

    for response_id in response_ids:
        response = walk.script.line(response_id)

        if not _passes(response, walk.context):
            continue

        label = _text_of(response, walk.context)
        speaker = _speaker_of(response, walk.context)

        if speaker:
            label = dialogue_const.RESPONSE_TEMPLATE.format(
                speaker=speaker, line=label)

        next_line = response.get(dialogue_const.FIELD_NEXT, dialogue_const.ID_NULL)
        walk.responses.append(Response(label, next_line, tuple(walk.stack)))

    walk.stopped = True

    return dialogue_const.ID_NULL


def _branch(walk: _Walk, line: dict) -> str:
    """An `if`, an `elif`, or an `else`. Go into the block if the condition
    holds. Else go to the next branch, or past the whole group."""
    if _passes(line, walk.context):
        return line.get(dialogue_const.FIELD_NEXT, dialogue_const.ID_NULL)

    next_sibling = line.get(dialogue_const.FIELD_NEXT_SIBLING)

    if next_sibling:
        return next_sibling

    return line.get(dialogue_const.FIELD_NEXT_AFTER, dialogue_const.ID_NULL)


def _match(walk: _Walk, line: dict) -> str:
    """A `match` line. Go to the first `when` that fits the value, then to
    the `else`, then past the whole group."""
    condition = line.get(dialogue_const.FIELD_CONDITION) or {}
    tokens = condition.get(dialogue_const.FIELD_EXPRESSION, [])
    match_value = expressions.evaluate(tokens, walk.context)
    else_target = line.get(dialogue_const.FIELD_NEXT_AFTER, dialogue_const.ID_NULL)

    for case in line.get(dialogue_const.FIELD_CASES) or []:
        case_target = case.get(dialogue_const.FIELD_NEXT, dialogue_const.ID_NULL)

        if case.get(dialogue_const.FIELD_IS_ELSE):
            else_target = case_target
            continue

        case_condition = case.get(dialogue_const.FIELD_CONDITION) or {}
        case_tokens = case_condition.get(dialogue_const.FIELD_EXPRESSION, [])

        if expressions.matches_case(match_value, case_tokens, walk.context):
            return case_target

    return else_target


def _mutate(walk: _Walk, line: dict) -> str:
    """A `do` line. Call its action, then continue."""
    mutation = line.get(dialogue_const.FIELD_MUTATION) or {}
    tokens = mutation.get(dialogue_const.FIELD_EXPRESSION, [])
    expressions.evaluate(tokens, walk.context, actions_allowed=True)

    return line.get(dialogue_const.FIELD_NEXT, dialogue_const.ID_NULL)


def _jump(walk: _Walk, line: dict) -> str:
    """A `=>` line. A `=><` line also puts the line after it on the return
    stack, so the script comes back when the target ends."""
    if line.get(dialogue_const.FIELD_IS_SNIPPET):
        return_to = line.get(dialogue_const.FIELD_NEXT_AFTER, dialogue_const.ID_NULL)
        walk.stack.append(return_to)

    return line.get(dialogue_const.FIELD_NEXT, dialogue_const.ID_NULL)


# The handler of each line type. A new line type is one row and one handler.
_LINE_HANDLERS: dict = {
    dialogue_const.TYPE_BLANK: _pass_line,
    dialogue_const.TYPE_COMMENT: _pass_line,
    dialogue_const.TYPE_CUE: _pass_line,
    dialogue_const.TYPE_DIALOGUE: _say_line,
    dialogue_const.TYPE_RESPONSE: _offer_responses,
    dialogue_const.TYPE_CONDITION: _branch,
    dialogue_const.TYPE_MATCH: _match,
    dialogue_const.TYPE_MUTATION: _mutate,
    dialogue_const.TYPE_GOTO: _jump,
}


def _next_or_return(walk: _Walk, line_id: str) -> str | None:
    """
    Purpose: Resolve an end id to the line where the script continues.

    Entry:
        line_id is the id that the last handler returned.

    Exit/Returns:
        Returns the id of a real line, or None if the script ended.

    Module Globals:
        None.

    Methodology:
        1. `END!` ends the conversation at once.
        2. `END` and an empty id end the current cue. If a `=><` line waits
           on the return stack, continue there.
        3. Each other id is a real line.

    Notes/References:
        `DialogueManager.get_line` in the addon is the model.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    current = line_id

    while current in dialogue_const.END_IDS:
        if current == dialogue_const.ID_END_CONVERSATION or not walk.stack:
            return None

        current = walk.stack.pop()

    return current


def _make_beat(script: CompiledScript, context: DialogueContext,
               line_id: str, stack: tuple) -> Beat:
    """
    Purpose: Read a compiled script from one line to the end of one beat.

    Entry:
        line_id is the id of a line, or an end id.
        stack is the return stack at that line.

    Exit/Returns:
        Returns the Beat. Raises DialogueScriptError for a line type with
        no handler, for a missing line, and at STEP_LIMIT lines.

    Module Globals:
        _LINE_HANDLERS read.

    Methodology:
        1. Resolve an end id through the return stack. If the script ended,
           stop.
        2. Give the line to the handler of its type.
        3. Continue at the id that the handler returns, until a handler
           stops the walk.
        4. Join the texts into the text of the beat.

    Notes/References:
        The step limit stops a script that jumps in a circle with no
        response in it.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    walk = _Walk(script=script, context=context, stack=list(stack))
    current = line_id
    steps = 0

    while not walk.stopped:
        current = _next_or_return(walk, current)

        if current is None:
            break

        steps += 1

        if steps > dialogue_const.STEP_LIMIT:
            raise DialogueScriptError(
                f"the script '{script.key}' read {dialogue_const.STEP_LIMIT} "
                f"lines with no response. A jump goes in a circle")

        line = script.line(current)
        line_type = line.get(dialogue_const.FIELD_TYPE, "")
        handler = _LINE_HANDLERS.get(line_type)

        if handler is None:
            raise DialogueScriptError(
                f"the script '{script.key}' has a '{line_type}' line, and "
                f"the server does not read that line type")

        current = handler(walk, line)

    text = dialogue_const.LINE_SEPARATOR.join(walk.texts)

    return Beat(text=text, responses=tuple(walk.responses))


# ─── Public routines ─────────────────────────────────────────────────────────

class Conversation:
    """
    Purpose: Run one compiled script for one player and one NPC.

    Entry:
        script is a CompiledScript that passed the content check.
        context names the player character and the NPC.

    Exit/Returns:
        Not applicable. `open` and `choose` each return a Beat.

    Module Globals:
        None.

    Methodology:
        The conversation keeps only the last beat. A response of that beat
        carries the line and the return stack where the script continues.
        Thus, the state of a conversation is one beat, and nothing goes
        into the database.

    Notes/References:
        The EvMenu module holds one Conversation on its menu. A test holds
        one directly.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """

    def __init__(self, script: CompiledScript, context: DialogueContext):
        self.script = script
        self.context = context
        self.beat = Beat()


    def open(self, cue: str = dialogue_const.CUE_START) -> Beat:
        """Start at a cue, and return the first beat. A conversation starts
        at the start cue. A test can start at a different cue."""
        start_line = self.script.cue_line(cue)

        if start_line is None:
            raise DialogueScriptError(
                f"the script '{self.script.key}' has no '{cue}' cue")

        self.beat = _make_beat(self.script, self.context, start_line, ())

        return self.beat


    def choose(self, index: int) -> Beat:
        """Give the response at this index of the last beat, and return the
        next beat. Raises DialogueScriptError for an index with no response."""
        responses = self.beat.responses

        if index < 0 or index >= len(responses):
            raise DialogueScriptError(
                f"the beat has {len(responses)} response(s), and none has "
                f"the index {index}")

        chosen = responses[index]
        self.beat = _make_beat(
            self.script, self.context, chosen.next_line, chosen.stack)

        return self.beat


    def farewell(self) -> str | None:
        """The parting line of the script: the text of its farewell cue.
        None for a script with no farewell cue."""
        farewell_line = self.script.cue_line(dialogue_const.CUE_FAREWELL)

        if farewell_line is None:
            return None

        parting = _make_beat(self.script, self.context, farewell_line, ())

        return parting.text
