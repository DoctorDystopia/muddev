"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Tests for BlackoutGotoCmd. `goto <place> then <command>` splits
             into the walk and the command at its end. The command gives both
             parts to the tile world walk.

             The walk itself is tested in commands/tests/test_tile_movement.py.

Run with:
    evennia test --settings test_settings.py commands.tests.test_movement_cmds
"""

import unittest
from unittest import mock

from commands.movement_cmds import BlackoutGotoCmd, MovementCmdSet
from systems.interface.statefeed import constants as feed_const

# Public constant definitions

COORD_ARGUMENT = "(4,7)"
FOLLOW_UP = "cut rusty pole"


def _parsed(args):
    """Build a goto command as the cmdhandler would, and parse `args`."""
    command = BlackoutGotoCmd()
    command.cmdstring = feed_const.TILE_COMMAND_GOTO
    command.args = args
    command.parse()

    return command


class TestGotoFollowUpParsing(unittest.TestCase):
    """
    Purpose: `then` splits a walk from the command at its end. A client
    builds a string from ENTITY_APPROACH_TEMPLATE, and the parse gives back
    its two parts.

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

    def test_a_place_name_containing_then_is_not_split(self):
        command = _parsed(" Heathen Market")

        self.assertEqual(command.args, "Heathen Market")
        self.assertEqual(command.follow_up, "")

    def test_only_the_first_separator_splits(self):
        separator = feed_const.GOTO_FOLLOW_UP_SEPARATOR
        follow_up = "say left" + separator + "right"

        command = _parsed(" " + COORD_ARGUMENT + separator + follow_up)

        self.assertEqual(command.args, COORD_ARGUMENT)
        self.assertEqual(command.follow_up, follow_up)

    def test_a_bare_goto_is_an_empty_target(self):
        command = _parsed("")

        self.assertEqual(command.args, "")
        self.assertEqual(command.follow_up, "")


class TestGotoRunsTheTileWalk(unittest.TestCase):
    """The command hands the parsed parts to the tile world walk."""

    def test_func_calls_run_goto_with_both_parts(self):
        command = _parsed(" " + COORD_ARGUMENT
                          + feed_const.GOTO_FOLLOW_UP_SEPARATOR + FOLLOW_UP)
        command.caller = mock.Mock()
        command.session = mock.Mock()

        with mock.patch("commands.movement_cmds.tile_movement.run_goto") as run:
            command.func()

        run.assert_called_once_with(command.caller, COORD_ARGUMENT, FOLLOW_UP,
                                    command.session)

    def test_the_cmdset_holds_goto_and_every_direction(self):
        cmdset = MovementCmdSet()
        cmdset.at_cmdset_creation()
        keys = {command.key for command in cmdset.commands}

        self.assertIn("goto", keys)
        self.assertIn("north", keys)
        self.assertIn("tiletp", keys)
