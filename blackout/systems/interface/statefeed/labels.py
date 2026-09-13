"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: The one owner of what a world LABEL may contain.

             A label is text an entity carries to be drawn beside itself in a
             graphical client -- a signpost's face, a dev annotation over a
             broken tile. Unlike a desc it is bounded, because it rides the
             entity row: `serialize_entity` is the biggest payload the feed
             sends, test_payload_size.py prices 1200 of those rows against a
             fixed budget, and a string with no ceiling there is a budget
             nothing can be written against.

             `normalise` is that ceiling, and it is the only thing that
             enforces it. It is called TWICE by design -- once by whatever
             writes the label, so the stored value is already clean, and once
             by the serializer, so a value written around the property still
             cannot blow the payload. That is not two owners of the rule: the
             rule lives here, and it is idempotent, so a second pass over a
             clean string returns it unchanged. Anything else would have to
             choose between trusting every future writer and truncating in two
             places that could disagree about the number.

             Markup is stripped rather than escaped, and it is stripped HERE
             rather than in the renderer. Evennia's `|r` codes mean nothing to
             a Godot Label3D and would be drawn literally; a label that
             arrives at a second client one day must not depend on that client
             knowing to remove them. The clean string is also what the text
             channel shows, so the two cannot describe a sign differently.
"""

from evennia.utils.ansi import strip_ansi

from . import constants as const


# ─── Public interface ────────────────────────────────────────────────────────

def normalise(text) -> str:
    """
    Purpose: Render any authored string as a label safe to put on the wire.

    Entry:
        text - whatever the caller holds. None, a non-string and an already
               normalised string are all ordinary inputs, not errors.

    Exit/Returns:
        Returns a string of at most WORLD_LABEL_MAX_CHARS characters over at
        most WORLD_LABEL_MAX_LINES lines, carrying no markup and no leading,
        trailing or doubled whitespace. Returns "" for anything that held no
        text, which every reader treats as "this entity has no label".

    Module Globals:
        const.WORLD_LABEL_MAX_CHARS and const.WORLD_LABEL_MAX_LINES read.

    Methodology:
        Ordered so each step cannot undo the one before it. Markup goes first,
        because `|555` is four characters a player never sees and the cap must
        count what is drawn. Whitespace is collapsed next, so the line count
        and the character count both measure the real thing. The two caps come
        last, lines before characters: cutting to length first could leave a
        fourth line that the line cap would then have to find again.

        IDEMPOTENT, and the property is load-bearing -- see the module
        docstring for why this runs on both the write and the read path.
        Re-normalising an already clean string has nothing left to strip, no
        whitespace left to collapse and nothing left to cut.

    Notes/References:
        strip_ansi handles Evennia's own `|`-markup as well as raw escapes;
        evennia/utils/ansi.py:562 says so in as many words.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    if not text:
        return ""

    plain = strip_ansi(str(text))
    lines = _collapsed_lines(plain)

    if not lines:
        return ""

    kept = lines[:const.WORLD_LABEL_MAX_LINES]
    joined = "\n".join(kept)

    return _capped(joined)


# ─── Private helper routines ─────────────────────────────────────────────────

def _collapsed_lines(plain: str) -> list:
    """
    Purpose: Break a plain string into its non-empty, single-spaced lines.

    Entry:
        plain - a string with no markup left in it.

    Exit/Returns:
        Returns a list of stripped lines, none of them empty and none of them
        carrying a run of more than one space. Empty list for a string that
        was all whitespace.

    Module Globals:
        None.

    Methodology:
        Blank lines are DROPPED rather than kept and counted. An author who
        double-spaced their three lines meant three lines, and a line cap that
        spent two of its three on nothing would silently eat the last one.

        `split` with no argument would collapse the line breaks too, which is
        the one piece of the author's formatting worth keeping.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    lines = []

    for raw in plain.splitlines():
        words = raw.split()

        if not words:
            continue

        lines.append(" ".join(words))

    return lines


def _capped(joined: str) -> str:
    """
    Purpose: Cut a label to the character ceiling without leaving a ragged end.

    Entry:
        joined - the collapsed lines, already within the line cap.

    Exit/Returns:
        Returns `joined` unchanged when it fits, and its first
        WORLD_LABEL_MAX_CHARS characters stripped of trailing whitespace when
        it does not.

    Module Globals:
        const.WORLD_LABEL_MAX_CHARS read.

    Methodology:
        A hard cut rather than a word boundary. Cutting at the last space
        looks tidier and is a worse trade: it makes the ceiling depend on
        where the spaces fall, so a payload test can only assert a bound the
        code does not actually promise. An author who wanted the whole phrase
        has a desc for it.

        The strip afterwards is what stops a cut landing on a space or a line
        break from leaving one dangling -- which would also break idempotence,
        the second pass having something left to remove.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    if len(joined) <= const.WORLD_LABEL_MAX_CHARS:
        return joined

    cut = joined[:const.WORLD_LABEL_MAX_CHARS]

    return cut.strip()
