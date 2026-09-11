"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for the slot display -- the block every screen shows when it
             wants to say what is in a chamber.

             The handler renders it, and that is the thing worth guarding.
             Three screens print it today (the chamber's craft menu, the
             dossier's Processing band, and `collect`'s refusal), and the whole
             reason it is assembled in one place is that three screens
             assembling it themselves would eventually describe the same slot
             three ways.

             So these tests assert what the BLOCK says, never which screen
             said it. The screens' own tests cover whether they show it.

Run with:
    evennia test --settings test_settings.py systems.gameplay.curing
"""



from evennia.utils.ansi import strip_ansi

from systems.gameplay.curing import constants as curing_constants

from .test_handler import CuringTestBase



class SlotDisplayTestBase(CuringTestBase):
    """A chamber, plus the one read every test here makes."""

    def _display(self):
        """The rendered block, stripped of colour so a test can read it."""
        lines = self.char1.curing.status_lines()

        return [strip_ansi(line) for line in lines]

    def _header(self):
        return self._display()[0]



class TestTheHeaderCountsSlots(SlotDisplayTestBase):
    """The line that answers "why can I not start another one"."""

    def test_an_idle_chamber_still_reports_its_slots(self):
        """The display is never empty.

        A player with room to spare is told so. It is the answer to the
        question they are about to ask, given before they ask it, and it costs
        one line on a screen they opened deliberately.
        """
        header = self._header()

        self.assertIn("0/", header)

    def test_the_header_counts_the_slots_the_level_opened(self):
        """Derived from the skill, so a third slot needs no edit here."""
        self._set_curing_level(max(curing_constants.CURING_SLOT_LEVELS))
        total = self.char1.curing.slot_total()

        header = self._header()

        self.assertIn(f"0/{total}", header)

    def test_a_started_cure_shows_in_the_count(self):
        self._give_chuck()
        self._start()

        header = self._header()

        self.assertIn("1/", header)

    def test_an_idle_chamber_does_not_claim_anything_is_ready(self):
        """The two headers are separate templates for this reason.

        "Ready to collect" on an empty chamber is a walk across the map for
        nothing.
        """
        header = self._header()

        self.assertNotIn("ready", header.lower())

    def test_a_finished_cure_says_so_in_the_header(self):
        """The one thing worth reading at a glance.

        A player scanning the dossier reads the header and nothing else, so
        "come back to the chamber" has to survive being the only line seen.
        """
        self._give_chuck()
        self._start()
        self._finish_everything()

        header = self._header()

        self.assertIn("ready", header.lower())



class TestEachSlotReportsItself(SlotDisplayTestBase):
    """The lines under the header, one per occupied slot."""

    def test_an_idle_chamber_draws_no_slot_lines(self):
        display = self._display()

        self.assertEqual(1, len(display))

    def test_one_cure_draws_one_line(self):
        self._give_chuck()
        self._start()

        display = self._display()

        self.assertEqual(2, len(display))

    def test_a_working_slot_names_what_is_in_it(self):
        self._give_chuck()
        self._start()

        display = self._display()

        self.assertIn("cured chuck", display[1].lower())

    def test_a_working_slot_counts_down(self):
        """A countdown, not a bare "in progress".

        Being told only that something is curing gives a player no way to
        decide whether to wait, which on a five-minute timer is the only
        useful thing the line can say.
        """
        self._give_chuck()
        self._start()

        display = self._display()

        self.assertIn("remaining", display[1].lower())

    def test_a_finished_slot_says_ready_rather_than_a_countdown(self):
        self._give_chuck()
        self._start()
        self._finish_everything()

        display = self._display()

        self.assertIn("ready", display[1].lower())
        self.assertNotIn("remaining", display[1].lower())

    def test_every_slot_line_is_indented_under_its_header(self):
        """The block arrives ready to print, indentation included.

        A caller that indented for itself would be a second owner of how this
        reads, and the screens showing it would drift the first time either
        was edited.
        """
        self._give_chuck()
        self._start()

        display = self._display()

        self.assertTrue(display[1].startswith(curing_constants.SLOT_LINE_INDENT))
        self.assertFalse(display[0].startswith(" "))



class TestReadyCount(SlotDisplayTestBase):
    """What a screen asks when it wants a number rather than a block."""

    def test_nothing_curing_is_nothing_ready(self):
        self.assertEqual(0, self.char1.curing.ready_count())

    def test_an_unfinished_cure_is_not_ready(self):
        self._give_chuck()
        self._start()

        self.assertEqual(0, self.char1.curing.ready_count())

    def test_a_finished_cure_is_ready(self):
        self._give_chuck()
        self._start()
        self._finish_everything()

        self.assertEqual(1, self.char1.curing.ready_count())

    def test_the_count_agrees_with_the_keys_it_is_derived_from(self):
        """Two readers of one fact, asserted to agree.

        ready_count and ready_keys are both public, and a screen picking the
        cheaper one must not get a different answer.
        """
        self._give_chuck()
        self._start()
        self._finish_everything()

        self.assertEqual(
            len(self.char1.curing.ready_keys()),
            self.char1.curing.ready_count(),
        )
