"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/13/2026
Description: Cases for `stats`, the full records sheet.

             The sheet's layout is RecordsPanel's and is tested there; these
             only guard that the command reaches it for the caller.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        commands.tests.test_stats_cmd
"""

from evennia.utils.test_resources import EvenniaCommandTest

from commands import progression_cmds
from systems.core.stat_tracker import constants as stat_constants
from systems.interface.summary.panel_defs import records
from typeclasses.characters import Character as BlackoutCharacter


class StatsCommandTests(EvenniaCommandTest):
    """`stats` prints the caller's own sheet."""

    character_typeclass = BlackoutCharacter

    def test_a_fresh_character_is_told_nothing_is_recorded(self):
        response = self.call(progression_cmds.CmdStats(), "")

        self.assertIn(records.EMPTY_SHEET_TEXT.lower(), response.lower())

    def test_a_recorded_kill_is_named(self):
        self.char1.stats.increment(stat_constants.KILLS_PER_HOSTILE_STAT_KEY, "mutant_raider")

        response = self.call(progression_cmds.CmdStats(), "")

        self.assertIn("mutant raider", response.lower())
