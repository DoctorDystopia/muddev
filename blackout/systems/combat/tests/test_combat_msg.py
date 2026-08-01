"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/01/2026
Description: Tests for the combat message builders -- specifically the per-hit
             XP readout and the combat HP bar. Pure string assembly, so a plain
             TestCase, wrapped in a class so Django's discovery collects it.

Run with:
    evennia test --settings settings.py systems.combat
"""



import unittest

from evennia.utils.ansi import strip_ansi

from systems.combat import combat_msg
from systems.ui.meters import METER_WIDTH



class _FakeCombatant:
    """Minimal stand-in for a CombatEntity: the formatters read only .key."""

    def __init__(self, key: str) -> None:
        self.key = key



class TestXpGainFormatting(unittest.TestCase):
    """Per-hit XP has to be visible on the hit line itself."""

    def test_empty_award_renders_nothing(self):
        """A miss appends this unconditionally, so it must vanish cleanly."""
        self.assertEqual(combat_msg.format_xp_gain([]), "")

    def test_single_award_names_skill_and_amount(self):
        visible = strip_ansi(combat_msg.format_xp_gain([("Strike", 4)]))

        self.assertIn("+4 Strike", visible)

    def test_multiple_awards_are_separated(self):
        awards = [("Strike", 4), ("Fortitude", 1)]

        visible = strip_ansi(combat_msg.format_xp_gain(awards))

        self.assertIn("+4 Strike", visible)
        self.assertIn("+1 Fortitude", visible)
        self.assertIn(combat_msg.XP_ENTRY_SEPARATOR, visible)

    def test_award_carries_colour_markup(self):
        rendered = combat_msg.format_xp_gain([("Strike", 4)])

        self.assertNotEqual(rendered, strip_ansi(rendered))

    def test_award_starts_with_a_space_so_it_can_be_appended(self):
        rendered = combat_msg.format_xp_gain([("Strike", 4)])

        self.assertTrue(rendered.startswith(" "))



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
        xp_text = combat_msg.format_xp_gain([("Strike", 12), ("Fortitude", 4)])

        rendered = combat_msg.format_outgoing_hit(
            self.attacker, self.target, 3, xp_text
        )
        visible = strip_ansi(rendered)

        self.assertNotIn("\n", visible)
        self.assertIn("for 3.", visible)
        self.assertIn("+12 Strike", visible)
        self.assertIn("+4 Fortitude", visible)



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
