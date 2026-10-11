"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: The pick menu of the Exterminator skill, for a session that
             draws no pop-up (telnet).

             `task pick` with no number opens it. A client that draws
             pop-ups gets the task pop-up with its cards. The menu and the
             pop-up read the same CardView list, and both pick through
             ExterminatorHandler.pick. Presentation only. DESIGN-0012,
             Phase 4.
"""

from systems.gameplay.exterminator import constants as ext_const
from systems.gameplay.exterminator.cards import card_views
from systems.interface.ui.colors import title as _line



_MENU_TITLE = "Pick a buff"  # TBD text
_OPTION_LATER = "Later."

# Spoken by BlackoutEvMenu.close_menu, however the menu ends.
CLOSING_TEXT = ""



def _card_option(view) -> dict:
    """One card as a menu option."""
    description = f"{view.name} ({view.rarity_name})"

    return {"desc": description, "goto": (_pick, {"number": view.number})}


def start(caller: object, **kwargs) -> tuple:
    """
    Purpose: Show the open offer, one option for each card.

    Entry:
        caller is a Character with an `exterminator` handler.

    Exit/Returns:
        Returns (text, options). With no card, the text says so and the
        options are None, so the menu closes.

    Module Globals:
        _MENU_TITLE, _OPTION_LATER read.

    Methodology:
        The text lists each card with its description and its warnings, from
        card_views. Each option picks one card.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    views = card_views(caller)

    if not views:
        return ext_const.MSG_NO_CARDS, None

    text_lines = [_line(_MENU_TITLE), ""]

    for view in views:
        text_lines.append(f"{view.name} ({view.rarity_name}): {view.description}")
        text_lines.extend(f"   {warning}" for warning in view.warnings)

    options = [_card_option(view) for view in views]
    options.append({"desc": _OPTION_LATER, "goto": "node_later"})

    return "\n".join(text_lines), options


def _pick(caller: object, raw_string: str = "", **kwargs) -> tuple:
    """Pick one card, then show what happened."""
    _picked, message = caller.exterminator.pick(kwargs.get("number", 0))

    return "node_result", {"message": message}


def node_result(caller: object, raw_string: str = "", **kwargs) -> tuple:
    """Show the result of the pick, and end the menu."""
    return kwargs.get("message", ""), None


def node_later(caller: object, raw_string: str = "", **kwargs) -> tuple:
    """End the menu. The pick stays in the bank."""
    return "", None
