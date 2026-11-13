"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: Tests of a dialogue script as an EvMenu (DESIGN-0017): `talk`
             opens the script of an NPC, a response moves to the next beat,
             and an ending closes the menu.

             The rules of a script have their tests in
             systems/gameplay/dialogue/tests/. These tests cover only the
             menu around them, on one real NPC: the Clinic recruiter.
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.dialogue.tests import helpers
from systems.gameplay.quests.content import quest_augmentation_intro as quest
from systems.interface.menus import dialogue_script
from systems.interface.menus.base_menu import MENU_UNAVAILABLE_MSG
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.npcs import _dialogue_script_for
from world.npc_database import NPC_DB


_NPC_DEF = NPC_DB[quest.NPC_CLINIC_KEY]


class _ScriptMenuTest(EvenniaTest):
    """The Clinic recruiter in the room of the first character."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.npc = _NPC_DEF.create(location=self.room1)

    def tearDown(self):
        menu = self.char1.ndb._evmenu

        if menu:
            menu.close_menu()

        super().tearDown()

    def _talk(self):
        self.char1.execute_cmd("talk", session=self.session)

        return self.char1.ndb._evmenu

    def _option_key(self, menu, keyword):
        """The key that a player types for the response with a keyword."""
        index = helpers.response_index(menu.conversation, keyword)

        return str(index + 1)


class TalkTests(_ScriptMenuTest):
    """`talk` on an NPC that speaks from a dialogue script."""

    def test_the_def_names_the_script(self):
        self.assertEqual(_dialogue_script_for(self.npc), _NPC_DEF.dialogue_script)

    def test_talk_opens_a_menu_with_the_first_beat(self):
        menu = self._talk()

        self.assertTrue(menu)
        self.assertIn(menu.conversation.beat.text, menu.nodetext)
        self.assertIn(self.npc.key, menu.nodetext)

    def test_the_menu_offers_one_option_for_each_response(self):
        menu = self._talk()
        labels = [response.label for response in menu.conversation.beat.responses]

        self.assertEqual(len(menu.options), len(labels))

    def test_a_response_moves_to_the_next_beat(self):
        menu = self._talk()
        first_text = menu.nodetext

        menu.parse_input(self._option_key(menu, "ask about the job"))

        self.assertNotEqual(menu.nodetext, first_text)
        self.assertIn(quest.QUEST_TITLE, menu.nodetext)

    def test_a_do_line_runs_through_the_menu(self):
        menu = self._talk()
        menu.parse_input(self._option_key(menu, "ask about the job"))

        menu.parse_input(self._option_key(menu, "Accept"))

        self.assertTrue(self.char1.quests.is_active(quest.QUEST_KEY))

    def test_an_ending_closes_the_menu(self):
        menu = self._talk()

        menu.parse_input(self._option_key(menu, "leave"))

        self.assertFalse(self.char1.ndb._evmenu)

    def test_the_farewell_cue_is_the_parting_line(self):
        menu = self._talk()
        expected = menu.conversation.farewell()

        closing = menu._resolve_closing_text()

        self.assertTrue(expected)
        self.assertIn("farewell", expected.lower())
        self.assertEqual(closing, expected)


class FaultTests(_ScriptMenuTest):
    """A script that the server cannot run never reaches a player."""

    def test_a_script_that_does_not_exist_opens_no_menu(self):
        with mock.patch.object(self.char1, "msg") as sent:
            menu = dialogue_script.open_script(self.char1, self.npc, "no_such_script")

        texts = [str(call.args[0]) for call in sent.call_args_list if call.args]

        self.assertIsNone(menu)
        self.assertFalse(self.char1.ndb._evmenu)
        self.assertTrue(any(MENU_UNAVAILABLE_MSG in text for text in texts), texts)

    def test_a_fault_in_a_beat_closes_the_menu(self):
        from systems.gameplay.dialogue.script import DialogueScriptError

        menu = self._talk()

        with mock.patch.object(menu.conversation, "choose",
                               side_effect=DialogueScriptError("broken")):
            menu.parse_input("1")

        self.assertFalse(self.char1.ndb._evmenu)
