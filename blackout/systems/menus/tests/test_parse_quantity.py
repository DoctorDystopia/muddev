"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/01/2026
Description: Tests for the shared menu quantity parser that replaced the two
             divergent numeric-entry implementations in banking_menu and
             npc_shopkeep.

Run with:
    evennia test --settings settings.py systems.menus
"""



import unittest

from systems.menus.base_menu import MIN_QUANTITY, QUANTITY_ALL_KEYWORD, parse_quantity



class TestValidEntries(unittest.TestCase):
    """Inputs that should produce a usable count."""

    def test_plain_number(self):
        count, error = parse_quantity("5", 10)

        self.assertEqual(count, 5)
        self.assertIsNone(error)

    def test_surrounding_whitespace_is_ignored(self):
        count, error = parse_quantity("  7  ", 10)

        self.assertEqual(count, 7)
        self.assertIsNone(error)

    def test_exact_maximum(self):
        count, error = parse_quantity("10", 10)

        self.assertEqual(count, 10)
        self.assertIsNone(error)

    def test_minimum_is_accepted(self):
        count, error = parse_quantity(str(MIN_QUANTITY), 10)

        self.assertEqual(count, MIN_QUANTITY)
        self.assertIsNone(error)



class TestAllKeyword(unittest.TestCase):
    """Shopkeep exposes 'all' as an option key; banking's custom node arms
    only _default, so before this the word was rejected there."""

    def test_all_yields_the_maximum(self):
        count, error = parse_quantity(QUANTITY_ALL_KEYWORD, 12)

        self.assertEqual(count, 12)
        self.assertIsNone(error)

    def test_all_is_case_insensitive(self):
        count, error = parse_quantity("ALL", 12)

        self.assertEqual(count, 12)
        self.assertIsNone(error)



class TestClamping(unittest.TestCase):
    """Over-asking is a reasonable way to say 'all of it'."""

    def test_above_maximum_clamps_down_silently(self):
        count, error = parse_quantity("999", 10)

        self.assertEqual(count, 10)
        self.assertIsNone(error)



class TestRejectedEntries(unittest.TestCase):
    """Inputs that must produce an error rather than a silent guess."""

    def test_non_numeric_is_refused(self):
        count, error = parse_quantity("banana", 10)

        self.assertIsNone(count)
        self.assertIsNotNone(error)

    def test_blank_is_refused(self):
        count, error = parse_quantity("   ", 10)

        self.assertIsNone(count)
        self.assertIsNotNone(error)

    def test_none_is_refused(self):
        count, error = parse_quantity(None, 10)

        self.assertIsNone(count)
        self.assertIsNotNone(error)

    def test_zero_is_refused_not_clamped_up(self):
        """This is the behaviour change for shopkeep, which used to turn a
        typed 0 into a purchase of 1."""
        count, error = parse_quantity("0", 10)

        self.assertIsNone(count)
        self.assertIsNotNone(error)

    def test_negative_is_refused_not_clamped_up(self):
        count, error = parse_quantity("-5", 10)

        self.assertIsNone(count)
        self.assertIsNotNone(error)

    def test_error_message_carries_no_colour_markup(self):
        """Callers wrap the message in their own ERROR_COLOR."""
        _count, error = parse_quantity("banana", 10)

        self.assertNotIn("|", error)
