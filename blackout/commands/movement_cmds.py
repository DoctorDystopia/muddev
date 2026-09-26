"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: The movement command set: `goto`, the direction commands, and
             `tiletp`. All three move on the tile world. The rules live in
             commands/tile_movement.py.

             `goto` was an override of the `goto` of the xyzgrid contrib until
             DESIGN-0011 Phase 4b (09/25/2026). Two of its changes stay:

             1. It accepts a target as an (X,Y) coordinate from any player,
                because a graphical client addresses tiles by coordinate and
                nothing else.
             2. It accepts a command to run on arrival:
                `goto (4,7) then cut rusty pole`. That is what a click on
                something standing on a far tile sends, so the player walks
                over and then acts.

             The contrib `path` command went with the contrib cmdset. The
             tile world has no path display.
"""

from evennia.commands.cmdset import CmdSet
from evennia.commands.command import Command

from systems.interface.statefeed import constants as feed_const

from . import tile_movement


class BlackoutGotoCmd(Command):
    """
    Walk to a place via the shortest path.

    Usage:
        goto <place>                - walk there, one tile each tick
        goto (x,y)                  - walk to a tile
        goto <place> then <command> - walk there, then run <command>
        goto                        - stop the walk in progress

    A place is the name of a thing that stands on a tile near you, for
    example `goto bank`.
    """

    key = "goto"
    locks = "cmd:all()"
    help_category = "General"

    # The command to run on arrival, split off the argument by `parse`. Empty
    # for a plain walk. A class default, so an instance that never parsed
    # reads as having no follow-up.
    follow_up = ""

    def parse(self):
        """
        Purpose: Split `<place> then <command>` into the destination and the
            command to run on arrival.

        Entry:
            self.args - the raw argument, as the cmdhandler set it.

        Exit/Returns:
            None. Leaves self.args holding the destination alone and
            self.follow_up holding the command, or "" when none was given.

        Module Globals:
            feed_const.GOTO_FOLLOW_UP_SEPARATOR read.

        Methodology:
            Split on the FIRST separator, so a follow-up that itself contains
            " then " arrives intact.

        Notes/References:
            The separator's spaces are part of it: `goto Heathen Market` is a
            place name, not a walk to "Hea" followed by "n Market".

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        raw = self.args.strip()
        destination, separator, follow_up = raw.partition(
            feed_const.GOTO_FOLLOW_UP_SEPARATOR)

        if not separator:
            self.args = raw
            self.follow_up = ""
            return

        self.args = destination.strip()
        self.follow_up = follow_up.strip()

    def func(self):
        """Walk on the tile world. See tile_movement.run_goto."""
        tile_movement.run_goto(self.caller, self.args, self.follow_up,
                               self.session)


class MovementCmdSet(CmdSet):
    """
    Purpose: Wraps the movement commands for registration on CharacterCmdSet.

    Notes/References:
        A tile room has no exit objects. The direction commands here take
        their place (commands/tile_movement.py).

    Author: Nick Hobar
    Creation date: 08/14/2026
    """

    key = "MovementCmdSet"

    def at_cmdset_creation(self):
        self.add(BlackoutGotoCmd())

        for command_class in tile_movement.TILE_DIRECTION_COMMANDS:
            self.add(command_class())

        self.add(tile_movement.CmdTileTeleport())
