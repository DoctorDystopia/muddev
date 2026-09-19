"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Commands for how the game DRAWS itself to you, as opposed to what
             it does.

             One command today. It exists because a preference with no command
             is not a preference: the ASCII map's automatic printing became
             settable on 08/28/2026 and, for a day, the only way to set it was
             `py self.db.show_ascii_map = False` -- superuser-locked,
             undocumented, and invisible to `help`. A player cannot use a
             switch nobody has told them about.
"""

from evennia import Command
from evennia import CmdSet

from commands.constants import HELP_CATEGORY_GENERAL
from systems.interface.popups import constants as popup_const
from systems.interface.statefeed import constants as feed_const

# Every line this module sends a player is the server speaking as itself, so
# the routing tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/interface/statefeed/constants.py.
_MSG_SYSTEM = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_SYSTEM}


# ─── Public constant definitions ─────────────────────────────────────────────

# What the command accepts, and what each means.
ARG_ON: str = "on"
ARG_OFF: str = "off"

MSG_ON: str = (
    "|wAutomap on.|n The area map will be printed every time you look or move."
)
MSG_OFF: str = (
    "|wAutomap off.|n The area map will no longer be printed when you move. "
    "Turn it back on with |wautomap on|n."
)
MSG_STATE_ON: str = (
    "Automap is |won|n: the area map is printed every time you look or move. "
    "Turn it off with |wautomap off|n."
)
MSG_STATE_OFF: str = (
    "Automap is |woff|n: the area map is not printed when you move. Turn it "
    "on with |wautomap on|n."
)

# Appended to the state report when nothing has been chosen, so a player can
# tell "I set this" from "this is what my client got by default".
MSG_DEFAULT_SUFFIX: str = " (the default for the client you are using)"

MSG_USAGE: str = "Usage: |wautomap|n, |wautomap on|n, or |wautomap off|n."


class CmdAutomap(Command):
    """
    show or hide the area map as you move

    Usage:
      automap
      automap on
      automap off

    The area map is the picture of your surroundings printed above each room
    description. With `automap` on it is redrawn every time you look or move;
    with it off you are shown the room and its exits and nothing else.

    With no argument, reports which way it is currently set.

    Your choice is remembered on your character and outlives a disconnect.

    THE DEFAULT DEPENDS ON YOUR CLIENT. A graphical client draws its own
    minimap from the game's map feed, so printing the same picture into the
    text log on every step would be the same information twice -- automap
    starts off there. Every other client starts with it on, exactly as it
    always was. Setting it either way overrides that, permanently.
    """

    key = "automap"
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_GENERAL

    def func(self):
        """
        Purpose: Report or set whether the area map is printed on movement.

        Entry:
            self.args carries "on", "off", or nothing.

        Exit/Returns:
            Returns nothing. Messages the caller in every branch.

        Module Globals:
            ARG_ON, ARG_OFF, MSG_* read.
            feed_const.ASCII_MAP_ATTR read and written.

        Methodology:
            Writes the same attribute GridTile._wants_ascii_map reads, named
            from the same constant, so the setting has one spelling. UNSET is a
            real third state and is not written by this command's report path:
            it means "decide from the client", and collapsing it to a stored
            True or False on a mere `automap` with no argument would silently
            pin a player to whatever their client happened to default to.

        Notes/References:
            The default is decided in typeclasses/rooms.py, which is also the
            only reader. This command is the only writer.

        Author: Nick Hobar
        Creation date: 08/28/2026
        """
        argument = self.args.strip().lower()

        if not argument:
            self._report()
            return

        if argument == ARG_ON:
            self.caller.attributes.add(feed_const.ASCII_MAP_ATTR, True)
            self.caller.msg((MSG_ON, _MSG_SYSTEM))
            return

        if argument == ARG_OFF:
            self.caller.attributes.add(feed_const.ASCII_MAP_ATTR, False)
            self.caller.msg((MSG_OFF, _MSG_SYSTEM))
            return

        self.caller.msg((MSG_USAGE, _MSG_SYSTEM))

    def _report(self):
        """
        Purpose: Say which way the setting currently resolves, and how it got
                 there.

        Entry:
            No conditions.

        Exit/Returns:
            Returns nothing.

        Module Globals:
            MSG_STATE_ON, MSG_STATE_OFF, MSG_DEFAULT_SUFFIX read.

        Methodology:
            Asks the ROOM rather than reading the attribute, so the report
            cannot disagree with what actually happens on the next look --
            which is the whole failure mode a settings report exists to
            prevent. A caller standing somewhere with no such room falls back
            to the attribute, and to on.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/28/2026
        """
        stored = self.caller.attributes.get(
            feed_const.ASCII_MAP_ATTR, default=None)
        location = self.caller.location
        resolve = getattr(location, "_wants_ascii_map", None)

        if resolve is None:
            showing = True if stored is None else bool(stored)
        else:
            showing = resolve(self.caller)

        message = MSG_STATE_ON if showing else MSG_STATE_OFF

        if stored is None:
            message += MSG_DEFAULT_SUFFIX

        self.caller.msg((message, _MSG_SYSTEM))


class CmdPopup(Command):
    """
    close a pop-up, or set its quantity

    Usage:
      popup close
      popup quantity <1-1000000|all>

    A graphical client shows some things, such as the bank, as a pop-up over
    the world. Its close button and its 1 / 5 / 10 / X / All buttons send these
    lines, and you can type them too.

    The quantity is what a left click moves: `popup quantity 5` makes a click
    on a vault item withdraw five. Each pop-up remembers its own quantity, and
    it outlives a logout.
    """

    key = popup_const.POPUP_COMMAND_KEY
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_GENERAL

    def func(self):
        """
        Purpose: Close the open pop-up, or set its quantity mode.

        Entry:
            self.args carries "close" or "quantity <amount>".

        Exit/Returns:
            Returns nothing. Messages the caller in every branch.

        Module Globals:
            popup_const.POPUP_ARG_* and popup_const.MSG_* read.

        Methodology:
            A thin parser over systems/interface/popups/service.py, which owns
            the state and the send. The service is imported inside the
            routine, because its registry imports every pop-up definition.

        Notes/References:
            In DisplayCmdSet because a pop-up is how the game draws itself.
            It changes nothing in the world.

        Author: Nick Hobar
        Creation date: 09/18/2026
        """
        from systems.interface.popups import service

        verb, _sep, rest = self.args.strip().partition(" ")
        verb = verb.lower()

        if verb == popup_const.POPUP_ARG_CLOSE:
            title = service.close_popup(self.caller)
            message = popup_const.MSG_NOTHING_OPEN

            if title:
                message = popup_const.MSG_CLOSED.format(title=title.lower())

            self.caller.msg((message, _MSG_SYSTEM))
            return

        if verb == popup_const.POPUP_ARG_QUANTITY:
            _succeeded, message = service.set_quantity_mode(self.caller, rest)
            self.caller.msg((message, _MSG_SYSTEM))
            return

        usage = popup_const.MSG_USAGE.format(
            maximum=popup_const.QUANTITY_MAX_CUSTOM)
        self.caller.msg((usage, _MSG_SYSTEM))


class DisplayCmdSet(CmdSet):
    """Commands for how the game draws itself."""

    key = "DisplayCmdSet"

    def at_cmdset_creation(self):
        self.add(CmdAutomap())
        self.add(CmdPopup())
