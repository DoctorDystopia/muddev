"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Tests for BlackoutGotoCmd -- a non-builder must be able to name a
             `goto` target by grid coordinate, because that is the only name
             the 3D pane has for a room.

Run with:
    evennia test --settings settings.py commands.tests.test_movement_cmds
"""

import unittest
from unittest import mock

from evennia.contrib.grid.xyzgrid.commands import CmdGoto

from commands.movement_cmds import BlackoutGotoCmd
from systems.tick.constants import TICK_SECONDS

# Public constant definitions

COORD_ARGUMENT = "(4,7)"
NAME_ARGUMENT = "Bank"
START_XYZ = ("2", "3", "oasis")
FOUND_ROOM = object()


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
