"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: `write` -- a player leaving words in the world.

             Thin on purpose. Every rule about who may write, what may be
             written, what it costs and how long it lasts lives in
             systems/gameplay/graffiti/, and this module's whole job is to
             turn a typed line into one service call and put the answer on the
             screen.

             That split is not tidiness. The same effects are reached by the
             hourly sweep and by the moderator's Erase row, neither of which
             has a command, a session or a caller to message -- so an effect
             implemented here would have to be re-implemented twice. It is the
             same arrangement CmdEgg has with systems/devtools/actions.py.

             There is no `erase` for players. Painting over someone else's
             scrawl is a real thing to want and a bigger design than a verb:
             it needs to not become griefing, which means rules about who may
             erase what, and none of those have been decided. A scrawl
             currently goes when it expires or when a moderator takes it.
"""

from commands.command import Command
from commands.constants import HELP_CATEGORY_GENERAL
from evennia import CmdSet
from systems.gameplay.graffiti import constants as graffiti_constants
from systems.gameplay.graffiti import service as graffiti_service
from systems.interface.statefeed import constants as feed_const

# Writing on a wall is a thing you do with an object out of your bag, and the
# line telling you how much paint is left is an inventory line. The SERVER says
# what a line IS; the client decides which tab shows it.
_MSG_INVENTORY = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_INVENTORY}


class CmdWrite(Command):
    """
    Write on the world, if you have something to write with.

    Usage:
      write <text>

    Needs a spray can or similar in your inventory, and spends one charge of
    it. What you write is short, stripped of colour codes and visible to
    everyone who comes past -- under your name, to anyone with the authority
    to ask.

    It does not last forever.
    """
    key = "write"
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_GENERAL


    def func(self) -> None:
        """
        Purpose: Turn a typed line into one write, and report the outcome.

        Entry:
            self.caller is a character. self.args is what they want written.

        Exit/Returns:
            No conditions. Messages the caller in every branch, including
            every refusal -- a silent no is a player who reports the command
            as broken.

        Module Globals:
            _MSG_INVENTORY and graffiti_constants.MSG_WRITE_WHAT read.

        Methodology:
            One branch and one call. The empty-argument case is handled here
            rather than in the service because it is not a rule about
            graffiti: it is a usage error, and a service told to write nothing
            should be answering about the text rather than about how the text
            arrived.

            The service's own message is passed through verbatim rather than
            re-worded per branch. There are six ways a write is refused and
            the service knows which; a command re-deriving that from a bare
            False would be a second copy of the rules.

        Notes/References:
            systems/gameplay/graffiti/service.py write() owns the rest.

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        caller = self.caller
        typed = self.args.strip()

        if not typed:
            caller.msg((graffiti_constants.MSG_WRITE_WHAT, _MSG_INVENTORY))

            return

        _succeeded, message = graffiti_service.write(caller, typed)

        caller.msg((message, _MSG_INVENTORY))


class GraffitiCmdSet(CmdSet):
    """
    Purpose: The player-writing command.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        `cmd:all()`, because the medium is the gate. A permission lock would
        be a second answer to "may this player write", and the first one --
        do they have a can with paint in it -- is the one the economy can
        actually tune.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    key = "GraffitiCmdSet"


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
        self.add(CmdWrite())
