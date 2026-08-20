"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Tests for action resolution — the OSRS equivalence net, seam
             winner resolution, and modifier channels reaching the formula.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat
"""

import random
import unittest

from systems.combat import combat_calc
from systems.combat import constants as const
from systems.combat.rules.context import ActionContext, ActionResult
from systems.combat.rules.pipeline import _resolve_winners, resolve_action
from systems.combat.rules.rule_defs.base_rules import (
    DEFAULT_ACTION_RULES,
    BaseActionRules,
)
from systems.progression.skills.constants import (
    BRAWN_SKILL_KEY,
    DEFENSE_SKILL_KEY,
    FORTITUDE_SKILL_KEY,
    STRIKE_SKILL_KEY,
)

from .rng_stubs import RecordingRandom, ScriptedRandom


# Private constant definitions

# How many seeds the equivalence sweep covers. Fifty is enough to exercise
# both branches of the bifurcated hit-chance curve and a spread of damage
# rolls, while staying instant.
_EQUIVALENCE_SEEDS = 50

# A stat block with non-trivial numbers in every field the swing reads, so a
# formula that dropped one of them shows up as a difference rather than a
# coincidental match on zero.
_ATTACKER_STATS = {
    "stab_attack_bonus": 7,
    "slash_attack_bonus": 4,
    "crush_attack_bonus": -2,
    "melee_strength_bonus": 9,
}

_DEFENDER_STATS = {
    "stab_defense_bonus": 5,
    "slash_defense_bonus": 3,
    "crush_defense_bonus": 11,
    "melee_strength_bonus": 0,
}

_ATTACKER_LEVELS = {
    STRIKE_SKILL_KEY: 40,
    BRAWN_SKILL_KEY: 35,
    DEFENSE_SKILL_KEY: 20,
    FORTITUDE_SKILL_KEY: 30,
}

_DEFENDER_LEVELS = {
    STRIKE_SKILL_KEY: 15,
    BRAWN_SKILL_KEY: 15,
    DEFENSE_SKILL_KEY: 25,
    FORTITUDE_SKILL_KEY: 22,
}

# The accurate stance: +3 Strike, nothing else.
_STANCE_BOOST = {STRIKE_SKILL_KEY: 3}


def _build_context(rng=None, attacker_rules=(), defender_rules=(),
                   attacker_levels=None, defender_levels=None):
    """Build an ActionContext from plain dicts, with no Evennia objects.

    The pipeline never touches attacker/defender except to hand them to a
    rules definition, so None is a valid stand-in for every test that does not
    involve a definition reading the entity itself.
    """
    return ActionContext(
        attacker=None,
        defender=None,
        weapon=None,
        weapon_data={},
        style={},
        attack_type=const.ATTACK_TYPE_STAB,
        attacker_stats=dict(_ATTACKER_STATS),
        defender_stats=dict(_DEFENDER_STATS),
        attacker_levels=dict(attacker_levels or _ATTACKER_LEVELS),
        defender_levels=dict(defender_levels or _DEFENDER_LEVELS),
        stance_boost=dict(_STANCE_BOOST),
        attacker_rules=tuple(attacker_rules),
        defender_rules=tuple(defender_rules),
        rng=rng if rng is not None else random.Random(0),
    )


def _reference_swing(rng):
    """Run the same swing through combat_calc directly, for comparison."""
    eff_atk = combat_calc.effective_level(
        _ATTACKER_LEVELS[STRIKE_SKILL_KEY],
        stance_bonus=_STANCE_BOOST[STRIKE_SKILL_KEY],
    )
    eff_str = combat_calc.effective_level(_ATTACKER_LEVELS[BRAWN_SKILL_KEY])
    eff_def = combat_calc.effective_level(_DEFENDER_LEVELS[DEFENSE_SKILL_KEY])

    return combat_calc.resolve_melee_swing(
        attacker_eff_atk=eff_atk,
        attacker_equip_atk=_ATTACKER_STATS["stab_attack_bonus"],
        attacker_eff_str=eff_str,
        attacker_equip_str=_ATTACKER_STATS["melee_strength_bonus"],
        defender_eff_def=eff_def,
        defender_equip_def=_DEFENDER_STATS["stab_defense_bonus"],
        rng=rng,
    )


class TestDefaultRulesMatchTheReference(unittest.TestCase):
    """The drift net.

    combat_calc.resolve_melee_swing is no longer called by the game, but it
    remains the OSRS oracle and keeps its exact-value tests. These assertions
    are what stop the live pipeline silently diverging from it: any change to
    a default seam that alters a number, a draw, or a draw ORDER fails here.
    """

    def test_the_default_pipeline_matches_the_reference_for_every_seed(self):
        for seed in range(_EQUIVALENCE_SEEDS):
            context = _build_context(rng=random.Random(seed))

            result = resolve_action(context)
            expected = _reference_swing(random.Random(seed))

            self.assertEqual(result.hit, expected["hit"], msg=f"seed {seed}")
            self.assertEqual(result.damage, expected["damage"], msg=f"seed {seed}")
            self.assertAlmostEqual(result.hit_prob, expected["hit_prob"],
                                   msg=f"seed {seed}")

    def test_the_sweep_actually_produces_both_hits_and_misses(self):
        # Guards the test above: if every seed missed, the damage assertion
        # would be comparing zero to zero and prove nothing.
        outcomes = set()

        for seed in range(_EQUIVALENCE_SEEDS):
            context = _build_context(rng=random.Random(seed))
            outcomes.add(resolve_action(context).hit)

        self.assertEqual(outcomes, {True, False})

    def test_accuracy_is_drawn_before_damage(self):
        # Draw ORDER, not just the seed, decides what a seeded run produces.
        # combat_calc draws random() then randint(); the pipeline must match
        # or the equivalence above holds only by luck.
        recorder = RecordingRandom(random.Random(1))
        context = _build_context(rng=recorder)

        result = resolve_action(context)

        self.assertTrue(result.hit, msg="seed 1 was chosen because it hits")
        self.assertEqual(recorder.trace, ["random", "randint"])

    def test_a_miss_draws_only_the_accuracy_roll(self):
        recorder = RecordingRandom(random.Random(0))
        context = _build_context(rng=recorder)

        result = resolve_action(context)

        self.assertFalse(result.hit, msg="seed 0 was chosen because it misses")
        self.assertEqual(recorder.trace, ["random"])

    def test_a_default_swing_is_typed_as_melee(self):
        context = _build_context(rng=random.Random(1))

        result = resolve_action(context)

        self.assertEqual(result.damage_type, const.DAMAGE_TYPE_MELEE)

    def test_a_default_swing_does_not_hurt_the_attacker(self):
        for seed in range(_EQUIVALENCE_SEEDS):
            context = _build_context(rng=random.Random(seed))

            self.assertEqual(resolve_action(context).self_damage, 0)


class TestSeamWinnerResolution(unittest.TestCase):
    """Highest priority wins each seam, independently, and never chains."""

    def test_no_contributors_resolves_every_seam_to_the_default(self):
        resolved = _resolve_winners(())

        self.assertIs(resolved.owner("roll_damage"), DEFAULT_ACTION_RULES)
        self.assertIs(resolved.owner("resolve"), DEFAULT_ACTION_RULES)

    def test_a_contributor_wins_only_the_seam_it_overrides(self):
        class _Diced(BaseActionRules):
            key = "t_diced"
            priority = const.RULES_PRIORITY_WEAPON

            def roll_damage(self, context, result) -> None:
                result.damage = 1

        rules = _Diced()
        rules._overridden_seams = frozenset({"roll_damage"})

        resolved = _resolve_winners((rules,))

        self.assertIs(resolved.owner("roll_damage"), rules)
        self.assertIs(resolved.owner("max_hit"), DEFAULT_ACTION_RULES)

    def test_the_later_contributor_wins_a_contested_seam(self):
        # collect_contributors sorts lowest priority first, so "later" is
        # "higher priority". Asserted here at the resolution layer so the two
        # halves of that contract are pinned separately.
        class _Low(BaseActionRules):
            key = "t_low"

        class _High(BaseActionRules):
            key = "t_high"

        low = _Low()
        low._overridden_seams = frozenset({"roll_damage"})
        high = _High()
        high._overridden_seams = frozenset({"roll_damage"})

        resolved = _resolve_winners((low, high))

        self.assertIs(resolved.owner("roll_damage"), high)

    def test_the_modifier_seam_is_never_contested(self):
        # Every contributor's modifiers run, so contribute_modifiers has no
        # winner to pick. Letting it resolve like the others would mean the
        # highest-priority item silently switched off everyone else's bonuses.
        class _Modifier(BaseActionRules):
            key = "t_modifier"
            priority = const.RULES_PRIORITY_OVERRIDE

            def contribute_modifiers(self, context, bag) -> None:
                bag.add_flat_pre(const.CHANNEL_BRAWN_LEVEL, 1)

        rules = _Modifier()
        rules._overridden_seams = frozenset({"contribute_modifiers"})

        resolved = _resolve_winners((rules,))

        self.assertIs(resolved.owner("contribute_modifiers"), DEFAULT_ACTION_RULES)

    def test_a_narrow_seam_override_is_reached_from_the_default_resolve(self):
        # The reason nested seams dispatch through context.rules rather than
        # self: the default owns resolve here, and it must still reach the
        # weapon that owns roll_damage.
        class _FixedDamage(BaseActionRules):
            key = "t_fixed"
            priority = const.RULES_PRIORITY_WEAPON

            def roll_damage(self, context, result) -> None:
                result.damage = 99

        rules = _FixedDamage()
        rules._overridden_seams = frozenset({"roll_damage"})
        context = _build_context(rng=random.Random(1), attacker_rules=(rules,))

        result = resolve_action(context)

        self.assertTrue(result.hit)
        self.assertEqual(result.damage, 99)

    def test_two_contributors_can_own_different_nested_seams(self):
        # A d20 weapon and a max-hit amulet worn together: the damage seam
        # winner must be reached, AND the max-hit winner must be reached from
        # inside whatever calls it.
        class _Ceiling(BaseActionRules):
            key = "t_ceiling"
            priority = const.RULES_PRIORITY_MODIFIER

            def max_hit(self, context, eff_str: int) -> int:
                return 3

        class _Doubler(BaseActionRules):
            key = "t_doubler"
            priority = const.RULES_PRIORITY_WEAPON

            def roll_damage(self, context, result) -> None:
                ceiling = context.rules.max_hit(context, 0)
                result.damage = ceiling * 2

        ceiling = _Ceiling()
        ceiling._overridden_seams = frozenset({"max_hit"})
        doubler = _Doubler()
        doubler._overridden_seams = frozenset({"roll_damage"})
        context = _build_context(rng=random.Random(1),
                                 attacker_rules=(ceiling, doubler))

        result = resolve_action(context)

        self.assertEqual(result.damage, 6)

    def test_a_resolve_override_bypasses_the_other_seams_entirely(self):
        class _Flat(BaseActionRules):
            key = "t_flat"
            priority = const.RULES_PRIORITY_OVERRIDE

            def resolve(self, context) -> ActionResult:
                return ActionResult(hit=True, damage=5, hit_prob=1.0)

        class _NeverCalled(BaseActionRules):
            key = "t_never"
            priority = const.RULES_PRIORITY_WEAPON

            def roll_damage(self, context, result) -> None:
                raise AssertionError("a resolve override must short-circuit")

        flat = _Flat()
        flat._overridden_seams = frozenset({"resolve"})
        never = _NeverCalled()
        never._overridden_seams = frozenset({"roll_damage"})
        context = _build_context(rng=random.Random(1),
                                 attacker_rules=(never, flat))

        result = resolve_action(context)

        self.assertEqual(result.damage, 5)


class TestModifierChannelsReachTheFormula(unittest.TestCase):
    """Each channel must move the number it claims to, and no other."""

    def _damage_with(self, contributor, seed: int = 1) -> int:
        context = _build_context(rng=random.Random(seed),
                                 attacker_rules=(contributor,))

        return resolve_action(context).damage

    def _make(self, channel_key: str, amount: int, priority=None):
        tier = priority if priority is not None else const.RULES_PRIORITY_MODIFIER

        class _Boost(BaseActionRules):
            key = f"t_boost_{channel_key}"

        _Boost.priority = tier

        def contribute(self, context, bag) -> None:
            bag.add_flat_pre(channel_key, amount)

        _Boost.contribute_modifiers = contribute
        instance = _Boost()
        instance._overridden_seams = frozenset({"contribute_modifiers"})

        return instance

    def test_every_contributors_modifiers_run_regardless_of_priority(self):
        low = self._make(const.CHANNEL_BRAWN_LEVEL, 5,
                         const.RULES_PRIORITY_MODIFIER)
        high = self._make(const.CHANNEL_STRENGTH_BONUS, 5,
                          const.RULES_PRIORITY_OVERRIDE)
        context = _build_context(rng=random.Random(1),
                                 attacker_rules=(low, high))

        resolve_action(context)

        touched = context.attacker_bag.touched_channels()
        self.assertIn(const.CHANNEL_BRAWN_LEVEL, touched)
        self.assertIn(const.CHANNEL_STRENGTH_BONUS, touched)

    def test_the_max_hit_channel_raises_the_damage_ceiling(self):
        baseline = _build_context(rng=random.Random(1))
        boosted = _build_context(rng=random.Random(1), attacker_rules=(
            self._make(const.CHANNEL_MAX_HIT, 20),
        ))

        base_damage = resolve_action(baseline).damage
        boosted_damage = resolve_action(boosted).damage

        self.assertGreater(boosted_damage, base_damage)

    def test_the_strength_bonus_channel_raises_the_damage_ceiling(self):
        context = _build_context(rng=random.Random(1))
        boosted = _build_context(rng=random.Random(1), attacker_rules=(
            self._make(const.CHANNEL_STRENGTH_BONUS, 100),
        ))

        self.assertGreater(resolve_action(boosted).damage,
                           resolve_action(context).damage)

    def test_the_attack_bonus_channel_raises_the_hit_probability(self):
        context = _build_context(rng=random.Random(1))
        boosted = _build_context(rng=random.Random(1), attacker_rules=(
            self._make(const.CHANNEL_ATTACK_BONUS, 200),
        ))

        self.assertGreater(resolve_action(boosted).hit_prob,
                           resolve_action(context).hit_prob)

    def test_the_defense_bonus_channel_comes_from_the_defender(self):
        # Regression-shaped. Reading the defender's armour out of the
        # attacker's bag is the exact bug get_defense_bonuses exists to
        # prevent, and the modifier layer must not reintroduce it.
        armour = self._make(const.CHANNEL_DEFENSE_BONUS, 500)
        on_defender = _build_context(rng=random.Random(1),
                                     defender_rules=(armour,))
        on_attacker = _build_context(rng=random.Random(1),
                                     attacker_rules=(armour,))
        baseline = _build_context(rng=random.Random(1))

        base_prob = resolve_action(baseline).hit_prob
        defender_prob = resolve_action(on_defender).hit_prob
        attacker_prob = resolve_action(on_attacker).hit_prob

        self.assertLess(defender_prob, base_prob)
        self.assertAlmostEqual(attacker_prob, base_prob)

    def test_defender_modifiers_do_not_land_in_the_attacker_bag(self):
        armour = self._make(const.CHANNEL_DEFENSE_BONUS, 5)
        context = _build_context(rng=random.Random(1), defender_rules=(armour,))

        resolve_action(context)

        self.assertEqual(context.attacker_bag.touched_channels(), ())
        self.assertIn(const.CHANNEL_DEFENSE_BONUS,
                      context.defender_bag.touched_channels())

    def test_a_conditional_modifier_reads_its_own_wearers_levels(self):
        # levels_for(bag) exists so the same definition worn by the defender
        # keys off the defender. Without it, a defender's amulet would read
        # its opponent's stats.
        seen = {}

        class _Reader(BaseActionRules):
            key = "t_reader"
            priority = const.RULES_PRIORITY_MODIFIER

            def contribute_modifiers(self, context, bag) -> None:
                levels = context.levels_for(bag)
                seen[id(bag)] = levels[BRAWN_SKILL_KEY]

        rules = _Reader()
        rules._overridden_seams = frozenset({"contribute_modifiers"})
        context = _build_context(rng=random.Random(1),
                                 attacker_rules=(rules,),
                                 defender_rules=(rules,))

        resolve_action(context)

        self.assertEqual(seen[id(context.attacker_bag)],
                         _ATTACKER_LEVELS[BRAWN_SKILL_KEY])
        self.assertEqual(seen[id(context.defender_bag)],
                         _DEFENDER_LEVELS[BRAWN_SKILL_KEY])

    def test_a_raising_contributor_is_skipped_rather_than_killing_the_action(self):
        class _Broken(BaseActionRules):
            key = "t_broken"
            priority = const.RULES_PRIORITY_MODIFIER

            def contribute_modifiers(self, context, bag) -> None:
                raise RuntimeError("this definition is broken")

        broken = _Broken()
        broken._overridden_seams = frozenset({"contribute_modifiers"})
        context = _build_context(rng=random.Random(1), attacker_rules=(broken,))

        result = resolve_action(context)

        self.assertTrue(result.hit)


class TestScriptedRngStub(unittest.TestCase):
    """The stub itself, since every deterministic test leans on it."""

    def test_exhausting_a_scripted_sequence_raises(self):
        rng = ScriptedRandom(randoms=[0.0])
        context = _build_context(rng=rng)

        with self.assertRaises(AssertionError):
            resolve_action(context)

    def test_a_scripted_low_roll_always_connects(self):
        # roll_damage is a SINGLE uniform randint on [0, max_hit], so the one
        # scripted draw is the damage. It briefly averaged two draws around a
        # coin flip (combat_calc.roll_damage's commented-out variant), which is
        # why this used to script three.
        rng = ScriptedRandom(randoms=[0.0], randints=[4])
        context = _build_context(rng=rng)

        result = resolve_action(context)

        self.assertTrue(result.hit)
        self.assertEqual(result.damage, 4)

    def test_a_scripted_high_roll_always_misses(self):
        rng = ScriptedRandom(randoms=[0.999999])
        context = _build_context(rng=rng)

        self.assertFalse(resolve_action(context).hit)
