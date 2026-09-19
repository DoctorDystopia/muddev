"""
Purpose:  Convert one line of game text to escaped BBCode for the Godot
          client. Pure: it imports no Portal and no socket.

Description:
          This code lived in server/conf/godot_websocket.py until 09/18/2026.
          The Portal converts every text frame on port 4008 with it. The
          Server now needs it too: the menu pop-up sends an EvMenu node over
          the statefeed, and that text never passes through the Portal's
          send_text. One parser for both paths means a menu in a pop-up and
          the same menu in the log escape a player's `[` the same way.

          godot_websocket.py imports these names back, so every import of
          them from there still works. Its module docstring keeps the full
          account of why the escape sits where it does (GAP 2).

Author:   Nick Hobar
Creation date: 08/25/2026
"""

import re

from evennia.contrib.base_systems.godotwebsocket.text2bbcode import (
    TextToBBCODEparser, parse_to_bbcode)
from evennia.utils.ansi import parse_ansi


# The only character that can open a BBCode tag, and the only one escaped.
#
# NOT the one immediately after an ESC: by the time this runs, markup has
# already become ANSI, and the `[` of a `CSI` sequence is the conversion's own
# input rather than the game's prose. Escaping it is what left every menu table
# printing raw escape codes at players -- see the docstring of
# server/conf/godot_websocket.py.
#
# `]` closes nothing on its own and is deliberately left alone, which is what
# keeps the `[MODTOOL]` audit line rendering as itself.
_TAG_OPEN = re.compile(r"(?<!\x1b)\[")

# Godot's RichTextLabel escape for a literal `[`. `[rb]` is its counterpart for
# `]` and is deliberately unused here.
_TAG_OPEN_ESCAPED = "[lb]"


def escape_bbcode(text: str) -> str:
    """
    Purpose: Neutralise BBCode a player could have typed into game text.

    Entry:
        text - one line of game output that has ALREADY been through
        parse_ansi, so that every `[` still in it is one the game wrote.
        A non-string is returned unchanged.

    Exit/Returns:
        The same text with every such `[` replaced by `[lb]`, which a
        RichTextLabel renders as a literal `[`.

    Module Globals:
        _TAG_OPEN, _TAG_OPEN_ESCAPED read.

    Methodology:
        A single substitution, deliberately. A denylist of known-dangerous
        tags (`img`, `url`, `color`) would have to be revised every time Godot
        adds a tag, and would be wrong the moment it did. Escaping the
        character that can open ANY tag cannot go stale.

        The one exclusion is the `[` of an ANSI CSI sequence, which always
        follows ESC. Those are the conversion's INPUT, not the game's prose,
        and escaping them is what broke every table and every coloured bar in
        the game until 08/27/2026.

        WHERE this runs is the rest of the fix and it is not this function's
        to decide -- see [BlackoutBBCodeParser].

    Notes/References:
        Godot RichTextLabel BBCode escapes: `[lb]` and `[rb]`.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    if not isinstance(text, str):
        return text

    return _TAG_OPEN.sub(_TAG_OPEN_ESCAPED, text)


class BlackoutBBCodeParser(TextToBBCODEparser):
    """
    Purpose: The contrib's ANSI-to-BBCode parser, with the escape moved to the
             one point in the conversion where the game's own brackets can
             still be told apart from the tags it is about to write, and with
             the HTML parser's character handling undone.

    Notes/References:
        The body of `parse` is the contrib's, with one line inserted after the
        ANSI conversion. It is copied rather than wrapped because there is no
        seam: `parse` calls parse_ansi itself and hands the result straight to
        the MXP substitutions, which are the first step that writes a bracket
        of its own. Calling super().parse on already-converted text would run
        parse_ansi TWICE, and that is not a no-op -- `||n`, the escape for a
        literal `|n`, survives one pass and becomes a real reset on the next.

        KEEP IN STEP WITH THE CONTRIB, the same way start_plugin_services
        below is kept in step with the contrib's own.

    Author: Nick Hobar
    Creation date: 08/27/2026
    """

    def sub_text(self, match):
        """
        Purpose: Replace one match of `re_string`, which covers line endings,
                 tabs, and the three characters HTML has to escape.

        Entry:
            match - a match of TextToHTMLparser.re_string.

        Exit/Returns:
            A line ending is normalised to "\\n"; everything else is returned
            as itself.

        Module Globals:
            None.

        Methodology:
            The contrib inherits this substitution from the HTML parser, where
            `<`, `&`, `>` and tabs all have to become entities -- and then
            returns None for every one of them, which DELETES them. Measured
            08/27/2026, on the real parser:

                'HP -> 40'          -> 'HP - 40'
                'usage: get <item>' -> 'usage: get item'
                'Tom & Jerry'       -> 'Tom  Jerry'

            None of the three means anything to a RichTextLabel, which escapes
            `[` and nothing else, so all three travel as themselves. The tab
            travels too: the label has its own `tab_size` and aligns to real
            tab stops, which expanding to a fixed run of spaces here could not.

        Notes/References:
            This is why the MXP substitutions two lines below can work at all:
            they match on markers the deletion was eating.

        Author: Nick Hobar
        Creation date: 08/27/2026
        """
        if match.groupdict()["lineend"]:
            return "\n"

        return match.group(0)

    def parse(self, text: str, strip_ansi: bool = False) -> str:
        """Convert one line of game text to BBCode, escaping what it wrote."""
        text = parse_ansi(text, strip_ansi=strip_ansi, xterm256=True, mxp=True)
        text = escape_bbcode(text)

        result = re.sub(self.re_string, self.sub_text, text)
        result = re.sub(self.re_mxplink, self.sub_mxp_links, result)
        result = re.sub(self.re_mxpurl, self.sub_mxp_urls, result)
        result = self.remove_bells(result)
        result = self.format_styles(result)
        result = self.remove_backspaces(result)
        result = self.convert_urls(result)

        return result


# The one parser every frame on 4008 goes through. Built once, like the
# contrib's own BBCODE_PARSER, because it holds no per-session state.
BLACKOUT_BBCODE_PARSER = BlackoutBBCodeParser()


def to_bbcode(text: str, strip_ansi: bool = False) -> str:
    """Convert one piece of game text to escaped BBCode, as the Portal does
    for a text frame. The single entry point the Server uses."""
    return parse_to_bbcode(text, strip_ansi=strip_ansi,
                           parser=BLACKOUT_BBCODE_PARSER)
