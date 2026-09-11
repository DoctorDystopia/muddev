"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for the craft menu at a facility whose output arrives later.

             Two things the menu owes a player standing at a curing chamber,
             neither of which it gave them before 09/11/2026:

               1. WHAT IS IN THERE. "Cannot craft: No free curing slot" is a
                  refusal with no way to act on it -- the player cannot see
                  what is occupying the slot or how long it has left, and the
                  only screen that would tell them is a command they have to
                  know exists.
               2. A WAY TO TAKE IT OUT. `collect` hangs on the chamber, so a
                  player in the menu had to quit it, type a command nothing had
                  mentioned, and open the menu again.

             What is asserted here is that the menu SHOWS the block and OFFERS
             the row. What the block says is the handler's, tested beside it in
             systems/gameplay/curing/tests/test_slot_display.py -- this file
             must not grow assertions about wording, or the two will drift and
             one of them will be edited to match the other.

Run with:
    evennia test --settings test_settings.py systems.interface.menus
"""



import time
from unittest import mock

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.crafting import crafting_service
from systems.gameplay.curing import constants as curing_constants
from systems.interface.menus import crafting_menu
from typeclasses.skill_facilities import (
    AnvilFacility,
    CuringChamberFacility,
)
from world.item_database import ITEM_DB



# Private constant definitions

# The level-0 curing recipe, used wherever a test needs "a cure" rather than a
# particular one.
_CHUCK_RECIPE = "mutant raider cured chuck"



class DeferredMenuTestBase(EvenniaTest):
    """A character at a curing chamber, driving the menu's start node."""

    def setUp(self):
        super().setUp()
        self.chamber = CuringChamberFacility.create(
            "Curing Chamber", location=self.char1.location
        )[0]

    def _start_a_cure(self):
        ITEM_DB["mutant_raider_raw_chuck"].create(location=self.char1)
        crafting_service.perform_craft(self.char1, _CHUCK_RECIPE)

    def _finish_everything(self):
        """Move every stored deadline into the past.

        The substitute for waiting five minutes, and what the design makes
        possible: readiness is a comparison against time.time() and nothing
        else. Rewritten in place, never rebound -- Evennia hands back a
        _SaverList and replacing it would lose the write-through.
        """
        past = time.time() - 1
        stored = self.char1.attributes.get(
            curing_constants.CURING_SLOTS_ATTR, default=[]
        )
        for slot in stored:
            slot[curing_constants.SLOT_DUE_AT_KEY] = past

    def _render(self, facility=None):
        """The start node, as (plain text, option descriptions)."""
        if facility is None:
            facility = self.chamber

        text, options = crafting_menu.start(self.char1, facility=facility)
        descriptions = [
            strip_ansi(str(option.get("desc", ""))) for option in options
        ]

        return strip_ansi(text), descriptions



class TestTheMenuShowsWhatIsInTheChamber(DeferredMenuTestBase):
    """The slot block, on the screen the player already has open."""

    def test_an_idle_chamber_still_shows_its_slots(self):
        text, _options = self._render()

        self.assertIn("slots", text.lower())

    def test_a_started_cure_appears_on_the_menu(self):
        self._start_a_cure()

        text, _options = self._render()

        self.assertIn("cured chuck", text.lower())

    def test_the_menu_prints_exactly_what_the_handler_rendered(self):
        """The menu is a printer here, not an author.

        A screen that reformatted the block would be a second owner of how a
        slot reads, which is the arrangement this display exists to avoid.
        """
        self._start_a_cure()
        expected = [
            strip_ansi(line) for line in self.char1.curing.status_lines()
        ]

        text, _options = self._render()

        for line in expected:
            with self.subTest(line=line):
                self.assertIn(line, text)

    def test_a_facility_with_nothing_deferred_shows_no_slot_block(self):
        """An anvil has no slots and must not grow a line saying so.

        The test is on the RECIPES, not the typeclass: what makes a menu show
        slots is that something workable there does not finish in the call that
        started it.
        """
        anvil = AnvilFacility.create(
            "Metalsmith Anvil", location=self.char1.location
        )[0]

        text, _options = self._render(facility=anvil)

        self.assertNotIn("slots", text.lower())



class TestCollectIsReachableFromTheMenu(DeferredMenuTestBase):
    """The row that saves a player from quitting the menu to type a command."""

    def test_an_idle_chamber_offers_no_collect_row(self):
        _text, options = self._render()

        self.assertNotIn(crafting_menu.DEFERRED_COLLECT_DESC, options)

    def test_a_chamber_with_something_in_it_offers_collect(self):
        """Offered while the cure is still WORKING, not only when it is done.

        The block directly above the row already says which, and an option that
        appears and disappears as a timer runs is one a player learns not to
        look for.
        """
        self._start_a_cure()

        _text, options = self._render()

        self.assertIn(crafting_menu.DEFERRED_COLLECT_DESC, options)

    def test_an_anvil_offers_no_collect_row(self):
        anvil = AnvilFacility.create(
            "Metalsmith Anvil", location=self.char1.location
        )[0]

        _text, options = self._render(facility=anvil)

        self.assertNotIn(crafting_menu.DEFERRED_COLLECT_DESC, options)

    def test_collecting_from_the_menu_delivers_the_item(self):
        self._start_a_cure()
        self._finish_everything()

        crafting_menu.collect_deferred(
            self.char1, "", facility=self.chamber
        )

        carried = [obj.db_key for obj in self.char1.contents]
        self.assertIn(_CHUCK_RECIPE, carried)

    def test_collecting_from_the_menu_frees_the_slot(self):
        """The refusal the whole feature started from.

        "Cannot craft: No free curing slot" has to be actionable from the
        screen that says it.
        """
        self._start_a_cure()
        self._finish_everything()

        crafting_menu.collect_deferred(
            self.char1, "", facility=self.chamber
        )

        self.assertTrue(self.char1.curing.has_free_slot())

    def test_collecting_returns_to_the_recipe_list(self):
        """A goto callable returns a node NAME, never a rendered node.

        _execute_node treats a non-tuple return as display text, so a goto
        callable that rendered would print its own screen at the player and
        navigate nowhere.
        """
        self._start_a_cure()
        self._finish_everything()

        destination = crafting_menu.collect_deferred(
            self.char1, "", facility=self.chamber
        )

        self.assertEqual(("start", {"facility": self.chamber}), destination)

    def test_collecting_nothing_ready_says_so(self):
        """Silence would read as a broken button.

        The menu re-renders the same screen either way, so without a line the
        player cannot tell a refusal from a click that did not land.
        """
        self._start_a_cure()
        self.char1.msg = mock.Mock()

        crafting_menu.collect_deferred(self.char1, "", facility=self.chamber)

        said = " ".join(
            strip_ansi(str(call)) for call in self.char1.msg.call_args_list
        )
        self.assertIn("ready", said.lower())

    def test_collecting_something_ready_does_not_say_it_is_not(self):
        self._start_a_cure()
        self._finish_everything()
        self.char1.msg = mock.Mock()

        crafting_menu.collect_deferred(self.char1, "", facility=self.chamber)

        said = " ".join(
            strip_ansi(str(call)) for call in self.char1.msg.call_args_list
        )
        self.assertNotIn(
            strip_ansi(crafting_menu.DEFERRED_NONE_READY).lower(), said.lower()
        )
