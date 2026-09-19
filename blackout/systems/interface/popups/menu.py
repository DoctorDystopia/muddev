"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: An EvMenu node as a pop-up: the node text, one button for each
             option, and a text box when the node takes typed input.

             THE MENU STAYS THE MENU. Nothing here chooses an option, and no
             node knows it is drawn in a pop-up. A button sends the option's
             KEY, the same "1" or "b" a telnet player types, and
             BlackoutEvMenu.parse_input answers it as always. The text box
             sends what the player typed, which is what a quantity prompt's
             `_default` option already reads.

             WHO SEES IT. A session that subscribes to CHANNEL_CHAR_POPUP gets
             the pop-up and not the node text in its log. Every other session
             of the same character gets the text, as before. A node with no
             options is an ending, so its text always goes to the log: the
             pop-up closes on the same node.

             ONE POP-UP AT A TIME. An open EvMenu wins over a grid pop-up,
             because the EvMenu cmdset takes every line the grid would send.
             BlackoutEvMenu forgets any grid pop-up when it opens.
"""

from evennia.utils.ansi import strip_ansi

from systems.interface.menus.constants import QUIT_KEYS
from systems.interface.statefeed import constants as feed_const


# ─── Public constant definitions ─────────────────────────────────────────────

# The key a menu snapshot carries. Tests read it. A client must never branch
# on it: the snapshot's own fields say what to draw.
MENU_POPUP_KEY: str = "menu"

# What the text box asks, for a node with a `_default` option.
INPUT_LABEL: str = "Type your answer"


# ─── Private helper routines ─────────────────────────────────────────────────

def _target_sessions(menu) -> list:
    """The sessions a node is shown to: the one that opened the menu, or all.

    EvMenu.msg sends to `menu._session` when it is set and to every session
    of the caller when it is not. This reads the same rule.
    """
    session = getattr(menu, "_session", None)

    if session is not None:
        return [session]

    handler = getattr(menu.caller, "sessions", None)

    if handler is None:
        return []

    return list(handler.all())


def _option_rows(menu) -> list:
    """One {key, label, command} for each option the node lists, in order.

    The label is plain text: a button draws no colour code. The command is the
    key, so a click types exactly what a telnet player types.
    """
    rows = []

    for key, desc in getattr(menu, "popup_options", []) or []:
        plain_key = strip_ansi(str(key)).strip()
        label = strip_ansi(str(desc)).strip() if desc else plain_key
        rows.append({"key": plain_key, "label": label, "command": plain_key})

    return rows


def _title_of(menu) -> str:
    """The name of whoever the menu belongs to: the NPC, or the facility."""
    for attribute in ("npc", "facility"):
        owner = getattr(menu, attribute, None)

        if owner is not None:
            return str(getattr(owner, "key", ""))

    return ""


# ─── Public routines ─────────────────────────────────────────────────────────

def popup_sessions(menu) -> list:
    """
    Purpose: Name the sessions that see this node as a pop-up.

    Entry:
        menu - a BlackoutEvMenu that has just formatted a node.

    Exit/Returns:
        Returns a list of sessions. Empty for a node with no options, and for
        a menu that nobody draws as a pop-up.

    Module Globals:
        feed_const.CHANNEL_CHAR_POPUP read.

    Methodology:
        1. If the node has no options and no `_default`, return nothing. The
           node is an ending, and its text belongs in the log.
        2. Else, keep each target session that subscribes to the channel.

    Notes/References:
        BlackoutEvMenu.display_nodetext sends the text to every OTHER target
        session, so a telnet session beside a Godot one keeps its menu.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    from systems.interface.statefeed import subscriptions

    has_choice = bool(getattr(menu, "options", None)) or bool(
        getattr(menu, "default", None))

    if not has_choice:
        return []

    found = []

    for session in _target_sessions(menu):
        subscribed = subscriptions.is_subscribed(
            session, feed_const.CHANNEL_CHAR_POPUP)

        if subscribed:
            found.append(session)

    return found


def text_sessions(menu, shown: list) -> list:
    """The target sessions that did NOT get the pop-up, so get the text."""
    return [session for session in _target_sessions(menu) if session not in shown]


def build_snapshot(menu) -> dict:
    """
    Purpose: Describe the node on screen as a pop-up snapshot.

    Entry:
        menu - the caller's open BlackoutEvMenu.

    Exit/Returns:
        Returns a dict with the fields of CharPopupPayload.

    Module Globals:
        MENU_POPUP_KEY, INPUT_LABEL, QUIT_KEYS read.

    Methodology:
        1. Convert the node text to escaped BBCode with the parser the Portal
           uses for the log, so a menu reads the same in both places.
        2. List the options in the order the node declared them.
        3. Offer a text box only when the node reads typed input.

    Notes/References:
        The close command is the first quit key, which EvMenu's auto_quit
        binds on every node. A menu with auto_quit off offers no close.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    from server.conf.bbcode import to_bbcode

    raw_text = getattr(menu, "popup_text", "") or ""
    formatted = menu.nodetext_formatter(raw_text)
    has_input = bool(getattr(menu, "default", None))
    auto_quit = getattr(menu, "auto_quit", False)
    close_command = QUIT_KEYS[0] if auto_quit else ""

    return {
        "open": True,
        "key": MENU_POPUP_KEY,
        "title": _title_of(menu),
        "status": "",
        "grids": [],
        "quantity": [],
        "actions": [],
        "text": to_bbcode(formatted),
        "choices": _option_rows(menu),
        "input": {"label": INPUT_LABEL} if has_input else {},
        "timers": {},
        "close_command": close_command,
    }
