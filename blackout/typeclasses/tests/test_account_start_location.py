"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: A brand-new character must spawn where a dead player respawns to,
             not settings.START_LOCATION (Limbo, #2) -- see
             typeclasses/accounts.py, Account.create_character.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py typeclasses
"""

from evennia.utils.test_resources import EvenniaTest

from typeclasses.tests import respawn_fixture
from typeclasses.tests.respawn_fixture import make_respawn_room


class TestNewCharacterStartLocation(EvenniaTest):
    """Account.create_character — where a freshly made character lands."""

    def setUp(self):
        super().setUp()
        respawn_fixture.install_empty_world()

    def tearDown(self):
        respawn_fixture.remove_world()
        super().tearDown()

    def test_new_character_spawns_at_the_respawn_room(self):
        room = make_respawn_room()

        character, errs = self.account.create_character(key="Newbie")

        self.assertFalse(errs)
        self.assertEqual(character.location, room)

    def test_the_home_of_a_new_character_is_the_respawn_room(self):
        room = make_respawn_room()

        character, _errs = self.account.create_character(key="Newbie")

        self.assertEqual(character.home, room)

    def test_missing_respawn_room_falls_back_to_start_location(self):
        """No respawn point placed. Must degrade to the parent's normal
        behaviour rather than raising or leaving location unset.
        """
        character, errs = self.account.create_character(key="Newbie")

        self.assertFalse(errs)
        self.assertIsNotNone(character.location)

    def test_an_explicit_location_kwarg_is_never_overridden(self):
        make_respawn_room()

        character, errs = self.account.create_character(
            key="Newbie", location=self.room2
        )

        self.assertFalse(errs)
        self.assertEqual(character.location, self.room2)
