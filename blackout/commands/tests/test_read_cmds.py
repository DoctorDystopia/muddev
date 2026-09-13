"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for `read` -- the words on a thing, not the look of it.

             Two claims worth pinning.

             IT IS NOT A SECOND `look`. The command exists because a sign's
             desc and its words are different facts, and the test that keeps
             them different is the one asserting the words come FIRST and that
             an object with no words says so rather than falling back to its
             description.

             WHAT IS READABLE IS THE OBJECT'S OWN ANSWER. `read` asks for an
             `is_readable` attribute rather than testing a typeclass, so the
             check that matters is a plain object being refused and anything
             declaring the attribute being served -- no typeclass mentioned
             either way.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \
        commands.tests.test_read_cmds
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from commands.read_cmds import CmdRead
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.signs import Sign


class TestReadCommand(EvenniaCommandTest):
    """
    Purpose: What `read` says, and what it refuses.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        EvenniaCommandTest, because the assertions are about the lines a
        player actually sees.

        Asserted on KEYWORDS rather than whole sentences, so a copy edit to
        the message templates does not fail a test about the command's
        behaviour.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """

    character_typeclass = BlackoutCharacter


    def _sign(self, text="NO ENTRY"):
        made = create_object(Sign, key="signpost", location=None)

        if text:
            made.world_label = text

        made.move_to(self.room1, quiet=True, move_type="teleport")

        return made


    def test_the_words_are_what_it_reports(self):
        self._sign("NO ENTRY")

        response = self.call(CmdRead(), "signpost", caller=self.char1)

        self.assertIn("NO ENTRY", response)


    def test_the_words_come_before_the_description(self):
        # The whole difference between this and `look`. A sign's desc is what
        # the post looks like; its label is what it says.
        sign = self._sign("NO ENTRY")
        sign.db.desc = "A board on a post."

        response = self.call(CmdRead(), "signpost", caller=self.char1)

        self.assertLess(
            response.index("NO ENTRY"), response.index("A board on a post."))


    def test_every_authored_line_survives(self):
        # A graphical client draws the line breaks, so a text client flattening
        # them would make the two disagree about what the sign says.
        self._sign("OASIS\nBANK: EAST")

        response = self.call(CmdRead(), "signpost", caller=self.char1)

        self.assertIn("OASIS", response)
        self.assertIn("BANK: EAST", response)


    def test_something_with_nothing_written_on_it_is_refused(self):
        create_object(key="a rock", location=self.room1)

        response = self.call(CmdRead(), "rock", caller=self.char1)

        self.assertIn("nothing written", response.lower())


    def test_a_readable_thing_that_is_blank_says_so_instead(self):
        # Told APART from the refusal above. Both are "no words", and which
        # one it is decides whether the player has the wrong target or the
        # builder has unfinished work.
        self._sign(text="")

        response = self.call(CmdRead(), "signpost", caller=self.char1)

        self.assertIn("blank", response.lower())


    def test_a_carried_notice_can_be_read(self):
        # caller.search covers the caller's own contents, so this works with no
        # branch of its own -- worth a test precisely because it is free and
        # would be silently lost by a switch to a location-only search.
        notice = create_object(Sign, key="notice", location=None)
        notice.world_label = "REWARD"
        notice.move_to(self.char1, quiet=True, move_type="teleport")

        response = self.call(CmdRead(), "notice", caller=self.char1)

        self.assertIn("REWARD", response)


    def test_reading_nothing_asks_what(self):
        response = self.call(CmdRead(), "", caller=self.char1)

        self.assertIn("read what", response.lower())
