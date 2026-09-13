"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: `read` -- the words on a thing, as opposed to the look of it.

             Not an alias for `look`, and the distinction is what makes the
             command worth having. A sign's DESC is what the object looks like;
             its `world_label` is what is written on it, capped because a
             graphical client draws it floating in the world. `read` is the one
             command that leads with the words.

             It also exists so a client has something to send. `Sign` publishes
             `read <key>` through `extra_actions`, which is what puts a Read row
             in the Godot pane's right-click menu -- and that string is a
             complete command a telnet player could type, which is the
             invariant that keeps a graphical client from doing anything a text
             one cannot.

             WHAT IS READABLE IS THE OBJECT'S OWN ANSWER. The command asks for
             an `is_readable` attribute rather than testing a typeclass, so a
             datapad, a terminal or a scrawled wall becomes readable by
             declaring one attribute and needs no edit here. A command that
             knew about signs would be wrong the first time something else had
             something to say.
"""

from commands.command import Command
from commands.constants import HELP_CATEGORY_GENERAL
from evennia import CmdSet
from systems.interface.statefeed import constants as feed_const

# Reading is looking at something, so the line routes to the tab a `look`
# already lands in rather than growing a message type of its own. The SERVER
# says what a line IS; the client decides which tab shows it.
_MSG_LOOK = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_LOOK}

# The attribute an object declares to say it carries words. Read through
# getattr, so nothing here imports the typeclass layer.
_READABLE_ATTR: str = "is_readable"

_HEADER_TEMPLATE: str = "{name} reads:"
_INDENT: str = "  "

_MSG_READ_WHAT: str = "Read what?"
_MSG_NOTHING_WRITTEN: str = "There is nothing written on {name}."
_MSG_BLANK: str = "{name} is blank."


class CmdRead(Command):
    """
    Read what is written on something.

    Usage:
      read <object>

    Signs, notices and anything else carrying words. What the object LOOKS
    like is `look`; this is what it says.
    """
    key = "read"
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_GENERAL


    def func(self) -> None:
        """
        Purpose: Say what is written on the named object.

        Entry:
            self.caller is a character. self.args names something in the room
            or in their hands.

        Exit/Returns:
            No conditions. Messages the caller in every branch.

        Module Globals:
            _MSG_LOOK, _READABLE_ATTR, _MSG_READ_WHAT, _MSG_NOTHING_WRITTEN
            and _MSG_BLANK read.

        Methodology:
            `caller.search` covers the room and the caller's own contents and
            messages its own failure, so a missing target needs no branch here
            -- and a player reading a notice they are carrying works for free.

            An object that is not readable is told apart from one that is
            readable and blank. Both are "no words", and a player deserves to
            know which: the first is the wrong target, the second is a sign
            nobody has written on.

        Notes/References:
            The verb reaches a graphical client through Sign.extra_actions.

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        caller = self.caller
        wanted = self.args.strip()

        if not wanted:
            caller.msg((_MSG_READ_WHAT, _MSG_LOOK))

            return

        target = caller.search(wanted)

        if target is None:
            return

        if not getattr(target, _READABLE_ATTR, False):
            caller.msg(
                (_MSG_NOTHING_WRITTEN.format(name=target.key), _MSG_LOOK))

            return

        caller.msg((self._reading_of(target), _MSG_LOOK))


    # ─── Private helper routines ─────────────────────────────────────────────

    def _reading_of(self, target) -> str:
        """
        Purpose: Lay out one readable object's words and its appearance.

        Entry:
            target - an object whose `is_readable` is true.

        Exit/Returns:
            Returns the whole message as one string.

        Module Globals:
            _HEADER_TEMPLATE, _INDENT and _MSG_BLANK read.

        Methodology:
            The WORDS lead and the description follows, which is the only
            thing separating this from `look`. Each line of the label is
            indented rather than run together: the label is authored with its
            line breaks meaning something -- a graphical client draws them --
            and flattening them here would make the two clients disagree about
            what the sign says.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        label = getattr(target, "world_label", "")

        if not label:
            return _MSG_BLANK.format(name=target.key)

        lines = [_HEADER_TEMPLATE.format(name=target.key)]

        for line in label.splitlines():
            lines.append(_INDENT + line)

        described = target.db.desc

        if described:
            lines.append("")
            lines.append(described)

        return "\n".join(lines)


class ReadCmdSet(CmdSet):
    """
    Purpose: The `read` command.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        Hangs on the CHARACTER rather than on readable objects. A cmdset on
        the object cannot outlive the object -- the lesson GatheringNode
        records in full, where a harvest consuming the node took its verbs
        with it -- and a sign is more likely to be destroyed by a map rebuild
        than anything else in the game.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    key = "ReadCmdSet"


    def at_cmdset_creation(self) -> None:
        """
        Purpose: Populate the cmdset.

        Entry:
            No conditions.

        Exit/Returns:
            No conditions.

        Module Globals:
            None.

        Methodology:
            One add.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        self.add(CmdRead())
