"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: BlackoutEvMenu — the styled EvMenu subclass every game menu
             should be launched through, plus start_blackout_menu.
"""

from evennia.utils.evmenu import EvMenu
from evennia.utils import evtable
from systems.ui.colors import (
    HIGHLIGHT_COLOR,
    RESET_COLOR,
)


# Public constant definitions
NODE_BORDER_CHAR = "="
SEPARATOR_LINE_CHAR = "-"

# Typed input meaning "as many as are available". Shopkeep already exposes this
# as a menu option key; banking's custom-quantity node arms only _default, so
# without this the word is rejected there.
QUANTITY_ALL_KEYWORD = "all"

# Smallest quantity a player may enter. Zero and negatives are refused rather
# than silently clamped -- buying 1 of something after typing 0 is surprising.
MIN_QUANTITY = 1



class BlackoutEvMenu(EvMenu):
    """
    Purpose: Base EvMenu subclass that applies Blackout's visual style
             and provides shared utility access for all game menus.

    Entry:
        caller is a valid Evennia Object, Account, or Session
        menudata is a string, module, or dict as per EvMenu parent

    Exit/Returns:
        No conditions (menu lifecycle managed by EvMenu parent)

    Module Globals:
        NODE_BORDER_CHAR read
        SEPARATOR_LINE_CHAR read
        SKILL_COLOR read
        TITLE_COLOR read
        HIGHLIGHT_COLOR read
        ERROR_COLOR read
        SUCCESS_COLOR read
        RESET_COLOR read

    Methodology:
        Overrides EvMenu's formatter methods to apply Blackout's
        color scheme and structural layout. Subclasses can further
        override for system-specific display needs.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """

    node_border_char = NODE_BORDER_CHAR


    def nodetext_formatter(self, nodetext: str) -> str:
        """
        Purpose: Formats the node description text with Blackout styling.

        Entry:
            nodetext is a string of arbitrary length

        Exit/Returns:
            Returns a dedented, stripped, and color-normalized string.

        Module Globals:
            RESET_COLOR read

        Methodology:
            Dedents and strips the raw text, then wraps it in
            a reset-color prefix to ensure clean rendering.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        import textwrap

        cleaned_text = textwrap.dedent(nodetext).strip()
        formatted_text = f"{RESET_COLOR}{cleaned_text}"

        return formatted_text


    def helptext_formatter(self, helptext: str) -> str:
        """
        Purpose: Formats the help text for a node.

        Entry:
            helptext is a string of arbitrary length

        Exit/Returns:
            Returns a dedented and stripped help string.

        Module Globals:
            HIGHLIGHT_COLOR read
            RESET_COLOR read

        Methodology:
            Applies highlight color to help text for visual distinction.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        import textwrap

        cleaned_text = textwrap.dedent(helptext).strip()
        formatted_text = f"{HIGHLIGHT_COLOR}{cleaned_text}{RESET_COLOR}"

        return formatted_text


    def options_formatter(self, optionlist: list) -> str:
        """
        Purpose: Formats the option list into a tabulated display.

        Entry:
            optionlist is a list of (key, description) tuples

        Exit/Returns:
            Returns a string with formatted option rows.

        Module Globals:
            HIGHLIGHT_COLOR read
            RESET_COLOR read

        Methodology:
            Uses EvTable to create a two-column layout. The key
            column uses highlight color, the description uses
            normal rendering.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        if not optionlist:
            return ""

        table = evtable.EvTable()

        for key, desc in optionlist:
            styled_key = f"{HIGHLIGHT_COLOR}{key}{RESET_COLOR}"
            table.add_row(styled_key, desc)

        table.reformat_column(0, align="l")
        table.reformat_column(1, align="l")

        formatted_table = str(table)

        return formatted_table


    def node_formatter(self, nodetext: str, optionstext: str) -> str:
        """
        Purpose: Combines node text and options into the final display.

        Entry:
            nodetext is a formatted string from nodetext_formatter
            optionstext is a formatted string from options_formatter

        Exit/Returns:
            Returns the complete display string for the node.

        Module Globals:
            SEPARATOR_LINE_CHAR read
            RESET_COLOR read

        Methodology:
            If optionstext is empty, returns just the nodetext.
            Otherwise joins the node text and options with a separator
            line and appends a prompt hint at the bottom.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        if not optionstext:
            return nodetext

        separator = f"{RESET_COLOR}{SEPARATOR_LINE_CHAR * 60}"
        prompt_hint = f"{HIGHLIGHT_COLOR}Enter an option number or command:{RESET_COLOR}"

        combined = f"{nodetext}\n\n{separator}\n\n{optionstext}\n\n{prompt_hint}"

        return combined



def start_blackout_menu(caller: object,
                        menudata: object,
                        startnode: str = "start",
                        **kwargs) -> BlackoutEvMenu:
    """
    Purpose: Convenience function to start a Blackout-styled EvMenu.

    Entry:
        caller is a valid Evennia Object, Account, or Session
        menudata is a string (module path), module, or dict
        startnode is the name of the initial node (default "start")
        **kwargs are passed to the EvMenu init

    Exit/Returns:
        Returns the BlackoutEvMenu instance.

    Module Globals:
        None

    Methodology:
        Wraps the BlackoutEvMenu constructor with sensible defaults.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    menu_instance = BlackoutEvMenu(caller, menudata, startnode=startnode, **kwargs)

    return menu_instance



def parse_quantity(raw_string: str, max_qty: int) -> tuple:
    """
    Purpose: Turn a player-typed quantity into a validated, clamped integer.

    Entry:
        raw_string is whatever the player typed. May be None or blank.
        max_qty is the largest quantity currently available, an integer.

    Exit/Returns:
        Returns a (count, error_message) tuple. Exactly one is non-None:
        a valid entry yields (int, None), a rejected one yields (None, str).
        The error message carries no colour markup -- callers apply their own.

    Module Globals:
        QUANTITY_ALL_KEYWORD read.
        MIN_QUANTITY read.

    Methodology:
        Accept the "all" keyword first, then parse an integer, then refuse
        anything below MIN_QUANTITY, then clamp down to max_qty. Clamping the
        top silently is deliberate: asking for more than is in stock is a
        reasonable way to say "all of it", whereas asking for zero is not a
        quantity at all.

    Notes/References:
        The repo had two divergent implementations of this: banking's two-pass
        _default node, which refused counts below 1, and shopkeep's one-pass
        parser callables, which silently clamped them up to 1. Both now route
        here, so shopkeep gains the refusal and banking gains the "all"
        keyword. Only the parse is shared -- each menu keeps its own node
        shape, because banking's two-pass form and shopkeep's goto-callable
        form are both correct EvMenu idioms and unifying them would fight the
        framework.

    Author: Nick Hobar
    Creation date: 08/01/2026
    """
    cleaned = (raw_string or "").strip().lower()

    if cleaned == QUANTITY_ALL_KEYWORD:
        return max_qty, None

    try:
        count = int(cleaned)
    except (ValueError, TypeError):
        parse_error = (
            f"Invalid number. Enter a quantity between {MIN_QUANTITY} and "
            f"{max_qty}, or '{QUANTITY_ALL_KEYWORD}'."
        )

        return None, parse_error

    if count < MIN_QUANTITY:
        range_error = f"Quantity must be at least {MIN_QUANTITY}."

        return None, range_error

    clamped = min(count, max_qty)

    return clamped, None
