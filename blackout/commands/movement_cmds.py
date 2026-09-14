"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Movement command overrides.

             Currently one command, with two changes to the xyzgrid contrib's
             `goto`:

             1. It accepts a target as an (X,Y) coordinate from any player,
                where the contrib gates that form behind a Builder lock --
                because a graphical client addresses tiles by coordinate and
                nothing else. See the click-to-move handling in
                godot/world/world_view.gd.
             2. It accepts a command to run on arrival:
                `goto (4,7) then cut rusty pole`. That is what a click on
                something standing on a far tile sends, so the player walks
                over and then acts, rather than being told the pole is not
                here.
"""

from collections import namedtuple

from evennia.commands.cmdset import CmdSet
from evennia.contrib.grid.xyzgrid.commands import CmdGoto

from systems.core.tick.constants import TICK_SECONDS
from systems.interface.statefeed import constants as feed_const

# Public constant definitions

# A command waiting on a walk: the room the walk was started towards, and the
# line to type once the player is standing in it. Kept on `caller.ndb`, beside
# the contrib's own `xy_path_data`, because it lives exactly as long as the
# walk does and must not survive a reload into a walk that no longer exists.
FollowUp = namedtuple("FollowUp", ("target", "command"))


class BlackoutGotoCmd(CmdGoto):
    """
    Go to a named location in this area via the shortest path.

    Usage:
        path <location>      - find shortest path to target location (don't move)
        goto <location>      - auto-move to target location, using shortest path
        goto <location> then <command>
                             - auto-move there, then run <command> on arrival
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

    # The command to run on arrival, split off the argument by `parse`. Empty
    # for a plain walk. A class default, so an instance that never parsed --
    # a test, or a path started by `path` -- reads as having no follow-up.
    follow_up = ""

    def parse(self):
        """
        Purpose: Split `<location> then <command>` into the destination the
            contrib searches for and the command to run on arrival.

        Entry:
            self.args - the raw argument, as the cmdhandler set it.

        Exit/Returns:
            None. Leaves self.args holding the destination alone and
            self.follow_up holding the command, or "" when none was given.

        Module Globals:
            feed_const.GOTO_FOLLOW_UP_SEPARATOR read.

        Methodology:
            Split on the FIRST separator, so a follow-up that itself contains
            " then " arrives intact. Done after the parent's parse, because
            the contrib's `func` reads only self.args -- rewriting that one
            field is what lets the whole search, the Builder dispatch and the
            path display run unmodified on a destination that no longer
            carries a command.

        Notes/References:
            The separator's spaces are part of it: `goto Heathen Market` is a
            room name, not a walk to "Hea" followed by "n Market".

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        super().parse()

        destination, separator, follow_up = self.args.partition(
            feed_const.GOTO_FOLLOW_UP_SEPARATOR)

        if not separator:
            self.follow_up = ""
            return

        self.args = destination.strip()
        self.follow_up = follow_up.strip()

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

    def _auto_step(self, caller, session, target=None, xymap=None,
                   directions=None, step_sequence=None, step=True):
        """
        Purpose: Take one step of the contrib's walk, then run the follow-up
            command if that step was the one that ended the walk at its
            target.

        Entry:
            Exactly the contrib's arguments. `target` is given only on the
            call that STARTS a walk; every later step is the delayed call
            re-entering with none.

        Exit/Returns:
            None.

        Module Globals:
            None.

        Methodology:
            Wraps rather than copies. The contrib's step routine is 130 lines
            with four separate ways for a walk to end -- arrival, a missing
            exit, leaving the grid, an `interrupt_path` node -- and none of
            them calls a hook. So this does not try to tell them apart: after
            the step, a walk with no scheduled next step is OVER, and the only
            question left is whether the player is standing in the room the
            walk was started towards. That one comparison covers all four
            endings, and every ending the contrib grows later.

            The follow-up is bound when the walk starts, so it belongs to that
            walk. A new `goto` -- a click anywhere else -- replaces it along
            with the path, and a search that finds nothing starts no walk and
            so leaves an earlier walk's follow-up alone rather than hijacking
            it. `path` binds none: it shows a route and walks nowhere.

            A target the player is already standing on ends on the first call,
            before any step, so `goto (x,y) then cut` from (x,y) cuts at once.

        Notes/References:
            The follow-up goes through `caller.execute_cmd`, the same route
            the contrib uses for each step. It is exactly what the player
            would have typed on arrival, under every lock and cooldown.

            Arrival is seen one tick after the last step lands, because that
            is when the contrib's own "Target reached." fires. The action is
            therefore paced like walking is: one tick per tile, then the act.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        if target:
            caller.ndb.goto_follow_up = self._follow_up_for(target, step)

        super()._auto_step(
            caller,
            session,
            target=target,
            xymap=xymap,
            directions=directions,
            step_sequence=step_sequence,
            step=step,
        )

        self._run_follow_up_on_arrival(caller, session)

    def _follow_up_for(self, target, step):
        """
        Purpose: The follow-up a walk starting now should carry, if any.

        Entry:
            target - the room the walk is headed for.
            step   - True for `goto`, False for `path`, which walks nowhere.

        Exit/Returns:
            Returns a FollowUp, or None for a plain walk and for `path`.

        Module Globals:
            FollowUp read.

        Methodology:
            None is written even when there is nothing to carry, because the
            walk starting now has replaced whatever walk carried the last one.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        if not step or not self.follow_up:
            return None

        pending = FollowUp(target=target, command=self.follow_up)

        return pending

    def _run_follow_up_on_arrival(self, caller, session):
        """
        Purpose: Run the walk's follow-up if the walk has ended where it was
            headed, and drop it if it ended anywhere else.

        Entry:
            caller  - the walking character.
            session - the session the walk was started from.

        Exit/Returns:
            None.

        Module Globals:
            None.

        Methodology:
            Cleared BEFORE it runs, so a follow-up that is itself a `goto`
            binds its own follow-up onto a clean slate rather than having it
            wiped by this routine on the way out.

        Notes/References:
            An NPC that walked off the tile while the player walked on is not
            chased: the follow-up runs, finds nothing named that, and says so,
            as the same typed command would.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        pending = caller.ndb.goto_follow_up

        if pending is None:
            return

        walking = _walk_in_progress(caller)

        if walking:
            return

        caller.ndb.goto_follow_up = None
        arrived = caller.location == pending.target

        if not arrived:
            return

        caller.execute_cmd(pending.command, session=session)


def _walk_in_progress(caller):
    """
    Purpose: Whether the contrib has a next step of a walk scheduled.

    Entry:
        caller - a character, walking or not.

    Exit/Returns:
        Returns True while another step is pending, False otherwise.

    Module Globals:
        None.

    Methodology:
        The contrib signals the end of a walk three different ways: clearing
        `xy_path_data`, leaving it with no task, or -- after an
        `interrupt_path` node -- leaving it holding the task that is running
        RIGHT NOW. That last one reads as finished too, because a
        TaskHandler task reports `active()` only until its deferred has been
        called, and the deferred is called before the callback runs.

    Notes/References:
        evennia/scripts/taskhandler.py, TaskHandler.active and .add.

    Author: Nick Hobar
    Creation date: 09/13/2026
    """
    path_data = caller.ndb.xy_path_data

    if not path_data or not path_data.task:
        return False

    running = path_data.task.active()

    return running


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
