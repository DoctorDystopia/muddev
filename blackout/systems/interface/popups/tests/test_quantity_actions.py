"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Cases for the quantity helpers every pop-up shares, and for the
             registry that finds the pop-ups.

             No database: the helpers take plain values and return plain
             values. Every expectation reads its numbers from
             popups/constants.py, so a new fixed button re-derives the test.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.popups.tests.test_quantity_actions
"""

import unittest

from systems.interface.popups import constants as popup_const
from systems.interface.popups import registry
from systems.interface.popups.popup_defs.base_popup import quantity_actions
from systems.interface.statefeed import constants as feed_const


# ─── Private constant definitions ────────────────────────────────────────────

_VERB = "Withdraw"
_TEMPLATE = f"withdraw widget {feed_const.ACTION_AMOUNT_PLACEHOLDER}"
_PROMPT = "Withdraw how many?"

# More units than any fixed button, so every button has something to reach.
_UNITS = 500

# A custom mode no fixed button shows.
_CUSTOM_MODE = 23


def _commands(actions) -> list:
    return [action["command"] for action in actions]


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestQuantityActions(unittest.TestCase):
    """The order of a slot's actions decides what a left click sends."""

    def test_the_active_mode_comes_first(self):
        for mode in popup_const.QUANTITY_FIXED_MODES:
            with self.subTest(mode=mode):
                actions = quantity_actions(_VERB, _TEMPLATE, mode, _UNITS, _PROMPT)

                self.assertEqual(f"withdraw widget {mode}", actions[0]["command"])

    def test_all_mode_comes_first_as_all(self):
        actions = quantity_actions(
            _VERB, _TEMPLATE, popup_const.QUANTITY_ALL, _UNITS, _PROMPT)

        self.assertEqual(
            f"withdraw widget {popup_const.QUANTITY_ALL}", actions[0]["command"])

    def test_each_mode_is_offered_once(self):
        actions = quantity_actions(_VERB, _TEMPLATE, 5, _UNITS, _PROMPT)
        whole = [command for command in _commands(actions) if command]

        self.assertEqual(len(whole), len(set(whole)))

    def test_a_custom_mode_joins_the_fixed_ones(self):
        actions = quantity_actions(_VERB, _TEMPLATE, _CUSTOM_MODE, _UNITS, _PROMPT)
        commands = _commands(actions)

        self.assertEqual(f"withdraw widget {_CUSTOM_MODE}", commands[0])

        for mode in popup_const.QUANTITY_FIXED_MODES:
            self.assertIn(f"withdraw widget {mode}", commands)

    def test_x_asks_and_sits_just_before_all(self):
        actions = quantity_actions(_VERB, _TEMPLATE, 1, _UNITS, _PROMPT)
        prompted = actions[-2]

        self.assertEqual("", prompted["command"])
        self.assertEqual(_TEMPLATE, prompted["template"])
        self.assertEqual(_UNITS, prompted["input"][feed_const.ACTION_INPUT_MAX_KEY])
        self.assertIn(popup_const.QUANTITY_ALL, actions[-1]["command"])

    def test_one_unit_offers_one_verb(self):
        actions = quantity_actions(
            _VERB, _TEMPLATE, popup_const.QUANTITY_ALL, 1, _PROMPT)

        self.assertEqual(1, len(actions))
        self.assertEqual("withdraw widget 1", actions[0]["command"])

    def test_a_brace_in_a_name_does_not_break_the_render(self):
        template = f"withdraw odd {{thing}} {feed_const.ACTION_AMOUNT_PLACEHOLDER}"
        actions = quantity_actions(_VERB, template, 5, _UNITS, _PROMPT)

        self.assertEqual("withdraw odd {thing} 5", actions[0]["command"])


class TestRegistry(unittest.TestCase):
    """The registry is the only way a pop-up is reached."""

    def test_every_module_loaded(self):
        self.assertEqual([], registry.LOAD_ERRORS)

    def test_every_registered_popup_is_well_formed(self):
        self.assertTrue(registry.POPUP_REGISTRY)

        for popup_key, popup in registry.POPUP_REGISTRY.items():
            with self.subTest(popup=popup_key):
                self.assertEqual(popup_key, popup.key)
                self.assertTrue(popup.title)

    def test_an_unknown_key_is_none(self):
        self.assertIsNone(registry.get_popup("no such pop-up"))
