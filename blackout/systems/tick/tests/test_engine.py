"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: Tests for the tick engine's rotation policy -- deterministic
             ordering, and the strike counter that replaced
             drop-on-first-exception.

Run with the Evennia/Django test runner from the game dir:

    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat

_tick is driven directly rather than through the LoopingCall, matching
test_debug.py, so every assertion here is deterministic rather than
wall-clock dependent.
"""

from unittest import mock

from evennia.scripts.models import ScriptDB
from evennia.utils.test_resources import EvenniaTest

from systems.tick import constants as const
from systems.combat.combat import ensure_combat_handler
from systems.tick.engine import TICK_ENGINE_KEY, BlackoutTickEngine, get_tick_engine


# Public constant definitions

# A count comfortably past the eviction threshold, for asserting that a
# handler which already left the rotation is not charged further.
WELL_PAST_THRESHOLD = const.TICK_HANDLER_MAX_STRIKES + 3


class _RotationTestCase(EvenniaTest):
    """Shared setup: an engine with a registry this test owns outright."""

    def setUp(self):
        super().setUp()
        self.engine = get_tick_engine()
        # Start from a known-empty rotation rather than whatever earlier
        # fixtures left registered.
        self.engine.ndb._handler_ids = {}
        self.engine.ndb._handler_strikes = {}


class TestRotationOrdering(_RotationTestCase):
    """Tick order is gameplay in an OSRS-derived engine, not an implementation
    detail. It used to be a plain set, so two combatants who would each kill
    the other on the same tick had the winner chosen by CPython internals."""

    def test_handlers_tick_in_registration_order(self):
        first = ensure_combat_handler(self.char1)
        second = ensure_combat_handler(self.char2)
        ticked = []

        # _advance_one re-resolves each id through the ORM, but Evennia's
        # idmapper hands back these same instances, so an instance-level patch
        # is what the engine actually calls.
        first.tick = mock.MagicMock(side_effect=lambda: ticked.append(first.id))
        second.tick = mock.MagicMock(side_effect=lambda: ticked.append(second.id))

        self.engine._tick()

        self.assertEqual(ticked, [first.id, second.id])

    def test_reversing_registration_reverses_tick_order(self):
        """Guards against the assertion above passing by database-id accident
        rather than because the registry's order is being honoured."""
        first = ensure_combat_handler(self.char1)
        second = ensure_combat_handler(self.char2)
        ticked = []

        first.tick = mock.MagicMock(side_effect=lambda: ticked.append(first.id))
        second.tick = mock.MagicMock(side_effect=lambda: ticked.append(second.id))

        self.engine.ndb._handler_ids = {}
        self.engine.register(second)
        self.engine.register(first)

        self.engine._tick()

        self.assertEqual(ticked, [second.id, first.id])

    def test_re_registering_does_not_move_a_handler_to_the_back(self):
        first = ensure_combat_handler(self.char1)
        second = ensure_combat_handler(self.char2)

        # Re-arming mid-fight (ensure_combat_handler runs on every attack)
        # must not reshuffle the rotation under the other combatant.
        self.engine.register(first)
        order = list(self.engine._registry())

        self.assertEqual(order, [first.id, second.id])

    def test_unregistering_removes_only_that_handler(self):
        first = ensure_combat_handler(self.char1)
        second = ensure_combat_handler(self.char2)

        self.engine.unregister(first)
        order = list(self.engine._registry())

        self.assertEqual(order, [second.id])


class TestStrikeCounter(_RotationTestCase):
    """A single bad tick must no longer end a fight silently and forever."""

    def _failing_handler(self):
        handler = ensure_combat_handler(self.char1)
        handler.tick = mock.MagicMock(side_effect=RuntimeError("boom"))

        return handler

    def test_one_failure_does_not_evict(self):
        handler = self._failing_handler()

        self.engine._tick()

        self.assertTrue(self.engine.is_registered(handler))
        self.assertEqual(self.engine.strike_count(handler), 1)

    def test_failures_below_the_threshold_keep_the_handler(self):
        handler = self._failing_handler()

        for _ in range(const.TICK_HANDLER_MAX_STRIKES - 1):
            self.engine._tick()

        self.assertTrue(self.engine.is_registered(handler))

    def test_the_threshold_failure_evicts(self):
        handler = self._failing_handler()

        for _ in range(const.TICK_HANDLER_MAX_STRIKES):
            self.engine._tick()

        self.assertFalse(self.engine.is_registered(handler))

    def test_an_evicted_handler_stops_being_ticked(self):
        handler = self._failing_handler()

        for _ in range(WELL_PAST_THRESHOLD):
            self.engine._tick()

        self.assertEqual(handler.tick.call_count, const.TICK_HANDLER_MAX_STRIKES)

    def test_a_clean_tick_forgives_earlier_strikes(self):
        """Strikes are CONSECUTIVE. A combatant whose target briefly vanished
        must not be carried toward eviction by an unrelated failure later."""
        handler = ensure_combat_handler(self.char1)
        outcomes = [RuntimeError("boom"), None, RuntimeError("boom")]
        handler.tick = mock.MagicMock(
            side_effect=lambda: self._raise_or_pass(outcomes)
        )

        for _ in range(3):
            self.engine._tick()

        self.assertTrue(self.engine.is_registered(handler))
        self.assertEqual(self.engine.strike_count(handler), 1)

    def _raise_or_pass(self, outcomes):
        outcome = outcomes.pop(0)

        if outcome is not None:
            raise outcome

    def test_a_healthy_handler_carries_no_strikes(self):
        handler = ensure_combat_handler(self.char1)
        handler.tick = mock.MagicMock(return_value=None)

        self.engine._tick()

        self.assertEqual(self.engine.strike_count(handler), 0)

    def test_one_broken_handler_never_stops_the_others(self):
        broken = self._failing_handler()
        healthy = ensure_combat_handler(self.char2)
        healthy.tick = mock.MagicMock(return_value=None)

        for _ in range(WELL_PAST_THRESHOLD):
            self.engine._tick()

        self.assertTrue(self.engine.is_registered(healthy))
        self.assertEqual(healthy.tick.call_count, WELL_PAST_THRESHOLD)

    def test_a_failing_handler_never_stops_the_tick_counter(self):
        self._failing_handler()
        self.engine.ndb.tick_number = None

        for _ in range(WELL_PAST_THRESHOLD):
            self.engine._tick()

        self.assertEqual(self.engine.ndb.tick_number, WELL_PAST_THRESHOLD)


class TestDeadRowHandling(_RotationTestCase):
    """A deleted handler is gone, not broken -- it leaves quietly and does not
    burn strikes on its way out."""

    def test_a_deleted_handler_is_dropped_on_the_next_tick(self):
        handler = ensure_combat_handler(self.char1)
        handler_id = handler.id
        handler.delete()

        self.engine._tick()
        registry = self.engine._registry()

        self.assertNotIn(handler_id, registry)

    def test_a_deleted_handler_records_no_strike(self):
        handler = ensure_combat_handler(self.char1)
        handler_id = handler.id
        handler.delete()

        self.engine._tick()
        strikes = self.engine._strikes()

        self.assertNotIn(handler_id, strikes)


class TestStaleTypeclassPath(EvenniaTest):
    """The engine row records its typeclass as an import path, so moving the
    module leaves a row Evennia loads as a plain DefaultScript. Every attack
    then died on ``'DefaultScript' object has no attribute '_ensure_loop'``
    until someone deleted the row by hand."""

    def _break_the_stored_path(self):
        """Point the live engine row at a module that does not exist."""
        engine = get_tick_engine()

        ScriptDB.objects.filter(id=engine.id).update(
            db_typeclass_path="systems.combat.tick_engine.BlackoutTickEngine"
        )
        # Drop the idmapper's cached instance so the next lookup re-resolves
        # the path rather than handing back the object we just invalidated.
        ScriptDB.flush_instance_cache(force=True)

        # Assert the break took: if a future Evennia raised on the bad path
        # instead of falling back, these tests would pass without testing
        # anything.
        broken = ScriptDB.objects.filter(db_key=TICK_ENGINE_KEY).first()
        self.assertNotIsInstance(broken, BlackoutTickEngine)

    def test_a_stale_path_is_repaired_rather_than_returned(self):
        self._break_the_stored_path()

        engine = get_tick_engine()

        self.assertIsInstance(engine, BlackoutTickEngine)

    def test_the_repaired_engine_leaves_exactly_one_row(self):
        """The stale row is replaced, not merely shadowed -- two rows under
        one key would make which engine you get an ordering accident."""
        self._break_the_stored_path()

        get_tick_engine()
        rows = ScriptDB.objects.filter(db_key=TICK_ENGINE_KEY)

        self.assertEqual(rows.count(), 1)

    def test_persistent_attributes_survive_the_repair(self):
        """The respawn queue and regen registry live on Attributes, so a
        rebuild that dropped them would cost real gameplay state."""
        engine = get_tick_engine()
        engine.attributes.add("canary", 17)
        self._break_the_stored_path()

        repaired = get_tick_engine()

        self.assertEqual(repaired.attributes.get("canary"), 17)
