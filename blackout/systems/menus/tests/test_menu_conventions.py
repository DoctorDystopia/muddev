"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/20/2026
Description: Tests for the conventions every Blackout menu shares -- the quit
             binding, the back key, the key footer, and the single place a
             menu says goodbye.

The central regression guarded here: an option left to EvMenu's auto-numbering
takes the next running number counted over ALL options, INCLUDING the hidden
_default one. A Cancel option sitting beside a _default therefore took the key
"2" -- and options are matched before _default -- so typing "2" at a "how many?"
prompt cancelled the purchase instead of buying two of the thing.
"""

import unittest
from unittest import mock

from evennia.utils.test_resources import EvenniaTest
from evennia.utils.utils import mod_import

from systems.menus import base_menu
from systems.menus.constants import (
    BACK_KEYS,
    CONFIRM_NO_KEYS,
    CONFIRM_YES_KEYS,
    QUANTITY_ALL_KEYS,
    QUANTITY_CUSTOM_KEYS,
    QUIT_KEYS,
)
from typeclasses.characters import Character as BlackoutCharacter


# Every menu module in the game, named one by one rather than discovered by a
# package walk. See CLAUDE.md: nothing under blackout/ gets bulk-imported.
MENU_MODULE_PATHS = (
    "systems.menus.banking_menu",
    "systems.menus.combat_options_menu",
    "systems.menus.crafting_menu",
    "systems.menus.dialogue",
    "systems.menus.equipment_menu",
    "systems.menus.skills_menu",
    "systems.menus.summary_menu",
    "systems.menus.npc_dialogues.npc_oasis_guide",
    "systems.menus.npc_dialogues.npc_shopkeep",
)


def _import_menu_module(path):
    """Import one named menu module and hand it back."""
    return mod_import(path)


class TestOptionBuilders(unittest.TestCase):
    """back_option and cancel_option are the only places the keys are typed."""

    def test_back_option_binds_the_standard_key(self):
        option = base_menu.back_option("Back to recipes", "start")

        self.assertEqual(BACK_KEYS, option["key"])
        self.assertEqual("Back to recipes", option["desc"])
        self.assertEqual("start", option["goto"])

    def test_back_option_displays_the_short_key_first(self):
        option = base_menu.back_option("Back", "start")

        self.assertEqual("b", option["key"][0])

    def test_cancel_option_is_never_a_digit(self):
        option = base_menu.cancel_option("node_buy")

        self.assertEqual(BACK_KEYS, option["key"])

        for key in option["key"]:
            self.assertFalse(key.isdigit())

    def test_cancel_option_carries_its_goto(self):
        goto = ("node_buy_quantity", {"buy_entry": object()})
        option = base_menu.cancel_option(goto)

        self.assertEqual(goto, option["goto"])


class TestQuantityPromptKeys(unittest.TestCase):
    """A quantity prompt must leave every digit free to mean a quantity."""

    def test_reserved_prompt_keys_hold_no_digits(self):
        reserved = QUANTITY_CUSTOM_KEYS + QUANTITY_ALL_KEYS + BACK_KEYS

        for key in reserved:
            self.assertFalse(key.isdigit(), f"{key} would shadow a quantity")

    def test_confirmation_keys_hold_no_digits(self):
        for key in CONFIRM_YES_KEYS + CONFIRM_NO_KEYS:
            self.assertFalse(key.isdigit())


class TestMenuModulesDeclareTheirExit(unittest.TestCase):
    """Nothing declares quitting as an option; everything declares its line."""

    def test_every_menu_module_names_its_closing_text(self):
        for path in MENU_MODULE_PATHS:
            module = _import_menu_module(path)

            self.assertTrue(
                hasattr(module, base_menu.CLOSING_TEXT_ATTR),
                f"{path} declares no {base_menu.CLOSING_TEXT_ATTR}",
            )

    def test_no_menu_module_keeps_a_bespoke_exit_node(self):
        for path in MENU_MODULE_PATHS:
            module = _import_menu_module(path)

            self.assertFalse(
                hasattr(module, "node_exit"),
                f"{path} still has a node_exit; quitting is EvMenu's job",
            )


class _LiveMenuTest(EvenniaTest):
    """Shared fixture: a Blackout character who can be put into a real menu."""

    character_typeclass = BlackoutCharacter

    def _open(self, module_path, **kwargs):
        menu = base_menu.start_blackout_menu(self.char1, module_path, **kwargs)

        return menu


class TestPromptKeysUnderEvMenu(_LiveMenuTest):
    """Drives EvMenu's real key assignment over a prompt-shaped node.

    This is the mechanism the bug lived in, so it is the mechanism the test
    uses: a node offering a hidden _default plus one visible option, run
    through the same code that decides what a typed key means.
    """

    def _prompt_menu(self):
        def _prompt(caller, raw_string=None, **kwargs):
            options = (
                {"key": "_default", "goto": "start"},
                base_menu.cancel_option("start"),
            )

            return "How many?", options

        menu = base_menu.start_blackout_menu(self.char1, {"start": _prompt})

        return menu

    def test_no_digit_is_bound_on_a_quantity_prompt(self):
        menu = self._prompt_menu()

        bound_digits = [key for key in menu.options if key.isdigit()]

        self.assertEqual([], bound_digits)

    def test_the_back_key_is_bound_on_a_quantity_prompt(self):
        menu = self._prompt_menu()

        self.assertIn(BACK_KEYS[0], menu.options)

    def test_an_unkeyed_option_beside_default_still_takes_a_digit(self):
        """The hazard itself, pinned: this is what cancel_option avoids."""
        def _prompt(caller, raw_string=None, **kwargs):
            options = (
                {"key": "_default", "goto": "start"},
                {"desc": "Cancel", "goto": "start"},
            )

            return "How many?", options

        menu = base_menu.start_blackout_menu(self.char1, {"start": _prompt})

        self.assertIn("2", menu.options)


class TestFooter(_LiveMenuTest):
    """The footer is how a player learns the keys that are never listed."""

    def test_footer_names_the_quit_key(self):
        footer = base_menu._menu_footer(back_offered=False)

        self.assertIn(f"[{QUIT_KEYS[0]}]", footer)

    def test_footer_names_back_only_when_back_is_offered(self):
        without_back = base_menu._menu_footer(back_offered=False)
        with_back = base_menu._menu_footer(back_offered=True)

        self.assertNotIn(f"[{BACK_KEYS[0]}]", without_back)
        self.assertIn(f"[{BACK_KEYS[0]}]", with_back)

    def test_back_is_detected_from_a_rendered_option_key(self):
        optionlist = [("1", "Craft it"), (BACK_KEYS[0], "Back to recipes")]

        self.assertTrue(base_menu._offers_back(optionlist))

    def test_a_node_without_back_is_reported_as_such(self):
        optionlist = [("1", "Buy items"), ("2", "Sell items")]

        self.assertFalse(base_menu._offers_back(optionlist))


class TestClosingText(_LiveMenuTest):
    """One exit, one line -- whichever route out the player took."""

    def test_a_module_closing_text_is_picked_up(self):
        closing = base_menu._module_closing_text("systems.menus.banking_menu")

        self.assertEqual("Closing banking menu.", closing)

    def test_an_explicit_close_text_wins_over_the_module(self):
        menu = self._open("systems.menus.equipment_menu", close_text="Bespoke.")

        self.assertEqual("Bespoke.", menu.close_text)
        menu.close_menu()

    def test_a_dict_menu_declares_no_closing_text(self):
        self.assertIsNone(base_menu._module_closing_text({"start": lambda caller: None}))

    def test_closing_text_is_spoken_once_on_quit(self):
        menu = self._open("systems.menus.equipment_menu")
        self.char1.msg = mock.MagicMock()

        menu.close_menu()
        menu.close_menu()

        spoken = str(self.char1.msg.mock_calls)
        self.assertEqual(1, spoken.count("Closing equipment menu."))

    def test_a_callable_closing_text_is_given_caller_and_menu(self):
        seen = {}

        def _closing(caller, menu):
            seen["caller"] = caller
            seen["menu"] = menu

            return "Bye."

        menu = self._open("systems.menus.equipment_menu", close_text=_closing)
        menu.close_menu()

        self.assertIs(self.char1, seen["caller"])
        self.assertIs(menu, seen["menu"])

    def test_a_failing_closing_text_still_lets_the_menu_close(self):
        def _closing(caller, menu):
            raise RuntimeError("boom")

        menu = self._open("systems.menus.equipment_menu", close_text=_closing)
        menu.close_menu()

        self.assertIsNone(self.char1.ndb._evmenu)
