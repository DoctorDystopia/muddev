"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: Tests for ExterminatorHandler: assign, count, complete, skip,
             and the death rule.

             The tests read every number from its owner: the Assignment, the
             PreceptorDef, the streak table, and the skip cost. No test
             asserts a balance value (CLAUDE.md, "Writing tests").
             DESIGN-0012, Phase 2.
"""

import random
import unittest
from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.exterminator import constants as ext_const
from systems.gameplay.exterminator.handler import streak_multiplier
from systems.gameplay.exterminator.preceptors import (
    PRECEPTOR_ATTICUS_QUIN,
    PRECEPTOR_DB,
    Assignment,
    PreceptorDef,
)
from systems.gameplay.progression.skills import constants as skill_constants
from typeclasses.characters import Character as BlackoutCharacter
from world.creature_types import CREATURE_TYPES, CreatureType



# Private constant definitions

_SEED: int = 1234

# Damage that kills any fixture outright.
_LETHAL_DAMAGE: int = 9999

# A test-only creature type that no level reaches, and a Preceptor for it.
_UNREACHABLE_TYPE: str = "test_unreachable_type"
_TEST_PRECEPTOR: str = "test_preceptor"

_EXTERMINATOR: str = skill_constants.SKILL_KEY_EXTERMINATOR

# Enough draws to see each allowed type of Quin many times.
_DRAW_COUNT: int = 50



def _quin():
    return PRECEPTOR_DB[PRECEPTOR_ATTICUS_QUIN]


def _unreachable_row():
    return CreatureType(_UNREACHABLE_TYPE, "Unreachable", "Unreachables",
                        skill_constants.MAX_BASE_SKILL_LEVEL + 1)



class StreakMultiplierTests(unittest.TestCase):
    """The multiplier comes from the table, highest milestone first."""

    def test_a_streak_on_no_milestone_gets_the_base(self):
        smallest = min(milestone for milestone, _mult in ext_const.STREAK_MULTIPLIERS)
        off_milestone = smallest + 1

        self.assertEqual(streak_multiplier(off_milestone), ext_const.STREAK_BASE_MULTIPLIER)
        self.assertEqual(streak_multiplier(0), ext_const.STREAK_BASE_MULTIPLIER)

    def test_each_milestone_gets_the_highest_multiplier_that_divides_it(self):
        for milestone, _mult in ext_const.STREAK_MULTIPLIERS:
            expected = next(mult for step, mult in ext_const.STREAK_MULTIPLIERS
                            if milestone % step == 0)

            with self.subTest(milestone=milestone):
                self.assertEqual(streak_multiplier(milestone), expected)

    def test_the_table_is_highest_first(self):
        milestones = [milestone for milestone, _mult in ext_const.STREAK_MULTIPLIERS]

        self.assertEqual(milestones, sorted(milestones, reverse=True))



class _HandlerTest(EvenniaTest):
    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.handler = self.char1.exterminator
        self.rng = random.Random(_SEED)

    def _assign_quin(self):
        assigned, _message = self.handler.assign(PRECEPTOR_ATTICUS_QUIN, rng=self.rng)
        self.assertTrue(assigned)

    def _task_types(self):
        return (self.handler.creature_type(),)



class AssignTests(_HandlerTest):

    def test_a_task_comes_from_the_pool_with_a_size_in_its_range(self):
        self._assign_quin()

        by_type = {a.creature_type: a for a in _quin().assignments}
        assignment = by_type[self.handler.creature_type()]

        self.assertGreaterEqual(self.handler.total(), assignment.min_size)
        self.assertLessEqual(self.handler.total(), assignment.max_size)
        self.assertEqual(self.handler.kills(), 0)

    def test_one_task_at_a_time(self):
        self._assign_quin()
        before = self.handler.task()

        assigned, message = self.handler.assign(PRECEPTOR_ATTICUS_QUIN, rng=self.rng)

        self.assertFalse(assigned)
        self.assertIn("already have a task", message.lower())
        self.assertEqual(self.handler.task(), before)

    def test_a_type_above_the_level_is_never_drawn(self):
        level = self.char1.skills.get_level(_EXTERMINATOR)
        allowed = {a.creature_type for a in _quin().assignments
                   if CREATURE_TYPES[a.creature_type].required_level <= level}

        for _draw in range(_DRAW_COUNT):
            self.char1.attributes.add(ext_const.TASK_ATTR, None)
            self._assign_quin()

            with self.subTest(drawn=self.handler.creature_type()):
                self.assertIn(self.handler.creature_type(), allowed)

    def test_no_allowed_type_refuses(self):
        preceptor = PreceptorDef(
            key=_TEST_PRECEPTOR, name="Test",
            assignments=(Assignment(_UNREACHABLE_TYPE, 1, 1, 1),), base_points=0)

        with mock.patch.dict(CREATURE_TYPES, {_UNREACHABLE_TYPE: _unreachable_row()}), \
                mock.patch.dict(PRECEPTOR_DB, {_TEST_PRECEPTOR: preceptor}):
            assigned, message = self.handler.assign(_TEST_PRECEPTOR, rng=self.rng)

        self.assertFalse(assigned)
        self.assertIn("no task", message.lower())
        self.assertFalse(self.handler.has_task())

    def test_a_preceptor_above_the_level_refuses(self):
        level = self.char1.skills.get_level(_EXTERMINATOR)
        preceptor = PreceptorDef(
            key=_TEST_PRECEPTOR, name="Test", assignments=_quin().assignments,
            base_points=0, required_level=level + 1)

        with mock.patch.dict(PRECEPTOR_DB, {_TEST_PRECEPTOR: preceptor}):
            assigned, _message = self.handler.assign(_TEST_PRECEPTOR, rng=self.rng)

        self.assertFalse(assigned)
        self.assertFalse(self.handler.has_task())



class KillTests(_HandlerTest):

    def test_a_kill_of_another_type_does_not_count(self):
        self._assign_quin()

        counted = self.handler.record_kill(("not_the_task_type",), 5)

        self.assertFalse(counted)
        self.assertEqual(self.handler.kills(), 0)

    def test_a_kill_with_no_task_does_not_count(self):
        counted = self.handler.record_kill(self._task_types(), 5)

        self.assertFalse(counted)

    def test_a_task_kill_counts_and_pays_its_xp(self):
        self._assign_quin()
        xp_before = self.char1.skills.get_total_xp(_EXTERMINATOR)
        share = 7

        counted = self.handler.record_kill(self._task_types(), share)

        self.assertTrue(counted)
        self.assertEqual(self.handler.kills(), 1)
        self.assertEqual(self.char1.skills.get_total_xp(_EXTERMINATOR), xp_before + share)

    def test_the_last_kill_completes_the_task_and_pays_points(self):
        self._assign_quin()
        types = self._task_types()
        streak_before = self.handler.streak()
        points_before = self.handler.points()

        for _kill in range(self.handler.total()):
            self.handler.record_kill(types, 0)

        expected_streak = streak_before + 1
        expected_points = points_before + _quin().base_points * streak_multiplier(expected_streak)

        self.assertFalse(self.handler.has_task())
        self.assertEqual(self.handler.streak(), expected_streak)
        self.assertEqual(self.handler.points(), expected_points)

    def test_the_streak_bonus_pays_the_multiplier_of_the_table(self):
        milestone, _mult = ext_const.STREAK_MULTIPLIERS[-1]
        self.char1.attributes.add(ext_const.STREAK_ATTR, milestone - 1)
        self._assign_quin()
        types = self._task_types()

        for _kill in range(self.handler.total()):
            self.handler.record_kill(types, 0)

        self.assertEqual(self.handler.points(), _quin().base_points * streak_multiplier(milestone))



class SkipTests(_HandlerTest):

    def test_too_few_points_cannot_skip(self):
        self._assign_quin()
        self.char1.attributes.add(ext_const.POINTS_ATTR, ext_const.SKIP_COST_POINTS - 1)

        skipped, message = self.handler.skip()

        self.assertFalse(skipped)
        self.assertIn("costs", message.lower())
        self.assertTrue(self.handler.has_task())

    def test_a_skip_costs_points_and_ends_the_streak(self):
        self._assign_quin()
        start_points = ext_const.SKIP_COST_POINTS + 3
        self.char1.attributes.add(ext_const.POINTS_ATTR, start_points)
        self.char1.attributes.add(ext_const.STREAK_ATTR, 4)

        skipped, _message = self.handler.skip()

        self.assertTrue(skipped)
        self.assertFalse(self.handler.has_task())
        self.assertEqual(self.handler.points(), start_points - ext_const.SKIP_COST_POINTS)
        self.assertEqual(self.handler.streak(), 0)

    def test_a_skip_with_no_task_refuses(self):
        skipped, _message = self.handler.skip()

        self.assertFalse(skipped)



class DeathRuleTests(_HandlerTest):
    """Nick, 10/06/2026: death has no effect on a task."""

    def test_a_player_death_leaves_the_task_unchanged(self):
        self._assign_quin()
        self.handler.record_kill(self._task_types(), 0)
        self.char1.attributes.add(ext_const.STREAK_ATTR, 3)
        self.char1.attributes.add(ext_const.POINTS_ATTR, 11)
        before = (self.handler.task(), self.handler.streak(), self.handler.points())
        self.char1.hp = self.char1.max_hp
        self.assertTrue(self.char1.is_alive())

        self.char1.at_damage(_LETHAL_DAMAGE, attacker=self.char2)

        after = (self.handler.task(), self.handler.streak(), self.handler.points())
        self.assertEqual(after, before)
