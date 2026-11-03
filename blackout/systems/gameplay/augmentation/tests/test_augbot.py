"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The AugBot and `amplify` (DESIGN-0015, Phase 1). The spawner
             stands one up under the room name of the `restore_point` kind,
             and `amplify` restores Grit in full.
Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.augmentation
"""

import unittest

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import pool
from systems.gameplay.progression.skills.constants import SKILL_KEY_AUGMENTATION
from typeclasses import spawners
from typeclasses.augbots import AugBot, CmdAmplify
from typeclasses.characters import Character as BlackoutCharacter
from world import object_kinds


_A_LEVEL = 12
_A_SPEND = 5


class TestAmplify(EvenniaCommandTest):

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.augbot = create_object(AugBot, key="augbot", location=self.room1)
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, _A_LEVEL)
        pool.restore(self.char1)

    def test_amplify_fills_the_pool(self):
        pool.spend(self.char1, _A_SPEND)

        self.call(CmdAmplify(), "", caller=self.char1, obj=self.augbot)

        self.assertEqual(pool.current(self.char1), pool.maximum(self.char1))

    def test_amplify_says_the_amplified_line(self):
        pool.spend(self.char1, _A_SPEND)

        response = self.call(CmdAmplify(), "", caller=self.char1, obj=self.augbot)

        self.assertIn("punishment", response.lower())

    def test_a_full_pool_says_so_and_stays_full(self):
        response = self.call(CmdAmplify(), "", caller=self.char1, obj=self.augbot)

        self.assertIn("full", response.lower())
        self.assertEqual(pool.current(self.char1), pool.maximum(self.char1))

    def test_the_augbot_names_its_verb_for_the_client(self):
        self.assertEqual(self.augbot.interact_verb, aug_const.AMPLIFY_COMMAND_KEY)

    def test_the_augbot_cannot_be_picked_up(self):
        allowed = self.augbot.access(self.char1, "get")

        self.assertFalse(allowed)


class TestAugBotSpawner(EvenniaCommandTest):

    character_typeclass = BlackoutCharacter

    def test_the_restore_point_kind_stands_up_an_augbot(self):
        spawners.load_all_spawners()
        kind = object_kinds.OBJECT_KINDS[object_kinds.RESTORE_KIND]
        spawner = spawners.SPAWNER_REGISTRY[kind.spawner]

        stood_up = spawner(self.room1)

        self.assertIsInstance(stood_up, AugBot)

    def test_a_second_run_stands_up_no_second_augbot(self):
        spawners.load_all_spawners()
        kind = object_kinds.OBJECT_KINDS[object_kinds.RESTORE_KIND]
        spawner = spawners.SPAWNER_REGISTRY[kind.spawner]

        first = spawner(self.room1)
        second = spawner(self.room1)

        self.assertIs(first, second)


class TestSpawnerKeyTwins(unittest.TestCase):
    """The room name has two spellings on purpose. They must stay equal.

    world/object_kinds.py cannot import the augmentation package, because
    the client export reads that module and the package imports the
    statefeed.
    """

    def test_the_kind_names_the_spawner_of_the_package(self):
        kind = object_kinds.OBJECT_KINDS[object_kinds.RESTORE_KIND]

        self.assertEqual(kind.spawner, aug_const.AUGBOT_SPAWNER_KEY)
