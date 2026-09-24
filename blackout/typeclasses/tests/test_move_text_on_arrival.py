"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/22/2026
Description: Cases for what a step prints, after `movetext`.

             The whole path, not the pieces: Character.at_post_move reads the
             choice, the look carries it, and GridTile leaves out each hidden
             part. A test of one piece cannot catch a kwarg that the next
             piece never receives.

             EvenniaTest, because the path is a real move_to into a real
             GridTile, with a second character to fill the Characters line.
"""

from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.interface.statefeed import constants as feed_const
from systems.interface.ui import move_text
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.exits import Exit
from typeclasses.objects import Object
from typeclasses.rooms import GridTile

_ROOM_NAME = "Dune Sea"
_ROOM_DESC = "Sand in every direction."
_EXIT_NAME = "north"
_THING_NAME = "rusty pole"


class MoveTextOnArrivalTests(EvenniaTest):
    """Which parts of the room the log prints when a character walks in."""

    character_typeclass = BlackoutCharacter
    room_typeclass = GridTile

    def setUp(self):
        super().setUp()
        self.destination = create_object(GridTile, key=_ROOM_NAME, nohome=True)
        self.destination.db.desc = _ROOM_DESC
        create_object(Exit, key=_EXIT_NAME, location=self.destination,
                      destination=self.room1)
        create_object(Object, key=_THING_NAME, location=self.destination)
        self.char2.move_to(self.destination, quiet=True)

        # The text that marks each part, keyed by part. Built here because
        # char2's key belongs to the fixture.
        self.markers = {
            move_text.PART_NAME: _ROOM_NAME,
            move_text.PART_DESC: _ROOM_DESC,
            move_text.PART_EXITS: _EXIT_NAME,
            move_text.PART_CHARACTERS: self.char2.key,
            move_text.PART_THINGS: _THING_NAME,
        }

    def _arrive(self) -> list:
        """Walk char1 in from room1 and return each look text it was sent."""
        self.char1.move_to(self.room1, quiet=True)

        with mock.patch.object(self.char1, "msg") as sent:
            self.char1.move_to(self.destination, quiet=True)

        looks = []

        for call in sent.call_args_list:
            text = call.kwargs.get("text")

            if not isinstance(text, tuple):
                continue

            if text[1].get(feed_const.MESSAGE_TYPE_KEY) == feed_const.MESSAGE_TYPE_LOOK:
                looks.append(text[0])

        return looks

    def test_the_default_prints_every_part(self):
        """What a step printed before the setting existed."""
        looks = self._arrive()

        self.assertEqual(len(looks), 1)

        for part, marker in self.markers.items():
            with self.subTest(part=part):
                self.assertIn(marker, looks[0])

    def test_a_hidden_part_is_left_out_and_the_rest_stay(self):
        for hidden in move_text.PART_KEYS:
            with self.subTest(hidden=hidden):
                move_text.reset(self.char1)
                move_text.set_part_shown(self.char1, hidden, False)
                looks = self._arrive()

                self.assertEqual(len(looks), 1)
                self.assertNotIn(self.markers[hidden], looks[0])

                for part, marker in self.markers.items():
                    if part != hidden:
                        self.assertIn(marker, looks[0])

    def test_a_hidden_name_leaves_no_empty_line(self):
        """The name line holds colour codes. A hidden name must take them
        with it, or the log shows a blank line on every step."""
        move_text.set_part_shown(self.char1, move_text.PART_NAME, False)
        looks = self._arrive()
        first_line = looks[0].splitlines()[0]

        self.assertIn(_ROOM_DESC, first_line)

    def test_every_part_hidden_sends_no_look(self):
        """An empty message puts a blank line in the log."""
        for part in move_text.PART_KEYS:
            move_text.set_part_shown(self.char1, part, False)

        self.assertEqual(self._arrive(), [])

    def test_a_typed_look_shows_every_part(self):
        """The choice is about STEPS. `look` must still show the exits."""
        for part in move_text.PART_KEYS:
            move_text.set_part_shown(self.char1, part, False)

        self._arrive()
        appearance = self.char1.at_look(self.destination)

        for part, marker in self.markers.items():
            with self.subTest(part=part):
                self.assertIn(marker, appearance)
