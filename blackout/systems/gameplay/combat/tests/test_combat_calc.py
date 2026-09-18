"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Pure-function suite for OSRS-exact math in systems/gameplay/combat/combat_calc.py.
             No Django, DB, or entity — just arithmetic truth.

             Wrapped in a TestCase so `evennia test` (Django/unittest
             discovery) collects it. As bare module-level functions these
             were invisible to that runner and only ran under a separate
             pytest invocation that could not run the rest of the suite.
"""

import random
from unittest import TestCase

from systems.gameplay.combat.combat_calc import (
    attack_roll,
    defense_roll,
    effective_level,
    hit_chance,
    max_hit,
    resolve_melee_swing,
    resolve_projectile_shot,
    roll_damage,
)

# ─── effective_level ──────────────────────────────────────────────────────


class TestCombatCalc(TestCase):
    """Pure OSRS math. No Django, DB, or entity -- just arithmetic truth."""

    def test_effective_level_no_bonuses_10(self):
        assert effective_level(10) == 18


    def test_effective_level_max_with_stance(self):
        assert effective_level(127, stance_bonus=3) == 138


    def test_effective_level_with_set_multiplier(self):
        assert effective_level(50, set_mult=1.10) == 63


    # ─── max_hit ─────────────────────────────────────────────────────


    def test_max_hit_zero_equip(self):
        assert max_hit(110, 0) == 11  # canonical OSRS: bare-fist at 99+8+3 = 110 -> 11


    def test_max_hit_level_one(self):
        assert max_hit(1, 0) == 0


    # ─── attack_roll / defense_roll ────────────────────────────


    def test_attack_roll_no_equip(self):
        assert attack_roll(110, 0) == 110 * 64


    def test_defense_roll_equalizes_attack(self):
        assert defense_roll(110, 0) == attack_roll(110, 0)


    # ─── hit_chance ───────────────────────────────────────────────────────────


    def test_hit_chance_equal_rolls_approx_half(self):
        r = attack_roll(10, 0)
        p = hit_chance(r, r)
        assert 0.49 < p < 0.50


    def test_hit_chance_double_attacker_greater(self):
        r = attack_roll(10, 0)
        p = hit_chance(2 * r, r)
        assert 0.74 < p < 0.76


    def test_defender_equip_bonus_lowers_hit_chance(self):
        """The defender's own equipment must move the accuracy curve.

        Guards the arithmetic side of the audit bug where the swing pipeline fed
        the *attacker's* equipment into defense_roll, so a defender's armour was
        mathematically inert. See test_combat_handler.TestDefenderBonuses for the
        plumbing side.
        """
        r_atk = attack_roll(50, 20)
        bare = hit_chance(r_atk, defense_roll(50, 0))
        armoured = hit_chance(r_atk, defense_roll(50, 100))

        assert armoured < bare


    # ─── roll_damage ───────────────────────────────────────────────────────────


    def test_roll_damage_seeded_no_zero(self):
        rng = random.Random(42)
        dmgs = [roll_damage(10, rng=rng) for _ in range(50)]
        assert all(0 <= d <= 10 for d in dmgs)


    def test_roll_damage_can_produce_zero(self):
        rng = random.Random(7)
        dmgs = [roll_damage(4, rng=rng) for _ in range(100)]
        assert 0 in dmgs


    # ─── resolve_melee_swing ──────────────────────────────────────────────────


    def test_resolve_swing_miss_returns_zero(self):
        rng = random.Random(12345)
        result = resolve_melee_swing(5, 0, 5, 0, 127, 64, rng=rng)
        assert result["hit"] is False
        assert result["damage"] == 0
        assert result["hit_prob"] > 0


    def test_resolve_swing_hit_produces_damage(self):
        rng = random.Random(1)
        result = resolve_melee_swing(110, 10, 110, 130, 5, 3, rng=rng)
        assert result["hit"] is True
        assert result["damage"] > 0


class TestProjectileShot(TestCase):
    """resolve_projectile_shot against hand-worked OSRS rows.

    The formulas are the melee ones. What these assert is that the SHOT reads
    the right inputs: the Guns level and a light/standard/heavy attack bonus
    for accuracy, the Ballistics level and the projectile strength bonus for
    damage. A shot that silently read a melee number would still return a
    plausible integer, which is exactly why it needs asserting.
    """

    def test_a_shot_uses_the_same_attack_roll_as_a_swing(self):
        """One formula, two callers. The roll is attack_roll either way."""
        rng = random.Random(1)
        result = resolve_projectile_shot(110, 8, 110, 7, 5, 3, rng=rng)

        expected = hit_chance(attack_roll(110, 8), defense_roll(5, 3))

        self.assertAlmostEqual(result["hit_prob"], expected)

    def test_the_damage_ceiling_comes_from_ballistics_and_the_ammo(self):
        """Never from Guns, and never from the bow.

        Forced to hit with a seed, then the damage is checked against the
        ceiling max_hit gives for the BALLISTICS level and the AMMUNITION's
        bonus. The Guns level here is deliberately far higher, so a shot that
        read the accuracy axis for damage would exceed this bound.
        """
        rng = random.Random(7)
        result = resolve_projectile_shot(127, 40, 20, 7, 1, 0, rng=rng)

        ceiling = max_hit(20, 7)

        self.assertTrue(result["hit"])
        self.assertLessEqual(result["damage"], ceiling)

    def test_a_shot_and_a_swing_agree_on_identical_inputs(self):
        """The two resolvers are one formula set, so identical inputs and one
        seed must give identical outcomes. That equivalence is what makes the
        projectile path free of new arithmetic to get wrong."""
        for seed in range(50):
            with self.subTest(seed=seed):
                swing = resolve_melee_swing(80, 12, 70, 9, 40, 6,
                                            rng=random.Random(seed))
                shot = resolve_projectile_shot(80, 12, 70, 9, 40, 6,
                                               rng=random.Random(seed))

                self.assertEqual(swing, shot)

    def test_a_defenceless_target_is_hit_more_often(self):
        """The defence roll still reads the DEFENDER's numbers.

        A regression this shape already happened once on the melee side --
        the attacker's own equipment was fed to the defence roll -- and the
        projectile path reads a different defence key, so it can happen again
        independently.
        """
        bare = hit_chance(attack_roll(60, 10), defense_roll(60, 0))
        armoured = hit_chance(attack_roll(60, 10), defense_roll(60, 100))

        self.assertGreater(bare, armoured)
