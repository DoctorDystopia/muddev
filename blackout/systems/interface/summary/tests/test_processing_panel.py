"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for the dossier's Processing band -- what the character has
             working somewhere they are not standing.

             The band exists because curing is the first stage in the game
             whose state a player carries around with them: a full chamber
             three rooms away is a fact about the character, and "why can I not
             start another cure" is a question asked away from the chamber.

             Two decisions are guarded above the rest:

               1. THE BAND IS SILENT WHEN NOTHING IS IN PROGRESS. Most players
                  most of the time have nothing curing, and a row reading
                  "Curing slots: 0/1" on every dossier in the game is noise on
                  every dossier in the game.
               2. IT NAMES NO STAGE. The lines are the handler's and the roster
                  of handlers is the recipe registry's, so a second deferred
                  stage appears here with no edit to the panel.

Run with:
    evennia test --settings test_settings.py systems.interface.summary
"""



import time

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.crafting import crafting_service
from systems.gameplay.curing import constants as curing_constants
from systems.interface.summary.panel_defs.processing import ProcessingPanel
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.skill_facilities import CuringChamberFacility
from world.item_database import ITEM_DB



# Private constant definitions

_CHUCK_RECIPE = "mutant raider cured chuck"



class ProcessingPanelTestBase(EvenniaTest):
    """A character who may or may not have something in a chamber."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.chamber = CuringChamberFacility.create(
            "Curing Chamber", location=self.char1.location
        )[0]

    def _start_a_cure(self):
        ITEM_DB["mutant_raider_raw_chuck"].create(location=self.char1)
        crafting_service.perform_craft(self.char1, _CHUCK_RECIPE)

    def _finish_everything(self):
        past = time.time() - 1
        stored = self.char1.attributes.get(
            curing_constants.CURING_SLOTS_ATTR, default=[]
        )
        for slot in stored:
            slot[curing_constants.SLOT_DUE_AT_KEY] = past

    def _lines(self):
        rendered = ProcessingPanel.render(self.char1)

        return [strip_ansi(line) for line in rendered]



class TestTheBandKnowsWhenToBeQuiet(ProcessingPanelTestBase):
    """An idle stage is not news on a screen every player reads."""

    def test_a_character_with_nothing_curing_draws_no_band(self):
        """An empty render takes the heading with it -- service.py's own rule."""
        self.assertEqual([], self._lines())

    def test_a_character_with_a_cure_running_draws_the_band(self):
        self._start_a_cure()

        self.assertNotEqual([], self._lines())

    def test_collecting_empties_the_band_again(self):
        """The band tracks the chamber, holding nothing of its own.

        A panel that persisted a number would be a second, staler copy of the
        game state, which is the one thing BasePanel forbids outright.
        """
        self._start_a_cure()
        self._finish_everything()
        self.char1.curing.collect()

        self.assertEqual([], self._lines())



class TestTheBandSaysWhatTheChamberSays(ProcessingPanelTestBase):
    """One block, two screens, and they must not drift."""

    def test_the_band_is_the_handlers_own_block(self):
        self._start_a_cure()
        expected = [
            strip_ansi(line) for line in self.char1.curing.status_lines()
        ]

        self.assertEqual(expected, self._lines())

    def test_a_finished_cure_reads_as_ready(self):
        self._start_a_cure()
        self._finish_everything()

        joined = " ".join(self._lines()).lower()

        self.assertIn("ready", joined)



class TestTheStructuredForm(ProcessingPanelTestBase):
    """What a graphical client is given instead of the prose."""

    def test_nothing_in_progress_is_an_empty_stage_list(self):
        payload = ProcessingPanel.data(self.char1)

        self.assertEqual({"stages": []}, payload)

    def test_a_running_cure_reports_its_stage_by_machine_name(self):
        """The handler's attribute name, not a display word.

        A client branches on it, so a copy edit to a sentence must not change
        it.
        """
        self._start_a_cure()

        payload = ProcessingPanel.data(self.char1)

        self.assertEqual("curing", payload["stages"][0]["stage"])

    def test_a_running_cure_reports_counts_a_client_can_draw(self):
        self._start_a_cure()

        stage = ProcessingPanel.data(self.char1)["stages"][0]

        self.assertEqual(1, stage["slots_used"])
        self.assertEqual(self.char1.curing.slot_total(), stage["slots_total"])
        self.assertEqual(0, stage["ready"])

    def test_a_slot_carries_a_deadline_rather_than_a_sentence(self):
        """Seconds, so a client can run its own countdown between updates.

        A client given "2m 14s remaining" can only print a number that is
        already wrong.
        """
        self._start_a_cure()

        slot = ProcessingPanel.data(self.char1)["stages"][0]["slots"][0]

        self.assertIsInstance(slot["remaining"], float)
        self.assertGreater(slot["remaining"], 0)

    def test_the_payload_carries_no_colour_markup(self):
        """Escape codes are telnet's business and no client should strip them."""
        self._start_a_cure()
        self._finish_everything()

        slot = ProcessingPanel.data(self.char1)["stages"][0]["slots"][0]

        for key, value in slot.items():
            with self.subTest(field=key):
                self.assertEqual(strip_ansi(str(value)), str(value))

    def test_a_finished_cure_is_counted_as_ready(self):
        self._start_a_cure()
        self._finish_everything()

        stage = ProcessingPanel.data(self.char1)["stages"][0]

        self.assertEqual(1, stage["ready"])
        self.assertEqual(
            curing_constants.SLOT_STATE_READY, stage["slots"][0]["state"]
        )
