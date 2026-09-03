"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: Render the facts a graphical client must know as source that
             client can read, so Python stays the single owner of every one.

             THE PROBLEM. A client cannot import Python. Every channel name,
             asset kind and item family therefore gets retyped in the client's
             own language, and nothing checks the copy. The Godot client
             restates a dozen-plus names in GDScript -- one copy of each fact,
             but still a copy, and still worth generating rather than trusting.

             This has already cost something, and with more than one client to
             boot. `ROOM_KIND_COLORS` named a room kind no map declares, so
             every client hand-typing that table quietly rendered the fallback
             hue -- and the dead key had been copied from one client into the
             other before anyone noticed. The two-client era that produced that
             incident is over (the three.js/GoldenLayout webclient is retired;
             see archive/webclient-js/), but the lesson survives it: a fact
             that CAN be generated should be, so there is nothing left to copy
             wrong. See tests/test_client_constants.py, which guards the tables
             that CANNOT be generated because they mix a server fact (which
             room kinds exist) with a client one (what colour each should be).

             THIS MODULE IS THE OTHER HALF: the facts that are purely the
             server's, emitted rather than guarded. A generated constant cannot
             drift, because there is nothing to keep in step.

             WHAT BELONGS HERE, and the line is worth stating precisely because
             the temptation is to move too much:

                 Python owns what is TRUE about the game.
                 The client owns what it LOOKS like.

             Channel names, asset kinds, item families and the tick are true
             about the game. Colours, mesh shapes, camera angles and the model
             registry are not, and generating them would move authorship of the
             game's appearance into a language that cannot see it.

             PURE. Rendering touches no file and no database -- it returns a
             string. Writing that string out is the caller's business, which is
             what lets the whole thing be tested without a filesystem and keeps
             this module safe to import from anywhere.

             _SYNTAX_BY_LANGUAGE stays a table, not a single hardcoded
             renderer, even with one language in it now: a future client is a
             row here, not a rewrite of this module.
"""

import os as _os

from . import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

# The banner every generated file carries. `%s` is the renderer's own name for
# the command that rebuilds it.
#
# Phrased for whoever opens the file to edit it, because they will: a generated
# file that does not say so is a file someone fixes by hand, and then the fix
# vanishes on the next render.
_HEADER_LINES: tuple = (
    "GENERATED FILE -- DO NOT EDIT.",
    "",
    "Rendered from systems/statefeed/constants.py by",
    "systems/statefeed/clientexport.py. Change the Python and re-run:",
    "",
    "    python scripts/export_client_constants.py",
    "",
    "Every name below is a fact the SERVER owns. Presentation -- colours,",
    "meshes, camera, the model registry -- is the client's own and is",
    "deliberately not generated; see the module docstring in clientexport.py.",
    "",
    "A test asserts the committed copy of this file matches a fresh render,",
    "so an edit here fails the suite rather than surviving quietly.",
)

# What each language spells the pieces of a constant declaration with.
#
# A table rather than a single hardcoded renderer, so a second client is a row
# here rather than a second copy of this whole module. There was a JS entry
# too, for the three.js/GoldenLayout webclient -- see archive/webclient-js/ --
# removed when that client was retired in favour of Godot as the sole client.
_GD_SYNTAX: dict = {
    "comment": "#",
    "open": "",
    "close": "",
    "indent": "",
    "declare": "const %s := %s",
    "publish": "",
    "list_open": "[",
    "list_close": "]",
    "map_open": "{",
    "map_close": "}",
    "pair": "%s: %s",
}

# The order channel constants are emitted in. Explicit rather than sorted,
# because the grouping carries meaning the alphabet would destroy -- the
# standard GMCP vocabulary first, then Blackout's own extensions, matching how
# constants.py itself is laid out.
_CHANNEL_EXPORTS: tuple = (
    ("CH_ROOM_INFO", const.CHANNEL_ROOM_INFO),
    ("CH_ROOM_PLAYERS", const.CHANNEL_ROOM_PLAYERS),
    ("CH_PLAYER_ADD", const.CHANNEL_ROOM_PLAYER_ADD),
    ("CH_PLAYER_REMOVE", const.CHANNEL_ROOM_PLAYER_REMOVE),
    ("CH_CHAR_AVATAR", const.CHANNEL_CHAR_AVATAR),
    ("CH_CHAR_VITALS", const.CHANNEL_CHAR_VITALS),
    ("CH_CHAR_STATUS", const.CHANNEL_CHAR_STATUS),
    ("CH_CHAR_SUMMARY", const.CHANNEL_CHAR_SUMMARY),
    ("CH_CHAR_ITEMS", const.CHANNEL_CHAR_ITEMS),
    ("CH_CHAR_QUESTS", const.CHANNEL_CHAR_QUESTS),
    ("CH_CHAR_SKILLS", const.CHANNEL_CHAR_SKILLS),
    ("CH_MAP", const.CHANNEL_MAP),
    ("CH_COMBAT", const.CHANNEL_COMBAT),
    ("CH_AURA", const.CHANNEL_AURA),
    ("CH_SUBSCRIBED", const.CHANNEL_SUBSCRIBED_ACK),
)

# Asset kinds, as the client's `family` vocabulary. world_view.gd needs
# FAMILY_CHARACTER on its own behalf -- it asks for the local player's mesh
# rather than passing a payload's key through -- and the rest are here so the
# set is complete rather than "the one that was needed first".
_KIND_EXPORTS: tuple = (
    ("FAMILY_ITEM", const.ASSET_KIND_ITEM),
    ("FAMILY_NPC", const.ASSET_KIND_NPC),
    ("FAMILY_CHARACTER", const.ASSET_KIND_CHARACTER),
    ("FAMILY_ROOM", const.ASSET_KIND_ROOM),
    ("FAMILY_STATION", const.ASSET_KIND_STATION),
    ("FAMILY_GATHERABLE", const.ASSET_KIND_GATHERABLE),
    ("FAMILY_GENERIC", const.ASSET_KEY_GENERIC),
)

# Item families, in the order family_shapes.gd builds procedural meshes for
# them, so the generated list reads alongside the file that consumes it.
_ITEM_FAMILY_EXPORTS: tuple = (
    ("ITEM_FAMILY_WEAPON", const.ITEM_FAMILY_WEAPON),
    ("ITEM_FAMILY_ARMOR", const.ITEM_FAMILY_ARMOR),
    ("ITEM_FAMILY_JEWELLERY", const.ITEM_FAMILY_JEWELLERY),
    ("ITEM_FAMILY_MATERIAL", const.ITEM_FAMILY_MATERIAL),
    ("ITEM_FAMILY_TOOL", const.ITEM_FAMILY_TOOL),
    ("ITEM_FAMILY_CURRENCY", const.ITEM_FAMILY_CURRENCY),
    ("ITEM_FAMILY_GENERIC", const.ITEM_FAMILY_GENERIC),
)

# What a tile action's `kind` can be. The client branches on these -- they
# decide whether a click starts, ends or ignores a tracked walk -- so they are
# the last thing that should be four string literals in a pane.
#
# Four, not five. KIND_NONE went with the wall markers on 08/28/2026; see the
# tile-affordance section of constants.py for why nothing says "no" by kind any
# more. A tile that affords nothing is one no client was told about.
_TILE_KIND_EXPORTS: tuple = (
    ("KIND_STEP", const.TILE_ACTION_KIND_STEP),
    ("KIND_WALK", const.TILE_ACTION_KIND_WALK),
    ("KIND_LOOK", const.TILE_ACTION_KIND_LOOK),
    ("KIND_CANCEL", const.TILE_ACTION_KIND_CANCEL),
)

# Single-value exports that are neither a channel nor a vocabulary.
#
# SUBSCRIBE_ALL is what the handshake sends; ASSET_KEY_CHARACTER is the model
# key the player's own avatar is registered against, and the one string that
# has to agree with the server or every character in the game loses its art.
_SCALAR_EXPORTS: tuple = (
    ("SUBSCRIBE_ALL", const.SUBSCRIBE_ALL),
    ("ASSET_KEY_CHARACTER", const.ASSET_KEY_CHARACTER),
    ("ROOM_KIND_TRANSITION", const.ROOM_KIND_TRANSITION),
    ("ROOM_KIND_DEFAULT", const.ROOM_KIND_DEFAULT),
    ("INVENTORY_SWAP_TEMPLATE", const.INVENTORY_SWAP_TEMPLATE),
    ("TILE_KEY_TEMPLATE", const.TILE_KEY_TEMPLATE),
    # The token a prompted action's `template` carries where the client's
    # answer goes, and the kind of box to open for it. These two are exported
    # and the templates are NOT: a template arrives per action, but the
    # substitution has to have one owner or two clients hold two spellings of
    # the same placeholder.
    ("ACTION_AMOUNT_PLACEHOLDER", const.ACTION_AMOUNT_PLACEHOLDER),
    ("ACTION_INPUT_KIND_QUANTITY", const.ACTION_INPUT_KIND_QUANTITY),
    ("ACTION_INPUT_KIND_KEY", const.ACTION_INPUT_KIND_KEY),
    ("ACTION_INPUT_MIN_KEY", const.ACTION_INPUT_MIN_KEY),
    ("ACTION_INPUT_MAX_KEY", const.ACTION_INPUT_MAX_KEY),
    ("ACTION_INPUT_LABEL_KEY", const.ACTION_INPUT_LABEL_KEY),
)

# What a line of game TEXT is about. Generated for the same reason the channel
# names are: a client that retyped these would be free to disagree with the
# server about what a tab contains, and nothing would check the copy.
#
# The KEY is exported too. A client reads `kwargs[MESSAGE_TYPE_KEY]`, and the
# one string that has to agree with Evennia's outputfunc convention is the last
# one worth typing twice.
_MESSAGE_TYPE_EXPORTS: tuple = (
    ("MESSAGE_TYPE_KEY", const.MESSAGE_TYPE_KEY),
    ("MSG_GENERAL", const.MESSAGE_TYPE_GENERAL),
    ("MSG_LOOK", const.MESSAGE_TYPE_LOOK),
    ("MSG_POSE", const.MESSAGE_TYPE_POSE),
    ("MSG_SAY", const.MESSAGE_TYPE_SAY),
    ("MSG_WHISPER", const.MESSAGE_TYPE_WHISPER),
    ("MSG_HELP", const.MESSAGE_TYPE_HELP),
    ("MSG_EXAMINE", const.MESSAGE_TYPE_EXAMINE),
    ("MSG_MOVE", const.MESSAGE_TYPE_MOVE),
    ("MSG_TELEPORT", const.MESSAGE_TYPE_TELEPORT),
    ("MSG_ROOM", const.MESSAGE_TYPE_ROOM),
    ("MSG_MAP", const.MESSAGE_TYPE_MAP),
    ("MSG_COMBAT", const.MESSAGE_TYPE_COMBAT),
    ("MSG_VITALS", const.MESSAGE_TYPE_VITALS),
    ("MSG_PROGRESSION", const.MESSAGE_TYPE_PROGRESSION),
    ("MSG_INVENTORY", const.MESSAGE_TYPE_INVENTORY),
    ("MSG_CRAFTING", const.MESSAGE_TYPE_CRAFTING),
    ("MSG_GATHERING", const.MESSAGE_TYPE_GATHERING),
    ("MSG_QUEST", const.MESSAGE_TYPE_QUEST),
    ("MSG_COMMERCE", const.MESSAGE_TYPE_COMMERCE),
    ("MSG_DIALOGUE", const.MESSAGE_TYPE_DIALOGUE),
    ("MSG_CHANNEL", const.MESSAGE_TYPE_CHANNEL),
    ("MSG_SYSTEM", const.MESSAGE_TYPE_SYSTEM),
)

_LANGUAGE_GD: str = "gd"

_SYNTAX_BY_LANGUAGE: dict = {
    _LANGUAGE_GD: _GD_SYNTAX,
}

# The game dir (blackout/), two levels up from systems/statefeed/clientexport.py.
_GAME_DIR: str = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

# The repo root. The Godot client is a sibling of the game dir, not inside it.
_REPO_ROOT: str = _os.path.dirname(_GAME_DIR)

# language -> where its rendered module is written.
#
# THIS LIVES HERE, not in scripts/export_client_constants.py, even though the
# script is the only thing that writes them. Two callers need the table -- the
# script, and the test that asserts the committed copy is current -- and
# CLAUDE.md marks blackout/scripts/ import-unsafe, so the test cannot read it
# from there. Putting it in the pure module gives it one owner that both can
# import, and leaves the script genuinely thin.
_OUTPUT_PATHS: dict = {
    _LANGUAGE_GD: _os.path.join(
        _REPO_ROOT, "godot", "autoload", "blackout_constants.gd"),
}


# ─── Private helper routines ─────────────────────────────────────────────────

def _quote(value) -> str:
    """
    Purpose: Render one scalar as a literal both target languages accept.

    Entry:
        value - a str, int or float.

    Exit/Returns:
        The literal as source text.

    Module Globals:
        None

    Methodology:
        Strings are double-quoted with backslashes and quotes escaped; numbers
        are passed through. Every target language agrees on all three forms,
        which is why there is one routine rather than one per language.

        A value this cannot render raises rather than guessing. Everything
        exported today is a plain scalar, and the failure mode of guessing --
        a client constant that is subtly the wrong type -- is worse than a
        loud refusal at render time.

    Notes/References:
        None
    """
    if isinstance(value, bool):
        raise TypeError("booleans are not exported; no client constant needs one")

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return '"%s"' % escaped

    raise TypeError("cannot render %r as a client literal" % (value,))


def _render_list(values, syntax: dict) -> str:
    """
    Purpose: Render a sequence of scalars as a list literal.

    Entry:
        values - an iterable of scalars.
        syntax - one of the _*_SYNTAX tables.

    Exit/Returns:
        The list literal on one line.

    Module Globals:
        None

    Methodology:
        One line rather than one entry per line. These lists are short and are
        read as a set rather than scanned, so the compact form is easier to
        diff when a channel is added.

    Notes/References:
        None
    """
    rendered = [_quote(value) for value in values]

    return "%s%s%s" % (
        syntax["list_open"], ", ".join(rendered), syntax["list_close"])


def _render_header(syntax: dict) -> str:
    """
    Purpose: Render the do-not-edit banner in the target language's comments.

    Entry:
        syntax - one of the _*_SYNTAX tables.

    Exit/Returns:
        The banner, newline-terminated.

    Module Globals:
        _HEADER_LINES read.

    Methodology:
        Prefix each line with the language's comment marker, trimming the
        trailing space off blank lines so the output carries no whitespace at
        end of line.

    Notes/References:
        None
    """
    marker = syntax["comment"]
    lines = []

    for line in _HEADER_LINES:
        lines.append(("%s %s" % (marker, line)).rstrip())

    return "\n".join(lines) + "\n"


def _render_body(syntax: dict, indent: str) -> str:
    """
    Purpose: Render every exported constant, in group order.

    Entry:
        syntax - one of the _*_SYNTAX tables.
        indent - the leading whitespace each declaration carries.

    Exit/Returns:
        The declarations as source text, newline-terminated.

    Module Globals:
        _CHANNEL_EXPORTS, _KIND_EXPORTS, _ITEM_FAMILY_EXPORTS,
        _TILE_KIND_EXPORTS, _MESSAGE_TYPE_EXPORTS, _SCALAR_EXPORTS read.

    Methodology:
        Walk the export tables in the order they are declared above,
        writing a section comment before each so the generated file reads the
        way constants.py does. Three derived lists follow: every subscribable
        channel, every item family and every message type, so a client can
        iterate rather than rebuild the set by hand from the individual names.

    Notes/References:
        The section order mirrors constants.py deliberately; see
        _CHANNEL_EXPORTS.
    """
    marker = syntax["comment"]
    declare = syntax["declare"]
    lines = []

    def section(title, exports):
        lines.append("%s%s %s" % (indent, marker, title))

        for name, value in exports:
            lines.append(indent + declare % (name, _quote(value)))

        lines.append("")

    section("Feed channels.", _CHANNEL_EXPORTS)
    section("Asset kinds -- the client's mesh `family` vocabulary.",
            _KIND_EXPORTS)
    section("Item families.", _ITEM_FAMILY_EXPORTS)
    section("Tile action kinds -- what a click does to a walk in progress.",
            _TILE_KIND_EXPORTS)
    section("Text routing -- what a line of game text is ABOUT. Which tab "
            "shows it is the client's own.", _MESSAGE_TYPE_EXPORTS)
    section("Everything else.", _SCALAR_EXPORTS)

    lines.append("%s%s Derived sets, so a client can iterate rather than"
                 % (indent, marker))
    lines.append("%s%s rebuild these from the names above." % (indent, marker))
    lines.append(indent + declare % (
        "SUBSCRIBABLE_CHANNELS",
        _render_list(sorted(const.SUBSCRIBABLE_CHANNELS), syntax)))
    lines.append(indent + declare % (
        "ITEM_FAMILIES",
        _render_list(sorted(const.ITEM_FAMILIES), syntax)))
    lines.append(indent + declare % (
        "MESSAGE_TYPES",
        _render_list(sorted(const.MESSAGE_TYPES), syntax)))
    lines.append("")

    return "\n".join(lines)


# ─── Public interface ────────────────────────────────────────────────────────

def render(language: str) -> str:
    """
    Purpose: Render the client constants module for one target language.

    Entry:
        language - "gd".

    Exit/Returns:
        The complete file contents, newline-terminated. Writes nothing.

    Module Globals:
        _SYNTAX_BY_LANGUAGE read.

    Methodology:
        Banner, then the language's module wrapper around the shared body.
        The GDScript form is a bare `const` block, which is what a Godot
        autoload or a preloaded script wants; it has no wrapper to add.

    Notes/References:
        Raises ValueError for an unknown language rather than defaulting, so a
        typo in the export script fails loudly instead of rendering nothing
        useful.
    """
    syntax = _SYNTAX_BY_LANGUAGE.get(language)

    if syntax is None:
        raise ValueError(
            "unknown client language %r; expected one of %s"
            % (language, sorted(_SYNTAX_BY_LANGUAGE)))

    parts = [_render_header(syntax)]

    if syntax["open"]:
        parts.append(syntax["open"])

    parts.append(_render_body(syntax, syntax["indent"]))

    if syntax["close"]:
        parts.append(syntax["close"])

    return "\n".join(parts).rstrip("\n") + "\n"


def languages() -> tuple:
    """
    Purpose: Every language render() accepts.

    Entry:
        None.

    Exit/Returns:
        A tuple of language keys.

    Module Globals:
        _SYNTAX_BY_LANGUAGE read.

    Methodology:
        Sorted for a stable order, so a caller iterating them writes files in
        the same order every run.

    Notes/References:
        The export script and the drift test both iterate this rather than
        naming languages, so adding a client means adding a syntax table and
        an output path and nothing else.
    """
    return tuple(sorted(_SYNTAX_BY_LANGUAGE))


def output_paths() -> dict:
    """
    Purpose: Where each rendered module is written.

    Entry:
        None.

    Exit/Returns:
        A fresh dict of language -> absolute path. A copy, so a caller cannot
        redirect the exporter by mutating what it was handed.

    Module Globals:
        _OUTPUT_PATHS read.

    Methodology:
        Straight copy. The reason the table lives in this module rather than in
        the script that writes the files is documented on _OUTPUT_PATHS.

    Notes/References:
        A language present in languages() and absent here is a client someone
        taught the renderer about without saying where its file goes; the test
        suite asserts the two agree rather than leaving the exporter to skip it.
    """
    return dict(_OUTPUT_PATHS)
