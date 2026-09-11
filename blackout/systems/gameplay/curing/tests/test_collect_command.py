"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for `collect`, the curing chamber's second command.

             The handler's own tests cover what collection DOES. These cover
             what the player is TOLD, because the three outcomes are easy to
             collapse into one and only one of them means come back later:

               - nothing curing at all
               - something curing, none of it ready
               - something ready

             Conflating the first two is the bug worth guarding. "Nothing in
             the chamber is ready yet" told to a player with an empty chamber
             sends them away to wait for nothing.

Run with:
    evennia test --settings test_settings.py systems.gameplay.curing
"""



import time

from evennia.utils.test_resources import EvenniaCommandTest

from systems.gameplay.crafting import crafting_service
from systems.gameplay.curing import constants as curing_constants
from systems.gameplay.progression.skills import constants as skill_constants
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.skill_facilities import CmdCollect, CuringChamberFacility
from world.item_database import ITEM_DB



# Private constant definitions

_CHUCK_RECIPE = "mutant raider cured chuck"



class CollectCommandTestBase(EvenniaCommandTest):
    """A character at a chamber, with the command bound to that chamber."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.chamber = CuringChamberFacility.create(
            "Curing Chamber", location=self.char1.location
        )[0]

    def _give_chuck(self):
        return ITEM_DB["mutant_raider_raw_chuck"].create(location=self.char1)

    def _start_a_cure(self):
        self._give_chuck()
        crafting_service.perform_craft(self.char1, _CHUCK_RECIPE)

    def _finish_everything(self):
        """Move every deadline into the past, in place.

        Rewriting the stored float rather than sleeping for five minutes, which
        is the whole reason readiness is a comparison against time.time().
        """
        past = time.time() - 1
        stored = self.char1.attributes.get(
            curing_constants.CURING_SLOTS_ATTR, default=[]
        )
        for slot in stored:
            slot[curing_constants.SLOT_DUE_AT_KEY] = past

    def _collect(self):
        """Run `collect` the way a player types it, and return the output."""
        return self.call(CmdCollect(), "", obj=self.chamber)



class TestCollectReportsTheRightThing(CollectCommandTestBase):
    """Which of the three outcomes the player is told about."""

    def test_an_empty_chamber_says_nothing_is_curing(self):
        response = self._collect()

        self.assertIn("nothing curing", response.lower())

    def test_an_empty_chamber_does_not_say_come_back_later(self):
        """The bug this file exists for.

        "Nothing is ready yet" sends a player away to wait for something they
        never started.
        """
        response = self._collect()

        self.assertNotIn("ready yet", response.lower())

    def test_an_unfinished_cure_says_not_ready_yet(self):
        self._start_a_cure()

        response = self._collect()

        self.assertIn("ready yet", response.lower())

    def test_an_unfinished_cure_reports_what_is_in_there(self):
        self._start_a_cure()

        response = self._collect()

        self.assertIn("cured chuck", response.lower())

    def test_an_unfinished_cure_reports_how_long_is_left(self):
        """A countdown, not a bare refusal.

        Being told only "not ready" gives the player no way to decide whether
        to wait or walk away, which on a five-minute timer is the only useful
        thing the command can say.
        """
        self._start_a_cure()

        response = self._collect()

        self.assertRegex(response, r"\d+m \d+s|\d+s")

    def test_an_unfinished_cure_is_not_taken(self):
        self._start_a_cure()

        self._collect()

        self.assertEqual(self.char1.curing.slot_used(), 1)

    def test_a_finished_cure_is_handed_over(self):
        self._start_a_cure()
        self._finish_everything()

        response = self._collect()

        self.assertIn("cured", response.lower())
        self.assertEqual(self.char1.curing.slot_used(), 0)

    def test_a_finished_cure_does_not_also_say_not_ready(self):
        self._start_a_cure()
        self._finish_everything()

        response = self._collect()

        self.assertNotIn("ready yet", response.lower())

    def test_the_cured_meat_is_actually_carried_afterwards(self):
        """The command's visible effect, not just its line of text."""
        self._start_a_cure()
        self._finish_everything()
        cured_name = ITEM_DB["mutant_raider_cured_chuck"].name

        self._collect()

        carried = [
            obj for obj in self.char1.contents if obj.db_key == cured_name
        ]
        self.assertEqual(len(carried), 1)

    def test_collecting_an_empty_chamber_twice_is_safe(self):
        self._collect()
        response = self._collect()

        self.assertIn("nothing curing", response.lower())



class TestCollectAtASecondChamber(CollectCommandTestBase):
    """A cure is collectable at ANY chamber, not the one it was started at.

    State is on the character, so there is nothing tying a cure to a room -- and
    deliberately so: storing the starting chamber would mean storing a room
    reference that a map rebuild invalidates, which is the whole reason the
    slots are not kept in the facility.
    """

    def test_a_cure_started_elsewhere_collects_here(self):
        self._start_a_cure()
        self._finish_everything()
        other = CuringChamberFacility.create(
            "Another Curing Chamber", location=self.char1.location
        )[0]
        self.chamber.delete()

        response = self.call(CmdCollect(), "", obj=other)

        self.assertIn("cured", response.lower())
        self.assertEqual(self.char1.curing.slot_used(), 0)

    def test_destroying_the_chamber_does_not_destroy_the_cure(self):
        """The decisive argument for keeping state off the facility.

        teardown.py destroys a facility with its room, depth-first, so contents
        die before the container. A cure held in the chamber would be destroyed
        by clean_and_reload_all_maps.ps1 -- an operator action.
        """
        self._start_a_cure()

        self.chamber.delete()

        self.assertEqual(self.char1.curing.slot_used(), 1)
