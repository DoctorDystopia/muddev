"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/08/2026
Description: Cases for bank tabs and placeholders on a real vault: the
             handler keeps the layout in step with deposits and withdrawals,
             the slot cap counts placeholders, and every `bank <verb>` line
             does what its help text says.

             layout.py has its own cases with no database. These cases prove
             that the handler gives that model the right facts.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.gameplay.banking.tests.test_tabs
"""

from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from systems.gameplay.banking import constants as bank_const
from systems.gameplay.banking import handler as bank_handler
from systems.gameplay.banking import layout as vault_layout
from typeclasses.bank_nodes import BankNode, CmdBank
from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB


# ─── Private constant definitions ────────────────────────────────────────────

# Stackable: one object, many units.
_DUST_KEY = "rusty_metal_dust"
_DUST_UNITS = 12

# Non-stackable: one vault slot for many objects.
_CHUNK_KEY = "rusty_metal_chunk"
_CHUNK_COUNT = 3


# ─── Private helper routines ─────────────────────────────────────────────────

class _TabFixture(EvenniaCommandTest):
    """A terminal in the room, and a character with an inventory."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.terminal = create_object(
            BankNode, key="bank terminal", location=self.room1)
        self.char1.inventory.sync()

    def _carry(self, key: str, count: int = 1) -> list:
        made = [ITEM_DB[key].create(location=self.char1) for _ in range(count)]
        self.char1.inventory.sync()

        return made

    def _bank_dust(self):
        dust = self._carry(_DUST_KEY)[0]
        dust.quantity = _DUST_UNITS
        self.char1.bank.deposit_many([dust])

        return ITEM_DB[_DUST_KEY].name.lower()

    def _bank_chunks(self):
        self.char1.bank.deposit_many(self._carry(_CHUNK_KEY, _CHUNK_COUNT))

        return ITEM_DB[_CHUNK_KEY].name.lower()

    def _layout(self):
        return self.char1.bank.layout()

    def _bank_cmd(self, args: str) -> str:
        return self.call(CmdBank(), f" {args}", caller=self.char1,
                         obj=self.terminal)

    def _withdraw_all(self, name: str) -> None:
        items = self.char1.bank.find_items_by_name(name)
        self.char1.bank.withdraw_many(items)


# ─── Cases ───────────────────────────────────────────────────────────────────

class TestLayoutFollowsTheVault(_TabFixture):

    def test_a_deposit_gets_one_slot_in_the_main_tab(self):
        name = self._bank_chunks()

        current = self._layout()

        self.assertEqual([name], current.tabs[bank_const.MAIN_TAB])

    def test_a_new_name_goes_into_the_viewed_tab(self):
        dust = self._bank_dust()
        self.char1.bank.move_to_tab(dust, bank_const.NEW_TAB_WORD)
        self.char1.bank.view_tab(bank_const.FIRST_TAB)

        chunks = self._bank_chunks()

        self.assertEqual(bank_const.FIRST_TAB,
                         vault_layout.tab_of(self._layout(), chunks))

    def test_a_withdrawal_of_everything_leaves_a_placeholder(self):
        dust = self._bank_dust()

        self._withdraw_all(dust)

        self.assertTrue(vault_layout.is_placeholder(self._layout(), dust))

    def test_with_placeholders_off_a_withdrawal_frees_the_slot(self):
        dust = self._bank_dust()
        self.char1.bank.set_keep_placeholders(False)

        self._withdraw_all(dust)

        self.assertEqual(0, self.char1.bank.used_slots())

    def test_a_placeholder_spends_a_slot_of_the_cap(self):
        dust = self._bank_dust()

        self._withdraw_all(dust)

        self.assertEqual(1, self.char1.bank.used_slots())

    def test_a_deposit_fills_a_placeholder_in_a_full_vault(self):
        dust = self._bank_dust()
        self._withdraw_all(dust)
        back = [obj for _slot, obj in self.char1.inventory.all_items() if obj]

        with mock.patch.object(bank_handler, "BANK_MAX_UNIQUE_KEYS", 1):
            result = self.char1.bank.deposit_many(back)

        self.assertTrue(result.success)
        self.assertFalse(vault_layout.is_placeholder(self._layout(), dust))

    def test_a_new_name_is_refused_when_placeholders_fill_the_cap(self):
        dust = self._bank_dust()
        self._withdraw_all(dust)
        chunks = self._carry(_CHUNK_KEY)

        with mock.patch.object(bank_handler, "BANK_MAX_UNIQUE_KEYS", 1):
            result = self.char1.bank.deposit_many(chunks)

        self.assertFalse(result.success)
        self.assertEqual(bank_handler.VAULT_FULL_ERROR, result.error)

    def test_list_items_follows_the_layout_order(self):
        dust = self._bank_dust()
        self._bank_chunks()

        self.char1.bank.move_to_tab(dust, bank_const.NEW_TAB_WORD)
        self.char1.bank.swap_slots(dust, ITEM_DB[_CHUNK_KEY].name)

        last = self.char1.bank.list_items()[-1]
        self.assertEqual(ITEM_DB[_CHUNK_KEY].name.lower(), last.key.lower())

    def test_an_item_placed_in_the_room_gets_a_slot(self):
        stray = ITEM_DB[_CHUNK_KEY].create(location=None)
        stray.location = self.char1.bank._get_bank_room()

        names = vault_layout.ordered_names(self._layout())

        self.assertIn(stray.key.lower(), names)

    def test_delete_bank_room_forgets_the_layout(self):
        self._bank_dust()

        self.char1.bank.delete_bank_room()

        self.assertIsNone(self.char1.attributes.get(bank_handler.BANK_LAYOUT_ATTR))


class TestBankVerbs(_TabFixture):

    def test_move_to_new_makes_a_tab(self):
        dust = self._bank_dust()

        response = self._bank_cmd(f"move {dust} = {bank_const.NEW_TAB_WORD}")

        self.assertIn("tab", response.lower())
        self.assertEqual(bank_const.FIRST_TAB,
                         vault_layout.tab_of(self._layout(), dust))

    def test_move_to_a_missing_tab_is_refused(self):
        dust = self._bank_dust()

        response = self._bank_cmd(f"move {dust} = {bank_const.FIRST_TAB + 3}")

        self.assertIn("no tab", response.lower())

    def test_view_sets_the_viewed_tab(self):
        dust = self._bank_dust()
        self.char1.bank.move_to_tab(dust, bank_const.NEW_TAB_WORD)

        self._bank_cmd(f"view {bank_const.FIRST_TAB}")

        self.assertEqual(bank_const.FIRST_TAB, self._layout().viewed)

    def test_name_sets_and_clears_a_tab_name(self):
        dust = self._bank_dust()
        self.char1.bank.move_to_tab(dust, bank_const.NEW_TAB_WORD)

        self._bank_cmd(f"name {bank_const.FIRST_TAB} = Dust pile")
        named = self._layout().names[bank_const.FIRST_TAB]
        self._bank_cmd(f"name {bank_const.FIRST_TAB}")

        self.assertEqual("Dust pile", named)
        self.assertEqual("", self._layout().names[bank_const.FIRST_TAB])

    def test_swap_exchanges_two_slots(self):
        dust = self._bank_dust()
        chunks = self._bank_chunks()

        self._bank_cmd(f"swap {dust} = {chunks}")

        self.assertEqual([chunks, dust],
                         self._layout().tabs[bank_const.MAIN_TAB])

    def test_placeholders_off_turns_them_off(self):
        self._bank_cmd(f"placeholders {bank_const.SWITCH_OFF_WORD}")

        self.assertFalse(self.char1.bank.keeps_placeholders())

    def test_release_frees_a_placeholder(self):
        dust = self._bank_dust()
        self._withdraw_all(dust)

        response = self._bank_cmd(f"release {dust}")

        self.assertIn("release", response.lower())
        self.assertEqual(0, self.char1.bank.used_slots())

    def test_release_refuses_a_stored_item(self):
        dust = self._bank_dust()

        response = self._bank_cmd(f"release {dust}")

        self.assertIn("not a placeholder", response.lower())

    def test_tabs_lists_every_tab_with_its_items(self):
        dust = self._bank_dust()
        self._bank_chunks()
        self.char1.bank.move_to_tab(dust, bank_const.NEW_TAB_WORD)

        response = self._bank_cmd(bank_const.VERB_TABS)

        self.assertIn("tab 1", response.lower())
        self.assertIn("main tab", response.lower())

    def test_an_unknown_verb_prints_the_usage(self):
        response = self._bank_cmd("juggle")

        self.assertIn("usage", response.lower())
