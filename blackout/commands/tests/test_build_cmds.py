"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for the builder commands that put words into the world.

             The claim worth a test is not that a sign is created -- that is
             one call -- but HOW. `create_object(location=...)` does not fire
             the room's at_object_receive, and that hook is what publishes an
             arrival to the statefeed, so a sign made the obvious way is
             invisible to every client already standing in the room until it
             next moves. CLAUDE.md lists this as gotcha 5 and it is silent both
             ways: the object exists, `look` finds it, and only the 3D pane is
             wrong.

             The rest is parsing, where the failures are quiet rather than
             loud: a sign reading `Fuel = Credits` losing half its text, or a
             label that normalised to nothing being stood up as a blank post.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \
        commands.tests.test_build_cmds
"""

from evennia.utils.test_resources import EvenniaCommandTest

from commands.build_cmds import CmdMarker, CmdSign
from systems.interface.statefeed import constants as const
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.signs import Marker, Sign


class TestSignCommand(EvenniaCommandTest):
    """
    Purpose: What `sign` stands up, and where.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        EvenniaCommandTest, because `self.call` is the whole point -- these
        assert what a builder typing the command actually gets, not what the
        helper routines return.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """

    character_typeclass = BlackoutCharacter


    def _signs_here(self, typeclass=Sign):
        found = []

        for obj in self.room1.contents:
            if isinstance(obj, typeclass):
                found.append(obj)

        return found


    def test_a_sign_is_stood_up_where_the_builder_is_standing(self):
        self.call(CmdSign(), "TRADE TOWN", caller=self.char1)

        made = self._signs_here()

        self.assertEqual(len(made), 1)
        self.assertEqual(made[0].location, self.room1)
        self.assertEqual(made[0].world_label, "TRADE TOWN")


    def test_it_arrives_through_the_hook_that_publishes_it(self):
        # The gotcha this command is shaped around. `create_object(location=)`
        # skips at_object_receive, so the feed never hears about the sign and
        # no client already in the room draws it. Moving in is what fires the
        # hook -- and a sign whose home is None would go to DEFAULT_HOME the
        # first time anything cleared the room, so the move has to have stuck.
        self.call(CmdSign(), "TRADE TOWN", caller=self.char1)

        made = self._signs_here()[0]

        self.assertEqual(made.location, self.room1)
        self.assertIn(made, self.room1.contents)


    def test_the_label_is_cleaned_once_on_the_way_in(self):
        self.call(CmdSign(), "|rKEEP    OUT|n", caller=self.char1)

        made = self._signs_here()[0]

        self.assertEqual(made.db.world_label, "KEEP OUT")


    def test_a_name_may_be_given_ahead_of_the_text(self):
        self.call(CmdSign(), "north post = TRADE TOWN", caller=self.char1)

        made = self._signs_here()[0]

        self.assertEqual(made.key, "north post")
        self.assertEqual(made.world_label, "TRADE TOWN")


    def test_only_the_first_separator_splits_the_line(self):
        # A sign reading `Fuel = Credits` is a reasonable thing to want, and
        # splitting on every separator would silently eat half of it.
        self.call(CmdSign(), "board = Fuel = Credits", caller=self.char1)

        made = self._signs_here()[0]

        self.assertEqual(made.key, "board")
        self.assertEqual(made.world_label, "Fuel = Credits")


    def test_an_unnamed_sign_is_called_what_it_says(self):
        # The key is what `look` and `destroy` match on, so it should be the
        # thing a builder would actually type.
        self.call(CmdSign(), "TRADE TOWN", caller=self.char1)

        made = self._signs_here()[0]

        self.assertEqual(made.key, "TRADE TOWN")


    def test_a_label_that_normalises_to_nothing_is_refused(self):
        response = self.call(CmdSign(), "|n|n", caller=self.char1)

        self.assertEqual(self._signs_here(), [])
        self.assertIn("nothing to read", response.lower())


    def test_a_bare_invocation_reports_what_is_labelled_here(self):
        self.call(CmdSign(), "TRADE TOWN", caller=self.char1)

        response = self.call(CmdSign(), "", caller=self.char1)

        self.assertIn("trade town", response.lower())


    def test_a_bare_invocation_in_an_unlabelled_room_says_so(self):
        response = self.call(CmdSign(), "", caller=self.char1)

        self.assertIn("nothing here is labelled", response.lower())


    def test_the_marker_command_stands_up_a_marker(self):
        # One attribute's worth of difference, and it is the one that stops a
        # developer's note being read as worldbuilding.
        self.call(CmdMarker(), "WIP -- no spawns", caller=self.char1)

        made = self._signs_here(typeclass=Marker)

        self.assertEqual(len(made), 1)
        self.assertEqual(made[0].label_kind, const.LABEL_KIND_MARKER)
