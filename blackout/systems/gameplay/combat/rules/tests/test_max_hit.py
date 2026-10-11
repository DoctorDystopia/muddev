"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/08/2026
Description: Tests for the max hit mark: ActionResult.is_max_hit, and the
             `max_hit` and `rolled` that each damage roll writes.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.combat.rules.tests.test_max_hit

No test names a max hit value. Each test reads the ceiling from the bounds
that the roll asked the RNG for, so a retune of the formula changes nothing
here (CLAUDE.md, "Never assert a balance value").
"""

import unittest

from systems.gameplay.combat import constants as const
from systems.gameplay.combat.rules.context import ActionContext, ActionResult
from systems.gameplay.combat.rules.pipeline import resolve_action
from systems.gameplay.combat.rules.registry import RULES_REGISTRY
from systems.gameplay.combat.rules.rule_defs.base_rules import BaseActionRules
from systems.gameplay.combat.rules.rule_defs.bit_blade import BitBladeRules
from systems.gameplay.combat.rules.rule_defs.toy_sword import (
    TOY_SWORD_DIE_MAX,
    ToySwordRules,
)
from systems.gameplay.progression.skills.constants import (
    SKILL_KEY_BRAWN,
    SKILL_KEY_DEFENSE,
    SKILL_KEY_FORTITUDE,
    SKILL_KEY_STRIKE,
)

from .rng_stubs import ScriptedRandom



# ─── Private constant definitions ────────────────────────────────────────────

# An accuracy roll that always connects, and one that never does.
_ALWAYS_HITS = 0.0
_NEVER_HITS = 0.9999999

# Fixture stats and levels. Not balance values: any block with a max hit
# above 1 serves.
_ATTACKER_STATS = {"stab_attack_bonus": 5, "melee_strength_bonus": 4}
_DEFENDER_STATS = {"stab_defense_bonus": 2}
_FIXTURE_LEVEL = 40

# The change that the test contributors add to the damage channel.
_DAMAGE_CHANGE = 3

# A fixture max hit for the ActionResult cases.
_FIXTURE_MAX_HIT = 14



def _levels() -> dict:
    """Return a skill-level snapshot with every combat axis present."""
    return {
        SKILL_KEY_STRIKE: _FIXTURE_LEVEL,
        SKILL_KEY_BRAWN: _FIXTURE_LEVEL,
        SKILL_KEY_DEFENSE: _FIXTURE_LEVEL,
        SKILL_KEY_FORTITUDE: _FIXTURE_LEVEL,
    }


def _context(rng, attacker_rules=()) -> ActionContext:
    """Build an ActionContext from plain dicts, with no Evennia objects."""
    return ActionContext(
        attacker=None,
        defender=None,
        weapon=None,
        weapon_data={},
        style={},
        attack_type=const.ATTACK_TYPE_STAB,
        attacker_stats=dict(_ATTACKER_STATS),
        defender_stats=dict(_DEFENDER_STATS),
        attacker_levels=_levels(),
        defender_levels=_levels(),
        stance_boost={},
        attacker_rules=tuple(attacker_rules),
        defender_rules=(),
        rng=rng,
    )


def _swing(face: int, attacker_rules=(), accuracy: float = _ALWAYS_HITS):
    """Resolve one action with the damage die scripted to `face`."""
    rng = ScriptedRandom(randints=[face], randoms=[accuracy])
    result = resolve_action(_context(rng, attacker_rules))

    return result, rng


def _default_ceiling() -> int:
    """Return the max hit that the default roll asks the RNG for."""
    _result, rng = _swing(0)

    return rng.randint_calls[0][1]



class _DamageChange(BaseActionRules):
    """Test-only contributor that adds a flat amount to the damage channel.

    Not in rule_defs/, so the registry never sees it.
    """

    key = "test_damage_change"
    priority = const.RULES_PRIORITY_MODIFIER

    def __init__(self, amount: int) -> None:
        self._overridden_seams = frozenset({"contribute_modifiers"})
        self._amount = amount

    def contribute_modifiers(self, context, bag) -> None:
        bag.add_flat_post(const.CHANNEL_DAMAGE, self._amount)



class TestActionResultMaxHit(unittest.TestCase):
    """The rule itself, on bare results."""

    def test_the_top_face_is_a_max_hit(self):
        result = ActionResult(hit=True, max_hit=_FIXTURE_MAX_HIT,
                              rolled=_FIXTURE_MAX_HIT)

        self.assertTrue(result.is_max_hit())
        self.assertEqual(result.shown_max_hit(), _FIXTURE_MAX_HIT)

    def test_a_lower_face_is_not(self):
        result = ActionResult(hit=True, max_hit=_FIXTURE_MAX_HIT,
                              rolled=_FIXTURE_MAX_HIT - 1)

        self.assertFalse(result.is_max_hit())
        self.assertEqual(result.shown_max_hit(), 0)

    def test_a_miss_is_never_a_max_hit(self):
        result = ActionResult(hit=False, max_hit=_FIXTURE_MAX_HIT,
                              rolled=_FIXTURE_MAX_HIT)

        self.assertFalse(result.is_max_hit())

    def test_a_zero_roll_on_a_zero_die_is_not_a_max_hit(self):
        result = ActionResult(hit=True, max_hit=0, rolled=0)

        self.assertFalse(result.is_max_hit())

    def test_a_result_that_no_roll_wrote_is_not_a_max_hit(self):
        # A whole-action override (the gizmo) never writes the two fields.
        self.assertFalse(ActionResult(hit=True, damage=5).is_max_hit())



class TestDefaultRollMaxHit(unittest.TestCase):
    """The OSRS roll writes its ceiling and its face."""

    def test_the_top_face_is_a_max_hit(self):
        ceiling = _default_ceiling()

        result, _rng = _swing(ceiling)

        self.assertTrue(result.is_max_hit())
        self.assertEqual(result.max_hit, ceiling)

    def test_one_below_the_top_face_is_not(self):
        ceiling = _default_ceiling()

        result, _rng = _swing(ceiling - 1)

        self.assertFalse(result.is_max_hit())

    def test_a_bonus_keeps_the_max_hit_and_changes_the_damage(self):
        ceiling = _default_ceiling()
        bonus = _DamageChange(_DAMAGE_CHANGE)

        result, _rng = _swing(ceiling, attacker_rules=(bonus,))

        self.assertTrue(result.is_max_hit())
        self.assertEqual(result.damage, ceiling + _DAMAGE_CHANGE)

    def test_a_bonus_does_not_make_a_lower_roll_a_max_hit(self):
        ceiling = _default_ceiling()
        bonus = _DamageChange(_DAMAGE_CHANGE)

        result, _rng = _swing(ceiling - 1, attacker_rules=(bonus,))

        self.assertGreaterEqual(result.damage, ceiling)
        self.assertFalse(result.is_max_hit())

    def test_a_penalty_does_not_take_the_max_hit_away(self):
        ceiling = _default_ceiling()
        penalty = _DamageChange(-_DAMAGE_CHANGE)

        result, _rng = _swing(ceiling, attacker_rules=(penalty,))

        self.assertTrue(result.is_max_hit())
        self.assertLess(result.damage, ceiling)

    def test_a_miss_on_the_top_face_is_not_a_max_hit(self):
        ceiling = _default_ceiling()
        rng = ScriptedRandom(randints=[ceiling], randoms=[_NEVER_HITS])

        result = resolve_action(_context(rng))

        self.assertFalse(result.is_max_hit())



class TestReplacedDiceMaxHit(unittest.TestCase):
    """A weapon with its own die has the top face of that die as max hit."""

    def test_a_natural_twenty_is_a_toy_sword_max_hit(self):
        sword = RULES_REGISTRY[ToySwordRules.key]

        result, _rng = _swing(TOY_SWORD_DIE_MAX, attacker_rules=(sword,))

        self.assertTrue(result.is_max_hit())
        self.assertEqual(result.max_hit, TOY_SWORD_DIE_MAX)

    def test_a_nineteen_is_not(self):
        sword = RULES_REGISTRY[ToySwordRules.key]

        result, _rng = _swing(TOY_SWORD_DIE_MAX - 1, attacker_rules=(sword,))

        self.assertFalse(result.is_max_hit())

    def test_the_top_face_of_a_bit_blade_is_a_max_hit(self):
        blade = RULES_REGISTRY[BitBladeRules.key]

        _result, rng = _swing(0, attacker_rules=(blade,))
        top_exponent = rng.randint_calls[0][1]
        result, _rng = _swing(top_exponent, attacker_rules=(blade,))

        self.assertTrue(result.is_max_hit())
        self.assertEqual(result.damage, result.max_hit)

    def test_a_lower_face_of_a_bit_blade_is_not(self):
        blade = RULES_REGISTRY[BitBladeRules.key]

        _result, rng = _swing(0, attacker_rules=(blade,))
        top_exponent = rng.randint_calls[0][1]
        result, _rng = _swing(top_exponent - 1, attacker_rules=(blade,))

        self.assertFalse(result.is_max_hit())
