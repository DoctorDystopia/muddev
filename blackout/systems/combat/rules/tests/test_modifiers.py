"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Tests for the modifier channel accumulators and appliers.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat
"""

import unittest

from systems.combat import combat_calc
from systems.combat import constants as const
from systems.combat.rules.modifiers import (
    ModifierBag,
    apply_to_int,
    apply_to_level,
    apply_to_scalar,
    clamp_damage,
    clamp_hit_chance,
)


# ─── Private constant definitions ────────────────────────────────────────────

# A mid-range level with no special properties, chosen so both multiplier
# stages produce a fractional intermediate and the floors are observable.
_SAMPLE_LEVEL = 50

# A level low enough that a small flat boost is a large relative change.
_LOW_LEVEL = 10

# Ten percent, as a contributor declares it.
_TEN_PERCENT = 0.10

# No stance boost. Passed explicitly rather than defaulted so the tests read
# as "this is the style contribution" rather than "this argument is noise".
_NO_STANCE = 0


class TestChannelValidation(unittest.TestCase):
    """A typo'd channel key must fail loudly, not accumulate into nothing."""

    def test_a_declared_channel_is_accepted(self):
        bag = ModifierBag()

        bag.add_flat_pre(const.CHANNEL_BRAWN_LEVEL, 1)

        self.assertEqual(bag.channel(const.CHANNEL_BRAWN_LEVEL).flat_pre, 1)

    def test_an_undeclared_channel_raises(self):
        bag = ModifierBag()

        with self.assertRaises(ValueError):
            bag.add_flat_pre("brawn_levl", 1)

    def test_the_reserved_attack_speed_channel_is_not_writable(self):
        # Declared as a constant so the key is not invented twice, but
        # deliberately not wired into the swing. Writing to it must fail
        # rather than silently do nothing.
        bag = ModifierBag()

        with self.assertRaises(ValueError):
            bag.add_flat_pre(const.CHANNEL_ATTACK_SPEED, 1)

    def test_an_untouched_bag_reports_no_channels(self):
        bag = ModifierBag()

        self.assertEqual(bag.touched_channels(), ())


class TestLevelChannel(unittest.TestCase):
    """apply_to_level must reproduce the OSRS floor sequence exactly.

    This class is the contract between the modifier layer and combat_calc. If
    any of it breaks, the default swing path has stopped being OSRS.
    """

    def test_empty_bag_is_the_identity(self):
        bag = ModifierBag()

        result = apply_to_level(bag, const.CHANNEL_BRAWN_LEVEL, _LOW_LEVEL,
                                _NO_STANCE)

        self.assertEqual(result, combat_calc.effective_level(_LOW_LEVEL))

    def test_empty_bag_still_carries_the_stance_bonus(self):
        bag = ModifierBag()
        stance = 3

        result = apply_to_level(bag, const.CHANNEL_BRAWN_LEVEL, _LOW_LEVEL,
                                stance)

        expected = combat_calc.effective_level(_LOW_LEVEL, stance_bonus=stance)
        self.assertEqual(result, expected)

    def test_flat_pre_matches_potion_boost(self):
        bag = ModifierBag()
        boost = 7
        bag.add_flat_pre(const.CHANNEL_BRAWN_LEVEL, boost)

        result = apply_to_level(bag, const.CHANNEL_BRAWN_LEVEL, _SAMPLE_LEVEL,
                                _NO_STANCE)

        expected = combat_calc.effective_level(_SAMPLE_LEVEL,
                                               potion_boost=boost)
        self.assertEqual(result, expected)

    def test_augment_bonus_matches_augmentation_mult(self):
        bag = ModifierBag()
        bag.add_augment_bonus(const.CHANNEL_BRAWN_LEVEL, _TEN_PERCENT)

        result = apply_to_level(bag, const.CHANNEL_BRAWN_LEVEL, _SAMPLE_LEVEL,
                                _NO_STANCE)

        expected = combat_calc.effective_level(
            _SAMPLE_LEVEL,
            augmentation_mult=const.AUGMENTATION_DEFAULT_MULT + _TEN_PERCENT,
        )
        self.assertEqual(result, expected)

    def test_set_bonus_matches_set_mult(self):
        bag = ModifierBag()
        bag.add_set_bonus(const.CHANNEL_BRAWN_LEVEL, _TEN_PERCENT)

        result = apply_to_level(bag, const.CHANNEL_BRAWN_LEVEL, _SAMPLE_LEVEL,
                                _NO_STANCE)

        expected = combat_calc.effective_level(
            _SAMPLE_LEVEL,
            set_mult=const.SET_DEFAULT_MULT + _TEN_PERCENT,
        )
        self.assertEqual(result, expected)

    def test_flat_post_adds_to_the_stance_bonus(self):
        bag = ModifierBag()
        post = 4
        stance = 3
        bag.add_flat_post(const.CHANNEL_BRAWN_LEVEL, post)

        result = apply_to_level(bag, const.CHANNEL_BRAWN_LEVEL, _SAMPLE_LEVEL,
                                stance)

        expected = combat_calc.effective_level(_SAMPLE_LEVEL,
                                               stance_bonus=stance + post)
        self.assertEqual(result, expected)

    def test_flat_post_is_not_scaled_by_either_stage(self):
        # A flat_post of N must raise the result by exactly N no matter what
        # the multipliers are. That is the difference between it and flat_pre,
        # and it is the reason both exist.
        post = 5
        stage_bag = ModifierBag()
        stage_bag.add_augment_bonus(const.CHANNEL_BRAWN_LEVEL, _TEN_PERCENT)
        both_bag = ModifierBag()
        both_bag.add_augment_bonus(const.CHANNEL_BRAWN_LEVEL, _TEN_PERCENT)
        both_bag.add_flat_post(const.CHANNEL_BRAWN_LEVEL, post)

        without = apply_to_level(stage_bag, const.CHANNEL_BRAWN_LEVEL,
                                 _SAMPLE_LEVEL, _NO_STANCE)
        with_post = apply_to_level(both_bag, const.CHANNEL_BRAWN_LEVEL,
                                   _SAMPLE_LEVEL, _NO_STANCE)

        self.assertEqual(with_post - without, post)

    def test_flat_pre_is_scaled_by_the_augment_stage(self):
        # The mirror of the test above: flat_pre goes in BEFORE the
        # multipliers, so a large enough multiplier must amplify it past its
        # own value. This is what makes the glass cannon amulet's choice of
        # flat_pre a meaningful one.
        pre = 20
        bag = ModifierBag()
        bag.add_flat_pre(const.CHANNEL_BRAWN_LEVEL, pre)
        bag.add_augment_bonus(const.CHANNEL_BRAWN_LEVEL, _TEN_PERCENT)
        baseline_bag = ModifierBag()
        baseline_bag.add_augment_bonus(const.CHANNEL_BRAWN_LEVEL, _TEN_PERCENT)

        without = apply_to_level(baseline_bag, const.CHANNEL_BRAWN_LEVEL,
                                 _SAMPLE_LEVEL, _NO_STANCE)
        with_pre = apply_to_level(bag, const.CHANNEL_BRAWN_LEVEL,
                                  _SAMPLE_LEVEL, _NO_STANCE)

        self.assertGreater(with_pre - without, pre)

    def test_both_stages_keep_both_floors(self):
        # The nested floor between the two multiplier stages is load-bearing:
        # it is why exactly two named stages exist rather than N. Assert the
        # nested value AND that it differs from the single-floor value, so a
        # refactor that collapses the stages fails here instead of shifting
        # every damage number in the game by one.
        bag = ModifierBag()
        bag.add_augment_bonus(const.CHANNEL_BRAWN_LEVEL, 0.15)
        bag.add_set_bonus(const.CHANNEL_BRAWN_LEVEL, 0.15)

        result = apply_to_level(bag, const.CHANNEL_BRAWN_LEVEL, 45, _NO_STANCE)

        nested = int(int(45 * 1.15) * 1.15) + const.EFFECTIVE_LEVEL_FLOOR_8
        collapsed = int(45 * 1.15 * 1.15) + const.EFFECTIVE_LEVEL_FLOOR_8
        self.assertEqual(result, nested)
        self.assertNotEqual(nested, collapsed)

    def test_contributions_are_order_independent(self):
        first = ModifierBag()
        first.add_flat_pre(const.CHANNEL_BRAWN_LEVEL, 3)
        first.add_augment_bonus(const.CHANNEL_BRAWN_LEVEL, _TEN_PERCENT)
        second = ModifierBag()
        second.add_augment_bonus(const.CHANNEL_BRAWN_LEVEL, _TEN_PERCENT)
        second.add_flat_pre(const.CHANNEL_BRAWN_LEVEL, 3)

        first_result = apply_to_level(first, const.CHANNEL_BRAWN_LEVEL,
                                      _SAMPLE_LEVEL, _NO_STANCE)
        second_result = apply_to_level(second, const.CHANNEL_BRAWN_LEVEL,
                                       _SAMPLE_LEVEL, _NO_STANCE)

        self.assertEqual(first_result, second_result)

    def test_stage_bonuses_are_additive_not_multiplicative(self):
        # Two +10% contributors into the SAME stage give x1.20, not x1.21.
        # Additive within a stage is what keeps the result independent of
        # which item was equipped first.
        bag = ModifierBag()
        bag.add_augment_bonus(const.CHANNEL_BRAWN_LEVEL, _TEN_PERCENT)
        bag.add_augment_bonus(const.CHANNEL_BRAWN_LEVEL, _TEN_PERCENT)

        accumulator = bag.channel(const.CHANNEL_BRAWN_LEVEL)

        self.assertAlmostEqual(accumulator.augment_mult(), 1.20)

    def test_channels_do_not_leak_into_each_other(self):
        bag = ModifierBag()
        bag.add_flat_pre(const.CHANNEL_BRAWN_LEVEL, 10)

        strike = apply_to_level(bag, const.CHANNEL_STRIKE_LEVEL,
                                _SAMPLE_LEVEL, _NO_STANCE)

        self.assertEqual(strike, combat_calc.effective_level(_SAMPLE_LEVEL))


class TestScalarChannels(unittest.TestCase):
    """apply_to_int / apply_to_scalar and the two clamps."""

    def test_empty_bag_is_the_identity_on_an_int(self):
        bag = ModifierBag()

        self.assertEqual(apply_to_int(bag, const.CHANNEL_MAX_HIT, 12), 12)

    def test_apply_to_int_is_flat_then_mult_then_flat(self):
        bag = ModifierBag()
        bag.add_flat_pre(const.CHANNEL_MAX_HIT, 2)
        bag.add_augment_bonus(const.CHANNEL_MAX_HIT, 0.50)
        bag.add_flat_post(const.CHANNEL_MAX_HIT, 1)

        result = apply_to_int(bag, const.CHANNEL_MAX_HIT, 10)

        # (10 + 2) * 1.5 = 18, + 1 = 19. Not (10 * 1.5) + 2 + 1 = 18.
        self.assertEqual(result, 19)

    def test_apply_to_int_uses_one_floor_not_two(self):
        bag = ModifierBag()
        bag.add_augment_bonus(const.CHANNEL_MAX_HIT, 0.15)
        bag.add_set_bonus(const.CHANNEL_MAX_HIT, 0.15)

        result = apply_to_int(bag, const.CHANNEL_MAX_HIT, 45)

        self.assertEqual(result, int(45 * 1.15 * 1.15))

    def test_apply_to_int_permits_a_negative_result(self):
        # A defense bonus is legitimately negative, so this applier must not
        # floor. Only the damage-bearing channels get clamp_damage, and their
        # caller applies it.
        bag = ModifierBag()
        bag.add_flat_post(const.CHANNEL_DEFENSE_BONUS, -10)

        result = apply_to_int(bag, const.CHANNEL_DEFENSE_BONUS, 2)

        self.assertEqual(result, -8)

    def test_apply_to_scalar_does_not_floor(self):
        bag = ModifierBag()
        bag.add_augment_bonus(const.CHANNEL_HIT_CHANCE, 0.50)

        result = apply_to_scalar(bag, const.CHANNEL_HIT_CHANCE, 0.4)

        self.assertAlmostEqual(result, 0.6)

    def test_clamp_damage_floors_a_negative_at_zero(self):
        self.assertEqual(clamp_damage(-5), const.ACTION_DAMAGE_FLOOR)

    def test_clamp_damage_leaves_a_positive_alone(self):
        self.assertEqual(clamp_damage(7), 7)

    def test_hit_chance_clamp_holds_the_floor(self):
        self.assertEqual(clamp_hit_chance(-1.0), const.HIT_CHANCE_FLOOR)

    def test_hit_chance_clamp_cannot_reach_certainty(self):
        # A saturating multiplier must not become "this weapon never misses" —
        # that is a roll_accuracy seam override, not a modifier.
        clamped = clamp_hit_chance(50.0)

        self.assertEqual(clamped, const.HIT_CHANCE_CEILING)
        self.assertLess(clamped, 1.0)

    def test_hit_chance_clamp_leaves_an_in_band_value_alone(self):
        self.assertAlmostEqual(clamp_hit_chance(0.42), 0.42)
