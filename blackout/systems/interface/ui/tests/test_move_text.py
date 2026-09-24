"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/22/2026
Description: Cases for the reader and the writers in move_text.py.

             Plain TestCase with a stub AttributeHandler. The module reads and
             writes one Attribute, and a database adds nothing to that.
"""

import unittest

from systems.interface.ui import move_text


class _Attributes:
    """Stands in for AttributeHandler: get, add and remove on one dict."""

    def __init__(self):
        self.stored = {}

    def get(self, key, default=None):
        return self.stored.get(key, default)

    def add(self, key, value):
        self.stored[key] = value

    def remove(self, key):
        self.stored.pop(key, None)


class _Character:
    def __init__(self):
        self.attributes = _Attributes()


class MoveTextTests(unittest.TestCase):
    """Which parts of the room a character hides on a move."""

    def setUp(self):
        self.character = _Character()

    def test_the_default_hides_nothing(self):
        """The game printed every part before the setting existed."""
        self.assertEqual(move_text.hidden_parts(self.character), frozenset())

    def test_every_part_key_is_unique_and_labelled(self):
        keys = [part.key for part in move_text.MOVE_TEXT_PARTS]

        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(set(keys), move_text.PART_KEYS)

        for part in move_text.MOVE_TEXT_PARTS:
            with self.subTest(part=part.key):
                self.assertTrue(part.label)

    def test_hiding_a_part_is_read_back(self):
        for part in move_text.MOVE_TEXT_PARTS:
            with self.subTest(part=part.key):
                character = _Character()
                move_text.set_part_shown(character, part.key, False)

                self.assertEqual(
                    move_text.hidden_parts(character), {part.key})

    def test_showing_the_last_hidden_part_removes_the_row(self):
        """The default costs no Attribute row."""
        move_text.set_part_shown(self.character, move_text.PART_EXITS, False)
        move_text.set_part_shown(self.character, move_text.PART_EXITS, True)

        self.assertNotIn(
            move_text.MOVE_TEXT_HIDDEN_ATTR, self.character.attributes.stored)

    def test_a_stale_key_in_the_row_is_dropped(self):
        """A part that a later change removes must not hide anything."""
        self.character.attributes.add(
            move_text.MOVE_TEXT_HIDDEN_ATTR,
            ["no_such_part", move_text.PART_DESC])

        self.assertEqual(
            move_text.hidden_parts(self.character), {move_text.PART_DESC})

    def test_reset_shows_every_part(self):
        for part in move_text.MOVE_TEXT_PARTS:
            move_text.set_part_shown(self.character, part.key, False)

        move_text.reset(self.character)

        self.assertEqual(move_text.hidden_parts(self.character), frozenset())
