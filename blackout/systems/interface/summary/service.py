"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Assembles the registered panels into the finished summary screen.
"""

from evennia.utils import logger

from systems.interface.ui.colors import ERROR_COLOR

from . import constants as const
from . import layout
from .registry import PANEL_REGISTRY


# ─── Private helper routines ─────────────────────────────────────────────────

def _panel_lines(panel: type, character: object) -> list:
    """
    Purpose: Render one panel, converting a failure into a visible row rather
    than an exception.

    Entry:
        panel is a registered BasePanel subclass.
        character is a Character.

    Exit/Returns:
        Returns the panel's display lines. On failure, returns a single row
        carrying PANEL_ERROR_TEXT.

    Module Globals:
        const.PANEL_ERROR_TEXT read.
        ERROR_COLOR read.

    Methodology:
        Containment is the point. The dossier's value is that it is the ONE
        screen a player checks, which means a single bad panel must not be able
        to take the other five with it -- a broken item on the readiness band
        should not hide the player's HP.

        A failure is shown, not swallowed: the heading still renders, with the
        marker underneath, so the player can see that something is missing
        rather than quietly reading a screen with a hole in it.

    Notes/References:
        The registry already tolerates a panel that fails to IMPORT. This is
        the same tolerance one stage later, for a panel that fails to RENDER.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    try:
        lines = panel.render(character)
    except Exception as exc:
        logger.log_err(f"[SUMMARY] Panel '{panel.key}' render failed: {exc!r}")
        error_row = layout.wide_field("", const.PANEL_ERROR_TEXT, color=ERROR_COLOR)

        return [error_row]

    return list(lines)


def _assemble(character: object) -> str:
    """
    Purpose: Walk the registry and build the finished screen.

    Entry:
        character is a Character with its handlers available.

    Exit/Returns:
        Returns the screen, newline-joined and bracketed by heavy rules.

    Module Globals:
        PANEL_REGISTRY read.

    Methodology:
        A panel with a `title` gets a separator and a heading; one without
        renders flush, which is how the identity band becomes the screen's
        title bar instead of a section like the rest.

        A panel returning no lines is skipped ENTIRELY, heading included, so a
        band with nothing to say costs no vertical space. That is what lets a
        future panel -- guild, faction standing, housing -- ship before the
        system behind it has anything to report.

        The screen is the same for every reader. `score` and `profile <name>`
        both build it here.

    Notes/References:
        Rendered width is const.SUMMARY_WIDTH, matched to the option separator
        BlackoutEvMenu draws beneath it.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    lines = [layout.rule(heavy=True)]

    for panel in PANEL_REGISTRY.values():
        panel_body = _panel_lines(panel, character)

        if not panel_body:
            continue

        heading = panel.title

        if heading:
            lines.extend(layout.section(heading))

        lines.extend(panel_body)

    lines.append(layout.rule(heavy=True))
    screen = "\n".join(lines)

    return screen


# ─── Public routines ─────────────────────────────────────────────────────────

def render_summary(character: object) -> str:
    """
    Purpose: Build the full dossier of a character.

    Entry:
        character is a Character with its handlers available. The reader may
        be that character or any other player.

    Exit/Returns:
        Returns the screen, newline-joined and bracketed by heavy rules.

    Module Globals:
        None.

    Methodology:
        Every registered panel, every panel's full renderer.

        Takes no viewer argument. The whole dossier is public, so nothing
        depends on who reads it. When a rule makes a band depend on the
        reader, the viewer becomes a parameter here.

    Notes/References:
        `score` shows the dossier of the caller. `profile <name>` shows this
        same screen for any character.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    screen = _assemble(character)

    return screen


def summary_data(character: object) -> dict:
    """
    Purpose: Build the whole summary as plain JSON-safe values, keyed by panel.

    Entry:
        character is a Character with its handlers available.

    Exit/Returns:
        Returns a dict of panel key -> that panel's data dict. A panel whose
        data() raises contributes an empty dict.

    Module Globals:
        PANEL_REGISTRY read.

    Methodology:
        Same containment as the text path, for the same reason. Nothing
        consumes this yet: the `char_summary` state-feed channel is phase 2.
        It exists now so that panels are written against both outputs while
        their author still has the handler reads in front of them.

    Notes/References:
        Every value must survive json.dumps -- see the constraints documented
        in systems/interface/statefeed/payloads.py.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    payload = {}

    for panel_key, panel in PANEL_REGISTRY.items():
        try:
            panel_data = panel.data(character)
        except Exception as exc:
            logger.log_err(f"[SUMMARY] Panel '{panel_key}' data failed: {exc!r}")
            panel_data = {}

        payload[panel_key] = panel_data

    return payload
