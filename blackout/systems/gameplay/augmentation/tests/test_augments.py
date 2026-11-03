"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The augments, the handler, the drain, and the modifiers
             (DESIGN-0015, Phase 2). The sustain loop is on hold, so no test
             here names a free window, an anneal, or a flick.
Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.augmentation
"""

import math
import random
import unittest

from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import pool
from systems.gameplay.augmentation.augment_defs.base_augment import BaseAugment
from systems.gameplay.augmentation.handler import (
    AUGMENT_HANDLER_KEY,
    ensure_augment_handler,
    get_augment_handler_for,
    resistance_for,
)
from systems.gameplay.augmentation.registry import (
    AUGMENT_REGISTRY,
    augments_in_order,
    find_augment,
)
from systems.gameplay.augmentation.rules import AugmentModifierRules, active_rules
from systems.gameplay.augmentation.tests import support
from systems.gameplay.combat import constants as combat_const
from systems.gameplay.combat.combat_calc import effective_level
from systems.gameplay.combat.rules.context import ActionContext
from systems.gameplay.combat.rules.rule_defs.base_rules import BaseActionRules
from systems.gameplay.progression.skills.constants import (
    SKILL_KEY_AUGMENTATION,
    SKILL_KEY_BRAWN,
    SKILL_KEY_DEFENSE,
    SKILL_KEY_FORTITUDE,
    SKILL_KEY_STRIKE,
)
from typeclasses.characters import Character as BlackoutCharacter


# A level past every placeholder unlock, so each augment lights.
_A_LEVEL = 50

# The accuracy axis of a melee swing, for the effective level check.
_A_STRIKE_LEVEL = 40


def _first_augment():
    """The first augment of the rail order: the one with no unlock."""
    return augments_in_order()[0]


def _levels() -> dict:
    return {
        SKILL_KEY_STRIKE: _A_STRIKE_LEVEL,
        SKILL_KEY_BRAWN: 35,
        SKILL_KEY_DEFENSE: 20,
        SKILL_KEY_FORTITUDE: 30,
    }


def _context(attacker_rules=()) -> ActionContext:
    """A melee context from plain dicts, with no Evennia objects."""
    return ActionContext(
        attacker=None,
        defender=None,
        weapon=None,
        weapon_data={},
        style={},
        attack_type=combat_const.MELEE_ATTACK_TYPE_STAB,
        attacker_stats={"melee_stab_attack_bonus": 5, "melee_strength_bonus": 4},
        defender_stats={"melee_stab_defense_bonus": 2},
        attacker_levels=_levels(),
        defender_levels=_levels(),
        stance_boost={},
        attacker_rules=tuple(attacker_rules),
        defender_rules=(),
        rng=random.Random(7),
    )


class TestAugmentRegistry(unittest.TestCase):
    """Auto-discovery and name resolution, the shape of the aura registry."""

    def test_every_registered_augment_has_its_fields(self):
        for key, augment in AUGMENT_REGISTRY.items():
            with self.subTest(augment=key):
                self.assertEqual(augment.key, key)
                self.assertIsInstance(augment, BaseAugment)
                self.assertTrue(augment.name)
                self.assertIn(augment.family, aug_const.AUG_FAMILIES)
                self.assertGreater(augment.drain, 0)
                self.assertGreaterEqual(augment.pct_per_level, 0)

    def test_the_base_augment_is_not_registered(self):
        self.assertNotIn(BaseAugment.key, AUGMENT_REGISTRY)

    def test_every_family_has_an_augment(self):
        families = {augment.family for augment in AUGMENT_REGISTRY.values()}

        for family in (aug_const.FAMILY_ACCURACY, aug_const.FAMILY_DAMAGE,
                       aug_const.FAMILY_DEFENSE):
            with self.subTest(family=family):
                self.assertIn(family, families)

    def test_find_accepts_the_key_and_the_name(self):
        for key, augment in AUGMENT_REGISTRY.items():
            with self.subTest(augment=key):
                self.assertIs(find_augment(key), augment)
                self.assertIs(find_augment(augment.name.lower()), augment)

    def test_find_rejects_an_unknown_name(self):
        self.assertIsNone(find_augment("no such augment"))

    def test_the_order_puts_the_open_augment_first(self):
        ordered = augments_in_order()

        self.assertEqual(ordered[0].unlock_level, aug_const.NO_UNLOCK_LEVEL)
        unlocks = [augment.unlock_level for augment in ordered]
        self.assertEqual(unlocks, sorted(unlocks))


class TestStepDial(unittest.TestCase):
    """Step 1 gives a share of the strength for the same share of the drain."""

    def test_the_top_step_gives_the_whole_bonus(self):
        for key, augment in AUGMENT_REGISTRY.items():
            with self.subTest(augment=key):
                whole = augment.pct_per_level * _A_LEVEL
                self.assertAlmostEqual(augment.bonus_for(_A_LEVEL, aug_const.AUG_STEPS), whole)
                self.assertAlmostEqual(augment.drain_for(aug_const.AUG_STEPS), augment.drain)

    def test_a_lower_step_scales_the_bonus_and_the_drain_alike(self):
        augment = _first_augment()
        step = aug_const.AUG_STEP_MIN
        share = step / aug_const.AUG_STEPS

        self.assertAlmostEqual(
            augment.bonus_for(_A_LEVEL, step),
            augment.bonus_for(_A_LEVEL, aug_const.AUG_STEPS) * share)
        self.assertAlmostEqual(augment.drain_for(step), augment.drain * share)


class TestAugmentUnlock(EvenniaTest):

    character_typeclass = BlackoutCharacter

    def _gated(self):
        """An augment with an unlock level, or None when every one is open."""
        for augment in augments_in_order():
            if augment.unlock_level > aug_const.NO_UNLOCK_LEVEL:
                return augment

        return None

    def test_refused_below_the_unlock_level(self):
        augment = self._gated()

        if augment is None:
            self.skipTest("no augment has an unlock level")

        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, augment.unlock_level - 1)

        allowed, reason = augment.can_activate(self.char1)

        self.assertFalse(allowed)
        self.assertIn(str(augment.unlock_level), reason)

    def test_allowed_at_the_unlock_level(self):
        augment = self._gated()

        if augment is None:
            self.skipTest("no augment has an unlock level")

        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, augment.unlock_level)

        allowed, _reason = augment.can_activate(self.char1)

        self.assertTrue(allowed)

    def test_an_open_augment_needs_no_level(self):
        augment = _first_augment()

        allowed, _reason = augment.can_activate(self.char1)

        self.assertTrue(allowed)


class _HandlerTest(EvenniaTest):
    """A holder at a known level, with a full pool and a handler."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, _A_LEVEL)
        pool.restore(self.char1)
        self.augment = _first_augment()
        self.handler = ensure_augment_handler(self.char1)

    def tearDown(self):
        handler = get_augment_handler_for(self.char1)

        if handler is not None:
            handler.stop_handler()

        super().tearDown()

    def _ticks_for_one_point(self, step: int) -> int:
        """The ticks until the counter first passes the resistance."""
        drain = self.augment.drain_for(step)
        resistance = resistance_for(self.char1)

        return math.ceil(resistance / drain)


class TestHandlerLitSet(_HandlerTest):

    def test_a_light_adds_the_augment_at_its_step(self):
        was_lit = self.handler.light(self.augment, aug_const.AUG_STEP_MIN)

        self.assertFalse(was_lit)
        self.assertTrue(self.handler.is_lit(self.augment.key))
        self.assertEqual(self.handler.step_of(self.augment.key), aug_const.AUG_STEP_MIN)

    def test_a_second_light_is_a_restep(self):
        self.handler.light(self.augment, aug_const.AUG_STEP_MIN)

        was_lit = self.handler.light(self.augment, aug_const.AUG_STEPS)

        self.assertTrue(was_lit)
        self.assertEqual(self.handler.step_of(self.augment.key), aug_const.AUG_STEPS)

    def test_the_lit_set_keeps_the_rail_order(self):
        wanted = support.one_of_each_group(augments_in_order())

        for augment in reversed(wanted):
            self.handler.light(augment, aug_const.AUG_STEPS)

        lit_keys = [augment.key for augment, _step in self.handler.lit_augments()]

        self.assertEqual(lit_keys, [augment.key for augment in wanted])

    def test_a_put_out_removes_one(self):
        self.handler.light(self.augment, aug_const.AUG_STEPS)

        was_lit = self.handler.put_out(self.augment.key)

        self.assertTrue(was_lit)
        self.assertFalse(self.handler.is_lit(self.augment.key))

    def test_the_handler_is_the_augments_accessor(self):
        self.assertIs(self.char1.augments, self.handler)
        self.assertEqual(self.handler.key, AUGMENT_HANDLER_KEY)


class TestHandlerDrain(_HandlerTest):
    """The OSRS counter: one point goes when the counter passes the resistance."""

    def test_one_point_goes_when_the_counter_passes_the_resistance(self):
        step = aug_const.AUG_STEPS
        self.handler.light(self.augment, step)
        before = pool.current(self.char1)
        ticks = self._ticks_for_one_point(step)

        for _ in range(ticks - 1):
            self.handler.tick()

        self.assertEqual(pool.current(self.char1), before)

        self.handler.tick()

        self.assertEqual(pool.current(self.char1), before - aug_const.AUG_DRAIN_POINT)

    def test_a_lower_step_drains_slower(self):
        low = self._ticks_for_one_point(aug_const.AUG_STEP_MIN)
        high = self._ticks_for_one_point(aug_const.AUG_STEPS)

        self.assertGreater(low, high)

    def test_two_lit_augments_drain_together(self):
        ordered = augments_in_order()

        if len(ordered) < 2:
            self.skipTest("one augment only")

        first, second = ordered[0], ordered[1]
        self.handler.light(first, aug_const.AUG_STEPS)
        self.handler.light(second, aug_const.AUG_STEPS)
        before = pool.current(self.char1)
        drain = first.drain_for(aug_const.AUG_STEPS) + second.drain_for(aug_const.AUG_STEPS)
        ticks = math.ceil(resistance_for(self.char1) / drain)

        for _ in range(ticks):
            self.handler.tick()

        self.assertEqual(pool.current(self.char1), before - aug_const.AUG_DRAIN_POINT)

    def test_nothing_lit_stops_the_handler(self):
        self.handler.tick()

        self.assertIsNone(get_augment_handler_for(self.char1))

    def test_an_empty_pool_puts_every_augment_out(self):
        step = aug_const.AUG_STEPS
        self.handler.light(self.augment, step)
        pool.spend(self.char1, pool.maximum(self.char1) - aug_const.AUG_DRAIN_POINT)
        ticks = self._ticks_for_one_point(step)

        for _ in range(ticks):
            self.handler.tick()

        self.assertEqual(pool.current(self.char1), aug_const.GRIT_EMPTY)
        self.assertIsNone(get_augment_handler_for(self.char1))

    def test_a_dead_holder_puts_every_augment_out(self):
        self.handler.light(self.augment, aug_const.AUG_STEPS)
        self.char1.hp = 0

        self.handler.tick()

        self.assertIsNone(get_augment_handler_for(self.char1))

    def test_the_resistance_reads_the_gear_bonus(self):
        base = resistance_for(self.char1)

        self.assertEqual(base, aug_const.AUG_DRAIN_BASE)


class TestAugmentRules(_HandlerTest):
    """The swing reads the lit set, and the bonus lands on the channel."""

    def test_nothing_lit_gives_no_rules(self):
        self.assertEqual(active_rules(self.char1), ())

    def test_one_rule_for_each_lit_augment_that_reaches_an_action(self):
        wanted = support.one_of_each_group(augments_in_order())

        for augment in wanted:
            self.handler.light(augment, aug_const.AUG_STEPS)

        rules = active_rules(self.char1)
        reaching = [augment for augment in wanted
                    if augment.family != aug_const.FAMILY_MODIFIER]

        self.assertEqual(len(rules), len(reaching))

        for rule in rules:
            with self.subTest(rule=rule.key):
                self.assertIsInstance(rule, AugmentModifierRules)
                self.assertEqual(rule.priority, combat_const.RULES_PRIORITY_MODIFIER)

    def test_the_bonus_is_the_level_times_the_rate_at_the_step(self):
        step = aug_const.AUG_STEP_MIN
        self.handler.light(self.augment, step)

        rule = active_rules(self.char1)[0]

        self.assertAlmostEqual(rule.bonus, self.augment.bonus_for(_A_LEVEL, step))

    def test_the_effective_level_matches_the_augmentation_multiplier(self):
        """The bonus lands on the accuracy channel through the OSRS formula."""
        accuracy = [augment for augment in augments_in_order()
                    if augment.family == aug_const.FAMILY_ACCURACY][0]
        bonus = accuracy.bonus_for(_A_LEVEL, aug_const.AUG_STEPS)
        rule = AugmentModifierRules(accuracy, bonus)
        context = _context(attacker_rules=(rule,))

        rule.contribute_modifiers(context, context.attacker_bag)
        got = BaseActionRules().effective_attack_level(context)

        expected = effective_level(
            _A_STRIKE_LEVEL,
            augmentation_mult=combat_const.AUGMENTATION_DEFAULT_MULT + bonus)
        self.assertEqual(got, expected)
        self.assertGreater(got, effective_level(_A_STRIKE_LEVEL))

    def test_the_defense_augment_lands_on_the_defense_channel(self):
        defense = [augment for augment in augments_in_order()
                   if augment.family == aug_const.FAMILY_DEFENSE][0]
        context = _context()

        channel = defense.channel_for(context)

        self.assertEqual(channel, combat_const.CHANNEL_DEFENSE_LEVEL)


class TestDeathPutsAugmentsOut(EvenniaTest):

    character_typeclass = BlackoutCharacter

    def test_at_death_leaves_no_handler(self):
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, _A_LEVEL)
        pool.restore(self.char1)
        handler = ensure_augment_handler(self.char1)
        handler.light(_first_augment(), aug_const.AUG_STEPS)

        self.char1._put_out_augments()

        self.assertIsNone(get_augment_handler_for(self.char1))
