"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Assembles the registered panels into the finished summary screen.
"""

from evennia.utils import logger

from systems.ui.colors import ERROR_COLOR

from . import constants as const
from . import layout
from .registry import PANEL_REGISTRY


# ─── Private helper routines ─────────────────────────────────────────────────

def _panel_lines(panel: type, character: object, public: bool = False) -> list:
    """
    Purpose: Render one panel, converting a failure into a visible row rather
    than an exception.

    Entry:
        panel is a registered BasePanel subclass.
        character is a Character.
        public selects render_public over render.

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
    if public:
        renderer = panel.render_public
    else:
        renderer = panel.render

    try:
        lines = renderer(character)
    except Exception as exc:
        logger.log_err(f"[SUMMARY] Panel '{panel.key}' render failed: {exc!r}")
        error_row = layout.wide_field("", const.PANEL_ERROR_TEXT, color=ERROR_COLOR)

        return [error_row]

    return list(lines)


def _assemble(character: object, public: bool) -> str:
    """
    Purpose: Walk the registry and build the finished screen.

    Entry:
        character is a Character with its handlers available.
        public restricts the walk to panels flagged public, and switches each
        one to its public renderer.

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
        system behind it has anything to report, and it is also what makes the
        public view fall out of the same code path rather than needing its own.

        The `public` gate is applied here, once, rather than inside each panel.
        A panel cannot opt itself into the public view by accident, and a panel
        author who forgets the flag gets the private-only default.

    Notes/References:
        Rendered width is const.SUMMARY_WIDTH, matched to the option separator
        BlackoutEvMenu draws beneath it.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    lines = [layout.rule(heavy=True)]

    for panel in PANEL_REGISTRY.values():
        if public and not panel.public:
            continue

        panel_body = _panel_lines(panel, character, public=public)

        if not panel_body:
            continue

        heading = panel.title

        if public and panel.public_title:
            heading = panel.public_title

        if heading:
            lines.extend(layout.section(heading))

        lines.extend(panel_body)

    lines.append(layout.rule(heavy=True))
    screen = "\n".join(lines)

    return screen


# ─── Public routines ─────────────────────────────────────────────────────────

def render_summary(character: object) -> str:
    """
    Purpose: Build the character's own full dossier.

    Entry:
        character is a Character with its handlers available.

    Exit/Returns:
        Returns the screen, newline-joined and bracketed by heavy rules.

    Module Globals:
        None.

    Methodology:
        Every registered panel, every panel's full renderer.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    screen = _assemble(character, public=False)

    return screen


def render_public_summary(character: object) -> str:
    """
    Purpose: Build the version of the dossier another player may read.

    Entry:
        character is a Character with its handlers available.

    Exit/Returns:
        Returns the screen, newline-joined and bracketed by heavy rules.

    Module Globals:
        None.

    Methodology:
        Panels flagged `public`, each through its `render_public`. Two gates
        rather than one, because "may strangers see this band" and "how much of
        it" are different questions -- see BasePanel.render_public.

        Takes no viewer argument. Nothing in Blackout yet makes what you can
        read about someone depend on who you are; when factions, guilds or the
        Mutant path change that, the viewer becomes a parameter here and the
        panels grow a second argument. Adding it before there is a rule to
        enforce would be a parameter nothing could answer questions about.

    Notes/References:
        Achaea's HONOURS is the same idea: a deliberately narrower, public
        counterpart to a private SCORE.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    screen = _assemble(character, public=True)

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
        in systems/statefeed/payloads.py.

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
