"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The graft, the samples, and the Augmentation Locus
             (DESIGN-0015, Phase 4). A graft anywhere pays `sample_xp`. A
             graft on a Locus tile pays AUG_LOCUS_XP_MULT times that. The
             quests hear the item key and the sample kind.
Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.augmentation
"""

import unittest
from unittest import mock

from evennia import create_object
from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaCommandTest

from commands.augment_cmds import CmdGraft
from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import graft as graft_service
from systems.gameplay.progression.skills.constants import SKILL_KEY_AUGMENTATION
from systems.gameplay.quests import constants as quest_constants
from typeclasses import spawners
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.loci import AugmentationLocus, locus_here
from world import object_kinds
from world.item_database import ITEM_DB


def _samples() -> list:
    """Every ItemDef that is a sample, from the owner of that fact."""
    return [item_def for item_def in ITEM_DB.values() if item_def.sample_xp is not None]


def _first_sample():
    return _samples()[0]


class TestSampleDefs(unittest.TestCase):
    """Every sample declares a kind, and the kind is also its tag."""

    def test_at_least_one_sample_exists(self):
        self.assertTrue(_samples())

    def test_every_sample_names_a_known_kind_and_tags_it(self):
        for item_def in _samples():
            with self.subTest(item=item_def.key):
                self.assertIn(item_def.sample_kind, aug_const.SAMPLE_KINDS)
                self.assertIn((item_def.sample_kind, aug_const.SAMPLE_TAG_CATEGORY),
                              item_def.tags)
                self.assertGreater(item_def.sample_xp, 0)

    def test_a_kind_tag_belongs_to_a_sample_only(self):
        for item_def in ITEM_DB.values():
            tagged = any(category == aug_const.SAMPLE_TAG_CATEGORY
                         for _key, category in item_def.tags)

            with self.subTest(item=item_def.key):
                self.assertEqual(tagged, item_def.sample_xp is not None)


class TestGraft(EvenniaCommandTest):

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.item_def = _first_sample()
        self.sample = self.item_def.create(location=self.char1, home=self.char1)

    def _xp(self) -> int:
        return self.char1.skills.get_total_xp(SKILL_KEY_AUGMENTATION)

    def test_the_sample_fields_reach_the_object(self):
        self.assertEqual(self.sample.attributes.get(aug_const.SAMPLE_XP_ATTR),
                         self.item_def.sample_xp)
        self.assertEqual(self.sample.attributes.get(aug_const.SAMPLE_KIND_ATTR),
                         self.item_def.sample_kind)
        self.assertTrue(graft_service.is_sample(self.sample))

    def test_a_graft_anywhere_pays_the_sample_xp(self):
        before = self._xp()

        response = self.call(CmdGraft(), f" {self.item_def.name}", caller=self.char1)

        self.assertIn("graft", response.lower())
        self.assertEqual(self._xp() - before, self.item_def.sample_xp)

    def test_a_graft_consumes_one_unit(self):
        self.sample.quantity = 2

        self.call(CmdGraft(), f" {self.item_def.name}", caller=self.char1)

        self.assertEqual(self.sample.quantity, 1)
        self.assertIn(self.sample, self.char1.contents)

    def test_the_last_unit_deletes_the_sample(self):
        self.call(CmdGraft(), f" {self.item_def.name}", caller=self.char1)

        self.assertNotIn(self.sample, self.char1.contents)

    def test_a_graft_on_a_locus_tile_pays_more(self):
        create_object(AugmentationLocus, key="locus", location=self.room1)
        before = self._xp()

        self.call(CmdGraft(), f" {self.item_def.name}", caller=self.char1)

        expected = round(self.item_def.sample_xp * aug_const.AUG_LOCUS_XP_MULT)
        self.assertEqual(self._xp() - before, expected)

    def test_a_graft_tells_the_quests_the_key_and_the_kind(self):
        with mock.patch("systems.gameplay.augmentation.graft.notify_quests") as hook:
            graft_service.graft(self.char1, self.sample)

        arguments = {call.args[2] for call in hook.call_args_list}

        self.assertEqual(arguments, {self.item_def.key, self.item_def.sample_kind})

        for call in hook.call_args_list:
            self.assertEqual(call.args[1], quest_constants.ACTION_GRAFT)

    def test_a_thing_that_is_no_sample_is_refused(self):
        other = ITEM_DB["rusty_metal_chunk"].create(location=self.char1, home=self.char1)
        before = self._xp()

        response = self.call(CmdGraft(), " rusty metal chunk", caller=self.char1)

        self.assertIn("cannot graft", response.lower())
        self.assertEqual(self._xp(), before)
        self.assertIn(other, self.char1.contents)

    def test_a_bare_graft_lists_the_samples(self):
        response = self.call(CmdGraft(), "", caller=self.char1)

        self.assertIn(self.item_def.name, strip_ansi(response))

    def test_a_bare_graft_with_no_sample_says_so(self):
        self.sample.delete()

        response = self.call(CmdGraft(), "", caller=self.char1)

        self.assertIn("no sample", response.lower())


class TestLocus(EvenniaCommandTest):

    character_typeclass = BlackoutCharacter

    def test_locus_here_finds_the_locus_in_the_room(self):
        self.assertIsNone(locus_here(self.char1))

        locus = create_object(AugmentationLocus, key="locus", location=self.room1)

        self.assertIs(locus_here(self.char1), locus)

    def test_the_locus_kind_stands_one_up_once(self):
        spawners.load_all_spawners()
        kind = object_kinds.OBJECT_KINDS[object_kinds.LOCUS_KIND]
        spawner = spawners.SPAWNER_REGISTRY[kind.spawner]

        first = spawner(self.room1)
        second = spawner(self.room1)

        self.assertIs(first, second)
        self.assertTrue(first.is_augmentation_locus)


class TestLocusSpawnerKeyTwins(unittest.TestCase):
    """The room name has two spellings on purpose. They must stay equal."""

    def test_the_kind_names_the_spawner_of_the_package(self):
        kind = object_kinds.OBJECT_KINDS[object_kinds.LOCUS_KIND]

        self.assertEqual(kind.spawner, aug_const.AUG_LOCUS_SPAWNER_KEY)
