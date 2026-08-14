"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Summary panel: who this character is. Renders the dossier's title
             bar rather than a titled section.
"""

from .. import constants as const
from .. import layout
from .base_panel import BasePanel


# Public constant definitions

# Title-bar prefix. The screen is framed as a Hegemony citizen record rather
# than a stat sheet, which is what gives the Character Mode markers below a
# place to sit that reads as in-world rather than as UI chrome.
DOSSIER_LABEL = "DOSSIER"
DOSSIER_SEPARATOR = " -- "

# Joins the mode marker to the hardcore marker on the right-hand side.
MARKER_SEPARATOR = " - "


class IdentityPanel(BasePanel):
    """
    Purpose: The dossier's title bar -- character name and path markers.

    Entry:
        character is a Character.

    Exit/Returns:
        Not applicable -- see render / data.

    Module Globals:
        const.CHARACTER_MODE_ATTR, const.CHARACTER_MODE_DEFAULT,
        const.HARDCORE_ATTR, const.HARDCORE_LABEL read.

    Methodology:
        `title` is deliberately empty: service.py draws a section heading for
        every panel that has one, and this panel IS the heading.

    Notes/References:
        02_Player/Character_Modes.md defines the three paths and the
        independent Hardcore flag this panel is shaped around.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """

    key = "identity"
    title = ""
    order = const.PANEL_ORDER_IDENTITY
    public = True


    @classmethod
    def _mode_marker(cls, character: object) -> str:
        """
        Purpose: Build the right-hand path marker text.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns e.g. "STANDARD" or "MUTANT - HARDCORE".

        Module Globals:
            const.CHARACTER_MODE_ATTR, const.CHARACTER_MODE_DEFAULT,
            const.HARDCORE_ATTR, const.HARDCORE_LABEL read.

        Methodology:
            Character Modes are not implemented. Reading the attribute with the
            documented default means the dossier shows the truth today (every
            character IS on the Standard path) and starts showing real modes
            the day the system writes these attributes, with no edit here.

        Notes/References:
            See the ownership warning on CHARACTER_MODE_ATTR in constants.py --
            this panel must be repointed when Character Modes ships.

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        mode = character.attributes.get(
            const.CHARACTER_MODE_ATTR, default=const.CHARACTER_MODE_DEFAULT
        )
        mode_text = str(mode or const.CHARACTER_MODE_DEFAULT).upper()

        is_hardcore = character.attributes.get(const.HARDCORE_ATTR, default=False)

        if not is_hardcore:
            return mode_text

        marker = f"{mode_text}{MARKER_SEPARATOR}{const.HARDCORE_LABEL}"

        return marker


    @classmethod
    def render(cls, character: object) -> list:
        """
        Purpose: Render the title bar.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a one-line list.

        Module Globals:
            DOSSIER_LABEL, DOSSIER_SEPARATOR read.

        Methodology:
            Name flush left, path markers flush right, via layout.split_line.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        left = f"{DOSSIER_LABEL}{DOSSIER_SEPARATOR}{character.key}"
        right = cls._mode_marker(character)
        line = layout.split_line(left, right)

        return [line]


    @classmethod
    def data(cls, character: object) -> dict:
        """
        Purpose: Structured form of the title bar.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a dict of plain JSON-safe values.

        Module Globals:
            const.CHARACTER_MODE_ATTR, const.CHARACTER_MODE_DEFAULT,
            const.HARDCORE_ATTR read.

        Methodology:
            Mode and hardcore are reported as separate fields rather than as
            the joined marker string, because a client will want to badge them
            independently.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        mode = character.attributes.get(
            const.CHARACTER_MODE_ATTR, default=const.CHARACTER_MODE_DEFAULT
        )
        is_hardcore = character.attributes.get(const.HARDCORE_ATTR, default=False)

        payload = {
            "name": str(character.key),
            "mode": str(mode or const.CHARACTER_MODE_DEFAULT),
            "hardcore": bool(is_hardcore),
        }

        return payload
