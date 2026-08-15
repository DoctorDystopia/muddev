"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Deterministic-RNG tests for the three shipped rules definitions.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat

Every outcome here is pinned with ScriptedRandom rather than a hand-picked
seed. A seed that happens to produce the wanted face is a coincidence that
breaks the moment a seam changes how many values it draws.
"""

import random
import unittest

from systems.combat import combat_calc
from systems.combat import constants as const
from systems.combat.rules.context import ActionContext
from systems.combat.rules.modifiers import apply_to_level
from systems.combat.rules.pipeline import resolve_action
from systems.combat.rules.registry import RULES_REGISTRY
from systems.combat.rules.rule_defs.glass_cannon_amulet import (
    GLASS_CANNON_BONUS_PER_STEP,
    GLASS_CANNON_BRAWN_PER_STEP,
    GlassCannonAmuletRules,
)
from systems.combat.rules.rule_defs.malfunctioning_gizmo import (
    GIZMO_BACKFIRE_DAMAGE,
    GIZMO_ROLL_SIDES,
    GIZMO_ZAP_DAMAGE,
    GIZMO_ZAP_OUTCOMES,
    MalfunctioningGizmoRules,
)
from systems.combat.rules.rule_defs.toy_sword import (
    TOY_SWORD_DIE_MAX,
    TOY_SWORD_DIE_MIN,
    TOY_SWORD_FUMBLE_DAMAGE,
    TOY_SWORD_FUMBLE_ROLL,
    ToySwordRules,
)
from systems.progression.skills.constants import (
    BRAWN_SKILL_KEY,
    DEFENSE_SKILL_KEY,
    FORTITUDE_SKILL_KEY,
    STRIKE_SKILL_KEY,
)

from .rng_stubs import ScriptedRandom


# Private constant definitions

# Seed and sample count for the gizmo's distribution check. Fixed so the test
# is reproducible; large enough that the 4/5 split lands well inside the
# tolerance below without the test becoming slow.
_GIZMO_TEST_SEED = 20260804
_GIZMO_TEST_SAMPLES = 10000

# Acceptable band around the exact 0.80 zap rate for _GIZMO_TEST_SAMPLES
# draws. Wide enough that no legitimate RNG stream trips it, tight enough that
# a 3/5 or 5/5 split would.
_GIZMO_ZAP_RATE_FLOOR = 0.78
_GIZMO_ZAP_RATE_CEILING = 0.82

# A roll that always connects, and one that never does. The accuracy check is
# `roll < chance`, and chance is clamped strictly below 1.0.
_ALWAYS_HITS = 0.0
_NEVER_HITS = 0.9999999

# Stat blocks. Kept minimal: these tests are about the definitions, not about
# the equipment maths, which test_action_pipeline already covers.
_ATTACKER_STATS = {"stab_attack_bonus": 5, "melee_strength_bonus": 4}
_DEFENDER_STATS = {"stab_defense_bonus": 2}

# A defender with enough armour that a normal swing would almost never land.
# Used to prove a whole-swing override bypasses accuracy entirely.
_ARMOURED_DEFENDER_STATS = {"stab_defense_bonus": 5000}


def _levels(strike=40, brawn=35, defense=20, fortitude=30) -> dict:
    """Build a skill-level snapshot with every combat axis present."""
    return {
        STRIKE_SKILL_KEY: strike,
        BRAWN_SKILL_KEY: brawn,
        DEFENSE_SKILL_KEY: defense,
        FORTITUDE_SKILL_KEY: fortitude,
    }


def _context(rng, attacker_rules=(), defender_rules=(),
             attacker_levels=None, defender_stats=None) -> ActionContext:
    """Build an ActionContext from plain dicts, with no Evennia objects."""
    return ActionContext(
        attacker=None,
        defender=None,
        weapon=None,
        weapon_data={},
        style={},
        attack_type=const.ATTACK_TYPE_STAB,
        attacker_stats=dict(_ATTACKER_STATS),
        defender_stats=dict(defender_stats or _DEFENDER_STATS),
        attacker_levels=attacker_levels or _levels(),
        defender_levels=_levels(strike=15, brawn=15, defense=25, fortitude=22),
        stance_boost={},
        attacker_rules=tuple(attacker_rules),
        defender_rules=tuple(defender_rules),
        rng=rng,
    )


class TestMalfunctioningGizmo(unittest.TestCase):
    """4/5 chance to zap for 5; 1/5 chance to hurt the wielder for 5."""

    def setUp(self):
        self.rules = RULES_REGISTRY[MalfunctioningGizmoRules.key]

    def _swing(self, face: int):
        context = _context(ScriptedRandom(randints=[face]),
                           attacker_rules=(self.rules,))

        return resolve_action(context)

    def test_it_is_discovered_and_owns_the_whole_swing(self):
        self.assertEqual(self.rules._overridden_seams, frozenset({"resolve"}))
        self.assertEqual(self.rules.priority, const.RULES_PRIORITY_OVERRIDE)

    def test_every_zap_face_deals_the_same_flat_damage(self):
        for face in range(1, GIZMO_ZAP_OUTCOMES + 1):
            result = self._swing(face)

            self.assertEqual(result.damage, GIZMO_ZAP_DAMAGE, msg=f"face {face}")
            self.assertEqual(result.self_damage, 0, msg=f"face {face}")

    def test_a_zap_is_typed_as_energy(self):
        self.assertEqual(self._swing(1).damage_type, const.DAMAGE_TYPE_ENERGY)

    def test_the_last_face_hurts_the_wielder_instead(self):
        result = self._swing(GIZMO_ROLL_SIDES)

        self.assertEqual(result.self_damage, GIZMO_BACKFIRE_DAMAGE)
        self.assertEqual(result.damage, 0)

    def test_a_backfire_is_typed_as_energy_not_a_dedicated_backfire_type(self):
        # The gizmo is an energy weapon; a backfire is that same gizmo
        # discharging into its own wielder, not a distinct damage type.
        result = self._swing(GIZMO_ROLL_SIDES)

        self.assertEqual(result.damage_type, const.DAMAGE_TYPE_ENERGY)

    def test_a_zap_bypasses_the_accuracy_roll(self):
        # The ScriptedRandom scripts no random() value at all, so reaching the
        # accuracy roll would raise. A defender in 5000 armour still takes 5.
        context = _context(ScriptedRandom(randints=[1]),
                           attacker_rules=(self.rules,),
                           defender_stats=_ARMOURED_DEFENDER_STATS)

        result = resolve_action(context)

        self.assertTrue(result.hit)
        self.assertEqual(result.damage, GIZMO_ZAP_DAMAGE)

    def test_a_zap_ignores_the_max_hit_channel(self):
        # Proves `resolve` short-circuits the pipeline rather than merely
        # sitting at the end of it: a max-hit modifier that would triple a
        # normal swing must do nothing here.
        booster = _MaxHitBooster()
        context = _context(ScriptedRandom(randints=[1]),
                           attacker_rules=(booster, self.rules))

        result = resolve_action(context)

        self.assertEqual(result.damage, GIZMO_ZAP_DAMAGE)

    def test_the_split_is_four_in_five_over_many_swings(self):
        rng = random.Random(_GIZMO_TEST_SEED)
        zaps = 0

        for _ in range(_GIZMO_TEST_SAMPLES):
            context = _context(rng, attacker_rules=(self.rules,))

            if resolve_action(context).damage > 0:
                zaps += 1

        rate = zaps / _GIZMO_TEST_SAMPLES
        self.assertGreater(rate, _GIZMO_ZAP_RATE_FLOOR)
        self.assertLess(rate, _GIZMO_ZAP_RATE_CEILING)

    def test_the_outcome_sequence_is_reproducible_for_a_fixed_seed(self):
        first = self._sequence(random.Random(_GIZMO_TEST_SEED))
        second = self._sequence(random.Random(_GIZMO_TEST_SEED))

        self.assertEqual(first, second)

    def test_both_outcomes_actually_occur_in_the_sequence(self):
        # Guards the reproducibility test above: two identical all-zap
        # sequences would compare equal and prove nothing.
        sequence = self._sequence(random.Random(_GIZMO_TEST_SEED))

        self.assertEqual(set(sequence), {True, False})

    def _sequence(self, rng, length: int = 40) -> list:
        outcomes = []

        for _ in range(length):
            context = _context(rng, attacker_rules=(self.rules,))
            outcomes.append(resolve_action(context).damage > 0)

        return outcomes


class TestToySword(unittest.TestCase):
    """A d20 in place of the uniform roll, with a natural 1 turning inward."""

    def setUp(self):
        self.rules = RULES_REGISTRY[ToySwordRules.key]

    def _swing(self, face: int, accuracy: float = _ALWAYS_HITS,
               attacker_rules=None):
        rules = attacker_rules if attacker_rules is not None else (self.rules,)
        rng = ScriptedRandom(randints=[face], randoms=[accuracy])
        context = _context(rng, attacker_rules=rules)

        return resolve_action(context)

    def test_it_is_discovered_and_owns_only_the_damage_roll(self):
        self.assertEqual(self.rules._overridden_seams,
                         frozenset({"roll_damage"}))
        self.assertEqual(self.rules.priority, const.RULES_PRIORITY_WEAPON)

    def test_a_natural_one_hurts_the_wielder(self):
        result = self._swing(TOY_SWORD_FUMBLE_ROLL)

        self.assertEqual(result.self_damage, TOY_SWORD_FUMBLE_DAMAGE)
        self.assertEqual(result.damage, 0)

    def test_a_natural_twenty_deals_twenty(self):
        self.assertEqual(self._swing(TOY_SWORD_DIE_MAX).damage,
                         TOY_SWORD_DIE_MAX)

    def test_the_roll_is_the_damage_for_every_non_fumble_face(self):
        for face in range(TOY_SWORD_FUMBLE_ROLL + 1, TOY_SWORD_DIE_MAX + 1):
            self.assertEqual(self._swing(face).damage, face, msg=f"face {face}")

    def test_damage_is_not_capped_by_the_osrs_max_hit(self):
        # A weak character's OSRS ceiling is far below 20. If the seam were
        # clamping to it, every high roll would flatten to the same number and
        # the die would be a die in name only.
        weak = _levels(brawn=1)
        rng = ScriptedRandom(randints=[TOY_SWORD_DIE_MAX], randoms=[_ALWAYS_HITS])
        context = _context(rng, attacker_rules=(self.rules,),
                           attacker_levels=weak)

        eff_str = combat_calc.effective_level(1)
        ceiling = combat_calc.max_hit(eff_str,
                                      _ATTACKER_STATS["melee_strength_bonus"])
        result = resolve_action(context)

        self.assertLess(ceiling, TOY_SWORD_DIE_MAX)
        self.assertEqual(result.damage, TOY_SWORD_DIE_MAX)

    def test_the_die_is_asked_for_the_right_bounds(self):
        rng = ScriptedRandom(randints=[5], randoms=[_ALWAYS_HITS])
        context = _context(rng, attacker_rules=(self.rules,))

        resolve_action(context)

        self.assertEqual(rng.randint_calls,
                         [(TOY_SWORD_DIE_MIN, TOY_SWORD_DIE_MAX)])

    def test_accuracy_still_applies(self):
        # The seam replaced the damage roll, not the whole swing: a miss must
        # still be a miss even on a scripted natural 20.
        rng = ScriptedRandom(randints=[TOY_SWORD_DIE_MAX], randoms=[_NEVER_HITS])
        context = _context(rng, attacker_rules=(self.rules,))

        result = resolve_action(context)

        self.assertFalse(result.hit)
        self.assertEqual(result.damage, 0)

    def test_every_face_of_the_die_appears_over_many_swings(self):
        rng = random.Random(_GIZMO_TEST_SEED)
        seen = set()

        for _ in range(1000):
            context = _context(rng, attacker_rules=(self.rules,))
            result = resolve_action(context)

            if result.hit and result.damage:
                seen.add(result.damage)

        expected = set(range(TOY_SWORD_FUMBLE_ROLL + 1, TOY_SWORD_DIE_MAX + 1))
        self.assertEqual(seen, expected)


class TestGlassCannonAmulet(unittest.TestCase):
    """+1 Brawn per 5 Brawn over Fortitude, floored at zero."""

    def setUp(self):
        self.rules = RULES_REGISTRY[GlassCannonAmuletRules.key]

    def _bonus_for(self, brawn: int, fortitude: int) -> int:
        """Return the flat_pre the amulet contributes at these levels."""
        rng = ScriptedRandom(randoms=[_NEVER_HITS])
        context = _context(rng, attacker_rules=(self.rules,),
                           attacker_levels=_levels(brawn=brawn,
                                                   fortitude=fortitude))

        resolve_action(context)

        return context.attacker_bag.channel(const.CHANNEL_BRAWN_LEVEL).flat_pre

    def test_it_is_discovered_and_owns_only_the_modifier_seam(self):
        self.assertEqual(self.rules._overridden_seams,
                         frozenset({"contribute_modifiers"}))
        self.assertEqual(self.rules.priority, const.RULES_PRIORITY_MODIFIER)

    def test_no_bonus_when_brawn_equals_fortitude(self):
        self.assertEqual(self._bonus_for(brawn=40, fortitude=40), 0)

    def test_no_bonus_below_one_full_step(self):
        short = GLASS_CANNON_BRAWN_PER_STEP - 1

        self.assertEqual(self._bonus_for(brawn=40 + short, fortitude=40), 0)

    def test_one_bonus_level_per_whole_step(self):
        step = GLASS_CANNON_BRAWN_PER_STEP

        self.assertEqual(self._bonus_for(brawn=40 + step, fortitude=40),
                         GLASS_CANNON_BONUS_PER_STEP)
        self.assertEqual(self._bonus_for(brawn=40 + step * 2, fortitude=40),
                         GLASS_CANNON_BONUS_PER_STEP * 2)

    def test_a_partial_step_is_discarded_not_rounded_up(self):
        step = GLASS_CANNON_BRAWN_PER_STEP

        self.assertEqual(self._bonus_for(brawn=40 + step * 2 + 1, fortitude=40),
                         GLASS_CANNON_BONUS_PER_STEP * 2)

    def test_a_negative_surplus_gives_no_penalty(self):
        # Python's // floors toward negative infinity, so the design note's
        # literal formula would give -8 here. Decided 08/04: pure upside.
        self.assertEqual(self._bonus_for(brawn=10, fortitude=50), 0)

    def test_the_bonus_lands_in_brawn_not_strike(self):
        rng = ScriptedRandom(randoms=[_NEVER_HITS])
        context = _context(rng, attacker_rules=(self.rules,),
                           attacker_levels=_levels(brawn=60, fortitude=10))

        resolve_action(context)

        touched = context.attacker_bag.touched_channels()
        self.assertEqual(touched, (const.CHANNEL_BRAWN_LEVEL,))

    def test_the_bonus_is_scaled_by_the_augmentation_stage(self):
        # flat_pre, not flat_post: the bonus enters before the multipliers,
        # so an Augmentation buff amplifies it. This is what distinguishes a
        # stat conversion from a flat damage add.
        from systems.combat.rules.modifiers import ModifierBag

        bag = ModifierBag()
        bag.add_flat_pre(const.CHANNEL_BRAWN_LEVEL, 10)
        bag.add_augment_bonus(const.CHANNEL_BRAWN_LEVEL, 1.0)

        boosted = apply_to_level(bag, const.CHANNEL_BRAWN_LEVEL, 40, 0)
        unboosted = combat_calc.effective_level(40, augmentation_mult=2.0)

        self.assertEqual(boosted - unboosted, 20)

    def test_the_bonus_raises_the_damage_ceiling(self):
        # End to end: more effective Brawn must mean a bigger max hit.
        wearing = _levels(brawn=60, fortitude=10)
        # roll_damage's first draw is a round-direction coin flip on [0, 1],
        # not the max-hit ceiling; the ceiling shows up on the second draw.
        rng = ScriptedRandom(randints=[999, 999, 999], randoms=[_ALWAYS_HITS])
        with_amulet = _context(rng, attacker_rules=(self.rules,),
                               attacker_levels=wearing)
        without = _context(
            ScriptedRandom(randints=[999, 999, 999], randoms=[_ALWAYS_HITS]),
            attacker_levels=wearing)

        resolve_action(with_amulet)
        resolve_action(without)

        # ScriptedRandom ignores the bounds it is given but records them, so
        # the requested max hit is readable straight off the call log.
        self.assertGreater(with_amulet.rng.randint_calls[1][1],
                           without.rng.randint_calls[1][1])

    def test_it_composes_with_a_seam_override(self):
        # The point of separating modifiers from seams: a d20 sword owning
        # the damage roll must not switch the amulet off.
        toy = RULES_REGISTRY[ToySwordRules.key]
        rng = ScriptedRandom(randints=[7], randoms=[_ALWAYS_HITS])
        context = _context(rng, attacker_rules=(self.rules, toy),
                           attacker_levels=_levels(brawn=60, fortitude=10))

        result = resolve_action(context)

        self.assertEqual(result.damage, 7)
        self.assertEqual(
            context.attacker_bag.channel(const.CHANNEL_BRAWN_LEVEL).flat_pre,
            GLASS_CANNON_BONUS_PER_STEP * 10,
        )


class _MaxHitBooster(GlassCannonAmuletRules):
    """Test-only contributor that triples the max hit.

    Defined at module level and NOT in rule_defs/, so the registry never sees
    it. Subclasses the amulet purely to inherit a real priority tier.
    """

    key = "test_max_hit_booster"
    priority = const.RULES_PRIORITY_MODIFIER

    def __init__(self) -> None:
        self._overridden_seams = frozenset({"contribute_modifiers"})

    def contribute_modifiers(self, context, bag) -> None:
        bag.add_augment_bonus(const.CHANNEL_MAX_HIT, 2.0)
