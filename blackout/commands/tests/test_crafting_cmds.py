"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/12/2026
Description: Tests for `toggle craft confirm`.

             The claim worth pinning is WHERE it lives. It moved off the
             workbench onto the character so the Godot Options button works
             from any room; a regression putting it back on CraftCmdSet would
             pass every test that runs the command directly and fail only for
             a player standing somewhere else.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \
        commands.tests.test_crafting_cmds
"""

import unittest

from evennia.utils.test_resources import EvenniaCommandTest

from commands.crafting_cmds import CmdToggleCraftConfirm
from commands.default_cmdsets import CharacterCmdSet


class TestToggleCraftConfirm(EvenniaCommandTest):
    """What the toggle writes and what it says."""

    def _run(self):
        """Run the command and return everything the caller was told."""
        return self.call(CmdToggleCraftConfirm(), "")

    def test_first_toggle_turns_the_default_off(self):
        """Unset means on, so the first toggle has to land on off."""
        response = self._run()

        self.assertIs(self.char1.db.craft_confirm, False)
        self.assertIn("off", response.lower())

    def test_second_toggle_turns_it_back_on(self):
        self._run()
        response = self._run()

        self.assertIs(self.char1.db.craft_confirm, True)
        self.assertIn("on", response.lower())


class TestToggleCraftConfirmIsReachable(unittest.TestCase):
    """The toggle rides the character, not a facility."""

    def test_the_character_cmdset_carries_it(self):
        cmdset = CharacterCmdSet()
        keys = [command.key for command in cmdset.commands]

        self.assertIn(CmdToggleCraftConfirm.key, keys)
