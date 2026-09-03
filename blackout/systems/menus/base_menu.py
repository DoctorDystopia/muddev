"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: BlackoutEvMenu — the styled EvMenu subclass every game menu
             should be launched through, plus start_blackout_menu.
"""

import textwrap

from evennia.utils import evtable
from evennia.utils import logger
from evennia.utils.ansi import strip_ansi
from evennia.utils.evmenu import EvMenu
from evennia.utils.utils import mod_import

from systems.menus.constants import (
    BACK_HINT_LABEL,
    BACK_KEYS,
    CANCEL_DESC,
    FOOTER_GAP,
    HELP_HINT_LABEL,
    HELP_KEYS,
    QUIT_HINT_LABEL,
    QUIT_KEYS,
)
from systems.ui.colors import (
    HIGHLIGHT_COLOR,
    RESET_COLOR,
)
from systems.statefeed import constants as feed_const

# Every line this module sends a player is something an NPC says, so the
# routing tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_DIALOGUE = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_DIALOGUE}


# Public constant definitions
NODE_BORDER_CHAR = "="
SEPARATOR_LINE_CHAR = "-"
SEPARATOR_WIDTH = 60

# Module-level attribute a menu module may define to name its own parting
# line. Keeping the text in the menu module puts it beside the nodes it
# belongs to, so no launcher has to know what a menu says when it closes.
# The attribute may hold a plain string, or a callable(caller, menu) -> str
# for a line that depends on live state.
CLOSING_TEXT_ATTR = "CLOSING_TEXT"

# Module-level attribute a menu module sets truthy to declare that it belongs
# to the room the player opened it in. Character.at_post_move closes one on the
# way out: a shop counter and a bank vault are things you STAND at, and a menu
# that survives the walk is one whose prices, stock and item list describe
# somewhere the player is no longer standing.
#
# Declared as a module attribute rather than as a launcher argument for the
# reason CLOSING_TEXT_ATTR gives: the fact belongs beside the nodes it is true
# of, so no launcher has to know what kind of menu it is opening.
ROOM_BOUND_ATTR = "ROOM_BOUND"

# Typed input meaning "as many as are available". Shopkeep already exposes this
# as a menu option key; banking's custom-quantity node arms only _default, so
# without this the word is rejected there.
QUANTITY_ALL_KEYWORD = "all"

# Smallest quantity a player may enter. Zero and negatives are refused rather
# than silently clamped -- buying 1 of something after typing 0 is surprising.
MIN_QUANTITY = 1



def _footer_hint(key: str, label: str) -> str:
    """Render one '[k] label' pair for the standard menu footer."""
    hint = f"{HIGHLIGHT_COLOR}[{key}]{RESET_COLOR} {label}"

    return hint


def _menu_footer(back_offered: bool) -> str:
    """
    Purpose: Build the key-hint line printed at the foot of every node.

    Entry:
        back_offered is True when the node being rendered declares a back
        option of its own.

    Exit/Returns:
        Returns the rendered footer string.

    Module Globals:
        QUIT_KEYS, BACK_KEYS, HELP_KEYS read.
        QUIT_HINT_LABEL, BACK_HINT_LABEL, HELP_HINT_LABEL read.
        FOOTER_GAP read.

    Methodology:
        Only the first spelling of each binding is advertised -- "q", not
        "q/quit/exit" -- because the footer is a reminder, not a reference.
        The longer spellings still work; EvMenu accepts them regardless.

    Notes/References:
        Quit and help are handled by EvMenu itself and appear in no option
        row, which is exactly why they need advertising here. Back IS a real
        option with its own row, and is named again only so that the footer
        keeps one shape from screen to screen.

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    hints = [_footer_hint(QUIT_KEYS[0], QUIT_HINT_LABEL)]

    if back_offered:
        hints.append(_footer_hint(BACK_KEYS[0], BACK_HINT_LABEL))

    hints.append(_footer_hint(HELP_KEYS[0], HELP_HINT_LABEL))
    footer = FOOTER_GAP.join(hints)

    return footer


def _offers_back(optionlist: list) -> bool:
    """Report whether any of a node's options is bound to the back key."""
    back_key = BACK_KEYS[0]

    for key, _desc in optionlist:
        cleaned = strip_ansi(key or "").strip().lower()

        if cleaned == back_key:
            return True

    return False


def back_option(desc: str, goto: object) -> dict:
    """
    Purpose: Build the option dict for "go up one level" on any node.

    Entry:
        desc names the destination, e.g. "Back to recipes". Naming it is
        worth more than uniform wording -- it is the KEY that standardises.
        goto is a node name, a (node name, kwargs) tuple, or a goto callable.

    Exit/Returns:
        Returns one EvMenu option dict bound to the standard back key.

    Module Globals:
        BACK_KEYS read.

    Methodology:
        Binding an explicit key rather than letting EvMenu auto-number the
        option does two things: one letter means one thing on every screen,
        and a digit typed at a quantity prompt can never be swallowed by a
        navigation option that happened to land on that number.

    Notes/References:
        Reserve this for moving up ONE level. A node that also offers a jump
        to the menu's root leaves that second option numbered, so that "b"
        never has to mean two different destinations on one screen.

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    option = {"key": BACK_KEYS, "desc": desc, "goto": goto}

    return option


def cancel_option(goto: object) -> dict:
    """
    Purpose: Build the option dict for abandoning a prompt.

    Entry:
        goto is where an abandoned prompt returns to.

    Exit/Returns:
        Returns one EvMenu option dict bound to the standard back key.

    Module Globals:
        CANCEL_DESC read.

    Methodology:
        Cancelling is backing out of a prompt, so it shares the back key
        rather than claiming one of its own. The wording differs because
        "Cancel" is what abandoning a half-answered question is called.

    Notes/References:
        This is what keeps a quantity prompt honest. Left auto-numbered, a
        Cancel option sitting beside a _default option takes the key "2" --
        EvMenu numbers by position over ALL options including _default -- and
        options are matched before _default, so typing "2" at "how many?"
        cancelled instead of choosing two.

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    option = back_option(CANCEL_DESC, goto)

    return option


def _module_attribute(menudata: object, name: str, default: object = None) -> object:
    """
    Purpose: Read one declared attribute off a menu module, if it declares
             one.

    Entry:
        menudata is whatever was handed to the menu: a python path string, an
        already-imported module, or a dict of nodes.
        name is the module-level attribute to read.
        default is what a menu that declares none gets.

    Exit/Returns:
        Returns the module's value for `name`, or `default`.

    Module Globals:
        None.

    Methodology:
        Resolves a string path through mod_import, which is the same call
        EvMenu._parse_menudata makes moments later; importlib caches, so the
        module is not loaded twice.

        Generic over the attribute NAME rather than one reader per fact,
        because there are now two -- the closing line and whether the menu is
        bound to a room -- and a second copy of the import-and-getattr dance
        would be the point at which the two could resolve menudata
        differently.

    Notes/References:
        This imports exactly ONE named module, the one the caller already
        asked to open. It is not a walk over a package -- see the warning in
        CLAUDE.md about bulk-importing anything under blackout/.

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    if isinstance(menudata, dict):
        return default

    module = mod_import(menudata) if isinstance(menudata, str) else menudata

    if module is None:
        return default

    return getattr(module, name, default)


def _module_closing_text(menudata: object) -> object:
    """Read a menu module's declared closing text, or None."""
    return _module_attribute(menudata, CLOSING_TEXT_ATTR)


def _module_room_bound(menudata: object) -> bool:
    """Report whether a menu module declares itself bound to a room.

    A room-bound menu is one whose counterparty stands somewhere: the shop
    and the bank vault. Walking away closes it, which
    Character.at_post_move performs -- see ROOM_BOUND_ATTR.
    """
    return bool(_module_attribute(menudata, ROOM_BOUND_ATTR, False))



class BlackoutEvMenu(EvMenu):
    """
    Purpose: Base EvMenu subclass that applies Blackout's visual style,
             advertises the standard key bindings, and speaks the menu's
             parting line on the way out.

    Entry:
        caller is a valid Evennia Object, Account, or Session
        menudata is a string, module, or dict as per EvMenu parent
        close_text, when given, overrides the menu module's CLOSING_TEXT

    Exit/Returns:
        No conditions (menu lifecycle managed by EvMenu parent)

    Module Globals:
        NODE_BORDER_CHAR read
        SEPARATOR_LINE_CHAR read
        SEPARATOR_WIDTH read
        HIGHLIGHT_COLOR read
        RESET_COLOR read

    Methodology:
        Overrides EvMenu's formatter methods to apply Blackout's
        color scheme and structural layout. Subclasses can further
        override for system-specific display needs.

    Notes/References:
        Quitting is NOT declared as an option by any Blackout menu. EvMenu's
        auto_quit already binds q/quit/exit on every node of every menu, and
        tests them before a node's _default option (EvMenu.parse_input), so
        re-declaring them would only shift every other option's number while
        changing nothing a player can do.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """

    node_border_char = NODE_BORDER_CHAR


    def __init__(self, caller: object, menudata: object, close_text: object = None, **kwargs):
        """
        Purpose: Resolve the menu's parting line before the menu starts.

        Entry:
            caller and menudata are as documented on EvMenu.
            close_text is a string, a callable(caller, menu) -> str, or None
            to fall back to the menu module's CLOSING_TEXT.

        Exit/Returns:
            None.

        Module Globals:
            None

        Methodology:
            Both attributes are set BEFORE delegating upward, because the
            parent's __init__ ends by entering the start node -- and a start
            node that offers no options closes the menu there and then, which
            reaches close_menu before this constructor would otherwise have
            finished.

        Notes/References:
            close_text is deliberately not forwarded into EvMenu's **kwargs,
            so it never becomes a menu attribute the nodes can see. It is
            likewise absent from the dict a persistent menu saves; no Blackout
            menu is persistent.

        Author: Nick Hobar
        Creation date: 08/20/2026
        """
        self.close_text = close_text if close_text is not None else _module_closing_text(menudata)
        self.room_bound = _module_room_bound(menudata)
        self._back_offered = False

        super().__init__(caller, menudata, **kwargs)


    def _resolve_closing_text(self) -> str:
        """
        Purpose: Produce the parting line for this menu, in this moment.

        Entry:
            self.close_text is a string, a callable, or None.

        Exit/Returns:
            Returns the text to print, or "" when there is none.

        Module Globals:
            None

        Methodology:
            A callable is handed (caller, menu) -- the same pair EvMenu hands
            cmd_on_exit -- so it can read live state such as menu.npc.

        Notes/References:
            A failure here must not strand the player in a menu that refuses
            to close, so the exception is logged and swallowed.

        Author: Nick Hobar
        Creation date: 08/20/2026
        """
        if not self.close_text:
            return ""

        if not callable(self.close_text):
            return self.close_text

        try:
            resolved = self.close_text(self.caller, self)
        except Exception as exc:
            logger.log_err(f"BlackoutEvMenu closing text failed: {exc!r}")

            return ""

        return resolved or ""


    def close_menu(self) -> None:
        """
        Purpose: Speak the menu's parting line, then tear the menu down.

        Entry:
            No conditions.

        Exit/Returns:
            None.

        Module Globals:
            None

        Methodology:
            This is the ONLY place a Blackout menu says goodbye. Every route
            out arrives here -- the q/quit/exit binding, a node that returns
            no options, and a new menu displacing this one -- so routing the
            text through here is what makes those routes indistinguishable to
            the player. An NPC's farewell in particular is no longer printed
            by the node that happens to be last; it belongs to the closing of
            the conversation, however the conversation ends.

        Notes/References:
            The _quitting guard is the parent's own re-entry flag. Testing it
            before delegating means a second call prints nothing, which
            matters because close_menu is reachable from several directions.

        Author: Nick Hobar
        Creation date: 08/20/2026
        """
        if not self._quitting:
            closing_text = self._resolve_closing_text()

            if closing_text:
                self.msg((closing_text, _MSG_DIALOGUE))

        super().close_menu()


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


    def _format_node(self, nodetext: str, optionlist: list) -> str:
        """
        Purpose: Note whether this node offers a back option, then format it.

        Entry:
            nodetext and optionlist are as documented on EvMenu._format_node.

        Exit/Returns:
            Returns the fully rendered node.

        Module Globals:
            None

        Methodology:
            node_formatter receives only the already-rendered option block,
            which is too late to tell a back option from any other row. The
            keys are still separable here, one call earlier, so the answer is
            recorded on the way past.

        Notes/References:
            Overriding a private parent method is deliberate: the alternative
            is to have options_formatter set the flag as a side effect and
            lean on the parent calling it first, which is the same coupling
            without the honesty.

        Author: Nick Hobar
        Creation date: 08/20/2026
        """
        self._back_offered = _offers_back(optionlist)
        formatted_node = super()._format_node(nodetext, optionlist)

        return formatted_node


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
            SEPARATOR_WIDTH read
            RESET_COLOR read

        Methodology:
            If optionstext is empty, returns just the nodetext -- a node with
            no options is closing the menu, and a key footer printed under a
            farewell would be nonsense.

            Otherwise the node text, the options and the key footer are laid
            out between separator rules, so the footer sits in the same place
            on every screen in the game and the standard keys are legible
            from any node, not just the ones that happen to list them.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        if not optionstext:
            return nodetext

        separator = f"{RESET_COLOR}{SEPARATOR_LINE_CHAR * SEPARATOR_WIDTH}"
        footer = _menu_footer(self._back_offered)

        combined = f"{nodetext}\n\n{separator}\n\n{optionstext}\n{separator}\n{footer}"

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
        EVERY menu in the game is launched through here. Constructing a bare
        EvMenu instead silently opts that menu out of the shared styling, the
        key footer and the closing line -- which is how six menus came to have
        six different words for "quit".

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
