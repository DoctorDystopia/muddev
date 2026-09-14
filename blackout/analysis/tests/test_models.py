"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/14/2026
Description: Checks that the analysis scripts model the game they describe.

Each script in analysis/ copies a small part of the live game into a model: a
swing, an NPC, a new character, an XP award. A model that drifts from the game
prints wrong numbers with no error. On 09/14/2026 the XP stub no longer passed
the planner's XpEarner gate, and show_xp_economy printed only zeros. These
tests compare each model with the live code that it copies.
"""

import math
import random
import unittest
from types import SimpleNamespace

from evennia.utils.test_resources import EvenniaTest

from analysis import _snapshot_env as env
from analysis import show_combat_level
from analysis import show_rules_map
from analysis import show_xp_economy


# Private constant definitions

# Seed for the pipeline contexts. The tests read hit_prob and the max hit,
# which no roll changes, so any seed gives the same answer.
_RNG_SEED: int = 20260914

# Player levels the swing comparison samples: both ends and the middle.
_SAMPLED_LEVELS: tuple = (0, 50, 127)

# Damage at which every XP style must pay every skill it names.
_PAYING_DAMAGE: int = 16

# A Fortitude level and an HP pool that differ, so a mix-up shows.
_DISTINCT_FORTITUDE: int = 7
_DISTINCT_MAX_HP: int = 99

# Planner inputs for the expected-award check.
_HALF_HIT_CHANCE: float = 0.5
_SMALL_MAX_HIT: int = 2


# Private helper routines

def _plain_profiles() -> list:
    """Unarmed plus every weapon that carries no combat_rules."""
    profiles = [env.unarmed_profile()]
    profiles.extend(
        profile for profile in env.weapon_profiles().values()
        if not profile.combat_rules
    )

    return profiles


def _plain_npcs() -> dict:
    """Every NPC that carries no combat_rules."""
    return {
        npc_key: npc for npc_key, npc in env.npc_combatants().items()
        if not npc.profile.combat_rules
    }


def _live_numbers(attacker, style_key: str, defender) -> tuple:
    """Return (hit_prob, max_hit) from the live rules pipeline for one swing."""
    from systems.gameplay.combat.rules.pipeline import resolve_action

    context = env.build_context(attacker, style_key, defender,
                                random.Random(_RNG_SEED))
    result = resolve_action(context)
    effective_strength = context.rules.effective_strength_level(context)
    max_hit = context.rules.max_hit(context, effective_strength)

    return result.hit_prob, max_hit


# Test cases

class TestSwingMetricsMatchThePipeline(unittest.TestCase):
    """swing_metrics must give the numbers that the live seams give."""

    def _assert_matches(self, attacker, style_key: str, defender) -> None:
        metrics = env.swing_metrics(attacker, style_key, defender)
        hit_prob, max_hit = _live_numbers(attacker, style_key, defender)

        self.assertAlmostEqual(metrics.clamped_hit_chance, hit_prob)
        self.assertEqual(metrics.max_hit, max_hit)

    def test_player_swings_match_for_every_plain_weapon(self):
        for npc_key, npc in _plain_npcs().items():
            for profile in _plain_profiles():
                for style_key in profile.combat_styles:
                    for level in _SAMPLED_LEVELS:
                        with self.subTest(npc=npc_key, weapon=profile.key,
                                          style=style_key, level=level):
                            player = env.player_combatant(level, profile)
                            self._assert_matches(player, style_key, npc)

    def test_npc_swings_match_in_their_active_style(self):
        unarmed = env.unarmed_profile()

        for npc_key, npc in _plain_npcs().items():
            style_key = env.active_style_key(npc.profile)

            for level in _SAMPLED_LEVELS:
                with self.subTest(npc=npc_key, level=level):
                    player = env.player_combatant(level, unarmed)
                    self._assert_matches(npc, style_key, player)

    def test_best_plain_weapon_carries_no_rules(self):
        for npc_key, npc in env.npc_combatants().items():
            with self.subTest(npc=npc_key):
                profile, _style, _metrics = env.best_plain_weapon(
                    _SAMPLED_LEVELS[1], npc
                )
                self.assertFalse(profile.combat_rules)


class TestCombatantsMatchTheGame(unittest.TestCase):
    """A Combatant must carry the numbers the live entity fights with."""

    def test_npc_combatant_copies_its_spawn_block(self):
        from world.npc_database import NPC_DB

        npcs = env.npc_combatants()

        for npc_key, npc_def in NPC_DB.items():
            with self.subTest(npc=npc_key):
                block = npc_def.to_combat_block()
                combatant = npcs[npc_key]

                self.assertEqual(combatant.fortitude_level, block["fortitude_level"])
                self.assertEqual(combatant.max_hp, block["max_hp"])
                self.assertEqual(combatant.profile.attack_speed, block["attack_speed"])
                self.assertEqual(combatant.profile.default_style,
                                 block["default_combat_style"])

    def test_every_npc_active_style_is_one_it_declares(self):
        for npc_key, npc in env.npc_combatants().items():
            with self.subTest(npc=npc_key):
                style_key = env.active_style_key(npc.profile)
                self.assertIn(style_key, npc.profile.combat_styles)

    def test_context_reads_the_fortitude_level_not_hit_points(self):
        from systems.gameplay.progression.skills.constants import FORTITUDE_SKILL_KEY

        profile = env.unarmed_profile()
        fighter = env.Combatant(
            name="fighter", strike_level=1, brawn_level=1, defense_level=1,
            fortitude_level=_DISTINCT_FORTITUDE, max_hp=_DISTINCT_MAX_HP,
            profile=profile,
        )
        style_key = next(iter(profile.combat_styles))
        context = env.build_context(fighter, style_key, fighter,
                                    random.Random(_RNG_SEED))

        self.assertEqual(context.attacker_levels[FORTITUDE_SKILL_KEY],
                         _DISTINCT_FORTITUDE)
        self.assertEqual(context.defender_levels[FORTITUDE_SKILL_KEY],
                         _DISTINCT_FORTITUDE)


class TestSpawnCombatantMatchesCharacterCreation(EvenniaTest):
    """spawn_combatant must be the character that creation makes."""

    def test_new_character_levels_and_hit_points(self):
        from systems.gameplay.combat.rules.context import read_skill_levels
        from systems.gameplay.progression.skills import constants as skill_const

        spawned = env.spawn_combatant(env.unarmed_profile())
        levels = read_skill_levels(self.char1)

        self.assertEqual(levels[skill_const.STRIKE_SKILL_KEY], spawned.strike_level)
        self.assertEqual(levels[skill_const.BRAWN_SKILL_KEY], spawned.brawn_level)
        self.assertEqual(levels[skill_const.DEFENSE_SKILL_KEY], spawned.defense_level)
        self.assertEqual(levels[skill_const.FORTITUDE_SKILL_KEY],
                         spawned.fortitude_level)
        self.assertEqual(self.char1.max_hp, spawned.max_hp)


class TestXpEconomyUsesThePlanner(unittest.TestCase):
    """show_xp_economy must get real awards out of combat's XP planner."""

    def test_planning_stub_passes_the_planner_gate(self):
        from systems.gameplay.combat.protocols import XpEarner

        self.assertIsInstance(show_xp_economy._PlanningStub.skills, XpEarner)

    def test_every_style_pays_every_skill_it_names(self):
        for style_name, entry in show_xp_economy._style_table().items():
            style = show_xp_economy._synthetic_style(style_name, entry["skills"])
            awards = dict(show_xp_economy._awards_for(style, _PAYING_DAMAGE))

            for skill_key in entry["skills"]:
                with self.subTest(style=style_name, skill=skill_key):
                    self.assertGreater(awards.get(skill_key, 0), 0)

    def test_expected_award_averages_misses_and_every_roll(self):
        from systems.gameplay.combat import constants as const
        from systems.gameplay.progression.skills.constants import FORTITUDE_SKILL_KEY

        metrics = SimpleNamespace(clamped_hit_chance=_HALF_HIT_CHANCE,
                                  max_hit=_SMALL_MAX_HIT)
        style = show_xp_economy._synthetic_style("controlled",
                                                 const.CONTROLLED_XP_SKILLS)
        rate = const.XP_PER_DAMAGE_BY_SKILL[FORTITUDE_SKILL_KEY]
        rolls = range(_SMALL_MAX_HIT + 1)
        per_roll = [int(round(rate * damage)) for damage in rolls]
        expected = _HALF_HIT_CHANCE * sum(per_roll) / len(per_roll)

        measured = show_xp_economy._expected_award(style, FORTITUDE_SKILL_KEY,
                                                   metrics)

        self.assertAlmostEqual(measured, expected)


class TestRulesMapFlagsEveryRulesWeapon(unittest.TestCase):
    """The caveat list must name every weapon that swing_metrics ignores."""

    def test_every_weapon_with_rules_is_flagged(self):
        flagged = {entry["name"] for entry in show_rules_map._unmodellable_profiles()}
        expected = {
            profile.name for profile in env.weapon_profiles().values()
            if profile.combat_rules
        }

        self.assertEqual(flagged, expected)


class TestCombatLevelCeiling(unittest.TestCase):
    """The unfloored combat level must floor to get_combat_level."""

    def test_every_build_at_every_level(self):
        for label, skill_keys in show_combat_level.BUILD_SHAPES.items():
            for level in env.level_range():
                with self.subTest(build=label, level=level):
                    value = show_combat_level._unfloored_level(skill_keys, level)
                    build = show_combat_level._build_levels(skill_keys, level)
                    expected = show_combat_level._combat_level_for(build)

                    self.assertEqual(math.floor(value), expected)
