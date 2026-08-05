"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/03/2026
Description: Tests for the aura radius query and the friend/foe predicate.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from evennia.utils.test_resources import EvenniaTest

from systems.combat.auras.targeting import (
    hostiles_in_rooms,
    is_hostile_pulse_target,
    rooms_within_radius,
)
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.rooms import GridTile

# The map name every fixture room is built on. Z is the map name, not a number.
TEST_MAP_NAME = "auratest"


def _make_tile(x: int, y: int, map_name: str = TEST_MAP_NAME) -> GridTile:
    """Create one grid room at (x, y).

    Called on GridTile rather than XYZRoom: XYZRoom.create passes
    `typeclass=cls` to DefaultRoom.create itself, so supplying a typeclass
    kwarg raises "got multiple values for keyword argument".
    """
    room = GridTile.create(key=f"tile_{x}_{y}", xyz=(x, y, map_name))[0]

    return room


class TestRoomsWithinRadius(EvenniaTest):
    """The bounding-box query plus the in-Python metric trim."""

    def test_radius_two_includes_axis_and_diagonal(self):
        origin = _make_tile(0, 0)
        on_axis = _make_tile(0, 2)
        diagonal = _make_tile(1, 1)

        in_range = rooms_within_radius(origin, 2)

        self.assertIn(origin, in_range)
        self.assertIn(on_axis, in_range)
        self.assertIn(diagonal, in_range)

    def test_radius_two_trims_the_box_corner(self):
        """Regression: (2,2) is inside the query's BOX but outside the circle.

        If the in-Python metric trim is ever dropped, the DB query alone would
        return this room and the aura would quietly gain reach on the diagonals.
        """
        origin = _make_tile(0, 0)
        corner = _make_tile(2, 2)

        in_range = rooms_within_radius(origin, 2)

        self.assertNotIn(corner, in_range)

    def test_rooms_outside_the_radius_are_excluded(self):
        origin = _make_tile(0, 0)
        far = _make_tile(0, 5)

        in_range = rooms_within_radius(origin, 2)

        self.assertNotIn(far, in_range)

    def test_spans_a_digit_boundary(self):
        """Regression: coordinates are TAG STRINGS, so "10" sorts before "9".

        A range-based lookup (db_key__gte / __lte) would compare
        lexicographically and drop rooms across a digit boundary. The query
        enumerates exact keys precisely so this case works.
        """
        origin = _make_tile(10, 0)
        neighbour = _make_tile(9, 0)

        in_range = rooms_within_radius(origin, 2)

        self.assertIn(neighbour, in_range)

    def test_other_maps_are_never_included(self):
        origin = _make_tile(0, 0)
        elsewhere = _make_tile(1, 0, map_name="someothermap")

        in_range = rooms_within_radius(origin, 2)

        self.assertNotIn(elsewhere, in_range)

    def test_off_grid_origin_degrades_to_own_room(self):
        """A plain Room has no .xyz. It must not raise -- hand-built areas exist."""
        in_range = rooms_within_radius(self.room1, 2)

        self.assertEqual(in_range, [self.room1])

    def test_zero_radius_is_own_room_only(self):
        origin = _make_tile(0, 0)
        _make_tile(0, 1)

        in_range = rooms_within_radius(origin, 0)

        self.assertEqual(in_range, [origin])

    def test_uses_a_single_query_not_one_per_tile(self):
        """The whole point of the bounding-box lookup.

        A naive get_xyz-per-coordinate implementation would issue (2r+1)^2 = 25
        queries here, every time the caster changes room.
        """
        origin = _make_tile(0, 0)
        for offset in range(1, 3):
            _make_tile(offset, 0)

        # Warm the .xyz tag cache so we measure only the radius query.
        origin.xyz

        with CaptureQueriesContext(connection) as captured:
            rooms_within_radius(origin, 2)

        self.assertEqual(len(captured.captured_queries), 1)


class TestIsHostilePulseTarget(EvenniaTest):
    """Friend/foe, inferred from db.npc_key plus CombatEntity-ness."""

    character_typeclass = BlackoutCharacter

    def test_hostile_npc_is_a_valid_target(self):
        self.char2.db.npc_key = "mutant_raider"

        self.assertTrue(is_hostile_pulse_target(self.char2, self.char1))

    def test_caster_never_targets_itself(self):
        self.char1.db.npc_key = "mutant_raider"

        self.assertFalse(is_hostile_pulse_target(self.char1, self.char1))

    def test_player_character_is_not_a_valid_target(self):
        """No npc_key means no target. This is what keeps auras out of PvP."""
        self.assertFalse(is_hostile_pulse_target(self.char2, self.char1))

    def test_non_combatant_npc_is_not_a_valid_target(self):
        """A shopkeeper has no is_alive at all -- the second guard catches it."""
        self.obj1.db.npc_key = "shopkeep"

        self.assertFalse(is_hostile_pulse_target(self.obj1, self.char1))

    def test_dead_hostile_is_not_a_valid_target(self):
        self.char2.db.npc_key = "mutant_raider"
        self.char2.hp = 0

        self.assertFalse(is_hostile_pulse_target(self.char2, self.char1))


class TestHostilesInRooms(EvenniaTest):
    """Collecting targets across every room in the radius."""

    character_typeclass = BlackoutCharacter

    def test_collects_across_multiple_rooms(self):
        far_room = _make_tile(0, 1)

        self.char2.db.npc_key = "mutant_raider"
        self.char2.location = far_room

        found = hostiles_in_rooms([self.room1, far_room], self.char1)

        self.assertEqual(found, [self.char2])

    def test_empty_when_nothing_hostile_is_in_range(self):
        found = hostiles_in_rooms([self.room1], self.char1)

        self.assertEqual(found, [])
