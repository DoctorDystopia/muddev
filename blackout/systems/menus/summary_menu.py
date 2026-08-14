"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: EvMenu nodes for the player summary screen ("dossier"): the whole
             summary on one node, with jumps into the panel that owns each
             number.
"""

from evennia.utils import logger

from systems.statefeed import events as feed
from systems.summary.service import render_summary

from .base_menu import start_blackout_menu


# Public constant definitions

MENU_PATH = "systems.menus.summary_menu"

# ndb slot holding the command to run once this menu has closed. ndb, not db:
# the value is consumed within the same turn it is set, and a followup left
# behind by a crash must not fire on next login.
FOLLOWUP_ATTR = "summary_followup"

# Run when the menu closes with no drill-down queued. Matches EvMenu's own
# default, so closing the dossier behaves like closing every other menu here.
DEFAULT_EXIT_COMMAND = "look"

# Drill-down targets: (option description, command to run after closing).
#
# Each entry names an EXISTING command rather than a menu module, so the target
# keeps its own lock, its own arguments and its own entry conditions. That is
# also why banking is absent: the bank menu is opened by a bank node the player
# must be standing at, and launching it from here would let anyone bank from
# anywhere. Quests are absent for the plainer reason that no quest command
# exists yet -- the summary reports the counts and stops there.
DRILL_DOWNS = (
    ("Skills panel", "skills"),
    ("Equipment", "equip"),
    ("Inventory", "inventory"),
    ("Combat options", "combatoptions"),
)

REFRESH_DESC = "Refresh"
CLOSE_DESC = "Close dossier"
CLOSE_TEXT = "Closing dossier."


def _on_exit(caller: object, menu: object) -> None:
    """
    Purpose: Run whatever drill-down the player chose, after the menu has
    already torn itself down.

    Entry:
        caller is the Character the menu was running on.
        menu is the closing EvMenu instance.

    Exit/Returns:
        No conditions.

    Module Globals:
        FOLLOWUP_ATTR read and cleared.
        DEFAULT_EXIT_COMMAND read.

    Methodology:
        EvMenu removes its cmdset BEFORE calling cmd_on_exit, so by the time
        this runs the caller's normal commands are reachable again. That
        ordering is the whole mechanism: a drill-down cannot simply invoke the
        target menu from inside a node, because two EvMenus would be fighting
        over the same merged cmdset.

        The followup is cleared before it is executed, so a command that itself
        raises cannot leave a stale one armed for the next close.

    Notes/References:
        cmd_on_exit is called from EvMenu.close_menu, which is reached either
        by the quit command or by a node returning no options -- node_launch
        below uses the latter.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    followup = getattr(caller.ndb, FOLLOWUP_ATTR, None)
    setattr(caller.ndb, FOLLOWUP_ATTR, None)

    if not followup:
        followup = DEFAULT_EXIT_COMMAND

    try:
        caller.execute_cmd(followup, session=menu._session)
    except Exception as exc:
        logger.log_err(f"summary_menu._on_exit failed running '{followup}': {exc!r}")


def start_summary_menu(caller: object) -> object:
    """
    Purpose: Open the dossier for `caller`.

    Entry:
        caller is a Character with its handlers available.

    Exit/Returns:
        Returns the running BlackoutEvMenu instance.

    Module Globals:
        MENU_PATH read.
        FOLLOWUP_ATTR cleared.

    Methodology:
        Clears any stale followup before opening, so a menu that was closed
        abnormally last time cannot fire its drill-down on this one's exit.

        The state-feed publish rides here rather than in the `score` command
        because this is the choke point every way of opening the dossier passes
        through. A graphical client asking for the summary gets the structured
        payload from the same action that draws the text screen, so the two can
        never show different numbers.

    Notes/References:
        emit_summary pre-checks the subscription and costs nothing on a server
        with no graphical clients; it also cannot raise, like every feed path.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    setattr(caller.ndb, FOLLOWUP_ATTR, None)
    feed.emit_summary(caller)
    menu = start_blackout_menu(caller, MENU_PATH, startnode="start", cmd_on_exit=_on_exit)

    return menu


def start(caller: object, **kwargs) -> tuple:
    """
    Purpose: The dossier itself -- the whole summary, plus its drill-downs.

    Entry:
        caller is a Character with its handlers available.

    Exit/Returns:
        Returns the (text, options) tuple EvMenu requires of a node.

    Module Globals:
        DRILL_DOWNS, REFRESH_DESC, CLOSE_DESC read.

    Methodology:
        One node holds the entire screen. The summary is rebuilt on every visit
        rather than cached, because every number on it is derived live and a
        cached dossier would be wrong the moment the player took a hit.

        Refresh re-enters this same node, which is what makes the screen usable
        as a passive readout during a fight.

    Notes/References:
        A node MUST return a (text, options) tuple -- returning a node name
        from a node prints that string at the player instead of navigating.
        Only goto callables return node names.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    text = render_summary(caller)
    options_list = []

    for description, command in DRILL_DOWNS:
        options_list.append({
            "desc": description,
            "goto": ("node_launch", {"command": command}),
        })

    options_list.append({"desc": REFRESH_DESC, "goto": "start"})
    options_list.append({"desc": CLOSE_DESC, "goto": "node_exit"})

    return text, tuple(options_list)


def node_launch(caller: object, **kwargs) -> tuple:
    """
    Purpose: Queue a drill-down command and close the menu so it can run.

    Entry:
        caller is a Character.
        kwargs["command"] is one of the command strings in DRILL_DOWNS.

    Exit/Returns:
        Returns (text, None). The None is load-bearing: EvMenu closes a node
        that offers no options, and closing is what lets _on_exit run the
        queued command against the caller's normal cmdset.

    Module Globals:
        FOLLOWUP_ATTR written.

    Methodology:
        The node prints nothing of its own -- the target command is about to
        print its own screen, and a "launching..." line between the two would
        just be noise.

    Notes/References:
        See _on_exit for why the handoff goes through menu teardown rather
        than being invoked here directly.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    command = kwargs.get("command")
    setattr(caller.ndb, FOLLOWUP_ATTR, command)

    return "", None


def node_exit(caller: object, **kwargs) -> tuple:
    """
    Purpose: Close the dossier without a drill-down.

    Entry:
        caller is a Character.

    Exit/Returns:
        Returns (text, None), which closes the menu.

    Module Globals:
        CLOSE_TEXT read.

    Methodology:
        Leaves FOLLOWUP_ATTR untouched at None, so _on_exit falls back to the
        default exit command.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    return CLOSE_TEXT, None
