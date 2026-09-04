"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: Guard the neighbourhood memo -- that it caches, that it stops
             caching when the map changes, and that a failure inside it costs
             performance rather than correctness.

Why the invalidation tests are the important half
-------------------------------------------------
A cache that never returns a stale answer but also never hits is merely slow;
a cache that hits and is wrong feeds a player a map with holes in it. So the
tests below spend most of their length on the second failure, and the one that
matters most is `test_building_a_tile_invalidates`: rooms are DEMOLISHED AND
REBUILT during a map rebuild, and a memo that only cleared on deletion would go
stale in exactly that window.
"""

import unittest

from evennia.utils.test_resources import EvenniaTest

from systems.statefeed import constants as const
from systems.statefeed import events, neighbourhood


# ─── Private constant definitions ────────────────────────────────────────────

# A z-coordinate of this suite's own, so a tile built here cannot collide with
# one another test left behind.
_TEST_MAP = "neighbourhood_test_map"

# Small, because these tests assert cache BEHAVIOUR rather than cost. A 3x3
# grid exercises every branch a 21x21 one would.
_GRID = 3


# ─── Private helper routines ─────────────────────────────────────────────────

def _build_tile(x: int, y: int):
    """Create one GridTile at the given coordinate on the test map."""
    from typeclasses.rooms import GridTile

    return GridTile.create(key=f"nb_tile_{x}_{y}", xyz=(x, y, _TEST_MAP))[0]


# ─── Test cases ──────────────────────────────────────────────────────────────

class NeighbourhoodCacheTests(EvenniaTest):
    """The memo, against real rooms."""

    def setUp(self):
        super().setUp()
        neighbourhood.reset()
        self.tiles = {}

        for x in range(_GRID):
            for y in range(_GRID):
                self.tiles[(x, y)] = _build_tile(x, y)

        # Building tiles invalidates, which is the behaviour under test
        # elsewhere. Start the counters clean so a hit/miss assertion below is
        # about the lookup and not about the fixture.
        neighbourhood.reset()
        self.centre = self.tiles[(1, 1)]

    def tearDown(self):
        neighbourhood.reset()
        super().tearDown()

    def test_the_first_lookup_is_a_miss_and_the_second_is_a_hit(self):
        neighbourhood.visible_rooms(self.centre, 1)
        neighbourhood.visible_rooms(self.centre, 1)

        stats = neighbourhood.stats()

        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hits"], 1)

    def test_a_cached_answer_equals_the_uncached_one(self):
        """The memo must not change what the lookup means."""
        from systems.combat.auras.targeting import rooms_within_radius

        direct = rooms_within_radius(self.centre, 1)
        cached = neighbourhood.visible_rooms(self.centre, 1)
        again = neighbourhood.visible_rooms(self.centre, 1)

        self.assertEqual(sorted(r.id for r in cached),
                         sorted(r.id for r in direct))
        self.assertEqual(sorted(r.id for r in again),
                         sorted(r.id for r in direct))

    def test_two_radii_do_not_share_an_entry(self):
        """The radius is part of the key, or a raised radius reads a stale
        answer from the lowered one -- which is precisely the change this
        cache is expected to live through."""
        narrow = neighbourhood.visible_rooms(self.centre, 0)
        wide = neighbourhood.visible_rooms(self.centre, 1)

        self.assertNotEqual(len(narrow), len(wide))
        self.assertEqual(neighbourhood.stats()["size"], 2)

    def test_the_returned_list_is_a_copy(self):
        """A caller appending to its result must not corrupt the cache."""
        first = neighbourhood.visible_rooms(self.centre, 1)
        first.append("not a room")
        second = neighbourhood.visible_rooms(self.centre, 1)

        self.assertNotIn("not a room", second)

    def test_demolishing_a_tile_invalidates(self):
        neighbourhood.visible_rooms(self.centre, 1)
        self.assertEqual(neighbourhood.stats()["size"], 1)

        self.tiles[(0, 0)].delete()

        self.assertEqual(neighbourhood.stats()["size"], 0)

    def test_building_a_tile_invalidates(self):
        """
        The half a delete-only invalidator would miss. A map rebuild demolishes
        and then rebuilds; an entry cached in that window names a map with
        holes in it, and nothing else would ever clear it.
        """
        neighbourhood.visible_rooms(self.centre, 1)
        self.assertEqual(neighbourhood.stats()["size"], 1)

        _build_tile(_GRID + 1, _GRID + 1)

        self.assertEqual(neighbourhood.stats()["size"], 0)

    def test_a_deleted_room_is_gone_from_the_next_answer(self):
        """The end-to-end claim, rather than the counter behind it."""
        victim = self.tiles[(0, 1)]
        victim_id = victim.id

        # Ids are read BEFORE the delete. Evennia's idmapper hands back the
        # same instance the cache is holding, and Django nulls its pk on
        # delete() -- so reading .id off the list afterwards reports None for
        # the victim and the assertion would be testing the wrong thing.
        before_ids = [room.id for room in
                      neighbourhood.visible_rooms(self.centre, 1)]

        victim.delete()

        after_ids = [room.id for room in
                     neighbourhood.visible_rooms(self.centre, 1)]

        self.assertIn(victim_id, before_ids)
        self.assertNotIn(victim_id, after_ids)
        self.assertNotIn(None, after_ids)

    def test_a_none_room_returns_empty_and_caches_nothing(self):
        self.assertEqual(neighbourhood.visible_rooms(None, 1), [])
        self.assertEqual(neighbourhood.stats()["size"], 0)

    def test_events_visible_rooms_uses_the_cache(self):
        """
        The wiring, not the module. _visible_rooms is documented as the single
        place STATEFEED_ENTITY_RADIUS is read, so this also pins that the
        radius still reaches the cache as its key.
        """
        events._visible_rooms(self.centre)
        events._visible_rooms(self.centre)

        stats = neighbourhood.stats()

        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["size"], 1)

        # The entry is keyed by the PRODUCTION radius, so a change to the
        # constant moves the cache with it rather than leaving a second entry
        # nobody reads.
        neighbourhood.reset()
        neighbourhood.visible_rooms(self.centre, const.STATEFEED_ENTITY_RADIUS)
        events._visible_rooms(self.centre)

        self.assertEqual(neighbourhood.stats()["hits"], 1)


class NeighbourhoodFailureTests(unittest.TestCase):
    """A broken cache must cost speed, never correctness."""

    def tearDown(self):
        neighbourhood.reset()

    def test_invalidate_on_an_empty_cache_is_harmless(self):
        neighbourhood.reset()

        self.assertEqual(neighbourhood.invalidate(), 0)

    def test_a_room_with_no_id_is_not_cached(self):
        """
        A room mid-creation has no primary key. Keying on one would put an
        entry in the cache that no invalidation could ever name.
        """
        class _Unsaved:
            id = None

        neighbourhood.reset()
        neighbourhood.visible_rooms(_Unsaved(), 1)

        self.assertEqual(neighbourhood.stats()["size"], 0)
