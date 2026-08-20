"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: Tests for the engine's INPUT phase — the inbound action queue that
             stopped commands mutating handler state mid-tick.

The determinism property is the point. A command arrives whenever its packet
does, at an arbitrary moment relative to the LoopingCall. Applying it on
arrival meant a command landing DURING a tick was seen by that tick or the next
depending on where its handler sat in the rotation. Draining at a fixed phase
makes the answer always "the next tick", for everyone.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.tick
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.combat.combat import ensure_combat_handler
from systems.tick.engine import get_tick_engine


class _InputTestCase(EvenniaTest):
    """An engine whose queues this test owns outright."""

    def setUp(self):
        super().setUp()
        self.engine = get_tick_engine()
        self.engine.ndb._handler_ids = {}
        self.engine.ndb._handler_strikes = {}
        self.engine.ndb._inbound_actions = []
        self.handler = ensure_combat_handler(self.char1)
        ensure_combat_handler(self.char2)


class TestActionsAreDeferred(_InputTestCase):
    """queue_action records an intention; it does not apply one."""

    def test_queueing_does_not_set_the_pending_action(self):
        self.handler.ndb.pending_action = None

        self.handler.queue_action({"kind": "attack", "target": self.char2})

        self.assertIsNone(self.handler.ndb.pending_action)

    def test_queueing_puts_the_action_on_the_engine(self):
        self.handler.queue_action({"kind": "attack", "target": self.char2})

        self.assertEqual(self.engine.pending_action_count(), 1)

    def test_the_action_lands_on_the_next_tick(self):
        self.handler.queue_action({"kind": "attack", "target": self.char2})

        self.engine._drain_inbound()

        self.assertIsNotNone(self.handler.ndb.pending_action)
        self.assertEqual(self.handler.ndb.target_id, self.char2.id)

    def test_draining_empties_the_queue(self):
        self.handler.queue_action({"kind": "attack", "target": self.char2})

        self.engine._drain_inbound()

        self.assertEqual(self.engine.pending_action_count(), 0)

    def test_a_hold_reaches_the_handler(self):
        self.handler.queue_action({"kind": "hold"})

        self.engine._drain_inbound()

        self.assertEqual(self.handler.ndb.pending_action.kind, "hold")

    def test_a_flee_clears_the_cooldown(self):
        self.handler.ndb.cooldown_ticks = 3

        self.handler.queue_action({"kind": "flee"})
        self.engine._drain_inbound()

        self.assertEqual(self.handler.ndb.cooldown_ticks, 0)


class TestOrderingIsDeterministic(_InputTestCase):
    """The hole this phase closes."""

    def test_an_action_queued_during_a_tick_waits_for_the_next_one(self):
        """Whether the current tick sees a command must not depend on where
        its handler sits in the rotation."""
        seen = []

        def _tick_and_queue():
            # A handler queueing an action mid-tick, which is what a command
            # arriving during _tick amounts to.
            self.handler.queue_action({"kind": "hold"})
            seen.append(self.handler.ndb.pending_action)

        self.handler.ndb.pending_action = None
        self.handler.tick = mock.MagicMock(side_effect=_tick_and_queue)

        self.engine._tick()

        # Nothing applied during the tick it was queued in...
        self.assertEqual(seen, [None])

        # ...and applied at the top of the next.
        self.engine._tick()
        self.assertIsNotNone(self.handler.ndb.pending_action)

    def test_input_runs_before_the_handlers(self):
        order = []

        self.handler.tick = mock.MagicMock(
            side_effect=lambda: order.append("handler")
        )
        with mock.patch.object(
            self.handler, "apply_action",
            side_effect=lambda _d: order.append("input"),
        ):
            self.handler.queue_action({"kind": "hold"})
            self.engine._tick()

        self.assertEqual(order, ["input", "handler"])

    def test_the_last_intention_for_a_handler_wins(self):
        """Matches the old behaviour: a second command replaces the first
        rather than queueing behind it."""
        self.handler.queue_action({"kind": "attack", "target": self.char2})
        self.handler.queue_action({"kind": "hold"})

        self.engine._drain_inbound()

        self.assertEqual(self.handler.ndb.pending_action.kind, "hold")


class TestValidationStaysImmediate(_InputTestCase):
    """A player who typed something impossible is told now, not in 600ms."""

    def test_attacking_a_dead_target_is_refused_at_once(self):
        self.char1.msg = mock.MagicMock()
        self.char2.hp = 0

        self.handler.queue_action({"kind": "attack", "target": self.char2})

        self.char1.msg.assert_called()
        self.assertEqual(self.engine.pending_action_count(), 0)

    def test_an_unknown_kind_is_not_queued(self):
        self.handler.queue_action({"kind": "pirouette"})

        self.assertEqual(self.engine.pending_action_count(), 0)

    def test_an_attack_without_a_target_is_not_queued(self):
        self.handler.queue_action({"kind": "attack"})

        self.assertEqual(self.engine.pending_action_count(), 0)

    def test_starting_combat_is_still_immediate(self):
        """Entering combat is the acknowledgement that a fight began -- read
        by the summary panel and examine -- and takes no part in per-tick
        resolution order, so it does not wait for the tick."""
        from systems.tick.states import ActivityState

        self.handler.queue_action({"kind": "attack", "target": self.char2})

        self.assertEqual(self.handler.state, ActivityState.ACTIVE)
        self.assertTrue(self.char1.in_combat)
        # The defender is in combat too, without having queued anything.
        self.assertTrue(self.char2.in_combat)


class TestDrainIsolation(_InputTestCase):
    """The drain must not be able to stop the tick."""

    def test_a_handler_deleted_before_the_drain_is_skipped(self):
        self.handler.queue_action({"kind": "hold"})
        self.handler.delete()

        applied = self.engine._drain_inbound()

        self.assertEqual(applied, 0)

    def test_a_raising_apply_does_not_stop_the_others(self):
        other = ensure_combat_handler(self.char2)
        self.engine.enqueue_action(self.handler, {"kind": "hold"})
        self.engine.enqueue_action(other, {"kind": "hold"})

        # Patch the INSTANCE, not the class: both handlers are
        # BlackoutCombatHandlers, so a class-level patch would break the one
        # this test needs to survive.
        with mock.patch.object(
            self.handler, "apply_action", side_effect=RuntimeError("boom")
        ):
            self.engine._drain_inbound()  # must not raise

        # The second handler's action still landed.
        self.assertIsNotNone(other.ndb.pending_action)

    def test_a_raising_apply_does_not_stop_the_tick(self):
        self.engine.ndb.tick_number = None
        self.engine.enqueue_action(self.handler, {"kind": "hold"})

        with mock.patch.object(
            self.handler, "apply_action", side_effect=RuntimeError("boom")
        ):
            self.engine._tick()

        self.assertEqual(self.engine.current_tick(), 1)

    def test_enqueueing_a_dead_handler_is_a_no_op(self):
        self.handler.delete()

        self.engine.enqueue_action(self.handler, {"kind": "hold"})

        self.assertEqual(self.engine.pending_action_count(), 0)

    def test_an_action_queued_by_an_action_waits_a_tick(self):
        """The drain swaps its list out before applying, so work added during
        a drain belongs to the next tick rather than extending this one."""
        applied = []

        def _requeue(_action_dict):
            applied.append("first")
            self.engine.enqueue_action(self.handler, {"kind": "hold"})

        with mock.patch.object(self.handler, "apply_action", side_effect=_requeue):
            self.engine.enqueue_action(self.handler, {"kind": "hold"})
            self.engine._drain_inbound()

        self.assertEqual(applied, ["first"])
        self.assertEqual(self.engine.pending_action_count(), 1)
