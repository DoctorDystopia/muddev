"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Tests for BlackoutGotoCmd -- a non-builder must be able to name a
             `goto` target by grid coordinate, because that is the only name
             the 3D pane has for a room.

             Also that `goto <location> then <command>` runs the command when,
             and only when, the walk ends where it was headed.

Run with:
    evennia test --settings test_settings.py commands.tests.test_movement_cmds
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from evennia.contrib.grid.xyzgrid.commands import CmdGoto

from commands.movement_cmds import BlackoutGotoCmd, FollowUp
from systems.core.tick.constants import TICK_SECONDS
from systems.interface.statefeed import constants as feed_const

# Public constant definitions

COORD_ARGUMENT = "(4,7)"
NAME_ARGUMENT = "Bank"
START_XYZ = ("2", "3", "oasis")
FOUND_ROOM = object()

FOLLOW_UP = "cut rusty pole"
TARGET_ROOM = object()
OTHER_ROOM = object()
SESSION = object()


def _parsed(args):
    """Build a goto command as the cmdhandler would, and parse `args`."""
    command = BlackoutGotoCmd()
    command.cmdstring = feed_const.TILE_COMMAND_GOTO
    command.args = args
    command.parse()

    return command


def _caller(location):
    """A stand-in character: ndb slots, a location, and a command recorder."""
    ndb = SimpleNamespace(xy_path_data=None, goto_follow_up=None)

    return SimpleNamespace(ndb=ndb, location=location, execute_cmd=mock.Mock())


def _still_walking(caller):
    """A contrib step that scheduled another step after itself."""
    task = mock.Mock()
    task.active.return_value = True
    caller.ndb.xy_path_data = SimpleNamespace(task=task)


def _walk_ended(caller):
    """A contrib step that found nothing left to walk and cleared the path."""
    caller.ndb.xy_path_data = None


class TestBlackoutGotoTargetSearch(unittest.TestCase):
    """
    Purpose: Pin the one behaviour the override exists for -- the dispatch
    inside _search_by_key_and_alias, which is where the parent's `func` sends
    every caller who does not hold perm(Builder).

    Both searches are patched out. What is under test is which one is reached
    for a given argument, not what either of them finds; finding is the
    contrib's job and the contrib tests it.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """

    def test_coordinate_argument_reaches_the_xyz_search(self):
        command = BlackoutGotoCmd()

        with mock.patch.object(
            BlackoutGotoCmd, "_search_by_xyz", return_value=FOUND_ROOM
        ) as by_xyz:
            found = command._search_by_key_and_alias(COORD_ARGUMENT, START_XYZ)

        by_xyz.assert_called_once_with(COORD_ARGUMENT, START_XYZ)
        self.assertIs(found, FOUND_ROOM)

    def test_name_argument_still_reaches_the_name_search(self):
        command = BlackoutGotoCmd()

        with mock.patch.object(
            CmdGoto, "_search_by_key_and_alias", return_value=FOUND_ROOM
        ) as by_name:
            found = command._search_by_key_and_alias(NAME_ARGUMENT, START_XYZ)

        by_name.assert_called_once_with(NAME_ARGUMENT, START_XYZ)
        self.assertIs(found, FOUND_ROOM)

    def test_partial_coordinate_syntax_is_treated_as_a_name(self):
        """
        A bracket alone is not a coordinate. This mirrors the parent's own
        test, which requires all three of "(", ")" and "," -- the two must
        agree, or a Builder and a player resolve the same string differently.
        """
        command = BlackoutGotoCmd()

        with mock.patch.object(
            CmdGoto, "_search_by_key_and_alias", return_value=FOUND_ROOM
        ) as by_name:
            command._search_by_key_and_alias("(4", START_XYZ)

        by_name.assert_called_once()


class TestBlackoutGotoPacing(unittest.TestCase):
    """
    Purpose: The auto-walk steps on the server's own tick.

    The value matters less than where it comes from: written as a literal it
    would drift the moment the tick is retuned, leaving the world running on
    two clocks. This test fails if someone replaces the derivation with 0.6.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """

    def test_one_tile_per_server_tick(self):
        self.assertEqual(BlackoutGotoCmd.auto_step_delay, TICK_SECONDS)

    def test_the_contrib_default_is_actually_overridden(self):
        # Guards against the attribute being renamed upstream, which would
        # leave the override inert and the walk silently back at 2 seconds.
        self.assertNotEqual(
            BlackoutGotoCmd.auto_step_delay, CmdGoto.auto_step_delay)

    def test_a_sub_second_delay_survives_as_a_float(self):
        # delay() is twisted's deferLater, not ScriptDB.db_interval -- an int
        # here would truncate to 0 and step the whole path instantly.
        self.assertIsInstance(BlackoutGotoCmd.auto_step_delay, float)


class TestGotoFollowUpParsing(unittest.TestCase):
    """
    Purpose: `then` splits a walk from the command run at its end, and the
    string a client builds from ENTITY_APPROACH_TEMPLATE parses back into the
    two parts it was built from.

    Author: Nick Hobar
    Creation date: 09/13/2026
    """

    def test_the_approach_template_parses_back_into_its_parts(self):
        # Derived from the template rather than typed, so a changed separator
        # or coordinate syntax is caught here instead of at a player's click.
        sent = feed_const.ENTITY_APPROACH_TEMPLATE.format(
            x=4, y=7, command=FOLLOW_UP)
        walk = feed_const.TILE_COMMAND_GOTO_TEMPLATE.format(x=4, y=7)
        verb = feed_const.TILE_COMMAND_GOTO

        command = _parsed(sent[len(verb):])

        self.assertEqual(command.args, walk[len(verb):].strip())
        self.assertEqual(command.follow_up, FOLLOW_UP)

    def test_a_plain_walk_carries_no_follow_up(self):
        command = _parsed(" " + COORD_ARGUMENT)

        self.assertEqual(command.args, COORD_ARGUMENT)
        self.assertEqual(command.follow_up, "")

    def test_a_room_name_containing_then_is_not_split(self):
        command = _parsed(" Heathen Market")

        self.assertEqual(command.args, "Heathen Market")
        self.assertEqual(command.follow_up, "")

    def test_only_the_first_separator_splits(self):
        separator = feed_const.GOTO_FOLLOW_UP_SEPARATOR
        follow_up = "say left" + separator + "right"

        command = _parsed(" " + COORD_ARGUMENT + separator + follow_up)

        self.assertEqual(command.args, COORD_ARGUMENT)
        self.assertEqual(command.follow_up, follow_up)


class TestGotoFollowUpOnArrival(unittest.TestCase):
    """
    Purpose: The follow-up runs once the walk ends in its target room, and
    never anywhere else.

    The contrib's step is patched out; each test scripts what that step did
    to the path. What is under test is the decision made after it, which is
    the whole of the override.

    Author: Nick Hobar
    Creation date: 09/13/2026
    """

    def _step(self, command, caller, effect, **kwargs):
        with mock.patch.object(
                CmdGoto, "_auto_step", side_effect=lambda *a, **k: effect(caller)):
            command._auto_step(caller, SESSION, **kwargs)

    def test_it_waits_for_the_walk_then_runs_on_arrival(self):
        caller = _caller(OTHER_ROOM)
        command = _parsed(" " + COORD_ARGUMENT + " then " + FOLLOW_UP)

        self._step(command, caller, _still_walking, target=TARGET_ROOM)
        caller.execute_cmd.assert_not_called()

        caller.location = TARGET_ROOM
        self._step(command, caller, _walk_ended)

        caller.execute_cmd.assert_called_once_with(FOLLOW_UP, session=SESSION)
        self.assertIsNone(caller.ndb.goto_follow_up)

    def test_already_standing_there_runs_it_at_once(self):
        caller = _caller(TARGET_ROOM)
        command = _parsed(" " + COORD_ARGUMENT + " then " + FOLLOW_UP)

        self._step(command, caller, _walk_ended, target=TARGET_ROOM)

        caller.execute_cmd.assert_called_once_with(FOLLOW_UP, session=SESSION)

    def test_a_walk_that_stops_short_drops_it(self):
        # An interrupt node, a missing exit, leaving the grid: every early
        # ending leaves the player somewhere other than the target.
        caller = _caller(OTHER_ROOM)
        command = _parsed(" " + COORD_ARGUMENT + " then " + FOLLOW_UP)

        self._step(command, caller, _walk_ended, target=TARGET_ROOM)

        caller.execute_cmd.assert_not_called()
        self.assertIsNone(caller.ndb.goto_follow_up)

    def test_a_new_plain_walk_replaces_it(self):
        caller = _caller(OTHER_ROOM)
        caller.ndb.goto_follow_up = FollowUp(TARGET_ROOM, FOLLOW_UP)
        command = _parsed(" " + COORD_ARGUMENT)

        self._step(command, caller, _still_walking, target=OTHER_ROOM)

        self.assertIsNone(caller.ndb.goto_follow_up)

    def test_path_never_runs_it(self):
        # `path` shows a route and walks nowhere, so there is no arrival.
        caller = _caller(TARGET_ROOM)
        command = _parsed(" " + COORD_ARGUMENT + " then " + FOLLOW_UP)

        self._step(command, caller, _walk_ended, target=TARGET_ROOM, step=False)

        caller.execute_cmd.assert_not_called()
