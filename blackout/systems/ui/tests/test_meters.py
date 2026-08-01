"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/01/2026
Description: Tests for the XP meter that replaced skills_menu._build_xp_bar.
             Pure formatting, so a plain TestCase -- but wrapped in one so the
             Django/unittest runner actually collects it.

Run with:
    evennia test --settings settings.py systems.ui
"""



import unittest

from evennia.utils.ansi import strip_ansi

from systems.ui.meters import (
    MAX_LEVEL_TEXT,
    METER_WIDTH,
    NO_HP_TEXT,
    build_hp_meter,
    build_xp_meter,
)



class TestMaxLevel(unittest.TestCase):
    """The one case the contrib cannot express."""

    def test_zero_total_reports_max_level(self):
        rendered = build_xp_meter(500, 0)

        self.assertIn(MAX_LEVEL_TEXT, strip_ansi(rendered))

    def test_negative_total_reports_max_level(self):
        rendered = build_xp_meter(500, -1)

        self.assertIn(MAX_LEVEL_TEXT, strip_ansi(rendered))



class TestMeterRendering(unittest.TestCase):
    """Width and content of a normal progress meter."""

    def test_width_is_exactly_meter_width(self):
        rendered = build_xp_meter(50, 100)
        visible = strip_ansi(rendered)

        self.assertEqual(len(visible), METER_WIDTH)

    def test_values_are_shown(self):
        rendered = build_xp_meter(50, 100)
        visible = strip_ansi(rendered)

        self.assertIn("50", visible)
        self.assertIn("100", visible)

    def test_output_carries_colour_markup(self):
        rendered = build_xp_meter(50, 100)

        self.assertNotEqual(rendered, strip_ansi(rendered))

    def test_empty_and_full_keep_the_same_width(self):
        """A ragged column was the failure mode of the hand-rolled bar."""
        empty = strip_ansi(build_xp_meter(0, 100))
        half = strip_ansi(build_xp_meter(50, 100))
        full = strip_ansi(build_xp_meter(100, 100))

        self.assertEqual(len(empty), METER_WIDTH)
        self.assertEqual(len(half), METER_WIDTH)
        self.assertEqual(len(full), METER_WIDTH)



class TestMeterClamping(unittest.TestCase):
    """Out-of-range inputs must not distort the bar."""

    def test_overfull_does_not_widen_the_bar(self):
        rendered = build_xp_meter(500, 100)

        self.assertEqual(len(strip_ansi(rendered)), METER_WIDTH)

    def test_negative_does_not_widen_the_bar(self):
        """_build_xp_bar clamped only the top of the range. A negative
        current_xp produced an empty fill and an over-long remainder, so the
        bar grew past its nominal width."""
        rendered = build_xp_meter(-50, 100)

        self.assertEqual(len(strip_ansi(rendered)), METER_WIDTH)



class TestHpMeter(unittest.TestCase):
    """The combat-side meter. Same wrapper, different palette."""

    def test_values_are_shown(self):
        visible = strip_ansi(build_hp_meter(6, 10))

        self.assertIn("6", visible)
        self.assertIn("10", visible)

    def test_width_matches_the_xp_meter(self):
        """Both bars share METER_WIDTH so a combat line and a skills line sit
        in the same column."""
        hp_width = len(strip_ansi(build_hp_meter(6, 10)))
        xp_width = len(strip_ansi(build_xp_meter(6, 10)))

        self.assertEqual(hp_width, METER_WIDTH)
        self.assertEqual(xp_width, METER_WIDTH)

    def test_every_fill_level_keeps_the_same_width(self):
        for current in (0, 1, 5, 9, 10):
            rendered = strip_ansi(build_hp_meter(current, 10))

            self.assertEqual(len(rendered), METER_WIDTH, f"hp={current}")

    def test_out_of_range_does_not_widen_the_bar(self):
        over = strip_ansi(build_hp_meter(500, 10))
        under = strip_ansi(build_hp_meter(-5, 10))

        self.assertEqual(len(over), METER_WIDTH)
        self.assertEqual(len(under), METER_WIDTH)

    def test_colour_shifts_as_the_bar_drains(self):
        """A full bar and a nearly-empty bar must not render identically —
        the gradient is the whole reason HP does not reuse the XP palette."""
        full = build_hp_meter(10, 10)
        nearly_empty = build_hp_meter(1, 10)

        self.assertNotEqual(full, nearly_empty)

    def test_zero_max_reports_no_data_rather_than_a_full_bar(self):
        """display_meter raises a zero maximum to 1 internally, so an
        uninitialised combatant would otherwise render as FULL health."""
        rendered = strip_ansi(build_hp_meter(0, 0))

        self.assertIn(NO_HP_TEXT, rendered)

    def test_negative_max_reports_no_data(self):
        rendered = strip_ansi(build_hp_meter(0, -3))

        self.assertIn(NO_HP_TEXT, rendered)
