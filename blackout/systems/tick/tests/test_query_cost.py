"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: Tests that the tick's database cost does not scale with how many
             combatants share a room.

Why this is a test and not a benchmark
--------------------------------------
The failure being guarded against is invisible at development scale. One player
fighting one raider issues a handful of queries per tick and looks fine; twenty
combatants in a room issued O(N*M) round trips every 0.6 seconds, because
check_stop_combat asked "does this occupant have a combat handler?" for every
occupant of every combatant, and each answer was `obj.scripts.all()`.

Nothing about that shows up as an error. It shows up as tick drift, which
tick_debug faithfully reports without being able to say why. So the query count
is asserted directly, with assertNumQueries, rather than left to be noticed.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.tick
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from evennia.utils.test_resources import EvenniaTest

from systems.combat.combat import COMBAT_HANDLER_KEY, ensure_combat_handler
from systems.tick.engine import get_tick_engine
from world.npc_database import NPC_DB


# Public constant definitions

# Enough combatants that an O(N*M) walk would be obvious against an O(N) one,
# while keeping the fixture cheap to build.
CROWD_SIZE = 6

# get_sides resolves the tick engine once, through get_singleton_script, which
# is one ScriptDB lookup. That is a FIXED cost -- it does not grow with the
# room -- and removing it needs a process-wide cache of a singleton Script,
# which was tried and rejected: it survives Django's per-test rollback and it
# outlives the stale-typeclass repair that deliberately replaces the row.
# One query that does not scale is the right trade against a cache that lies.
ENGINE_LOOKUP_QUERIES = 1


class _CrowdedRoomTestCase(EvenniaTest):
    """A room holding several mutually-aware combatants."""

    def setUp(self):
        super().setUp()
        self.engine = get_tick_engine()
        self.engine.ndb._handler_ids = None
        self.engine.ndb._owner_index = None
        self.engine.ndb._inbound_actions = []

        # NPC_DB.create rather than spawn_mutant_raider: the spawner refuses
        # a second raider on one tile ("never two raiders on one tile"), so it
        # would hand back None for all but the first and the crowd this test
        # needs would never exist.
        self.raiders = [self._make_raider() for _ in range(CROWD_SIZE)]
        self.handlers = [ensure_combat_handler(raider) for raider in self.raiders]

        self.player = ensure_combat_handler(self.char1)
        self.player.apply_action(
            {"kind": "attack", "target": self.raiders[0]}
        )

    def _make_raider(self):
        raider = NPC_DB["mutant_raider"].create(location=self.room1)

        self.assertIsNotNone(raider, msg="the crowd fixture must actually spawn")

        return raider


class TestOwnerLookupIsFree(_CrowdedRoomTestCase):
    """Resolving a handler by its owner must not touch the database."""

    def test_a_registered_handler_is_found_without_a_query(self):
        owner = self.raiders[0]
        self.engine.handler_for(owner.id, COMBAT_HANDLER_KEY)  # warm the index

        with self.assertNumQueries(0):
            found = self.engine.handler_for(owner.id, COMBAT_HANDLER_KEY)

        self.assertIsNotNone(found)

    def test_an_unregistered_owner_is_answered_without_a_query(self):
        self.engine._owner_index()  # warm

        with self.assertNumQueries(0):
            found = self.engine.handler_for(self.obj1.id, COMBAT_HANDLER_KEY)

        self.assertIsNone(found)

    def test_a_deleted_handler_is_not_handed_out(self):
        owner = self.raiders[0]
        self.handlers[0].delete()

        found = self.engine.handler_for(owner.id, COMBAT_HANDLER_KEY)

        self.assertIsNone(found)

    def test_a_stale_entry_is_evicted_rather_than_re_found(self):
        owner = self.raiders[0]
        self.handlers[0].delete()

        self.engine.handler_for(owner.id, COMBAT_HANDLER_KEY)

        self.assertNotIn(
            (owner.id, COMBAT_HANDLER_KEY), self.engine._owner_index()
        )


class TestGetSidesDoesNotScan(_CrowdedRoomTestCase):
    """The O(N*M) site."""

    def test_scanning_a_crowded_room_costs_one_fixed_query(self):
        self.engine._owner_index()  # warm the index

        with self.assertNumQueries(ENGINE_LOOKUP_QUERIES):
            allies, enemies = self.player.get_sides()

        self.assertEqual(allies, [self.char1])
        self.assertIn(self.raiders[0], enemies)

    def test_the_cost_does_not_grow_with_the_crowd(self):
        """The property that matters, and the one that was broken: adding
        occupants must not add queries. It used to add one per occupant per
        combatant, every 0.6 seconds."""
        self.engine._owner_index()

        with self.assertNumQueries(ENGINE_LOOKUP_QUERIES):
            self.player.get_sides()

        for _ in range(CROWD_SIZE):
            extra = self._make_raider()
            ensure_combat_handler(extra)

        with self.assertNumQueries(ENGINE_LOOKUP_QUERIES):
            self.player.get_sides()

    def test_it_still_finds_the_right_enemies(self):
        """Guards the assertions above: a get_sides that returned nothing
        would issue no queries either."""
        allies, enemies = self.player.get_sides()

        self.assertEqual(allies, [self.char1])
        self.assertEqual(enemies, [self.raiders[0]])

    def test_an_unengaged_occupant_is_not_an_enemy(self):
        _allies, enemies = self.player.get_sides()

        self.assertNotIn(self.raiders[1], enemies)


class TestTickCostIsBounded(_CrowdedRoomTestCase):
    """The whole tick, not just one routine."""

    def test_resolving_a_handler_from_the_rotation_is_free(self):
        """The rotation holds the handler objects themselves, so finding one
        to drive used to be a ScriptDB round trip per handler per tick and is
        now a dict hit. Asserted on the lookup alone -- _advance_one also RUNS
        the handler, which legitimately queries."""
        registry = self.engine._registry()  # warm
        handler_id = self.handlers[0].id

        with self.assertNumQueries(0):
            found = registry.get(handler_id)

        self.assertIsNotNone(found)
        self.assertEqual(found.id, handler_id)

    def test_advancing_a_handler_costs_the_same_in_a_bigger_rotation(self):
        """The scaling property for the tick loop: more registered handlers
        must not make driving one of them more expensive."""
        self.engine._registry()
        handler_id = self.handlers[0].id

        with CaptureQueriesContext(connection) as small:
            self.engine._advance_one(handler_id)

        for _ in range(CROWD_SIZE):
            extra = self._make_raider()
            ensure_combat_handler(extra)

        with CaptureQueriesContext(connection) as large:
            self.engine._advance_one(handler_id)

        self.assertEqual(len(large), len(small))

    def test_a_dropped_handler_leaves_both_structures(self):
        handler = self.handlers[0]
        owner = self.raiders[0]

        self.engine.unregister(handler)

        self.assertNotIn(handler.id, self.engine._registry())
        self.assertNotIn(
            (owner.id, COMBAT_HANDLER_KEY), self.engine._owner_index()
        )

    def test_reseeding_rebuilds_both_structures_together(self):
        """They are populated by one query so they cannot disagree about what
        is registered."""
        self.engine.ndb._handler_ids = None
        self.engine.ndb._owner_index = None

        registry = self.engine._registry()
        owners = self.engine._owner_index()

        for handler in registry.values():
            owner = handler.obj
            if owner is not None:
                self.assertIn((owner.id, handler.key), owners)
