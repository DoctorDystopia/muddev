"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/01/2026
Description: Fortitude -> max HP scaling.

Design reference: 02_Player/Player_Overview.md §"Health" — hitpoints are
directly linked to the Fortitude skill, players start at exactly level 10,
and every point of damage dealt grants 1.33 Fortitude XP regardless of the
combat style used.

Regression guarded: sync_max_hp_from_fortitude had zero callers, so max_hp
stayed at its creation value forever no matter how much Fortitude XP was
earned -- every character was permanently a 10 HP character.
"""

from evennia.utils.test_resources import EvenniaTest

from systems.combat import constants as combat_constants
from systems.progression.skills import logic
from systems.progression.skills.constants import FORTITUDE_SKILL_KEY
from typeclasses.characters import Character as BlackoutCharacter


class TestFortitudeHpScaling(EvenniaTest):

    character_typeclass = BlackoutCharacter

    def test_new_character_starts_at_seed_level(self):
        self.char1.skills.seed_fortitude_on_creation()

        level = self.char1.skills.get_level(FORTITUDE_SKILL_KEY)
        self.assertEqual(level, combat_constants.FORTITUDE_START_LEVEL)

    def test_new_character_max_hp_matches_seed_level(self):
        self.char1.skills.seed_fortitude_on_creation()

        expected = (
            combat_constants.FORTITUDE_START_LEVEL
            * combat_constants.HP_PER_FORTITUDE_LEVEL
        )
        self.assertEqual(self.char1.db.max_hp, expected)

    def test_sync_tracks_fortitude_one_to_one(self):
        self.char1.db.skills[FORTITUDE_SKILL_KEY] = {"level": 42, "xp": 0}

        self.char1.skills.sync_max_hp_from_fortitude()

        self.assertEqual(
            self.char1.db.max_hp, 42 * combat_constants.HP_PER_FORTITUDE_LEVEL
        )

    def test_levelling_fortitude_raises_max_hp(self):
        """The regression: gaining a Fortitude level must move the HP cap."""
        self.char1.skills.seed_fortitude_on_creation()
        before_level = self.char1.skills.get_level(FORTITUDE_SKILL_KEY)
        before_cap = self.char1.db.max_hp

        # Enough XP to clear at least one level from the seed point.
        needed = logic.calculate_xp_needed(before_level)
        self.char1.skills.add_xp(FORTITUDE_SKILL_KEY, needed * 2)

        after_level = self.char1.skills.get_level(FORTITUDE_SKILL_KEY)
        self.assertGreater(after_level, before_level)
        self.assertGreater(self.char1.db.max_hp, before_cap)
        self.assertEqual(
            self.char1.db.max_hp,
            after_level * combat_constants.HP_PER_FORTITUDE_LEVEL,
        )

    def test_levelling_another_skill_does_not_touch_max_hp(self):
        """Only Fortitude is registered as an HP-affecting level-up."""
        self.char1.skills.seed_fortitude_on_creation()
        before_cap = self.char1.db.max_hp

        needed = logic.calculate_xp_needed(0)
        self.char1.skills.add_xp("strike", needed * 3)

        self.assertEqual(self.char1.db.max_hp, before_cap)

    def test_max_hp_cap_matches_max_fortitude_level(self):
        expected = (
            combat_constants.MAX_FORTITUDE_LEVEL
            * combat_constants.HP_PER_FORTITUDE_LEVEL
        )
        self.assertEqual(combat_constants.MAX_HP_CAP, expected)


class TestFortitudeXpRate(EvenniaTest):
    """Fortitude earns its own rate, not the attacking style's."""

    character_typeclass = BlackoutCharacter

    def test_fortitude_has_a_dedicated_rate(self):
        self.assertIn(
            FORTITUDE_SKILL_KEY, combat_constants.XP_PER_DAMAGE_BY_SKILL
        )

    def test_fortitude_rate_is_133_per_damage(self):
        rate = combat_constants.XP_PER_DAMAGE_BY_SKILL[FORTITUDE_SKILL_KEY]
        self.assertAlmostEqual(rate, 4.0 / 3.0)

    def test_fortitude_earns_its_own_rate_under_an_accurate_style(self):
        """An accurate-style hit pays strike 4.0/dmg but fortitude 1.33/dmg."""
        from systems.combat.combat import _award_style_xp

        self.char1.skills.seed_fortitude_on_creation()
        style = combat_constants.UNARMED_COMBAT_STYLES["punch"]
        damage = 3

        strike_before = self.char1.skills.get_total_xp("strike")
        fort_before = self.char1.skills.get_total_xp(FORTITUDE_SKILL_KEY)

        _award_style_xp(self.char1, style, damage)

        strike_gain = self.char1.skills.get_total_xp("strike") - strike_before
        fort_gain = self.char1.skills.get_total_xp(FORTITUDE_SKILL_KEY) - fort_before

        self.assertEqual(strike_gain, round(combat_constants.XP_PER_DAMAGE_ACCURATE * damage))
        self.assertEqual(fort_gain, round(combat_constants.XP_PER_DAMAGE_FORTITUDE * damage))
        self.assertLess(fort_gain, strike_gain)
