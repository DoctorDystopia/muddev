"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The `aug` command (DESIGN-0015, Phase 2).
Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.augmentation
"""

from evennia.utils.test_resources import EvenniaCommandTest

from commands.augment_cmds import CmdAug
from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import pool
from systems.gameplay.augmentation import sockets
from systems.gameplay.augmentation.handler import get_augment_handler_for
from systems.gameplay.augmentation.registry import augments_in_order
from systems.gameplay.augmentation.tests import support
from systems.gameplay.progression.skills.constants import SKILL_KEY_AUGMENTATION
from typeclasses.characters import Character as BlackoutCharacter


_A_LEVEL = 50


class TestAugCommand(EvenniaCommandTest):

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, _A_LEVEL)
        pool.restore(self.char1)
        # The rail shows the socketed augments only (Phase 5), so the rig
        # holds every augment that finds a socket at this level.
        self.rig = support.socket_fitting(self.char1, augments_in_order())
        self.augment = self.rig[0]

    def tearDown(self):
        handler = get_augment_handler_for(self.char1)

        if handler is not None:
            handler.stop_handler()

        super().tearDown()

    def _handler(self):
        return get_augment_handler_for(self.char1)

    def test_a_bare_aug_lists_every_socketed_augment(self):
        response = self.call(CmdAug(), "", caller=self.char1)

        for augment in sockets.socketed_augments(self.char1):
            with self.subTest(augment=augment.key):
                self.assertIn(augment.name, response)

    def test_an_augment_outside_the_rig_is_refused(self):
        outside = [augment for augment in augments_in_order()
                   if augment not in self.rig]

        if not outside:
            self.skipTest("every augment found a socket")

        response = self.call(CmdAug(), f" {outside[0].name}", caller=self.char1)

        self.assertIn("rig", response.lower())
        self.assertIsNone(self._handler())

    def test_a_name_lights_the_augment_at_the_top_step(self):
        response = self.call(CmdAug(), f" {self.augment.name}", caller=self.char1)

        self.assertIn("online", response.lower())
        self.assertEqual(self._handler().step_of(self.augment.key), aug_const.AUG_STEP_DEFAULT)

    def test_a_name_and_a_step_light_at_that_step(self):
        self.call(CmdAug(), f" {self.augment.name} {aug_const.AUG_STEP_MIN}", caller=self.char1)

        self.assertEqual(self._handler().step_of(self.augment.key), aug_const.AUG_STEP_MIN)

    def test_a_second_light_resteps(self):
        self.call(CmdAug(), f" {self.augment.name} {aug_const.AUG_STEP_MIN}", caller=self.char1)

        response = self.call(CmdAug(), f" {self.augment.name}", caller=self.char1)

        self.assertIn("shifts", response.lower())
        self.assertEqual(self._handler().step_of(self.augment.key), aug_const.AUG_STEP_DEFAULT)

    def test_a_bad_step_is_refused(self):
        bad = aug_const.AUG_STEPS + 1

        response = self.call(CmdAug(), f" {self.augment.name} {bad}", caller=self.char1)

        self.assertIn("step", response.lower())
        self.assertIsNone(self._handler())

    def test_an_unknown_name_is_refused(self):
        response = self.call(CmdAug(), " no such thing", caller=self.char1)

        self.assertIn("know no augment", response.lower())

    def test_name_off_puts_one_out_and_the_last_one_ends_the_handler(self):
        self.call(CmdAug(), f" {self.augment.name}", caller=self.char1)

        response = self.call(CmdAug(), f" {self.augment.name} {aug_const.AUG_OFF_ARG}",
                             caller=self.char1)

        self.assertIn("dark", response.lower())
        self.assertIsNone(self._handler())

    def test_off_puts_every_augment_out(self):
        for augment in self.rig:
            self.call(CmdAug(), f" {augment.name}", caller=self.char1)

        response = self.call(CmdAug(), f" {aug_const.AUG_OFF_ARG}", caller=self.char1)

        self.assertIn("every augment", response.lower())
        self.assertIsNone(self._handler())

    def test_off_with_nothing_lit_says_so(self):
        response = self.call(CmdAug(), f" {aug_const.AUG_OFF_ARG}", caller=self.char1)

        self.assertIn("no augment", response.lower())

    def test_no_grit_refuses_the_light(self):
        pool.spend(self.char1, pool.maximum(self.char1))

        response = self.call(CmdAug(), f" {self.augment.name}", caller=self.char1)

        self.assertIn("grit", response.lower())
        self.assertIsNone(self._handler())

    def test_a_locked_augment_is_refused(self):
        gated = [augment for augment in self.rig
                 if augment.unlock_level > aug_const.NO_UNLOCK_LEVEL]

        if not gated:
            self.skipTest("no augment has an unlock level")

        augment = gated[0]
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, augment.unlock_level - 1)

        response = self.call(CmdAug(), f" {augment.name}", caller=self.char1)

        self.assertIn("needs", response.lower())
        self.assertIsNone(self._handler())

    def test_the_listing_marks_a_lit_augment(self):
        self.call(CmdAug(), f" {self.augment.name}", caller=self.char1)

        response = self.call(CmdAug(), "", caller=self.char1)

        self.assertIn("online", response.lower())
