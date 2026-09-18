"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/01/2026
Description: Tests for the combat message builders -- specifically how a hit
             line carries its XP readout, and the combat HP bar. Pure string
             assembly, so a plain TestCase, wrapped in a class so Django's
             discovery collects it.

             The readout itself is tested where it now lives,
             systems/gameplay/progression/tests/test_xp_awards.py.

Run with:
    evennia test --settings settings.py systems.gameplay.combat
"""



import unittest

from evennia.utils.ansi import strip_ansi

from systems.gameplay.combat import combat_msg
from systems.gameplay.combat import constants as const
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills import xp_awards
from systems.interface.ui.meters import METER_WIDTH



class _FakeCombatant:
    """Minimal stand-in for a CombatEntity: the formatters read only .key."""

    def __init__(self, key: str) -> None:
        self.key = key



class TestOutgoingHitCarriesXp(unittest.TestCase):
    """format_outgoing_hit must fold the award into one line."""

    def setUp(self):
        self.attacker = _FakeCombatant("superuser_val")
        self.target = _FakeCombatant("Mutant Raider")

    def test_hit_without_xp_is_unchanged(self):
        """The xp_text default keeps every pre-existing call site valid."""
        visible = strip_ansi(
            combat_msg.format_outgoing_hit(self.attacker, self.target, 3)
        )

        self.assertEqual(visible, "You hit Mutant Raider for 3.")

    def test_hit_with_xp_appends_the_award_on_one_line(self):
        awards = [(skill_constants.SKILL_KEY_STRIKE, 12), (skill_constants.SKILL_KEY_FORTITUDE, 4)]
        xp_text = xp_awards.format_xp_suffix(awards)

        rendered = combat_msg.format_outgoing_hit(
            self.attacker, self.target, 3, xp_text
        )
        visible = strip_ansi(rendered)

        self.assertNotIn("\n", visible)
        self.assertIn("for 3.", visible)
        self.assertIn(strip_ansi(xp_awards.format_xp_readout(awards)), visible)



class TestHpStatusFormatting(unittest.TestCase):
    """The combat HP bar: a label plus the shared meter."""

    def test_label_precedes_the_bar(self):
        visible = strip_ansi(combat_msg.format_hp_status("Mutant Raider", 3, 5))

        self.assertTrue(visible.startswith("Mutant Raider"))

    def test_numbers_are_readable_without_colour(self):
        """Screen readers get the values even though the fill is a colour."""
        visible = strip_ansi(combat_msg.format_hp_status("Mutant Raider", 3, 5))

        self.assertIn("3", visible)
        self.assertIn("5", visible)

    def test_a_long_name_does_not_eat_the_bar(self):
        """The label lives outside the meter precisely so this cannot happen —
        display_meter truncates its own base text to the bar width."""
        long_name = "A Very Long Cybernetic Horror Indeed"

        visible = strip_ansi(combat_msg.format_hp_status(long_name, 3, 5))
        bar_portion = visible[len(long_name) + 1:]

        self.assertEqual(len(bar_portion), METER_WIDTH)

    def test_self_label_is_available_for_the_defender(self):
        visible = strip_ansi(
            combat_msg.format_hp_status(combat_msg.SELF_HP_LABEL, 8, 10)
        )

        self.assertTrue(visible.startswith("You"))

    def test_a_dead_target_renders_an_empty_bar_not_a_full_one(self):
        empty = strip_ansi(combat_msg.format_hp_status("Mutant Raider", 0, 5))
        full = strip_ansi(combat_msg.format_hp_status("Mutant Raider", 5, 5))

        self.assertIn("0", empty)
        self.assertNotEqual(empty, full)



class TestCombatStatBonusFormatting(unittest.TestCase):
    """Player-facing rendering of a combat_stat_bonuses dict."""

    def test_empty_dict_renders_no_lines(self):
        self.assertEqual(combat_msg.format_combat_stat_bonuses({}), [])

    def test_all_zero_dict_renders_no_lines(self):
        bonuses = {"stab_attack_bonus": 0, "melee_strength_bonus": 0}

        self.assertEqual(combat_msg.format_combat_stat_bonuses(bonuses), [])

    def test_key_is_derived_into_a_title_cased_label(self):
        visible = strip_ansi(
            combat_msg.format_combat_stat_bonuses({"stab_attack_bonus": 4})[0]
        )

        self.assertEqual(visible, "Stab Attack: +4")

    def test_negative_value_has_no_plus_sign(self):
        visible = strip_ansi(
            combat_msg.format_combat_stat_bonuses({"crush_attack_bonus": -2})[0]
        )

        self.assertEqual(visible, "Crush Attack: -2")

    def test_zero_entries_are_skipped_among_nonzero_ones(self):
        bonuses = {"stab_attack_bonus": 4, "slash_attack_bonus": 0}

        lines = [strip_ansi(line) for line in combat_msg.format_combat_stat_bonuses(bonuses)]

        self.assertEqual(lines, ["Stab Attack: +4"])

    def test_positive_and_negative_use_different_colours(self):
        positive = combat_msg.format_combat_stat_bonuses({"stab_attack_bonus": 4})[0]
        negative = combat_msg.format_combat_stat_bonuses({"stab_attack_bonus": -4})[0]

        self.assertNotEqual(positive, negative)
        self.assertNotEqual(strip_ansi(positive), positive)


class TestMissVerbs(unittest.TestCase):
    """A bow that "swings at" its target is the only thing a player can read
    on a missed shot, and it was the literal word in the line until the
    damage type started deciding it."""

    def setUp(self):
        self.attacker = _FakeCombatant("Archer")
        self.target = _FakeCombatant("Mutant Raider")

    def _outgoing(self, damage_type):
        return strip_ansi(
            combat_msg.format_outgoing_miss(self.attacker, self.target, damage_type)
        )

    def _incoming(self, damage_type):
        return strip_ansi(
            combat_msg.format_incoming_miss(self.attacker, self.target, damage_type)
        )

    def test_a_melee_miss_still_swings(self):
        expected = const.MISS_VERBS[const.DAMAGE_TYPE_MELEE][
            const.MISS_VERB_SELF_KEY
        ]

        self.assertIn(expected, self._outgoing(const.DAMAGE_TYPE_MELEE))

    def test_a_projectile_miss_does_not_swing(self):
        melee = const.MISS_VERBS[const.DAMAGE_TYPE_MELEE][const.MISS_VERB_SELF_KEY]

        self.assertNotIn(melee, self._outgoing(const.DAMAGE_TYPE_PROJECTILE))

    def test_a_projectile_miss_reads_its_own_verb(self):
        expected = const.MISS_VERBS[const.DAMAGE_TYPE_PROJECTILE][
            const.MISS_VERB_SELF_KEY
        ]

        self.assertIn(expected, self._outgoing(const.DAMAGE_TYPE_PROJECTILE))

    def test_both_sides_of_one_miss_name_one_action(self):
        """Two persons of one row, so the attacker and the defender cannot
        read two different events."""
        row = const.MISS_VERBS[const.DAMAGE_TYPE_PROJECTILE]

        self.assertIn(
            row[const.MISS_VERB_OTHER_KEY], self._incoming(const.DAMAGE_TYPE_PROJECTILE)
        )

    def test_an_unknown_damage_type_still_makes_a_sentence(self):
        """This runs on the tick. A missing row costs a word, never a fight."""
        fallback = const.MISS_VERBS[const.MISS_VERB_FALLBACK_TYPE][
            const.MISS_VERB_SELF_KEY
        ]

        self.assertIn(fallback, self._outgoing(None))
        self.assertIn(fallback, self._outgoing("no_such_damage_type"))

    def test_every_declared_row_carries_both_persons(self):
        for damage_type, row in const.MISS_VERBS.items():
            with self.subTest(damage_type=damage_type):
                self.assertTrue(row[const.MISS_VERB_SELF_KEY])
                self.assertTrue(row[const.MISS_VERB_OTHER_KEY])
