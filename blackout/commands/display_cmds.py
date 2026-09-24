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
from systems.interface.ui import move_text
from systems.interface.ui.colors import (
    DIM_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    TITLE_COLOR,
)

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

# `movetext`. The part keys and their labels come from
# systems/interface/ui/move_text.py, never from a list here.
MOVETEXT_KEY: str = "movetext"
MOVETEXT_ARG_RESET: str = "reset"

MOVETEXT_MSG_HEADER: str = f"{TITLE_COLOR}Room text when you move:{RESET_COLOR}"

# The colour goes OUTSIDE each padded field. Markup inside it counts toward
# the width, and the columns then do not line up.
MOVETEXT_MSG_ROW: str = (
    f"  {TITLE_COLOR}{{key:<12}}{RESET_COLOR}"
    f"{{colour}}{{state:<5}}{RESET_COLOR}{{label}}"
)
MOVETEXT_MSG_FOOTER: str = (
    f"Change one with {TITLE_COLOR}movetext <part> on{RESET_COLOR} or "
    f"{TITLE_COLOR}movetext <part> off{RESET_COLOR}. "
    f"{TITLE_COLOR}look{RESET_COLOR} always shows the whole room."
)
MOVETEXT_MSG_SET: str = (
    f"{TITLE_COLOR}Movetext:{RESET_COLOR} {{label}} is now "
    f"{{colour}}{{state}}{RESET_COLOR} when you move."
)
MOVETEXT_MSG_RESET: str = (
    f"{TITLE_COLOR}Movetext reset.{RESET_COLOR} "
    "Every part of the room prints when you move."
)
MOVETEXT_MSG_USAGE: str = (
    f"Usage: {TITLE_COLOR}movetext{RESET_COLOR}, "
    f"{TITLE_COLOR}movetext <part> on{RESET_COLOR}, "
    f"{TITLE_COLOR}movetext <part> off{RESET_COLOR}, or "
    f"{TITLE_COLOR}movetext reset{RESET_COLOR}. Parts: {{parts}}."
)

# How each state reads, and in what colour. Keyed by "is the part shown".
_MOVETEXT_STATES: dict = {
    True: (ARG_ON, SUCCESS_COLOR),
    False: (ARG_OFF, DIM_COLOR),
}


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


class CmdMovetext(Command):
    """
    choose what the log prints when you move

    Usage:
      movetext
      movetext <part> on
      movetext <part> off
      movetext reset

    Each step prints the room you walk into: its name, its description, the
    exits, who is here, and what you can see. Turn off the parts you do not
    want, and walking gets quieter.

    Parts:
      name        the room name
      desc        the room description
      exits       the Exits line
      characters  the Characters line
      things      the You see line

    With no argument, lists every part and whether it is on. `reset` turns
    every part back on.

    This changes what a STEP prints and nothing else. Typing `look` always
    shows the whole room. The area map has its own switch: see `automap`.

    Your choice is remembered on your character.
    """

    key = MOVETEXT_KEY
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_GENERAL

    def func(self):
        """
        Purpose: Report or set which parts of the room text print on a move.

        Entry:
            self.args carries nothing, "reset", or "<part> on|off".

        Exit/Returns:
            Returns nothing. Messages the caller in every branch.

        Module Globals:
            MOVETEXT_* and ARG_* read.

        Methodology:
            A thin parser over systems/interface/ui/move_text.py, which owns
            the parts and the Attribute. The part keys come from that table,
            so a new part needs no edit here.

        Notes/References:
            The one reader is Character._look_on_arrival.

        Author: Nick Hobar
        Creation date: 09/22/2026
        """
        words = self.args.strip().lower().split()

        if not words:
            self._report()
            return

        if words == [MOVETEXT_ARG_RESET]:
            move_text.reset(self.caller)
            self.caller.msg((MOVETEXT_MSG_RESET, _MSG_SYSTEM))
            return

        self._set(words)

    def _set(self, words: list) -> None:
        """
        Purpose: Turn one part on or off, or give the usage for a bad line.

        Entry:
            words - the lowered words of the argument, at least one.

        Exit/Returns:
            Returns nothing. Messages the caller.

        Module Globals:
            _MOVETEXT_STATES, MOVETEXT_MSG_SET, MOVETEXT_MSG_USAGE read.

        Methodology:
            Exactly two words: a part key, then on or off. Anything else gets
            the usage, with the part keys read from the table.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/22/2026
        """
        parts = {part.key: part for part in move_text.MOVE_TEXT_PARTS}
        is_pair = len(words) == 2
        part = parts.get(words[0]) if is_pair else None
        choice = words[1] if is_pair else None

        if part is None or choice not in (ARG_ON, ARG_OFF):
            names = ", ".join(parts)
            usage = MOVETEXT_MSG_USAGE.format(parts=names)
            self.caller.msg((usage, _MSG_SYSTEM))
            return

        shown = choice == ARG_ON
        move_text.set_part_shown(self.caller, part.key, shown)

        state, colour = _MOVETEXT_STATES[shown]
        message = MOVETEXT_MSG_SET.format(
            label=part.label, state=state, colour=colour)
        self.caller.msg((message, _MSG_SYSTEM))

    def _report(self) -> None:
        """
        Purpose: List every part, in the order the room prints them, and
                 whether each one prints on a move.

        Entry:
            No conditions.

        Exit/Returns:
            Returns nothing.

        Module Globals:
            _MOVETEXT_STATES and MOVETEXT_MSG_* read.

        Methodology:
            Reads through move_text.hidden_parts, the same call the look on
            movement makes. Thus, the report cannot disagree with the next
            step.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/22/2026
        """
        hidden = move_text.hidden_parts(self.caller)
        lines = [MOVETEXT_MSG_HEADER]

        for part in move_text.MOVE_TEXT_PARTS:
            state, colour = _MOVETEXT_STATES[part.key not in hidden]
            row = MOVETEXT_MSG_ROW.format(
                key=part.key, state=state, colour=colour, label=part.label)
            lines.append(row)

        lines.append(MOVETEXT_MSG_FOOTER)
        report = "\n".join(lines)
        self.caller.msg((report, _MSG_SYSTEM))


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
        self.add(CmdMovetext())
        self.add(CmdPopup())
