"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Pure-function suite for OSRS-exact math in systems/combat/combat_calc.py.
             No Django, DB, or entity — just arithmetic truth.

             Wrapped in a TestCase so `evennia test` (Django/unittest
             discovery) collects it. As bare module-level functions these
             were invisible to that runner and only ran under a separate
             pytest invocation that could not run the rest of the suite.
"""

import random
from unittest import TestCase

from systems.combat.combat_calc import (
    melee_attack_roll,
    melee_defense_roll,
    effective_level,
    hit_chance,
    max_melee_hit,
    resolve_melee_swing,
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


    # ─── max_melee_hit ─────────────────────────────────────────────────────


    def test_max_hit_zero_equip(self):
        assert max_melee_hit(110, 0) == 11  # canonical OSRS: bare-fist at 99+8+3 = 110 -> 11


    def test_max_hit_level_one(self):
        assert max_melee_hit(1, 0) == 0


    # ─── melee_attack_roll / melee_defense_roll ────────────────────────────


    def test_attack_roll_no_equip(self):
        assert melee_attack_roll(110, 0) == 110 * 64


    def test_defense_roll_equalizes_attack(self):
        assert melee_defense_roll(110, 0) == melee_attack_roll(110, 0)


    # ─── hit_chance ───────────────────────────────────────────────────────────


    def test_hit_chance_equal_rolls_approx_half(self):
        r = melee_attack_roll(10, 0)
        p = hit_chance(r, r)
        assert 0.49 < p < 0.50


    def test_hit_chance_double_attacker_greater(self):
        r = melee_attack_roll(10, 0)
        p = hit_chance(2 * r, r)
        assert 0.74 < p < 0.76


    def test_defender_equip_bonus_lowers_hit_chance(self):
        """The defender's own equipment must move the accuracy curve.

        Guards the arithmetic side of the audit bug where the swing pipeline fed
        the *attacker's* equipment into melee_defense_roll, so a defender's armour was
        mathematically inert. See test_combat_handler.TestDefenderBonuses for the
        plumbing side.
        """
        r_atk = melee_attack_roll(50, 20)
        bare = hit_chance(r_atk, melee_defense_roll(50, 0))
        armoured = hit_chance(r_atk, melee_defense_roll(50, 100))

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
