"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Cases for statefeed.text, which reads a tagged `text` message
             back apart.

             Plain unittest.TestCase: the module touches no database, no
             session and no typeclass, and EvenniaTest would build two accounts
             and a script per method to test two pure functions.
"""

import unittest

from .. import constants as const
from .. import text


class LineOfTests(unittest.TestCase):
    """The prose comes back whichever shape carried it."""

    def test_a_bare_string_is_itself(self):
        """Half of Evennia's own output is still untagged."""
        self.assertEqual(text.line_of("You cannot go that way."),
                         "You cannot go that way.")

    def test_a_tagged_pair_yields_its_prose(self):
        sent = ("You hit the raider.",
                {const.MESSAGE_TYPE_KEY: const.MESSAGE_TYPE_COMBAT})

        self.assertEqual(text.line_of(sent), "You hit the raider.")

    def test_a_list_is_read_like_a_tuple(self):
        """JSON round-trips a tuple into a list, and a test double may hand
        one over; neither is worth a different answer."""
        self.assertEqual(text.line_of(["hello", {}]), "hello")

    def test_an_empty_container_is_not_an_error(self):
        """`str(())` would be the alternative, and it is a Python repr in the
        middle of a player-facing assertion."""
        self.assertEqual(text.line_of(()), "()")

    def test_a_non_string_first_element_is_stringified(self):
        """msg() stringifies it downstream; disagreeing here would make this
        the surprising reader."""
        self.assertEqual(text.line_of((42, {})), "42")


class TypeOfTests(unittest.TestCase):
    """The tag comes back, and its absence is an answer rather than a fault."""

    def test_a_tagged_pair_yields_its_tag(self):
        sent = ("You hit the raider.",
                {const.MESSAGE_TYPE_KEY: const.MESSAGE_TYPE_COMBAT})

        self.assertEqual(text.type_of(sent), const.MESSAGE_TYPE_COMBAT)

    def test_an_untagged_line_answers_empty(self):
        """An EvMenu node sends a bare string and that is not a bug -- see the
        UNTAGGED IS A REAL STATE note in constants.py."""
        self.assertEqual(text.type_of("Choose an option."), "")

    def test_kwargs_without_the_key_answer_empty(self):
        """Evennia's own channel payload carries `from_channel` and, before
        Account.channel_msg was overridden, no type at all."""
        self.assertEqual(text.type_of(("hi", {"from_channel": 7})), "")

    def test_a_malformed_pair_answers_empty_rather_than_raising(self):
        """A reader of somebody else's outgoing message has no business
        deciding their kwargs are wrong."""
        self.assertEqual(text.type_of(("hi", "not a dict")), "")
        self.assertEqual(text.type_of(("hi",)), "")

    def test_every_tag_it_reads_back_is_one_the_vocabulary_declares(self):
        """The round trip, over the whole vocabulary rather than one example.

        Derived from MESSAGE_TYPES so a tag added tomorrow is covered without
        an edit here; asserting a list of names would be the census CLAUDE.md
        forbids.
        """
        for tag in sorted(const.MESSAGE_TYPES):
            with self.subTest(tag=tag):
                sent = ("line", {const.MESSAGE_TYPE_KEY: tag})

                self.assertEqual(text.type_of(sent), tag)
                self.assertEqual(text.line_of(sent), "line")
