"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Cases for `automap`.

             The command exists because the setting it writes was, for one
             day, reachable only through `py self.db.show_ascii_map = False`.
             So the cases that matter are the ones about being USABLE: that it
             writes the attribute the room actually reads, that it reports
             honestly, and that the unset state stays a third state rather than
             being collapsed the first time somebody asks a question.
"""

from evennia.utils.test_resources import EvenniaCommandTest

from commands import display_cmds
from systems.statefeed import constants as feed_const


class AutomapTests(EvenniaCommandTest):
    """Reporting and setting the area map's automatic printing."""

    def _run(self, argument=""):
        """Run the command and return everything the caller was told."""
        return self.call(display_cmds.CmdAutomap(), argument)

    def test_on_writes_the_attribute_the_room_reads(self):
        """The command is the only writer and the room is the only reader, so
        a disagreement between them is silent and permanent."""
        self._run(display_cmds.ARG_ON)

        self.assertIs(
            self.char1.attributes.get(feed_const.ASCII_MAP_ATTR), True)

    def test_off_writes_it_too(self):
        self._run(display_cmds.ARG_OFF)

        self.assertIs(
            self.char1.attributes.get(feed_const.ASCII_MAP_ATTR), False)

    def test_setting_it_says_so(self):
        """A setting that changes nothing visible has to answer, or the player
        cannot tell a working command from a typo."""
        self.assertIn("off", self._run(display_cmds.ARG_OFF).lower())
        self.assertIn("on", self._run(display_cmds.ARG_ON).lower())

    def test_the_choice_survives_being_read_back(self):
        self._run(display_cmds.ARG_OFF)

        self.assertIn("off", self._run().lower())

    def test_reporting_does_not_pin_an_unset_choice(self):
        """UNSET is a real third state -- "decide from my client" -- and
        collapsing it to a stored value the first time somebody asks would
        silently freeze a player to whatever their client happened to default
        to, including on a client they later stop using."""
        self._run()

        self.assertIsNone(
            self.char1.attributes.get(feed_const.ASCII_MAP_ATTR, default=None))

    def test_an_unset_report_says_it_is_the_default(self):
        """So a player can tell "I chose this" from "this is what I got"."""
        self.assertIn(display_cmds.MSG_DEFAULT_SUFFIX.strip(), self._run())

    def test_a_set_report_does_not(self):
        self._run(display_cmds.ARG_OFF)

        self.assertNotIn(display_cmds.MSG_DEFAULT_SUFFIX.strip(), self._run())

    def test_nonsense_is_answered_with_the_usage(self):
        """And changes nothing. `automap yes` must not be read as `off`."""
        self._run(display_cmds.ARG_ON)
        response = self._run("sideways")

        self.assertIn("Usage", response)
        self.assertIs(
            self.char1.attributes.get(feed_const.ASCII_MAP_ATTR), True)

    def test_it_is_reachable_by_an_ordinary_player(self):
        """The whole point. A Builder lock here would put it back where it
        was -- and `map`, the contrib command, is exactly that lock."""
        self.assertEqual(display_cmds.CmdAutomap.locks, "cmd:all()")

    def test_it_is_in_the_help_index(self):
        """`help automap` is the only route a telnet player has to discover
        this at all, and a command with no help category is not in the index."""
        self.assertTrue(display_cmds.CmdAutomap.help_category)
        self.assertTrue(display_cmds.CmdAutomap.__doc__.strip())

    def test_the_help_names_both_arguments(self):
        """A player reading it must be able to act on it without guessing."""
        text = display_cmds.CmdAutomap.__doc__

        self.assertIn("automap %s" % display_cmds.ARG_ON, text)
        self.assertIn("automap %s" % display_cmds.ARG_OFF, text)
