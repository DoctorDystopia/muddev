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

from typeclasses.rooms import GridTile
from world.respawn import RESPAWN_XYZ


def _make_respawn_room() -> GridTile:
    """Build the grid tile world/respawn.py points at.

    Mirrors typeclasses/tests/test_respawn.py -- no xyzgrid exists in a test
    database, so the one coordinate under test is built by hand.
    """
    x, y, z = RESPAWN_XYZ
    return GridTile.create(key="Oasis Entrance", xyz=(x, y, z))[0]


class TestNewCharacterStartLocation(EvenniaTest):
    """Account.create_character — where a freshly made character lands."""

    def test_new_character_spawns_at_the_respawn_room(self):
        room = _make_respawn_room()

        character, errs = self.account.create_character(key="Newbie")

        self.assertFalse(errs)
        self.assertEqual(character.location, room)

    def test_missing_respawn_room_falls_back_to_start_location(self):
        """No grid built. Must degrade to the parent's normal behaviour
        rather than raising or leaving location unset.
        """
        character, errs = self.account.create_character(key="Newbie")

        self.assertFalse(errs)
        self.assertIsNotNone(character.location)

    def test_an_explicit_location_kwarg_is_never_overridden(self):
        _make_respawn_room()

        character, errs = self.account.create_character(
            key="Newbie", location=self.room2
        )

        self.assertFalse(errs)
        self.assertEqual(character.location, self.room2)
