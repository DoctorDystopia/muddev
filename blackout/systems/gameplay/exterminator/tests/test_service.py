"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: Tests for the work of a Preceptor, the `task` command, the Task
             Writ, and the task pop-up. DESIGN-0012, Phase 2.
"""

import random

from evennia.utils.test_resources import EvenniaCommandTest
from evennia.utils import create
from evennia.utils.test_resources import EvenniaTest

from commands.exterminator_cmds import CmdTask
from systems.gameplay.exterminator import constants as ext_const
from systems.gameplay.exterminator import service
from systems.interface.popups import service as popup_service
from systems.interface.popups.popup_defs.exterminator import EXTERMINATOR_POPUP_KEY
from typeclasses.characters import Character as BlackoutCharacter
from world.npc_database import NPC_DB



_SEED: int = 99
_QUIN_KEY: str = "atticus_quin"



def _writs(character) -> list:
    """Every Task Writ that the character carries."""
    return [item for item in character.contents
            if getattr(item, service.TASK_WRIT_FLAG_ATTR, False)]



class _QuinHere(EvenniaTest):
    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.quin = NPC_DB[_QUIN_KEY].create(location=self.room1)
        self.rng = random.Random(_SEED)



class ServiceTests(_QuinHere):

    def test_the_preceptor_here_is_found_by_name_or_alone(self):
        self.assertEqual(service.preceptor_here(self.char1), self.quin)
        self.assertEqual(service.preceptor_here(self.char1, "atti"), self.quin)
        self.assertIsNone(service.preceptor_here(self.char1, "nobody"))

    def test_no_preceptor_in_another_room(self):
        self.char1.location = self.room2

        self.assertIsNone(service.preceptor_here(self.char1))

    def test_a_task_comes_with_one_writ(self):
        service.take_task(self.char1, self.quin, rng=self.rng)

        self.assertTrue(self.char1.exterminator.has_task())
        self.assertEqual(len(_writs(self.char1)), 1)

    def test_a_second_writ_is_refused(self):
        service.give_writ(self.char1, self.quin)
        line = service.give_writ(self.char1, self.quin)

        self.assertEqual(len(_writs(self.char1)), 1)
        self.assertIn("already carry", line.lower())

    def test_a_lost_writ_is_given_again(self):
        service.give_writ(self.char1, self.quin)
        _writs(self.char1)[0].delete()

        service.give_writ(self.char1, self.quin)

        self.assertEqual(len(_writs(self.char1)), 1)

    def test_the_writ_offers_the_task_command(self):
        service.give_writ(self.char1, self.quin)
        actions = _writs(self.char1)[0].inventory_actions()

        self.assertEqual(actions[0]["command"], ext_const.TASK_COMMAND_KEY)

    def test_the_preceptor_offers_talk_and_a_task(self):
        commands = [action["command"] for action in self.quin.extra_actions()]

        self.assertIn(f"{ext_const.TASK_NEW_COMMAND} {self.quin.key}", commands)



class PopupTests(_QuinHere):

    def setUp(self):
        super().setUp()
        service.take_task(self.char1, self.quin, rng=self.rng)
        self.writ = _writs(self.char1)[0]

    def test_the_popup_shows_the_task_lines(self):
        opened = popup_service.open_popup(self.char1, EXTERMINATOR_POPUP_KEY, self.writ)
        snapshot = popup_service.build_snapshot(self.char1)

        self.assertTrue(opened)
        self.assertTrue(snapshot["open"])

        for line in self.char1.exterminator.summary_lines():
            with self.subTest(line=line):
                self.assertIn(line, snapshot["status"])

    def test_the_popup_offers_the_skip_command(self):
        popup_service.open_popup(self.char1, EXTERMINATOR_POPUP_KEY, self.writ)
        snapshot = popup_service.build_snapshot(self.char1)
        commands = [action["command"] for action in snapshot["actions"]]

        self.assertIn(ext_const.TASK_SKIP_COMMAND, commands)

    def test_a_writ_that_leaves_the_bag_closes_the_popup(self):
        popup_service.open_popup(self.char1, EXTERMINATOR_POPUP_KEY, self.writ)
        self.writ.location = self.room1

        snapshot = popup_service.build_snapshot(self.char1)

        self.assertFalse(snapshot["open"])

    def test_walking_away_keeps_it_open(self):
        popup_service.open_popup(self.char1, EXTERMINATOR_POPUP_KEY, self.writ)
        self.char1.move_to(self.room2, quiet=True)

        snapshot = popup_service.build_snapshot(self.char1)

        self.assertTrue(snapshot["open"])



class CmdTaskTests(EvenniaCommandTest):
    character_typeclass = BlackoutCharacter

    def test_no_task_says_so(self):
        self.call(CmdTask(), "", "You have no Exterminator task")

    def test_new_with_no_preceptor_refuses(self):
        self.call(CmdTask(), ext_const.TASK_ARG_NEW, "No Preceptor is here")

    def test_an_unknown_word_shows_the_usage(self):
        self.call(CmdTask(), "dance", "Usage: task")

    def test_new_with_a_preceptor_assigns_a_task(self):
        NPC_DB[_QUIN_KEY].create(location=self.room1)

        self.call(CmdTask(), ext_const.TASK_ARG_NEW, "[NEW TASK]")

        self.assertTrue(self.char1.exterminator.has_task())

    def test_skip_with_no_task_refuses(self):
        self.call(CmdTask(), ext_const.TASK_ARG_SKIP, "You have no Exterminator task")
