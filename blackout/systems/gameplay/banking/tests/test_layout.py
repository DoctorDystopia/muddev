"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/08/2026
Description: Cases for the vault layout model: the fit to the stored items,
             the tabs, the order, the names, and the placeholders.

             Pure data, so plain unittest.TestCase and no database.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.gameplay.banking.tests.test_layout
"""

import unittest

from systems.gameplay.banking import constants as bank_const
from systems.gameplay.banking import layout as vault_layout


# ─── Private helper routines ─────────────────────────────────────────────────

def _present(*names) -> dict:
    """A `present` map for reconcile: each name is its own display key, with
    a prototype key made from it."""
    return {name: (name.title(), name.replace(" ", "_")) for name in names}


def _fitted(*names, new_tab=bank_const.MAIN_TAB) -> vault_layout.VaultLayout:
    """A new layout fitted to the given stored names."""
    current = vault_layout.VaultLayout()
    vault_layout.reconcile(current, _present(*names), new_tab)

    return current


# ─── Cases ───────────────────────────────────────────────────────────────────

class TestReconcile(unittest.TestCase):

    def test_a_new_vault_puts_every_stored_name_in_the_main_tab(self):
        current = _fitted("ore", "bar", "gem")

        self.assertEqual(["ore", "bar", "gem"],
                         current.tabs[bank_const.MAIN_TAB])

    def test_a_new_name_goes_into_the_viewed_tab(self):
        current = _fitted("ore", "bar")
        vault_layout.move(current, "ore", len(current.tabs))
        vault_layout.set_view(current, bank_const.FIRST_TAB)

        vault_layout.reconcile(current, _present("ore", "bar", "gem"),
                               current.viewed)

        self.assertEqual(bank_const.FIRST_TAB, vault_layout.tab_of(current, "gem"))

    def test_a_viewed_tab_that_does_not_exist_sends_new_names_to_main(self):
        current = _fitted("ore", new_tab=bank_const.FIRST_TAB + 5)

        self.assertEqual(bank_const.MAIN_TAB, vault_layout.tab_of(current, "ore"))

    def test_a_name_that_leaves_becomes_a_placeholder_when_kept(self):
        current = _fitted("ore", "bar")
        current.keep_placeholders = True

        vault_layout.reconcile(current, _present("bar"), current.viewed)

        self.assertTrue(vault_layout.is_placeholder(current, "ore"))
        self.assertIn("ore", vault_layout.ordered_names(current))

    def test_a_name_that_leaves_loses_its_slot_when_not_kept(self):
        current = _fitted("ore", "bar")
        current.keep_placeholders = False

        vault_layout.reconcile(current, _present("bar"), current.viewed)

        self.assertNotIn("ore", vault_layout.ordered_names(current))
        self.assertNotIn("ore", current.meta)

    def test_turning_placeholders_off_keeps_the_ones_that_exist(self):
        current = _fitted("ore", "bar")
        vault_layout.reconcile(current, _present("bar"), current.viewed)
        current.keep_placeholders = False

        vault_layout.reconcile(current, _present("bar"), current.viewed)

        self.assertTrue(vault_layout.is_placeholder(current, "ore"))

    def test_a_deposit_fills_the_placeholder_in_its_place(self):
        current = _fitted("ore", "bar", "gem")
        vault_layout.reconcile(current, _present("bar", "gem"), current.viewed)
        order = vault_layout.ordered_names(current)

        vault_layout.reconcile(current, _present("ore", "bar", "gem"),
                               current.viewed)

        self.assertFalse(vault_layout.is_placeholder(current, "ore"))
        self.assertEqual(order, vault_layout.ordered_names(current))

    def test_a_placeholder_keeps_its_tab_alive(self):
        current = _fitted("ore", "bar")
        vault_layout.move(current, "ore", len(current.tabs))

        vault_layout.reconcile(current, _present("bar"), current.viewed)

        self.assertEqual(bank_const.FIRST_TAB, vault_layout.tab_of(current, "ore"))

    def test_the_placeholder_keeps_the_display_key_and_prototype(self):
        current = _fitted("iron ore")

        vault_layout.reconcile(current, {}, current.viewed)

        display, prototype = _present("iron ore")["iron ore"]
        entry = current.meta["iron ore"]
        self.assertEqual(display, vault_layout.display_key(current, "iron ore"))
        self.assertEqual(prototype, entry[bank_const.META_PROTOTYPE])


class TestTabs(unittest.TestCase):

    def test_a_move_to_the_new_tab_number_makes_a_tab(self):
        current = _fitted("ore", "bar")
        new_tab = len(current.tabs)

        moved = vault_layout.move(current, "ore", new_tab)

        self.assertTrue(moved)
        self.assertEqual(new_tab, vault_layout.tab_of(current, "ore"))
        self.assertEqual(len(current.tabs), len(current.names))

    def test_a_move_past_the_new_tab_number_is_refused(self):
        current = _fitted("ore")

        self.assertFalse(vault_layout.move(current, "ore", len(current.tabs) + 1))

    def test_a_tab_that_empties_disappears_and_later_tabs_move_down(self):
        current = _fitted("ore", "bar", "gem")
        vault_layout.move(current, "ore", len(current.tabs))
        vault_layout.move(current, "bar", len(current.tabs))
        vault_layout.rename(current, bank_const.FIRST_TAB + 1, "Bars")

        vault_layout.move(current, "ore", bank_const.MAIN_TAB)

        self.assertEqual(bank_const.FIRST_TAB, vault_layout.tab_of(current, "bar"))
        self.assertEqual("Bars", current.names[bank_const.FIRST_TAB])

    def test_the_viewed_tab_follows_a_tab_that_moves_down(self):
        current = _fitted("ore", "bar")
        vault_layout.move(current, "ore", len(current.tabs))
        vault_layout.move(current, "bar", len(current.tabs))
        vault_layout.set_view(current, bank_const.FIRST_TAB + 1)

        vault_layout.move(current, "ore", bank_const.MAIN_TAB)

        self.assertEqual(vault_layout.tab_of(current, "bar"), current.viewed)

    def test_the_viewed_tab_returns_to_main_when_it_disappears(self):
        current = _fitted("ore", "bar")
        vault_layout.move(current, "ore", len(current.tabs))
        vault_layout.set_view(current, bank_const.FIRST_TAB)

        vault_layout.move(current, "ore", bank_const.MAIN_TAB)

        self.assertEqual(bank_const.MAIN_TAB, current.viewed)

    def test_the_main_view_shows_main_first_and_the_tabs_last(self):
        current = _fitted("ore", "bar", "gem")
        vault_layout.move(current, "ore", len(current.tabs))

        order = vault_layout.ordered_names(current)

        self.assertEqual(current.tabs[bank_const.MAIN_TAB],
                         order[:len(current.tabs[bank_const.MAIN_TAB])])
        self.assertEqual("ore", order[-1])

    def test_a_swap_across_tabs_exchanges_the_tabs(self):
        current = _fitted("ore", "bar")
        vault_layout.move(current, "ore", len(current.tabs))

        swapped = vault_layout.swap(current, "ore", "bar")

        self.assertTrue(swapped)
        self.assertEqual(bank_const.FIRST_TAB, vault_layout.tab_of(current, "bar"))
        self.assertEqual(bank_const.MAIN_TAB, vault_layout.tab_of(current, "ore"))

    def test_a_swap_in_one_tab_exchanges_the_places(self):
        current = _fitted("ore", "bar", "gem")

        vault_layout.swap(current, "ore", "gem")

        self.assertEqual(["gem", "bar", "ore"],
                         current.tabs[bank_const.MAIN_TAB])

    def test_resolve_prefers_an_exact_name_to_a_prefix(self):
        current = _fitted("rusty scrap metal", "rusty scrap")

        self.assertEqual("rusty scrap", vault_layout.resolve(current, "Rusty Scrap"))
        self.assertEqual("rusty scrap metal",
                         vault_layout.resolve(current, "rusty scrap m"))


class TestNames(unittest.TestCase):

    def test_a_name_is_cut_to_the_maximum_length(self):
        long_name = "x" * (bank_const.TAB_NAME_MAX_LENGTH * 2)

        cleaned = vault_layout.clean_tab_name(long_name)

        self.assertEqual(bank_const.TAB_NAME_MAX_LENGTH, len(cleaned))

    def test_a_name_loses_colour_codes_and_extra_spaces(self):
        cleaned = vault_layout.clean_tab_name("  |rRed|n   ores  ")

        self.assertNotIn("|", cleaned)
        self.assertNotIn("  ", cleaned)

    def test_an_empty_name_shows_the_icon_again(self):
        current = _fitted("ore")
        vault_layout.move(current, "ore", len(current.tabs))
        vault_layout.rename(current, bank_const.FIRST_TAB, "Ores")

        vault_layout.rename(current, bank_const.FIRST_TAB, "")

        self.assertEqual("", current.names[bank_const.FIRST_TAB])

    def test_a_rename_of_a_missing_tab_is_refused(self):
        current = _fitted("ore")

        self.assertFalse(vault_layout.rename(current, len(current.tabs), "Ores"))


class TestRelease(unittest.TestCase):

    def test_release_frees_a_placeholder(self):
        current = _fitted("ore", "bar")
        vault_layout.reconcile(current, _present("bar"), current.viewed)

        released = vault_layout.release(current, "ore")

        self.assertTrue(released)
        self.assertNotIn("ore", vault_layout.ordered_names(current))

    def test_release_refuses_a_stored_item(self):
        current = _fitted("ore")

        self.assertFalse(vault_layout.release(current, "ore"))

    def test_release_all_counts_what_it_freed(self):
        current = _fitted("ore", "bar", "gem")
        vault_layout.reconcile(current, _present("gem"), current.viewed)

        freed = vault_layout.release_all(current)

        self.assertEqual(2, freed)
        self.assertEqual([], vault_layout.placeholder_names(current))


class TestRecord(unittest.TestCase):

    def test_a_record_survives_the_round_trip(self):
        current = _fitted("ore", "bar")
        vault_layout.move(current, "ore", len(current.tabs))
        vault_layout.rename(current, bank_const.FIRST_TAB, "Ores")
        vault_layout.set_view(current, bank_const.FIRST_TAB)

        record = vault_layout.to_record(current)
        again = vault_layout.from_record(record)

        self.assertEqual(record, vault_layout.to_record(again))

    def test_a_missing_record_gives_an_empty_main_tab(self):
        current = vault_layout.from_record(None)

        self.assertEqual([[]], current.tabs)
        self.assertEqual(bank_const.MAIN_TAB, current.viewed)

    def test_a_bad_record_is_repaired(self):
        record = {
            bank_const.RECORD_TABS: [["ore"], ["ore", "bar"]],
            bank_const.RECORD_NAMES: [],
            bank_const.RECORD_VIEWED: 99,
        }

        current = vault_layout.from_record(record)

        self.assertEqual([["ore"], ["bar"]], current.tabs)
        self.assertEqual(len(current.tabs), len(current.names))
        self.assertEqual(bank_const.MAIN_TAB, current.viewed)
