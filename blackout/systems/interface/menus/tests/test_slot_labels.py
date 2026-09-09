"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/01/2026
Description: WieldLocation display labels and ordering.

Regression guarded: the equipment menu carried a hand-written slot->label
dict restating all eight enum members. Adding a slot meant editing two
places, and a missed edit fell back silently to the raw underscore value.
"""

from unittest import TestCase

from items.equipment.constants import SLOT_DISPLAY_ORDER, WieldLocation


class TestSlotLabels(TestCase):

    def test_every_slot_has_a_label(self):
        for slot in WieldLocation:
            self.assertTrue(slot.label, f"{slot} has no label")

    def test_label_is_title_cased_with_spaces(self):
        self.assertEqual(WieldLocation.MAIN_HAND.label, "Main Hand")
        self.assertEqual(WieldLocation.TWO_HANDS.label, "Two Hands")
        self.assertEqual(WieldLocation.BACK.label, "Back")

    def test_no_label_leaks_an_underscore(self):
        for slot in WieldLocation:
            self.assertNotIn("_", slot.label, f"{slot.label} looks like a raw value")

    def test_display_order_covers_every_slot_exactly_once(self):
        self.assertEqual(set(SLOT_DISPLAY_ORDER), set(WieldLocation))
        self.assertEqual(len(SLOT_DISPLAY_ORDER), len(list(WieldLocation)))
