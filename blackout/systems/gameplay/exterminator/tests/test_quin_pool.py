"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/07/2026
Description: Tests for the pool of Atticus Quin and its seven buffs.

             Every number comes from its owner: the `strengths` of a buff,
             the PreceptorDef, the streak table. No test asserts a balance
             value (CLAUDE.md, "Writing tests"). DESIGN-0012, Phase 5.
"""

import math
import random
import unittest
from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.combat import constants as combat_const
from systems.gameplay.combat.combat import ActionAttack, ensure_combat_handler
from systems.gameplay.combat.rules.context import ActionResult
from systems.gameplay.combat.rules.pipeline import _resolve_winners, resolve_action
from systems.gameplay.exterminator import constants as ext_const
from systems.gameplay.exterminator.buff_defs import (
    best_of_two_rolls,
    damage_for_defense,
    low_hp_max_hit,
)
from systems.gameplay.exterminator.buffs import BUFF_REGISTRY, buff_name
from systems.gameplay.exterminator.handler import streak_multiplier
from systems.gameplay.exterminator.preceptors import (
    PRECEPTOR_ATTICUS_QUIN,
    PRECEPTOR_DB,
    PoolEntry,
    PreceptorDef,
    assignment_for,
)
from typeclasses.characters import Character as BlackoutCharacter
from world import creature_types
from world.npc_database import NPC_DB



# ─── Private constant definitions ────────────────────────────────────────────

_MUTANT_CRAB_KEY: str = "mutant_crab"     # a mutant AND a crab
_FLOATING_EYE_KEY: str = "floating_eye"   # an eye, no other type

_TASK_SEED: int = 5
_TASK_TOTAL: int = 9

# Fixture HP for the HP line tests. Not a balance value.
_FIXTURE_MAX_HP: int = 100
_PERCENT: int = 100

# Fixture playtime for the par clock tests.
_PLAYTIME_AT_ASSIGN: int = 1000

# A positive defense bonus for the cut test. Not a balance value.
_FIXTURE_DEFENSE_BONUS: int = 20

_TEST_PRECEPTOR_KEY: str = "test_named_preceptor"
_TEST_POOL_NAME: str = "Test Pool Name"



class _ScriptedRng:
    """A stand-in for random.Random: randint gives the scripted rolls in order."""

    def __init__(self, rolls) -> None:
        self._rolls = list(rolls)

    def randint(self, _low, _high) -> int:
        return self._rolls.pop(0)

    def random(self) -> float:
        return 0.0



# ─── The pool and the registry (no database) ────────────────────────────────

class PoolShapeTests(unittest.TestCase):

    def test_every_pool_entry_names_a_registered_buff(self):
        for preceptor in PRECEPTOR_DB.values():
            for entry in preceptor.buff_pool:
                with self.subTest(preceptor=preceptor.key, buff=entry.buff_key):
                    self.assertIn(entry.buff_key, BUFF_REGISTRY)
                    self.assertGreater(entry.weight, 0)

    def test_quin_teaches_a_pool(self):
        self.assertTrue(PRECEPTOR_DB[PRECEPTOR_ATTICUS_QUIN].buff_pool)

    def test_every_buff_declares_an_archetype(self):
        for buff_key, buff in BUFF_REGISTRY.items():
            with self.subTest(buff=buff_key):
                self.assertTrue(buff.archetype)
                self.assertTrue(buff.name)

    def test_every_strength_row_is_a_rarity(self):
        for buff_key, buff in BUFF_REGISTRY.items():
            with self.subTest(buff=buff_key):
                self.assertLessEqual(set(buff.strengths), set(ext_const.RARITIES))

    def test_every_description_renders_at_every_rarity(self):
        for buff_key, buff in BUFF_REGISTRY.items():
            for rarity in ext_const.RARITIES:
                with self.subTest(buff=buff_key, rarity=rarity):
                    text = buff.describe(rarity)
                    self.assertNotIn("{", text)

    def test_a_card_shows_the_number_of_its_rarity(self):
        buff = BUFF_REGISTRY[ext_const.BUFF_ACCURACY_VS_TYPE]
        value = buff.strengths[ext_const.RARITY_RARE]

        self.assertIn(str(value), buff.describe(ext_const.RARITY_RARE))

    def test_a_pool_name_wins_over_the_plain_name(self):
        buff = BUFF_REGISTRY[ext_const.BUFF_ACCURACY_VS_TYPE]
        named = PreceptorDef(
            key=_TEST_PRECEPTOR_KEY, name="Test", assignments=(), base_points=0,
            buff_pool=(PoolEntry(buff.key, 1, name=_TEST_POOL_NAME),))

        with mock.patch.dict(PRECEPTOR_DB, {named.key: named}):
            self.assertEqual(buff_name(buff, _TEST_PRECEPTOR_KEY), _TEST_POOL_NAME)

    def test_an_entry_with_no_name_shows_the_plain_name(self):
        buff = BUFF_REGISTRY[ext_const.BUFF_ACCURACY_VS_TYPE]

        self.assertEqual(buff_name(buff, PRECEPTOR_ATTICUS_QUIN), buff.name)
        self.assertEqual(buff_name(buff, None), buff.name)



# ─── Shared fixture ─────────────────────────────────────────────────────────

class _QuinTest(EvenniaTest):
    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.crab = NPC_DB[_MUTANT_CRAB_KEY].create(location=self.room1)
        self.eye = NPC_DB[_FLOATING_EYE_KEY].create(location=self.room1)

    def _give_task(self, buff_key: str, rarity: str = ext_const.RARITY_COMMON,
                   picks_earned: int = 0) -> None:
        """A crab task that holds one buff."""
        task = {
            ext_const.FIELD_PRECEPTOR: PRECEPTOR_ATTICUS_QUIN,
            ext_const.FIELD_CREATURE_TYPE: creature_types.CREATURE_TYPE_CRAB,
            ext_const.FIELD_TOTAL: _TASK_TOTAL,
            ext_const.FIELD_KILLS: 0,
            ext_const.FIELD_STARTED_AT: 0.0,
            ext_const.FIELD_BUFFS: [{ext_const.CARD_KEY: buff_key, ext_const.CARD_RARITY: rarity}],
            ext_const.FIELD_PICKS_EARNED: picks_earned,
            ext_const.FIELD_BANKED_PICKS: 0,
            ext_const.FIELD_OFFER: None,
            ext_const.FIELD_PLAYTIME_AT_START: 0,
        }
        self.char1.attributes.add(ext_const.TASK_ATTR, task)

    def _context(self, attacker, target):
        """A real context, from the collector that combat uses."""
        handler = ensure_combat_handler(attacker)

        return ActionAttack(target.id)._build_context(handler, attacker, target)

    def _contribute(self, buff_key: str, context, bag) -> None:
        BUFF_REGISTRY[buff_key].contribute_modifiers(context, bag)



# ─── The combat buffs ───────────────────────────────────────────────────────

class AccuracyVsTypeTests(_QuinTest):

    def test_it_adds_the_levels_of_its_rarity_against_the_task_type(self):
        self._give_task(ext_const.BUFF_ACCURACY_VS_TYPE, ext_const.RARITY_RARE)
        buff = BUFF_REGISTRY[ext_const.BUFF_ACCURACY_VS_TYPE]
        context = self._context(self.char1, self.crab)

        resolve_action(context)

        channel = context.attacker_bag.channel(context.accuracy_channel())
        self.assertEqual(channel.flat_pre, buff.strengths[ext_const.RARITY_RARE])

    def test_it_does_nothing_against_another_type(self):
        self._give_task(ext_const.BUFF_ACCURACY_VS_TYPE)
        context = self._context(self.char1, self.eye)

        resolve_action(context)

        self.assertNotIn(context.accuracy_channel(), context.attacker_bag.touched_channels())

    def test_it_does_nothing_when_the_holder_defends(self):
        self._give_task(ext_const.BUFF_ACCURACY_VS_TYPE)
        context = self._context(self.crab, self.char1)

        self._contribute(ext_const.BUFF_ACCURACY_VS_TYPE, context, context.defender_bag)

        self.assertEqual(context.defender_bag.touched_channels(), ())


class DefenseSealTests(_QuinTest):

    def test_it_adds_defense_bonus_when_a_task_creature_attacks(self):
        self._give_task(ext_const.BUFF_DEFENSE_SEAL)
        buff = BUFF_REGISTRY[ext_const.BUFF_DEFENSE_SEAL]
        context = self._context(self.crab, self.char1)

        self.assertIn(buff, context.defender_rules)
        self._contribute(buff.key, context, context.defender_bag)

        channel = context.defender_bag.channel(combat_const.CHANNEL_DEFENSE_BONUS)
        self.assertEqual(channel.flat_pre, buff.value_at(ext_const.RARITY_COMMON))

    def test_it_does_nothing_when_the_holder_attacks(self):
        self._give_task(ext_const.BUFF_DEFENSE_SEAL)
        context = self._context(self.char1, self.crab)

        self._contribute(ext_const.BUFF_DEFENSE_SEAL, context, context.attacker_bag)

        self.assertEqual(context.attacker_bag.touched_channels(), ())


class MilestoneGrowthTests(_QuinTest):

    def test_the_first_milestone_gives_no_step(self):
        self._give_task(ext_const.BUFF_MILESTONE_GROWTH, picks_earned=1)
        context = self._context(self.char1, self.crab)

        self._contribute(ext_const.BUFF_MILESTONE_GROWTH, context, context.attacker_bag)

        self.assertEqual(context.attacker_bag.touched_channels(), ())

    def test_each_later_milestone_adds_one_step(self):
        picks_earned = ext_const.PICK_MILESTONE_COUNT
        self._give_task(ext_const.BUFF_MILESTONE_GROWTH, ext_const.RARITY_EPIC, picks_earned)
        buff = BUFF_REGISTRY[ext_const.BUFF_MILESTONE_GROWTH]
        context = self._context(self.char1, self.crab)

        self._contribute(buff.key, context, context.attacker_bag)

        expected = (picks_earned - 1) * buff.strengths[ext_const.RARITY_EPIC]
        accuracy = context.attacker_bag.channel(context.accuracy_channel())
        damage = context.attacker_bag.channel(context.damage_channel())
        self.assertEqual(accuracy.flat_pre, expected)
        self.assertEqual(damage.flat_pre, expected)


class LowHpMaxHitTests(_QuinTest):

    def setUp(self):
        super().setUp()
        self._give_task(ext_const.BUFF_LOW_HP_MAX_HIT)
        self.crab.max_hp = _FIXTURE_MAX_HP

    def _max_hit_post(self) -> int:
        context = self._context(self.char1, self.crab)
        self._contribute(ext_const.BUFF_LOW_HP_MAX_HIT, context, context.attacker_bag)

        return context.attacker_bag.channel(combat_const.CHANNEL_MAX_HIT).flat_post

    def test_it_adds_max_hit_under_the_line(self):
        line_hp = low_hp_max_hit.LOW_HP_LINE_PERCENT * _FIXTURE_MAX_HP // _PERCENT
        self.crab.hp = line_hp - 1
        buff = BUFF_REGISTRY[ext_const.BUFF_LOW_HP_MAX_HIT]

        self.assertEqual(self._max_hit_post(), buff.value_at(ext_const.RARITY_COMMON))

    def test_it_does_nothing_at_the_line(self):
        self.crab.hp = low_hp_max_hit.LOW_HP_LINE_PERCENT * _FIXTURE_MAX_HP // _PERCENT

        self.assertEqual(self._max_hit_post(), 0)


class BestOfTwoRollsTests(_QuinTest):

    def test_it_keeps_the_highest_roll(self):
        self._give_task(ext_const.BUFF_BEST_OF_TWO_ROLLS)
        rolls = list(range(best_of_two_rolls.DAMAGE_ROLL_COUNT))
        context = self._context(self.char1, self.crab)
        context.rng = _ScriptedRng(rolls)
        result = ActionResult()

        BUFF_REGISTRY[ext_const.BUFF_BEST_OF_TWO_ROLLS].roll_damage(context, result)

        self.assertEqual(result.damage, max(rolls))

    def test_the_kept_roll_decides_the_max_hit(self):
        # The highest roll comes FIRST, so the last call of the default roll
        # writes a lower face. The kept face must be the highest one.
        self._give_task(ext_const.BUFF_BEST_OF_TWO_ROLLS)
        rolls = sorted(range(best_of_two_rolls.DAMAGE_ROLL_COUNT), reverse=True)
        context = self._context(self.char1, self.crab)
        context.rng = _ScriptedRng(rolls)
        result = ActionResult()

        BUFF_REGISTRY[ext_const.BUFF_BEST_OF_TWO_ROLLS].roll_damage(context, result)

        self.assertEqual(result.rolled, max(rolls))

    def test_it_owns_the_damage_roll_against_the_task_type(self):
        self._give_task(ext_const.BUFF_BEST_OF_TWO_ROLLS)
        buff = BUFF_REGISTRY[ext_const.BUFF_BEST_OF_TWO_ROLLS]
        context = self._context(self.char1, self.crab)

        owner = _resolve_winners(context.attacker_rules).owner("roll_damage")

        self.assertIs(owner, buff)


class DamageForDefenseTests(_QuinTest):

    def test_it_raises_the_max_hit_of_the_holder(self):
        self._give_task(ext_const.BUFF_DAMAGE_FOR_DEFENSE, ext_const.RARITY_LEGENDARY)
        buff = BUFF_REGISTRY[ext_const.BUFF_DAMAGE_FOR_DEFENSE]
        context = self._context(self.char1, self.crab)

        self._contribute(buff.key, context, context.attacker_bag)

        channel = context.attacker_bag.channel(combat_const.CHANNEL_MAX_HIT)
        self.assertAlmostEqual(channel.augment_bonus, buff.strengths[ext_const.RARITY_LEGENDARY])

    def test_it_cuts_a_positive_defense_bonus(self):
        self._give_task(ext_const.BUFF_DAMAGE_FOR_DEFENSE)
        context = self._context(self.crab, self.char1)
        bonus_key = f"{context.attack_type}_defense_bonus"
        context.defender_stats = {bonus_key: _FIXTURE_DEFENSE_BONUS}

        self._contribute(ext_const.BUFF_DAMAGE_FOR_DEFENSE, context, context.defender_bag)

        channel = context.defender_bag.channel(combat_const.CHANNEL_DEFENSE_BONUS)
        self.assertAlmostEqual(channel.augment_bonus, -damage_for_defense.DEFENSE_BONUS_CUT)

    def test_it_never_cuts_a_bonus_that_is_not_positive(self):
        self._give_task(ext_const.BUFF_DAMAGE_FOR_DEFENSE)
        context = self._context(self.crab, self.char1)
        bonus_key = f"{context.attack_type}_defense_bonus"
        context.defender_stats = {bonus_key: -_FIXTURE_DEFENSE_BONUS}

        self._contribute(ext_const.BUFF_DAMAGE_FOR_DEFENSE, context, context.defender_bag)

        self.assertEqual(context.defender_bag.touched_channels(), ())



# ─── The task buff and the par clock ────────────────────────────────────────

class ParTimePointsTests(_QuinTest):

    def setUp(self):
        super().setUp()
        self.playtime = _PLAYTIME_AT_ASSIGN
        patcher = mock.patch.object(
            BlackoutCharacter, "playtime_seconds",
            new_callable=mock.PropertyMock, side_effect=lambda: self.playtime)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.handler = self.char1.exterminator
        self.handler.assign(PRECEPTOR_ATTICUS_QUIN, rng=random.Random(_TASK_SEED))
        self.handler.grant_buff(ext_const.BUFF_PAR_TIME_POINTS, ext_const.RARITY_RARE)

    def _finish(self) -> int:
        """Bring the task to its last kill, and give the points it paid."""
        task = self.handler.task()
        task[ext_const.FIELD_KILLS] = self.handler.total() - 1
        self.char1.attributes.add(ext_const.TASK_ATTR, task)
        points_before = self.handler.points()

        self.handler.record_kill((self.handler.creature_type(),), 0)

        return self.handler.points() - points_before

    def _payout(self) -> int:
        """The points of a task with no buff, at streak 1."""
        base = PRECEPTOR_DB[PRECEPTOR_ATTICUS_QUIN].base_points

        return base * streak_multiplier(1)

    def test_the_par_time_comes_from_the_assignment(self):
        assignment = assignment_for(PRECEPTOR_ATTICUS_QUIN, self.handler.creature_type())

        expected = self.handler.total() * assignment.par_seconds_per_kill
        self.assertEqual(self.handler.par_seconds(), expected)

    def test_the_clock_counts_playtime_since_the_assignment(self):
        self.playtime = _PLAYTIME_AT_ASSIGN + self.handler.par_seconds()

        self.assertEqual(self.handler.elapsed_seconds(), self.handler.par_seconds())

    def test_a_task_inside_par_pays_the_bonus(self):
        self.playtime = _PLAYTIME_AT_ASSIGN + self.handler.par_seconds()
        buff = BUFF_REGISTRY[ext_const.BUFF_PAR_TIME_POINTS]
        payout = self._payout()

        earned = self._finish()

        bonus = math.floor(payout * buff.strengths[ext_const.RARITY_RARE])
        self.assertEqual(earned, payout + bonus)

    def test_a_task_over_par_pays_no_bonus(self):
        self.playtime = _PLAYTIME_AT_ASSIGN + self.handler.par_seconds() + 1

        self.assertEqual(self._finish(), self._payout())

    def test_the_card_names_the_par_time(self):
        buff = BUFF_REGISTRY[ext_const.BUFF_PAR_TIME_POINTS]
        minutes = self.handler.par_seconds() // ext_const.SECONDS_PER_MINUTE

        text = buff.describe(ext_const.RARITY_RARE, self.char1)

        self.assertIn(f"{minutes} min", text)



# ─── The offer and the held buffs line ──────────────────────────────────────

class QuinOfferTests(_QuinTest):

    def test_a_new_task_offers_cards_from_the_pool_of_quin(self):
        handler = self.char1.exterminator
        handler.assign(PRECEPTOR_ATTICUS_QUIN, rng=random.Random(_TASK_SEED))
        pool_keys = {entry.buff_key for entry in PRECEPTOR_DB[PRECEPTOR_ATTICUS_QUIN].buff_pool}

        offer = handler.offer()

        self.assertEqual(len(offer), min(len(pool_keys), handler.cards_per_offer()))

        for card in offer:
            with self.subTest(card=card[ext_const.CARD_KEY]):
                self.assertIn(card[ext_const.CARD_KEY], pool_keys)

    def test_the_task_text_names_each_held_buff_and_its_rarity(self):
        self._give_task(ext_const.BUFF_DEFENSE_SEAL, ext_const.RARITY_EPIC)
        buff = BUFF_REGISTRY[ext_const.BUFF_DEFENSE_SEAL]

        text = " ".join(self.char1.exterminator.summary_lines())

        self.assertIn(buff.name, text)
        self.assertIn(ext_const.RARITY_NAMES[ext_const.RARITY_EPIC], text)
