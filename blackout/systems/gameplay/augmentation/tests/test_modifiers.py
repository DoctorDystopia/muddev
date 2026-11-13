"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The Phase 5 mechanics of DESIGN-0015: the roll of Overclock,
             the guard augments on the defender side of the pipeline, the
             conflict group, Mend on the regen sweep, and Reach on the ring
             of the lit aura. Every expectation is derived from the owner
             of the number, never typed.
Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.augmentation
"""

import random
import unittest
from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import detail
from systems.gameplay.augmentation import rules
from systems.gameplay.augmentation import sockets
from systems.gameplay.augmentation.handler import (
    BlackoutAugmentHandler,
    ensure_augment_handler,
    get_augment_handler_for,
)
from systems.gameplay.augmentation.registry import AUGMENT_REGISTRY, augments_in_order
from systems.gameplay.augmentation.rules import AugmentModifierRules
from systems.gameplay.augmentation.tests import support
from systems.gameplay.combat import constants as combat_const
from systems.gameplay.combat import hp_regen
from systems.gameplay.combat.auras import aura_handler as aura_handler_module
from systems.gameplay.combat.auras.aura_handler import ensure_aura_handler
from systems.gameplay.combat.auras.registry import AURA_REGISTRY
from systems.gameplay.combat.rules.context import ActionContext
from systems.gameplay.combat.rules.pipeline import resolve_action
from systems.gameplay.progression.skills.constants import (
    SKILL_KEY_AUGMENTATION,
    SKILL_KEY_BRAWN,
    SKILL_KEY_DEFENSE,
    SKILL_KEY_FORTITUDE,
    SKILL_KEY_STRIKE,
)
from typeclasses.characters import Character as BlackoutCharacter


_A_LEVEL = 50
_SEEDS = range(40)

# A stat block with numbers in every field the swing reads, so a dropped
# field shows as a difference.
_ATTACKER_STATS = {
    "melee_stab_attack_bonus": 7,
    "melee_slash_attack_bonus": 4,
    "melee_crush_attack_bonus": -2,
    "melee_strength_bonus": 9,
}
_DEFENDER_STATS = {
    "melee_stab_defense_bonus": 5,
    "melee_slash_defense_bonus": 3,
    "melee_crush_defense_bonus": 11,
    "melee_strength_bonus": 0,
}
_ATTACKER_LEVELS = {
    SKILL_KEY_STRIKE: 60,
    SKILL_KEY_BRAWN: 60,
    SKILL_KEY_DEFENSE: 20,
    SKILL_KEY_FORTITUDE: 30,
}
_DEFENDER_LEVELS = {
    SKILL_KEY_STRIKE: 15,
    SKILL_KEY_BRAWN: 15,
    SKILL_KEY_DEFENSE: 10,
    SKILL_KEY_FORTITUDE: 22,
}


def _augments_that(predicate) -> list:
    return [augment for augment in augments_in_order() if predicate(augment)]


def _one(predicate, test):
    found = _augments_that(predicate)

    if not found:
        test.skipTest("no augment of that kind is registered")

    return found[0]


def _context(seed: int, attacker_rules=(), defender_rules=()) -> ActionContext:
    """A melee stab with no Evennia objects, as the pipeline tests build it."""
    return ActionContext(
        attacker=None,
        defender=None,
        weapon=None,
        weapon_data={},
        style={},
        attack_type=combat_const.MELEE_ATTACK_TYPE_STAB,
        attacker_stats=dict(_ATTACKER_STATS),
        defender_stats=dict(_DEFENDER_STATS),
        attacker_levels=dict(_ATTACKER_LEVELS),
        defender_levels=dict(_DEFENDER_LEVELS),
        stance_boost={},
        attacker_rules=tuple(attacker_rules),
        defender_rules=tuple(defender_rules),
        rng=random.Random(seed),
    )


class _Lit:

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, _A_LEVEL)
        self.handler = ensure_augment_handler(self.char1)

    def tearDown(self):
        handler = get_augment_handler_for(self.char1)

        if handler is not None:
            handler.stop_handler()

        super().tearDown()

    def _light(self, augment, power_level=aug_const.AUG_POWER_LEVEL_DEFAULT) -> None:
        self.handler.light(augment, power_level)


class TestOverclock(_Lit, EvenniaTest):
    """One augment rolls. The roll rides every other lit stat augment."""

    def setUp(self):
        super().setUp()
        self.roller = _one(lambda augment: augment.rolls, self)
        self.stat = _one(lambda augment: augment.family == aug_const.FAMILY_ACCURACY, self)

    def _light_rolled(self, seed: int) -> float:
        with mock.patch.object(BlackoutAugmentHandler, "roll_rng", random.Random(seed)):
            self._light(self.roller)

        return self.handler.roll_of(self.roller.key)

    def test_a_light_rolls_inside_the_range_of_the_level(self):
        roll = self._light_rolled(3)
        low = self.roller.roll_low(_A_LEVEL)

        self.assertGreaterEqual(roll, low)
        self.assertLessEqual(roll, aug_const.AUG_ROLL_HIGH)
        self.assertGreater(low, self.roller.roll_low(aug_const.NO_UNLOCK_LEVEL))

    def test_the_low_end_never_passes_the_high_end(self):
        top = max(aug_const.SOCKET_UNLOCK_LEVELS.values()) * 10

        self.assertLessEqual(self.roller.roll_low(top), aug_const.AUG_ROLL_HIGH)

    def test_the_roll_rides_every_other_lit_stat_augment(self):
        roll = self._light_rolled(5)
        self._light(self.stat)

        built = {rule.augment.key: rule for rule in rules.active_rules(self.char1)}

        self.assertNotIn(self.roller.key, built, "the roller contributes no channel of its own")
        expected = self.stat.bonus_for(_A_LEVEL, aug_const.AUG_POWER_LEVEL_DEFAULT) + roll
        self.assertAlmostEqual(expected, built[self.stat.key].bonus)

    def test_a_relight_rerolls(self):
        first = self._light_rolled(1)
        second = self._light_rolled(2)

        self.assertNotEqual(first, second)

    def test_a_put_out_drops_the_roll(self):
        self._light_rolled(4)

        self.handler.put_out(self.roller.key)

        self.assertEqual(0.0, rules.strength_roll(self.char1))

    def test_the_row_shows_the_roll_as_its_note(self):
        support.open_every_socket(self.char1)
        support.socket_fitting(self.char1, [self.roller])
        roll = self._light_rolled(6)

        rows = {row["key"]: row for row in detail.ability_rows(self.char1)}
        note = rows[self.roller.key][aug_const.AUG_ROLL_NOTE[:0] or "note"]

        self.assertEqual(aug_const.AUG_ROLL_NOTE.format(percent=roll * 100), note)
        self.assertEqual("", rows[aug_const.AUG_SET_ROW_KEY]["note"])


class TestGuards(_Lit, EvenniaTest):
    """A guard cuts the landed damage of its type, on the defender side only."""

    def setUp(self):
        super().setUp()
        self.guards = _augments_that(lambda augment: augment.family == aug_const.FAMILY_GUARD)

        if not self.guards:
            self.skipTest("no guard is registered")

    def _guard_for(self, damage_type: str):
        for guard in self.guards:
            if guard.damage_type == damage_type:
                return guard

        self.skipTest(f"no guard of type {damage_type}")

    def test_the_guards_share_one_conflict_group(self):
        groups = {guard.conflict_group for guard in self.guards}

        self.assertEqual({aug_const.CONFLICT_GROUP_GUARD}, groups)

    def test_lighting_one_guard_puts_the_other_out(self):
        if len(self.guards) < 2:
            self.skipTest("one guard only")

        first, second = self.guards[0], self.guards[1]
        self._light(first)
        self._light(second)

        self.assertFalse(self.handler.is_lit(first.key))
        self.assertTrue(self.handler.is_lit(second.key))

    def test_a_guard_cuts_the_damage_of_its_type_on_the_defender_side(self):
        guard = self._guard_for(combat_const.DAMAGE_TYPE_MELEE)
        bonus = guard.bonus_for(_A_LEVEL, aug_const.AUG_POWER_LEVEL_DEFAULT)
        rule = AugmentModifierRules(guard, bonus)
        cut_seen = False

        for seed in _SEEDS:
            plain = resolve_action(_context(seed))
            guarded = resolve_action(_context(seed, defender_rules=(rule,)))

            with self.subTest(seed=seed):
                self.assertEqual(plain.hit, guarded.hit)

                if plain.damage > 0:
                    expected = max(combat_const.ACTION_DAMAGE_FLOOR,
                                   int(plain.damage * (1.0 - bonus)))
                    self.assertEqual(expected, guarded.damage)
                    cut_seen = cut_seen or guarded.damage < plain.damage

        self.assertTrue(cut_seen, "no seed landed enough damage to show the cut")

    def test_a_guard_on_the_attacker_side_changes_nothing(self):
        guard = self._guard_for(combat_const.DAMAGE_TYPE_MELEE)
        rule = AugmentModifierRules(guard, guard.bonus_for(_A_LEVEL, aug_const.AUG_POWER_LEVELS))

        for seed in _SEEDS:
            plain = resolve_action(_context(seed))
            armed = resolve_action(_context(seed, attacker_rules=(rule,)))

            with self.subTest(seed=seed):
                self.assertEqual(plain.damage, armed.damage)

    def test_a_guard_of_another_type_changes_nothing(self):
        guard = self._guard_for(combat_const.DAMAGE_TYPE_PROJECTILE)
        rule = AugmentModifierRules(guard, guard.bonus_for(_A_LEVEL, aug_const.AUG_POWER_LEVELS))

        for seed in _SEEDS:
            plain = resolve_action(_context(seed))
            guarded = resolve_action(_context(seed, defender_rules=(rule,)))

            with self.subTest(seed=seed):
                self.assertEqual(plain.damage, guarded.damage)


class TestMend(_Lit, EvenniaTest):
    """Mend shortens the regen interval: the sweep heals a share more."""

    def setUp(self):
        super().setUp()
        self.mend = _one(lambda augment: augment.modifies == aug_const.MODIFIES_REGEN, self)

    def test_nothing_lit_keeps_the_whole_interval(self):
        self.assertEqual(1.0, rules.regen_interval_share(self.char1))
        self.assertEqual(combat_const.HP_REGEN_AMOUNT, hp_regen._heal_amount(self.char1))

    def test_mend_cuts_the_share_by_its_bonus(self):
        self._light(self.mend)
        expected = 1.0 - self.mend.bonus_for(_A_LEVEL, aug_const.AUG_POWER_LEVEL_DEFAULT)

        self.assertAlmostEqual(max(aug_const.AUG_REGEN_SHARE_FLOOR, expected),
                               rules.regen_interval_share(self.char1))

    def test_the_sweeps_heal_the_whole_of_the_shortened_interval(self):
        self._light(self.mend)
        share = rules.regen_interval_share(self.char1)
        sweeps = 8

        total = sum(hp_regen._heal_amount(self.char1) for _ in range(sweeps))

        expected = sweeps * combat_const.HP_REGEN_AMOUNT / share
        self.assertGreaterEqual(total, int(expected) - 1)
        self.assertLessEqual(total, int(expected))
        self.assertGreater(total, sweeps * combat_const.HP_REGEN_AMOUNT)


class TestReach(_Lit, EvenniaTest):
    """Reach widens the ring of the lit aura, and the ring cache follows."""

    def setUp(self):
        super().setUp()
        self.reach = _one(lambda augment: augment.modifies == aug_const.MODIFIES_REACH, self)
        self.aura = AURA_REGISTRY["righteous_fire"]
        self.char1.db.skills[SKILL_KEY_FORTITUDE] = {"level": 100, "xp": 0}
        self.aura_handler = ensure_aura_handler(self.char1)
        self.aura_handler.activate(self.aura)

    def tearDown(self):
        handler = aura_handler_module.get_aura_handler_for(self.char1)

        if handler is not None:
            handler.stop_aura()

        super().tearDown()

    def test_the_tiles_follow_the_power_level(self):
        levels = range(aug_const.AUG_POWER_LEVEL_MIN,
                       aug_const.AUG_POWER_LEVELS + 1)
        tiles = [self.reach.tiles_for(power_level) for power_level in levels]

        self.assertEqual(sorted(tiles), tiles)
        self.assertEqual(aug_const.AUG_REACH_TILES, tiles[-1])
        self.assertGreaterEqual(tiles[0], 1)

    def test_nothing_lit_keeps_the_radius_of_the_aura(self):
        self.assertEqual(0, rules.reach_bonus(self.char1))
        self.assertEqual(self.aura.radius, self.aura_handler.radius_for(self.char1, self.aura))

    def test_reach_adds_its_tiles_to_the_radius(self):
        self._light(self.reach, aug_const.AUG_POWER_LEVEL_MIN)

        expected = self.aura.radius + self.reach.tiles_for(aug_const.AUG_POWER_LEVEL_MIN)
        self.assertEqual(expected, self.aura_handler.radius_for(self.char1, self.aura))

    def test_the_ring_cache_rebuilds_when_the_radius_moves(self):
        self.aura_handler._current_ring(self.char1, self.aura)
        self.assertEqual(self.aura.radius, self.aura_handler.ndb.ring_radius)

        self._light(self.reach)
        self.aura_handler._current_ring(self.char1, self.aura)

        self.assertEqual(self.aura_handler.radius_for(self.char1, self.aura),
                         self.aura_handler.ndb.ring_radius)

    def test_a_light_sends_the_ring_again_with_the_new_radius(self):
        with mock.patch.object(aura_handler_module.feed, "emit_aura") as sent:
            self._light(self.reach)

        radii = [call.args[3] for call in sent.call_args_list
                 if call.args[1] == aura_handler_module.feed.AURA_EVENT_ACTIVATE]

        self.assertIn(self.aura_handler.radius_for(self.char1, self.aura), radii)


class TestModifierDefs(unittest.TestCase):
    """The shapes of the Phase 5 augments. No DB."""

    def test_a_modifier_names_what_it_changes(self):
        for augment in AUGMENT_REGISTRY.values():
            if augment.family in (aug_const.FAMILY_MODIFIER, aug_const.FAMILY_REGEN,
                                  aug_const.FAMILY_AURA):
                with self.subTest(augment=augment.key):
                    self.assertTrue(augment.modifies)

    def test_the_guard_base_is_not_registered(self):
        self.assertNotIn(aug_const.FAMILY_GUARD, AUGMENT_REGISTRY)

        for augment in AUGMENT_REGISTRY.values():
            with self.subTest(augment=augment.key):
                self.assertNotEqual(augment.key, "base")

    def test_every_tip_has_an_effect_line_and_the_sockets(self):
        for augment in AUGMENT_REGISTRY.values():
            with self.subTest(augment=augment.key):
                lines = augment.tip_lines(_A_LEVEL)

                self.assertEqual(augment.description, lines[0])
                self.assertTrue(any("Fits:" in line for line in lines))
