"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Tests for the moderator's read-only report.

             Two things are worth pinning here, and neither is the prose. The
             first is that the report CHANGES NOTHING -- it is the only screen
             on the egg that a moderator can open on a live player without
             consequence, and that has to stay true. The second is
             containment: one broken section must not cost the whole screen,
             because the value of a one-screen report is that it is one
             screen.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.devtools
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.devtools import actions as dev_actions
from systems.devtools import constants as dev_constants
from systems.devtools import dossier as dev_dossier
from world.item_database import ITEM_DB



class ReportContentTests(EvenniaTest):
    """What the staff addendum must carry."""

    def test_the_report_names_the_character_and_its_dbref(self):
        """The dbref is the whole point of the staff half: the question this
        screen answers usually ends in a `py` call that needs the id."""
        report = dev_dossier.render_report(self.char2, self.char1)

        self.assertIn(self.char1.key, report)
        self.assertIn(f"#{self.char1.id}", report)

    def test_the_report_names_the_location_and_its_dbref(self):
        report = dev_dossier.render_report(self.char2, self.char1)

        self.assertIn(f"#{self.char1.location.id}", report)

    def test_the_report_carries_the_player_dossier_verbatim(self):
        """
        Reused from systems/summary/, not re-rendered. A moderator comparing
        what they see against what the player sees is asking "is this what
        they are looking at", and a staff-only re-render of the same numbers
        cannot answer that.
        """
        from systems.summary.service import render_summary

        dossier = render_summary(self.char1)
        report = dev_dossier.render_report(self.char2, self.char1)

        self.assertIn(dossier, report)

    def test_the_report_states_god_mode(self):
        off_report = dev_dossier.render_report(self.char2, self.char1)
        dev_actions.set_godmode(self.char2, self.char1, True)
        on_report = dev_dossier.render_report(self.char2, self.char1)

        self.assertNotEqual(off_report, on_report)

    def test_the_report_names_the_account_behind_the_character(self):
        report = dev_dossier.render_report(self.char2, self.char1)

        self.assertIn(self.account.key, report)

    def test_the_report_shows_account_permissions_not_character_ones(self):
        """
        Evennia's `perm` lockfunc reads the ACCOUNT's hierarchy permissions
        for a puppeted object and ignores the character's own unless the
        account is quelling. Printing the character's would show a number that
        decides nothing.

        Asserted lowercase because Evennia NORMALISES permission strings on
        storage: "Builder" goes in and "builder" comes back. Worth pinning --
        a moderator grepping this report for "Admin" finds nothing.
        """
        self.account.permissions.add("Builder")
        self.char1.permissions.add("charonlyperm")
        report = dev_dossier.render_report(self.char2, self.char1)

        self.assertIn("builder", report)
        self.assertNotIn("charonlyperm", report)

    def test_an_unpuppeted_character_is_reported_not_crashed_on(self):
        """Every logged-out player is one. Normal, not an error."""
        self.char2.account = None
        report = dev_dossier.render_report(self.char1, self.char2)

        self.assertIn(self.char2.key, report)

    def test_carried_items_are_itemised_with_slot_and_dbref(self):
        """The dossier says "1 / 32"; the moderator needs to know WHAT."""
        item_key = sorted(ITEM_DB.keys())[0]
        item_def = ITEM_DB[item_key]
        item = item_def.create(location=self.char1, home=self.char1)
        report = dev_dossier.render_report(self.char2, self.char1)

        self.assertIn(item.key, report)
        self.assertIn(f"#{item.id}", report)

    def test_slot_numbers_are_one_based_as_the_commands_parse_them(self):
        """
        The handler indexes from 0; `inventory` prints from 1, and so do the
        drop and equip commands. A staff screen printing the other one sends
        moderators to the wrong slot.
        """
        item_key = sorted(ITEM_DB.keys())[0]
        ITEM_DB[item_key].create(location=self.char1, home=self.char1)
        report = dev_dossier.render_report(self.char2, self.char1)

        self.assertIn("  1. ", report)

    def test_an_empty_bag_says_so_rather_than_rendering_nothing(self):
        report = dev_dossier.render_report(self.char2, self.char1)

        self.assertIn(dev_constants.INSPECT_LABEL_CARRYING, report)



class ReportIsReadOnlyTests(EvenniaTest):
    """The one screen that can be opened on a live player without effect."""

    def test_rendering_twice_changes_nothing_about_the_target(self):
        before_hp = self.char1.hp
        before_location = self.char1.location
        before_inventory = self.char1.inventory.count_used()
        before_quests = self.char1.quests.active_keys()

        dev_dossier.render_report(self.char2, self.char1)
        dev_dossier.render_report(self.char2, self.char1)

        self.assertEqual(self.char1.hp, before_hp)
        self.assertIs(self.char1.location, before_location)
        self.assertEqual(self.char1.inventory.count_used(), before_inventory)
        self.assertEqual(self.char1.quests.active_keys(), before_quests)

    def test_the_read_is_audited(self):
        """Who looked at whom is what a moderation review asks, and a read
        that leaves no trace is the one nobody can account for."""
        with mock.patch.object(dev_dossier.dev_actions, "audit_inspect") as audited:
            dev_dossier.render_report(self.char2, self.char1)

        audited.assert_called_once_with(self.char2, self.char1)



class ReportContainmentTests(EvenniaTest):
    """One broken section must not cost the screen."""

    def test_a_failing_section_is_marked_rather_than_raising(self):
        with mock.patch.object(dev_dossier, "_carried_rows",
                               side_effect=RuntimeError("boom")):
            report = dev_dossier.render_report(self.char2, self.char1)

        self.assertIn(dev_constants.INSPECT_SECTION_FAILED, report)
        self.assertIn(self.char1.key, report)

    def test_a_failing_summary_still_leaves_the_staff_half(self):
        """
        The dbrefs and the god-mode flag are the part needed mid-incident.
        Losing them because a skills panel raised would be the wrong trade.
        """
        with mock.patch.object(dev_dossier, "render_summary",
                               side_effect=RuntimeError("boom")):
            report = dev_dossier.render_report(self.char2, self.char1)

        self.assertIn(f"#{self.char1.id}", report)
        self.assertIn(dev_constants.INSPECT_STAFF_HEADING, report)

    def test_a_failing_section_does_not_stop_the_ones_after_it(self):
        with mock.patch.object(dev_dossier, "_account_rows",
                               side_effect=RuntimeError("boom")):
            report = dev_dossier.render_report(self.char2, self.char1)

        self.assertIn(dev_constants.INSPECT_LABEL_CARRYING, report)
        self.assertIn(dev_constants.INSPECT_LABEL_QUESTS, report)
