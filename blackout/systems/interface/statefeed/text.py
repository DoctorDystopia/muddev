"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Read the two halves of a tagged `text` message back apart.

             Evennia's `text` outputfunc takes either a bare string or a
             `(string, {kwargs})` pair, and Blackout now sends the pair
             everywhere so a client can route the line -- see MESSAGE_TYPES in
             constants.py.

             That makes anything INSPECTING an outgoing message have to know
             both shapes. Twelve tests found that out at once on 08/28/2026:
             each pulled `mocked.call_args[0][0]` and handed it straight to
             `strip_ansi`, which had been a string that morning and was a tuple
             by the afternoon. The failure was in the assertion rather than in
             the game -- players saw exactly what they had seen before -- but it
             was twelve copies of one small piece of knowledge, and this module
             is that piece with one owner.

             Deliberately tolerant, and that is the point of it. A caller
             holding a `msg` argument does NOT know whether the sender tagged
             it: Evennia's own commands send `look`, `say` and `help` tagged and
             their EvMenu nodes send nothing at all, so a reader that raised on
             an untagged line would be wrong about half the game. `line_of`
             answers for both, and `type_of` says "" rather than guessing.
"""

from . import constants as const


# ─── Public interface ────────────────────────────────────────────────────────

def line_of(sent) -> str:
    """
    Purpose: Return the prose out of whatever a `text` message carried.

    Entry:
        sent - the first argument of a `msg` / `msg_contents` call. Either a
               string, or a `(string, {kwargs})` pair.

    Exit/Returns:
        The string. A pair whose first element is not a string is stringified
        rather than refused, because `msg` itself stringifies it downstream and
        a reader that disagreed with the sender would be the surprising one.

    Module Globals:
        None.

    Methodology:
        A tuple or list of at least one element yields its first element;
        anything else is itself.

    Notes/References:
        Evennia's accepted forms are listed on
        SessionHandler.clean_senddata; this covers the two that reach a
        `text` outputfunc.
    """
    if isinstance(sent, (tuple, list)) and sent:
        return str(sent[0])

    return str(sent)


def type_of(sent) -> str:
    """
    Purpose: Return the routing tag a `text` message carried, if any.

    Entry:
        sent - the first argument of a `msg` / `msg_contents` call.

    Exit/Returns:
        The tag, or "" when the message carried none.

    Module Globals:
        const.MESSAGE_TYPE_KEY read.

    Methodology:
        Read the key off the pair's kwargs dict. An untagged line is not an
        error and must not be reported as one -- see the module docstring.

    Notes/References:
        What the tag may say is MESSAGE_TYPES in constants.py. This function
        does not validate against it: the ENGINE sends tags this game does not
        declare, and refusing them here would make a reader disagree with the
        wire.
    """
    if not isinstance(sent, (tuple, list)) or len(sent) < 2:
        return ""

    kwargs = sent[1]

    if not isinstance(kwargs, dict):
        return ""

    return str(kwargs.get(const.MESSAGE_TYPE_KEY, ""))
