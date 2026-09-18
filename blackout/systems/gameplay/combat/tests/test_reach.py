"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/17/2026
Description: Tests for systems/gameplay/combat/reach.py — the metric, the Z
             guard, the cross-map guard, and the data that decides how far a
             weapon carries.

The pure half runs on plain dicts and needs no database. The grid half needs
XYZ rooms, which EvenniaTest's fixtures are not, so those cases build the two
tiles they measure between.
"""

from unittest import TestCase

from evennia.utils.test_resources import EvenniaTestCase

from typeclasses.rooms import GridTile

from systems.gameplay.combat import constants as const
from systems.gameplay.combat import reach


# ─── Private helper routines ─────────────────────────────────────────────────

def _weapon_data(max_range=0, style=None) -> dict:
    """One combat_profile snapshot, with only the fields reach reads."""
    return {"max_range": max_range, "active_combat_style": style or {}}


class _Standing:
    """Something standing in a room. All reach asks of an object is .location."""

    def __init__(self, location):
        self.location = location


# ─── The pure half ───────────────────────────────────────────────────────────

class TestReachTiles(TestCase):
    """How far a weapon carries is read from data, never from a branch."""

    def test_a_weapon_with_no_range_reaches_its_own_tile(self):
        """Which is every melee weapon, and is why none of them declare one."""
        self.assertEqual(reach.reach_tiles(_weapon_data()), const.MELEE_REACH_TILES)

    def test_a_missing_snapshot_reaches_its_own_tile(self):
        """None and {} are both "no weapon", not an error on the tick."""
        self.assertEqual(reach.reach_tiles(None), const.MELEE_REACH_TILES)
        self.assertEqual(reach.reach_tiles({}), const.MELEE_REACH_TILES)

    def test_the_style_range_bonus_adds_to_the_weapon(self):
        """Snipe is the reason this exists. The bonus is the style's, the
        base is the weapon's, and the sum is what the check uses."""
        style = {const.STYLE_RANGE_BONUS_KEY: 2}

        self.assertEqual(reach.reach_tiles(_weapon_data(7, style)), 9)

    def test_a_negative_bonus_cannot_drive_the_reach_below_melee(self):
        """A negative radius is not a smaller bounding box, it is a broken
        query. The floor is what stops one reaching the database."""
        style = {const.STYLE_RANGE_BONUS_KEY: -20}

        self.assertEqual(
            reach.reach_tiles(_weapon_data(7, style)), const.MELEE_REACH_TILES
        )

    def test_a_style_with_no_bonus_reads_zero(self):
        """Every melee style, and three of the four projectile ones."""
        self.assertEqual(reach.style_range_bonus({}), 0)
        self.assertEqual(reach.style_range_bonus(None), 0)


class TestReachWithoutCoordinates(EvenniaTestCase):
    """Off the grid, reach falls back to comparing rooms.

    This is the case the whole test suite runs in: EvenniaTest's fixture
    rooms are plain Rooms with no coordinates. Melee has to keep working
    there, and a projectile weapon has to refuse rather than invent a
    distance.
    """

    def setUp(self):
        super().setUp()

        from evennia import create_object

        self.room = create_object("typeclasses.rooms.Room", key="here")
        self.elsewhere = create_object("typeclasses.rooms.Room", key="there")
        self.attacker = _Standing(self.room)

    def test_melee_reaches_something_in_the_same_room(self):
        target = _Standing(self.room)

        self.assertTrue(reach.in_reach(self.attacker, target, 0))

    def test_melee_does_not_reach_another_room(self):
        target = _Standing(self.elsewhere)

        self.assertFalse(reach.in_reach(self.attacker, target, 0))

    def test_a_wide_reach_off_the_grid_falls_back_to_the_room(self):
        """A bow in a hand-built area is a bow in one room.

        Reporting a distance for two rooms with no coordinates would be
        inventing geometry, so the answer degrades to the same-tile one
        rather than to "always in range".
        """
        near = _Standing(self.room)
        far = _Standing(self.elsewhere)

        self.assertTrue(reach.in_reach(self.attacker, near, 7))
        self.assertFalse(reach.in_reach(self.attacker, far, 7))

    def test_distance_is_none_when_neither_room_is_on_the_grid(self):
        """None, not zero. A caller that read it as a distance would report
        two rooms on different maps as the same tile."""
        target = _Standing(self.elsewhere)

        self.assertIsNone(reach.tile_distance(self.attacker, target))

    def test_nothing_reaches_a_combatant_with_no_location(self):
        nowhere = _Standing(None)

        self.assertFalse(reach.in_reach(self.attacker, nowhere, 7))
        self.assertFalse(reach.in_reach(_Standing(None), nowhere, 7))


# ─── The grid half ───────────────────────────────────────────────────────────

class TestReachOnTheGrid(EvenniaTestCase):
    """The metric, the Z guard and the cross-map guard, measured on real tiles."""

    def setUp(self):
        super().setUp()

        self.origin = self._tile(0, 0, "testmap")

    def _tile(self, x, y, z):
        """One XYZ room at the given coordinates."""
        # GridTile.create, not XYZRoom.create with a typeclass= argument:
        # the contrib passes its own class through that keyword, so naming
        # one raises "multiple values for keyword argument".
        room, _err = GridTile.create(f"tile-{x}-{y}-{z}", xyz=(x, y, z))

        return room

    def test_a_tile_inside_the_radius_is_in_reach(self):
        attacker = _Standing(self.origin)
        target = _Standing(self._tile(3, 4, "testmap"))

        self.assertTrue(reach.in_reach(attacker, target, 7))

    def test_a_tile_outside_the_radius_is_not(self):
        attacker = _Standing(self.origin)
        target = _Standing(self._tile(0, 9, "testmap"))

        self.assertFalse(reach.in_reach(attacker, target, 7))

    def test_the_metric_cuts_the_corners_of_the_box(self):
        """Euclidean, not chebyshev.

        (5, 5) is inside the 7x7 BOX and outside the circle of radius 7,
        because 5*5 + 5*5 is 50 and 7*7 is 49. Asserted against the
        configured metric rather than against the literal answer, so a
        deliberate retune to chebyshev moves this test with it instead of
        breaking it.
        """
        attacker = _Standing(self.origin)
        target = _Standing(self._tile(5, 5, "testmap"))
        expected = reach.in_reach(attacker, target, 7)

        self.assertEqual(expected, const.REACH_DISTANCE_METRIC == "chebyshev")

    def test_the_distance_reported_is_the_straight_line(self):
        attacker = _Standing(self.origin)
        target = _Standing(self._tile(3, 4, "testmap"))

        self.assertEqual(reach.tile_distance(attacker, target), 5)

    def test_a_different_z_is_out_of_reach_at_any_distance(self):
        """The adjacent tile one floor up is not adjacent."""
        attacker = _Standing(self.origin)
        target = _Standing(self._tile(0, 1, "upstairs"))

        self.assertFalse(reach.in_reach(attacker, target, 99))
        self.assertIsNone(reach.tile_distance(attacker, target))

    def test_a_different_map_is_out_of_reach_at_the_same_coordinates(self):
        """Two maps can both have a tile at (0, 0). A shot between them
        would be a shot through the worst kind of wall."""
        attacker = _Standing(self.origin)
        target = _Standing(self._tile(0, 0, "othermap"))

        self.assertFalse(reach.in_reach(attacker, target, 7))

    def test_a_melee_attacker_on_the_grid_still_needs_the_same_tile(self):
        """A radius of 0 compares rooms, so adding coordinates changes
        nothing about how melee behaves."""
        attacker = _Standing(self.origin)
        target = _Standing(self._tile(0, 1, "testmap"))

        self.assertFalse(reach.in_reach(attacker, target, 0))
        self.assertTrue(reach.in_reach(attacker, _Standing(self.origin), 0))


class TestSearchCandidates(EvenniaTestCase):
    """The attack command's search has to cover as far as the weapon shoots."""

    def setUp(self):
        super().setUp()

        from evennia import create_object

        self.room = create_object("typeclasses.rooms.Room", key="here")
        self.attacker = create_object("typeclasses.objects.Object", key="me")
        self.attacker.location = self.room

    def test_a_melee_reach_asks_for_the_default_candidates(self):
        """None is the answer, not a failure: Evennia's own default set is
        already the right one for a same-tile weapon."""
        self.assertIsNone(reach.search_candidates(self.attacker, 0))

    def test_a_wider_reach_returns_an_explicit_list(self):
        self.assertIsInstance(reach.search_candidates(self.attacker, 7), list)


class TestNearestTileInReach(EvenniaTestCase):
    """Where `attack` walks to when it cannot reach.

    The ring is asked of the TARGET, so a bow stops as soon as the shot is
    legal and a sword keeps walking onto the tile. Both answers come from one
    number on the ItemDef.
    """

    def setUp(self):
        super().setUp()

        # A whole row of tiles, because rooms_in_reach returns the tiles that
        # EXIST. Two lone tiles ten apart would make the target's own tile the
        # only member of its ring, and every case below would pass for the
        # wrong reason.
        self.row = [self._tile(x, 0, "walkmap") for x in range(11)]
        self.attacker = _Standing(self.row[0])
        self.target = _Standing(self.row[10])

    def _tile(self, x, y, z):
        room, _err = GridTile.create(f"walk-{x}-{y}-{z}", xyz=(x, y, z))

        return room

    def test_a_melee_attacker_walks_onto_the_target_tile(self):
        """The behaviour every sword had before this routine existed."""
        destination = reach.nearest_tile_in_reach(
            self.attacker, self.target, const.MELEE_REACH_TILES
        )

        self.assertIs(destination, self.target.location)

    def test_a_ranged_attacker_stops_at_its_own_reach(self):
        """The bug this fixes: an archer walked onto the raider to fire a shot
        that was already legal from where it stood."""
        radius = 7
        destination = reach.nearest_tile_in_reach(
            self.attacker, self.target, radius
        )
        distance = reach.room_distance(destination, self.target.location)

        self.assertIsNotNone(destination)
        self.assertLessEqual(distance, radius)
        self.assertIsNot(destination, self.target.location)

    def test_the_chosen_tile_satisfies_the_check_that_follows_it(self):
        """The walk and the reach check read one metric, so the walk cannot
        end one tile short of its own rule."""
        radius = 7
        destination = reach.nearest_tile_in_reach(
            self.attacker, self.target, radius
        )

        self.assertTrue(
            reach.in_reach(_Standing(destination), self.target, radius)
        )

    def test_a_target_sharing_no_geometry_has_no_tile_to_walk_to(self):
        """Another map is not a longer walk. It is a refusal."""
        elsewhere = _Standing(self._tile(0, 0, "othermap"))

        self.assertIsNone(
            reach.nearest_tile_in_reach(self.attacker, elsewhere, 7)
        )


class TestEngagementCoversEveryWeapon(TestCase):
    """The fight has to be wider than the longest shot in it.

    ENGAGEMENT_RADIUS_TILES bounds who counts as still fighting. A weapon that
    outranged it could open a fight from outside one, and the fight would end
    on the grace while the shots kept landing. Read from ITEM_DB rather than
    asserted as a list, so a longer bow fails this instead of editing it.
    """

    def test_no_weapon_outranges_the_engagement_radius(self):
        from world.item_database import ITEM_DB

        for item_key, item_def in ITEM_DB.items():
            with self.subTest(item=item_key):
                styles = item_def.combat_styles or {}
                bonuses = [
                    reach.style_range_bonus(style) for style in styles.values()
                ]
                widest = int(item_def.max_range or 0) + max(bonuses or [0])

                self.assertLessEqual(widest, const.ENGAGEMENT_RADIUS_TILES)
