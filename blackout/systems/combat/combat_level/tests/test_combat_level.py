"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Tests for combat level -- branch registry discovery, the
             base-branch score formula, and the end-to-end formula for both
             Characters and NPCs.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat
"""

import math

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.combat import constants as const
from systems.combat.combat_level.branch_defs.base_branch import CombatBranch
from systems.combat.combat_level.branch_defs.melee import MeleeBranch
from systems.combat.combat_level.logic import get_combat_level
from systems.combat.combat_level.registry import COMBAT_BRANCH_REGISTRY
from systems.progression.skills.constants import FORTITUDE_SKILL_KEY
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.npc_combat import HostileNPC


class TestCombatBranchRegistry(EvenniaTest):
    """Auto-discovery mirrors AURA_REGISTRY / SKILL_REGISTRY."""

    def test_melee_branch_is_discovered(self):
        self.assertIn(MeleeBranch.key, COMBAT_BRANCH_REGISTRY)

    def test_registry_holds_instances_not_classes(self):
        self.assertIsInstance(COMBAT_BRANCH_REGISTRY[MeleeBranch.key], MeleeBranch)

    def test_base_branch_is_not_registered(self):
        self.assertNotIn("base", COMBAT_BRANCH_REGISTRY)


class TestCombatBranchScoreShapes(EvenniaTest):
    """compute_score's default covers both a solo skill and a paired sum."""

    def test_paired_skills_sum_raw(self):
        branch = MeleeBranch()
        levels = {"strike": 40, "brawn": 20}

        score = branch.compute_score(lambda key: levels[key])

        self.assertEqual(score, (40 + 20) * const.COMBAT_LEVEL_BRANCH_WEIGHT)

    def test_solo_skill_applies_the_osrs_multiplier(self):
        class SoloBranch(CombatBranch):
            key = "solo_test"
            name = "Solo Test"
            skill_keys = ("guns",)

        branch = SoloBranch()
        score = branch.compute_score(lambda key: 50)

        expected_raw = math.floor(50 * const.COMBAT_LEVEL_SOLO_SKILL_MULTIPLIER)
        self.assertEqual(score, expected_raw * const.COMBAT_LEVEL_BRANCH_WEIGHT)

    def test_branch_with_no_skills_scores_zero(self):
        branch = CombatBranch()
        self.assertEqual(branch.compute_score(lambda key: 999), 0.0)


class TestGetCombatLevelForCharacter(EvenniaTest):
    """End-to-end formula against a real Character + SkillHandler."""

    character_typeclass = BlackoutCharacter

    def _set_level(self, skill_key: str, level: int) -> None:
        self.char1.db.skills[skill_key] = {"level": level, "xp": 0}

    def test_fresh_character_uses_seeded_fortitude_only(self):
        # Character creation seeds Fortitude to FORTITUDE_START_LEVEL (10);
        # strike/brawn/defense start at 0.
        expected_base = const.COMBAT_LEVEL_BASE_WEIGHT * const.FORTITUDE_START_LEVEL

        self.assertEqual(get_combat_level(self.char1), math.floor(expected_base))

    def test_melee_stats_raise_combat_level(self):
        self._set_level(FORTITUDE_SKILL_KEY, 50)
        self._set_level("defense", 40)
        self._set_level("strike", 60)
        self._set_level("brawn", 30)

        base = const.COMBAT_LEVEL_BASE_WEIGHT * (50 + 40)
        melee = const.COMBAT_LEVEL_BRANCH_WEIGHT * (60 + 30)
        expected = math.floor(base + melee)

        self.assertEqual(get_combat_level(self.char1), expected)

    def test_unbuilt_augmentation_skill_does_not_raise(self):
        # 'augmentation' is not in SKILL_REGISTRY yet -- this must not raise
        # ValueError the way a direct skills.get_level('augmentation') would.
        try:
            get_combat_level(self.char1)
        except ValueError:
            self.fail("get_combat_level raised on an unbuilt Combat Specialty skill")

    def test_combat_level_property_matches_the_function(self):
        self._set_level("strike", 25)
        self.assertEqual(self.char1.combat_level, get_combat_level(self.char1))


class TestGetCombatLevelForNPC(EvenniaTest):
    """The same formula must work off HostileNPC's StatBlockSkills."""

    def setUp(self):
        super().setUp()
        self.npc = create_object(HostileNPC, key="Test Mutant", location=self.room1)
        self.npc.apply_combat_stats(
            {
                "strike_level": 20,
                "brawn_level": 15,
                "defense_level": 10,
                "max_hp": 50,
            }
        )

    def test_npc_combat_level_matches_formula(self):
        # This stat block is hand-built rather than assembled by
        # NpcDef.to_combat_block, so it names no fortitude_level at all and
        # StatBlockSkills reports the absent-skill floor of 0. An NPC that
        # came from an NpcDef gets its Fortitude derived from max_hp instead
        # -- see test_an_npc_def_derives_fortitude_from_max_hp below.
        base = const.COMBAT_LEVEL_BASE_WEIGHT * (0 + 10)
        melee = const.COMBAT_LEVEL_BRANCH_WEIGHT * (20 + 15)
        expected = math.floor(base + melee)

        self.assertEqual(get_combat_level(self.npc), expected)

    def test_npc_combat_level_property_works(self):
        self.assertEqual(self.npc.combat_level, get_combat_level(self.npc))

    def test_an_npc_def_derives_fortitude_from_max_hp(self):
        """The regression the shim hid.

        to_combat_block never emitted a fortitude_level, and the old shim
        answered its unknown-key default of 1 -- so the Big Mutant's 87
        hitpoints produced a combat level computed off a Fortitude of 1, and
        it read as a far weaker monster than it is.
        """
        from world.npc_database import NPC_DB

        big_mutant = NPC_DB["big_mutant"].create(location=self.room1)

        self.assertEqual(big_mutant.skills.get_level("fortitude"), 87)

        base = const.COMBAT_LEVEL_BASE_WEIGHT * (87 + 1)
        melee = const.COMBAT_LEVEL_BRANCH_WEIGHT * (1 + 1)
        expected = math.floor(base + melee)

        self.assertEqual(get_combat_level(big_mutant), expected)
        self.assertGreater(
            get_combat_level(big_mutant),
            get_combat_level(NPC_DB["mutant_raider"].create(location=self.room1)),
            msg="an 87-hp monster must out-level a 5-hp one",
        )
