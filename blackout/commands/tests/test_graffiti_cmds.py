"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for `write`, the command a player uses to leave words in
             the world.

             Deliberately thin, because the command is. Every rule lives in
             systems/gameplay/graffiti/service.py and has its own tests there;
             what is checked here is the wiring and the one thing the command
             owns -- that a refusal REACHES the player. A service returning a
             message nobody prints is the same bug as a service that says
             nothing, and it is the shape a thin command layer fails in.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \
        commands.tests.test_graffiti_cmds
"""

from evennia.utils.test_resources import EvenniaCommandTest

from commands.graffiti_cmds import CmdWrite
from systems.gameplay.graffiti import service as graffiti_service
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.signs import Graffiti
from world.item_database import ITEM_DB


class TestWriteCommand(EvenniaCommandTest):
    """
    Purpose: The command's wiring, and that a refusal is shown.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        EvenniaCommandTest, because the assertions are about the lines a
        player sees.

        Asserted on keywords rather than whole sentences, so a copy edit to a
        template does not fail a test about the command.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """

    character_typeclass = BlackoutCharacter


    def _scrawls(self):
        return list(Graffiti.objects.all_family())


    def test_a_player_with_a_can_can_write(self):
        ITEM_DB["spray_can"].create(location=self.char1)

        self.call(CmdWrite(), "KEEP OUT", caller=self.char1)

        made = self._scrawls()

        self.assertEqual(len(made), 1)
        self.assertEqual(made[0].world_label, "KEEP OUT")
        self.assertEqual(made[0].location, self.char1.location)


    def test_the_charge_count_is_reported_back(self):
        # A can is a consumable and a player spending one is entitled to know
        # how many they have left.
        ITEM_DB["spray_can"].create(location=self.char1)

        response = self.call(CmdWrite(), "KEEP OUT", caller=self.char1)

        self.assertIn("left", response.lower())


    def test_a_refusal_reaches_the_player(self):
        # The one thing this layer owns. A service message nobody prints is
        # the same bug as a service that says nothing.
        response = self.call(CmdWrite(), "KEEP OUT", caller=self.char1)

        self.assertEqual(self._scrawls(), [])
        self.assertIn("nothing to write with", response.lower())


    def test_writing_nothing_asks_what(self):
        response = self.call(CmdWrite(), "", caller=self.char1)

        self.assertIn("write what", response.lower())


    def test_the_scrawl_records_the_player_who_typed_it(self):
        ITEM_DB["spray_can"].create(location=self.char1)

        self.call(CmdWrite(), "KEEP OUT", caller=self.char1)

        self.assertEqual(
            graffiti_service.author_id_of(self._scrawls()[0]), self.char1.id)
