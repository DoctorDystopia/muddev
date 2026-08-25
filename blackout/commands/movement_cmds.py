"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Movement command overrides.

             Currently one: the xyzgrid contrib's `goto` accepts a target as
             either a room name or an (X,Y) coordinate, but gates the
             coordinate form behind a Builder lock. Blackout un-gates it,
             because a graphical client addresses tiles by coordinate and
             nothing else -- see the click-to-move section of
             web/static/webclient/js/plugins/blackout3d.js.
"""

from evennia.commands.cmdset import CmdSet
from evennia.contrib.grid.xyzgrid.commands import CmdGoto

from systems.tick.constants import TICK_SECONDS


class BlackoutGotoCmd(CmdGoto):
    """
    Go to a named location in this area via the shortest path.

    Usage:
        path <location>      - find shortest path to target location (don't move)
        goto <location>      - auto-move to target location, using shortest path
        path                 - show current target location and shortest path
        goto                 - abort current goto, otherwise show current path
        path clear           - clear current path

    A location may be named, or given as a grid coordinate: `goto (4,7)`.

    Finds the shortest route to a location in your current area and
    can then automatically walk you there.
    """

    # One tile per server tick, down from the contrib's 2 seconds.
    #
    # The tick is the game's own unit of time, and Blackout's combat maths is
    # OSRS-derived -- where one tile per tick IS walking speed. Pacing the
    # auto-walk to anything else invents a second clock for the same world.
    #
    # Derived from TICK_SECONDS rather than written as 0.6, so retuning
    # the tick moves the walk with it.
    #
    # A float is safe here. This is handed to evennia.utils.utils.delay, which
    # is twisted's deferLater and honours sub-second values -- it is NOT the
    # ScriptDB.db_interval integer field that truncates 0.6 to 0 and silently
    # disables a timer. See the comment beside TICK_SECONDS for the
    # trap this is not.
    #
    # This paces AUTO-WALK only. Manual movement -- a typed direction, the
    # WASD hotkeys, a click on an adjacent tile -- is ungated: nothing in
    # Blackout hooks exit traversal, so a player can still outrun their own
    # pathfinder by typing. Throttling that too would mean a gate in
    # Character.at_pre_move, which is a gameplay decision affecting telnet
    # players and has deliberately not been taken here.
    auto_step_delay = TICK_SECONDS

    def _search_by_key_and_alias(self, inp, xyz_start):
        """
        Purpose: Resolve a `goto` target, accepting an (X,Y) coordinate from
            any player rather than from Builders only.

        Entry:
            inp       - the raw target string the player typed.
            xyz_start - the caller's current (X, Y, Z); only Z is read, to
                        confine the search to the map they are standing on.

        Exit/Returns:
            Returns the target room, or None when nothing matches. The parent
            reports the failure to the caller itself, so a None here is already
            explained on screen.

        Module Globals:
            None.

        Methodology:
            The parent's `func` picks between two searches: it calls
            `_search_by_xyz` when the caller passes `perm(Builder)` AND the
            argument looks like a coordinate, and `_search_by_key_and_alias`
            otherwise. So the non-builder path lands HERE with the coordinate
            string intact, and re-dispatching it is the whole override -- four
            lines instead of a copy of the parent's 70-line `func`, which would
            then have to be re-audited on every Evennia upgrade.

            The coordinate test mirrors the parent's exactly, including its
            looseness: a room legitimately named with a bracket and a comma
            would be read as a coordinate here, fail to parse, and report
            "Could not find a room at ...". No such room exists in Blackout,
            and matching the parent's test matters more than improving it --
            a Builder and a player must resolve the same string to the same
            room, or the client's click means two different things depending
            on who clicked.

        Notes/References:
            This grants no reach a player did not already have. The parent's
            own name search runs over `filter_xyz(("*", "*", Z))` -- every room
            on the map, visited or not -- so `goto <room name>` already walks
            anywhere the coordinate form could reach. The lock is about
            coordinates being a builder's vocabulary, not about privileged
            movement, and a graphical client has no vocabulary but coordinates.

            The walk itself is unprivileged either way: `_auto_step` moves the
            player with `caller.execute_cmd(exit_name)`, one ordinary exit
            command at a time, honouring `interrupt_path` map nodes and
            re-pathing if the player walks off-route manually.

        Author: Nick Hobar
        Creation date: 08/14/2026
        """
        looks_like_coords = all(char in inp for char in ("(", ")", ","))

        if looks_like_coords:
            return self._search_by_xyz(inp, xyz_start)

        return super()._search_by_key_and_alias(inp, xyz_start)


class MovementCmdSet(CmdSet):
    """
    Purpose: Wraps the movement overrides for registration on CharacterCmdSet.

    Notes/References:
        Must be added AFTER XYZGridCmdSet in CharacterCmdSet.at_cmdset_creation,
        so BlackoutGotoCmd overloads the contrib's CmdGoto rather than the
        other way round.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """

    key = "MovementCmdSet"

    def at_cmdset_creation(self):
        self.add(BlackoutGotoCmd())
