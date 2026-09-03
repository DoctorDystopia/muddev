"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: Tests for the NPC behaviour registry, the aggressive_melee
             behaviour, and the controller seam on the combat handler.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.ai

Before this package existed, queue_action had exactly four callers, all of them
player commands, so an NPC's handler ticked forever and returned at
`if action is None`. These tests pin the path that closes that gap.
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.ai.behaviors import aggressive_melee
from systems.ai.constants import (
    AI_BEHAVIOR_AGGRESSIVE_MELEE,
    AI_BEHAVIOR_ATTR,
    LAST_ATTACKER_ID_ATTR,
)
from systems.ai.registry import (
    BEHAVIOR_REGISTRY,
    get_behavior,
    load_all_behaviors,
)
from systems.combat.combat import ensure_combat_handler, get_handler_for
from systems.combat.rules.context import ActionResult
from systems.tick.engine import bootstrap_tick, get_tick_engine
from typeclasses.npc_combat import spawn_mutant_raider


class TestBehaviorRegistry(EvenniaTestCase):
    """The decorator registry, modelled on SPAWNER_REGISTRY."""

    def test_the_melee_behavior_is_registered_under_its_constant(self):
        load_all_behaviors()

        self.assertIn(AI_BEHAVIOR_AGGRESSIVE_MELEE, BEHAVIOR_REGISTRY)

    def test_get_behavior_resolves_the_callable(self):
        self.assertIs(get_behavior(AI_BEHAVIOR_AGGRESSIVE_MELEE), aggressive_melee)

    def test_an_unknown_key_resolves_to_none_rather_than_raising(self):
        """The caller is a combat tick, where a KeyError would be swallowed."""
        self.assertIsNone(get_behavior("no_such_behavior"))

    def test_an_empty_key_resolves_to_none(self):
        """A player Character names no behaviour; that is not an error."""
        self.assertIsNone(get_behavior(None))
        self.assertIsNone(get_behavior(""))


class TestLastAttackerRecord(EvenniaTest):
    """at_damage's record — the seam a threat table drops into later."""

    def test_taking_damage_records_the_attacker(self):
        npc = spawn_mutant_raider(self.room1)

        npc.at_damage(1, attacker=self.char1)

        self.assertEqual(
            getattr(npc.ndb, LAST_ATTACKER_ID_ATTR), self.char1.id
        )

    def test_self_damage_is_not_recorded(self):
        """A backfiring gadget must not make its wielder its own target.

        at_death normalises a self-kill to no killer for the same reason.
        """
        npc = spawn_mutant_raider(self.room1)

        npc.at_damage(1, attacker=npc)

        self.assertIsNone(getattr(npc.ndb, LAST_ATTACKER_ID_ATTR, None))

    def test_unattributed_damage_does_not_clear_an_existing_record(self):
        """Poison or fall damage mid-fight must not make a monster forget."""
        npc = spawn_mutant_raider(self.room1)
        npc.at_damage(1, attacker=self.char1)

        npc.at_damage(1, attacker=None)

        self.assertEqual(
            getattr(npc.ndb, LAST_ATTACKER_ID_ATTR), self.char1.id
        )


class TestAggressiveMeleeBehavior(EvenniaTest):
    """The behaviour in isolation — called directly, no tick engine."""

    def _handler_for_a_bitten_npc(self):
        """An NPC that has been hit once by char1."""
        npc = spawn_mutant_raider(self.room1)
        npc.at_damage(1, attacker=self.char1)
        handler = ensure_combat_handler(npc)

        return handler, npc

    def test_it_swings_back_at_the_last_attacker(self):
        handler, _npc = self._handler_for_a_bitten_npc()

        action = aggressive_melee(handler)

        self.assertEqual(action, {"kind": "attack", "target": self.char1})

    def test_an_unhit_npc_does_nothing(self):
        """Purely reactive. Unprovoked aggro is a separate trigger."""
        npc = spawn_mutant_raider(self.room1)
        handler = ensure_combat_handler(npc)

        self.assertIsNone(aggressive_melee(handler))

    def test_it_does_not_chase_out_of_the_room(self):
        handler, _npc = self._handler_for_a_bitten_npc()
        self.char1.location = self.room2

        self.assertIsNone(aggressive_melee(handler))

    def test_it_does_not_swing_at_a_corpse(self):
        handler, _npc = self._handler_for_a_bitten_npc()
        self.char1.db.hp = 0

        self.assertIsNone(aggressive_melee(handler))

    def test_a_deleted_attacker_resolves_to_no_action(self):
        """The id is stored precisely because the row can vanish.

        The attacker here is a second NPC rather than char1: a Blackout
        Character cannot currently be deleted at all (its at_object_delete
        override returns None, which Evennia reads as a veto), so deleting
        char1 would leave the row standing and the test would prove nothing
        about this code path.
        """
        npc = spawn_mutant_raider(self.room1)
        attacker = spawn_mutant_raider(self.room2)
        npc.at_damage(1, attacker=attacker)
        handler = ensure_combat_handler(npc)

        attacker.delete()

        self.assertIsNone(aggressive_melee(handler))


class TestControllerSeam(EvenniaTest):
    """BlackoutCombatHandler._consult_controller."""

    def test_a_player_is_never_handed_an_action(self):
        """The player 'controller' is 'wait for a command', expressed as the
        absence of the attribute rather than as a branch."""
        handler = ensure_combat_handler(self.char1)
        handler.init_runtime_state()

        handler._consult_controller()

        self.assertIsNone(handler.ndb.pending_action)

    def test_an_unknown_behavior_key_is_logged_and_survives(self):
        npc = spawn_mutant_raider(self.room1)
        setattr(npc.db, AI_BEHAVIOR_ATTR, "no_such_behavior")
        handler = ensure_combat_handler(npc)
        handler.init_runtime_state()

        with mock.patch("systems.combat.combat.logger.log_err") as mocked_log:
            handler._consult_controller()

        self.assertTrue(mocked_log.called)

    def test_a_raising_behavior_is_caught_and_logged(self):
        """The gotcha this whole seam is shaped around.

        The tick engine isolates a handler's exceptions, so an uncaught error
        in a behaviour would present as an NPC that silently stopped fighting
        with nothing in the log saying why.
        """
        npc = spawn_mutant_raider(self.room1)
        handler = ensure_combat_handler(npc)
        handler.init_runtime_state()

        def _explode(_handler):
            raise RuntimeError("behaviour blew up")

        with mock.patch(
            "systems.combat.combat.get_behavior", return_value=_explode
        ):
            with mock.patch("systems.combat.combat.logger.log_err") as mocked_log:
                handler._consult_controller()  # must not raise

        self.assertTrue(mocked_log.called)


class TestRetaliationOverTicks(EvenniaTest):
    """The end-to-end behaviour: a hostile that fights back, and keeps at it."""

    def setUp(self):
        super().setUp()
        self.engine = bootstrap_tick()

        # Both sides need to outlast the exchange: the point of these tests is
        # the CADENCE, and a combatant dying partway through would end the
        # fight and hide a stalled AI behind a legitimate teardown.
        self.npc = spawn_mutant_raider(self.room1)
        self.npc.db.max_hp = 500
        self.npc.hp = 500

        self.char1.db.max_hp = 500
        self.char1.hp = 500

    def _run_ticks(self, count):
        """Drive `count` whole engine ticks, counting NPC hits on char1.

        Whole engine ticks, not handler.tick(): queue_action routes through the
        engine's INPUT phase, so a test calling handler.tick() directly would
        never drain the action the controller just queued and would conclude
        the AI does nothing.
        """
        landed = []
        real_at_damage = type(self.char1).at_damage

        def _counting_at_damage(inner_self, amount, attacker=None, **kwargs):
            if inner_self is self.char1 and attacker is self.npc:
                landed.append(amount)

            return real_at_damage(inner_self, amount, attacker=attacker, **kwargs)

        always_hits = ActionResult(hit=True, damage=1, hit_prob=1.0)

        with mock.patch(
            "systems.combat.combat.resolve_action", return_value=always_hits
        ):
            with mock.patch.object(
                type(self.char1), "at_damage", _counting_at_damage
            ):
                for _ in range(count):
                    self.engine._tick()

        return landed

    def _player_attacks_the_npc(self):
        """What CmdAttack does: a handler for each side, an action for one."""
        ensure_combat_handler(self.npc)
        handler = ensure_combat_handler(self.char1)
        handler.queue_action({"kind": "attack", "target": self.npc})

    def test_an_attacked_raider_hits_back(self):
        self._player_attacks_the_npc()

        landed = self._run_ticks(8)

        self.assertTrue(landed, "the raider never retaliated")

    def test_it_keeps_hitting_back_at_its_attack_speed(self):
        """Not just one swing.

        A retaliation that fired once and stopped would pass the test above.
        The raider's attack_speed is 4 ticks, so ~20 ticks is room for about
        five swings; requiring at least three proves the cadence sustains
        rather than that a single opening blow landed.
        """
        self._player_attacks_the_npc()

        landed = self._run_ticks(20)

        self.assertGreaterEqual(
            len(landed), 3, f"retaliation stalled after {len(landed)} swing(s)"
        )

    def test_it_stops_when_the_player_leaves_the_room(self):
        self._player_attacks_the_npc()
        self._run_ticks(8)

        self.char1.move_to(self.room2, quiet=True, move_type="teleport")
        after_leaving = self._run_ticks(8)

        self.assertEqual(after_leaving, [])
        self.assertIsNone(get_handler_for(self.npc))

    def test_two_players_on_one_npc_are_not_enemies_of_each_other(self):
        """get_sides regression.

        Treating every handler-bearing entity in the room as an enemy made two
        players attacking the same monster enemies of one another. Retaliation
        is the first thing that puts a third handler in the room routinely, so
        this is where that would resurface.
        """
        self.char2.location = self.room1
        self.char2.db.max_hp = 500
        self.char2.hp = 500

        self._player_attacks_the_npc()
        second = ensure_combat_handler(self.char2)
        second.queue_action({"kind": "attack", "target": self.npc})

        self._run_ticks(8)

        handler = get_handler_for(self.char1)
        self.assertIsNotNone(handler, "char1 should still be fighting")

        _allies, enemies = handler.get_sides()

        self.assertIn(self.npc, enemies)
        self.assertNotIn(self.char2, enemies)
