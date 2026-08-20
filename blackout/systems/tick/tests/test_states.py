"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: Tests for the activity state machine and for combat's in_combat
             becoming a derived property rather than a stored flag.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.tick
"""

import unittest

from evennia.utils.test_resources import EvenniaTest

from systems.combat.combat import ensure_combat_handler
from systems.tick import states
from systems.tick.states import ActivityEvent, ActivityState


class TestTransitionTable(unittest.TestCase):
    """Pure data -- no database involved."""

    def test_a_queued_action_engages_an_idle_actor(self):
        result = states.next_state(
            ActivityState.IDLE, ActivityEvent.ACTION_QUEUED
        )

        self.assertEqual(result, ActivityState.ACTIVE)

    def test_resolving_an_action_starts_recovery(self):
        result = states.next_state(
            ActivityState.ACTIVE, ActivityEvent.ACTION_RESOLVED
        )

        self.assertEqual(result, ActivityState.RECOVERING)

    def test_recovery_ending_re_engages(self):
        result = states.next_state(
            ActivityState.RECOVERING, ActivityEvent.COOLDOWN_EXPIRED
        )

        self.assertEqual(result, ActivityState.ACTIVE)

    def test_queueing_while_recovering_does_not_skip_the_cooldown(self):
        """Replacing the pending action must not let an actor swing early."""
        result = states.next_state(
            ActivityState.RECOVERING, ActivityEvent.ACTION_QUEUED
        )

        self.assertEqual(result, ActivityState.RECOVERING)

    def test_losing_a_target_ends_the_activity(self):
        """Models what Blackout does: a target vanishing tears the handler
        down. Staying IDLE and re-targetable would be a rules change."""
        result = states.next_state(
            ActivityState.ACTIVE, ActivityEvent.TARGET_INVALID
        )

        self.assertEqual(result, ActivityState.ENDING)

    def test_running_out_of_resources_ends_the_activity(self):
        """The same shape, for a gatherer whose vein is empty or a crafter
        out of materials -- craft_batch halts and clears the batch today."""
        result = states.next_state(
            ActivityState.ACTIVE, ActivityEvent.RESOURCES_EXHAUSTED
        )

        self.assertEqual(result, ActivityState.ENDING)

    def test_abandoning_moves_to_teardown(self):
        result = states.next_state(
            ActivityState.ACTIVE, ActivityEvent.ACTIVITY_ABANDONED
        )

        self.assertEqual(result, ActivityState.ENDING)

    def test_incapacitation_is_legal_from_every_non_final_state(self):
        for state in (
            ActivityState.IDLE,
            ActivityState.ACTIVE,
            ActivityState.RECOVERING,
            ActivityState.ENDING,
        ):
            result = states.next_state(
                state, ActivityEvent.ACTOR_INCAPACITATED
            )

            self.assertEqual(result, ActivityState.TERMINATED, msg=state.name)

    def test_an_illegal_pair_has_no_answer(self):
        """Absent means illegal. The machine says so rather than guessing."""
        result = states.next_state(
            ActivityState.IDLE, ActivityEvent.COOLDOWN_EXPIRED
        )

        self.assertIsNone(result)

    def test_nothing_escapes_a_terminated_actor(self):
        for event in ActivityEvent:
            result = states.next_state(ActivityState.TERMINATED, event)

            self.assertIsNone(result, msg=event.name)


class TestPredicates(unittest.TestCase):
    def test_only_acting_and_recovering_count_as_busy(self):
        self.assertTrue(states.is_busy(ActivityState.ACTIVE))
        self.assertTrue(states.is_busy(ActivityState.RECOVERING))
        self.assertFalse(states.is_busy(ActivityState.IDLE))
        self.assertFalse(states.is_busy(ActivityState.ENDING))
        self.assertFalse(states.is_busy(ActivityState.TERMINATED))

    def test_only_teardown_states_are_final(self):
        self.assertTrue(states.is_final(ActivityState.ENDING))
        self.assertTrue(states.is_final(ActivityState.TERMINATED))
        self.assertFalse(states.is_final(ActivityState.IDLE))
        self.assertFalse(states.is_final(ActivityState.ACTIVE))


class TestVocabularyIsGeneric(unittest.TestCase):
    """The constraint the machine was designed under: every name has to read
    correctly for a player mining a rock, not just for one swinging a sword.

    Asserted rather than left to review because the leak already happened
    twice in this codebase -- the tick engine wrote `db.in_combat`, and
    statefeed still exports `emit_swing`.
    """

    FICTION_WORDS = (
        "swing", "sword", "weapon", "attack", "combat", "melee",
        "hit", "strike", "blow", "kill", "dead",
    )

    def test_no_state_name_names_a_fiction(self):
        for state in ActivityState:
            lowered = state.name.lower()
            for word in self.FICTION_WORDS:
                self.assertNotIn(word, lowered, msg=state.name)

    def test_no_event_name_names_a_fiction(self):
        for event in ActivityEvent:
            lowered = event.name.lower()
            for word in self.FICTION_WORDS:
                self.assertNotIn(word, lowered, msg=event.name)


class TestHandlerState(EvenniaTest):
    """The machine as a handler carries it."""

    def setUp(self):
        super().setUp()
        self.handler = ensure_combat_handler(self.char1)

    def test_a_new_handler_starts_idle(self):
        self.assertEqual(self.handler.state, ActivityState.IDLE)

    def test_dispatching_a_legal_event_moves_the_state(self):
        moved = self.handler.dispatch(ActivityEvent.ACTION_QUEUED)

        self.assertTrue(moved)
        self.assertEqual(self.handler.state, ActivityState.ACTIVE)

    def test_dispatching_an_illegal_event_changes_nothing(self):
        moved = self.handler.dispatch(ActivityEvent.COOLDOWN_EXPIRED)

        self.assertFalse(moved)
        self.assertEqual(self.handler.state, ActivityState.IDLE)

    def test_the_last_transition_is_recorded(self):
        """So a diagnostic can report HOW a handler reached the state it is
        stuck in, not merely that it is stuck."""
        self.handler.dispatch(ActivityEvent.ACTION_QUEUED)

        previous, event, resulting = self.handler.ndb.last_transition

        self.assertEqual(previous, ActivityState.IDLE)
        self.assertEqual(event, ActivityEvent.ACTION_QUEUED)
        self.assertEqual(resulting, ActivityState.ACTIVE)

    def test_busy_tracks_the_state(self):
        self.assertFalse(self.handler.is_busy())

        self.handler.dispatch(ActivityEvent.ACTION_QUEUED)

        self.assertTrue(self.handler.is_busy())


class TestInCombatIsDerived(EvenniaTest):
    """The review's headline finding: combat state was five facts that nothing
    kept in agreement. It is one now, and the rest read it."""

    def test_an_entity_with_no_handler_is_not_in_combat(self):
        self.assertFalse(self.char1.in_combat)

    def test_gaining_a_handler_puts_an_entity_in_combat(self):
        ensure_combat_handler(self.char1)

        self.assertTrue(self.char1.in_combat)

    def test_a_defender_is_in_combat_without_having_acted(self):
        """`examine mutant raider` reporting otherwise was a bug once. A
        defender's handler sits in IDLE -- it has queued nothing -- and that
        is still in combat."""
        handler = ensure_combat_handler(self.char2)

        self.assertEqual(handler.state, ActivityState.IDLE)
        self.assertTrue(self.char2.in_combat)

    def test_ending_combat_ends_it_for_the_reader_too(self):
        handler = ensure_combat_handler(self.char1)

        handler.end_combat()

        self.assertFalse(self.char1.in_combat)

    def test_nothing_stores_the_flag_any_more(self):
        """The Attribute is gone. If this fails, something has started writing
        a second copy of the fact."""
        ensure_combat_handler(self.char1)

        self.assertIsNone(self.char1.attributes.get("in_combat"))
        self.assertTrue(self.char1.in_combat)

    def test_a_terminated_handler_reads_as_out_of_combat(self):
        handler = ensure_combat_handler(self.char1)

        handler.dispatch(ActivityEvent.ACTOR_INCAPACITATED)

        self.assertFalse(self.char1.in_combat)


class TestActionsReportEvents(EvenniaTest):
    """Actions say what happened; the table says what it means.

    The six exit checks ActionAttack.resolve carried are one predicate and one
    event now -- `target is None`, a missing is_alive, is_alive() returning
    False, and a deleted row after at_damage are all TARGET_INVALID.
    """

    def setUp(self):
        super().setUp()
        from systems.tick.engine import get_tick_engine

        self.engine = get_tick_engine()
        self.engine.ndb._handler_ids = {}
        self.handler = ensure_combat_handler(self.char1)

    def _attack(self, target):
        from systems.combat.combat import ActionAttack

        return ActionAttack(target.id)

    def test_a_missing_target_reports_target_invalid(self):
        from systems.combat.combat import ActionAttack

        action = ActionAttack(999999)

        event = action.resolve(self.handler)

        self.assertEqual(event, ActivityEvent.TARGET_INVALID)

    def test_a_dead_target_reports_target_invalid(self):
        self.char2.hp = 0
        action = self._attack(self.char2)

        event = action.resolve(self.handler)

        self.assertEqual(event, ActivityEvent.TARGET_INVALID)

    def test_a_deleted_target_reports_target_invalid(self):
        """The case an NPC deleting itself inside at_damage produces, and the
        reason resolve re-checks after the swing.

        A spawned NPC, not char2: Evennia refuses to delete an account-backed
        character (delete() returns False), so using one would assert this
        against an object that is still very much alive.
        """
        from typeclasses.npc_combat import spawn_mutant_raider

        raider = spawn_mutant_raider(self.room1)
        action = self._attack(raider)
        deleted = raider.delete()

        self.assertTrue(deleted, msg="the NPC must actually be gone")

        event = action.resolve(self.handler)

        self.assertEqual(event, ActivityEvent.TARGET_INVALID)

    def test_holding_is_a_resolved_action(self):
        from systems.combat.combat import ActionHold

        event = ActionHold().resolve(self.handler)

        self.assertEqual(event, ActivityEvent.ACTION_RESOLVED)

    def test_fleeing_reports_abandonment(self):
        from systems.combat.combat import ActionFlee

        event = ActionFlee().resolve(self.handler)

        self.assertEqual(event, ActivityEvent.ACTIVITY_ABANDONED)

    def test_an_action_never_tears_the_handler_down_itself(self):
        """Teardown moved to one place. An action returning a terminal event
        must leave the handler intact -- _settle is what dismantles it."""
        from systems.combat.combat import ActionFlee

        ActionFlee().resolve(self.handler)

        self.assertIsNotNone(self.handler.pk)

    def test_settling_a_terminal_event_ends_combat(self):
        self.handler.dispatch(ActivityEvent.ACTION_QUEUED)

        finished = self.handler._settle(ActivityEvent.ACTIVITY_ABANDONED)

        self.assertTrue(finished)
        self.assertFalse(self.char1.in_combat)

    def test_settling_a_non_terminal_event_carries_on(self):
        self.handler.dispatch(ActivityEvent.ACTION_QUEUED)

        finished = self.handler._settle(ActivityEvent.ACTION_RESOLVED)

        self.assertFalse(finished)
        self.assertIsNotNone(self.handler.pk)
