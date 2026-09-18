"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/17/2026
Description: Tests for the chasing_melee behaviour — the step toward an
             attacker out of reach, and the leash that stops the chase.

Why this matters more than it looks
-----------------------------------
The chase is the only thing that makes a projectile weapon's balance numbers
mean anything. Without it a player shoots a melee NPC from seven tiles and
takes no damage, ever, and every figure for a bow describes a fight that
cannot be lost.

These cases run on real grid tiles, because a chase is a question about
coordinates and exits. EvenniaTest's fixture rooms have neither.
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.ai.behaviors import chasing_melee
from systems.gameplay.ai.constants import (
    AI_BEHAVIOR_ATTR,
    AI_BEHAVIOR_CHASING_MELEE,
    LAST_ATTACKER_ID_ATTR,
    LEASH_DISTANCE_TILES,
    LEASH_ORIGIN_ATTR,
)
from systems.gameplay.ai.registry import get_behavior
from systems.gameplay.combat import reach
from systems.gameplay.combat.combat import ensure_combat_handler
from typeclasses.npc_combat import spawn_mutant_raider
from typeclasses.rooms import GridTile


# Public constant definitions

# The map these cases build their tiles on.
MAP_Z = "chasetest"


class _ChaseFixture(EvenniaTest):
    """A line of tiles, an NPC on the first, and a player somewhere along it.

    The tiles are linked with real exits in both directions, because
    step_toward walks exits and a tile with none is a dead end.
    """

    tile_count = 12

    def setUp(self):
        super().setUp()

        self.tiles = [self._tile(x) for x in range(self.tile_count)]
        self._link(self.tiles)

        self.npc = spawn_mutant_raider(self.tiles[0])
        setattr(self.npc.db, AI_BEHAVIOR_ATTR, AI_BEHAVIOR_CHASING_MELEE)

        self.handler = ensure_combat_handler(self.npc)

    def _tile(self, x):
        room, _err = GridTile.create(f"chase-{x}", xyz=(x, 0, MAP_Z))

        return room

    def _link(self, tiles):
        """One exit each way between every adjacent pair."""
        for index in range(len(tiles) - 1):
            create_object(
                "typeclasses.exits.Exit",
                key="east",
                location=tiles[index],
                destination=tiles[index + 1],
            )
            create_object(
                "typeclasses.exits.Exit",
                key="west",
                location=tiles[index + 1],
                destination=tiles[index],
            )

    def _stand_player_at(self, index):
        self.char1.location = self.tiles[index]
        setattr(self.npc.ndb, LAST_ATTACKER_ID_ATTR, self.char1.id)


class TestTheChaseStep(_ChaseFixture):
    """An NPC out of reach closes the distance, one tile per consultation."""

    def test_the_behaviour_is_registered_under_its_constant(self):
        """A key an NpcDef names and the registry does not know makes the NPC
        silently inert, which is why the key is a constant."""
        self.assertIs(get_behavior(AI_BEHAVIOR_CHASING_MELEE), chasing_melee)

    def test_an_attacker_in_the_same_room_is_attacked_not_chased(self):
        self._stand_player_at(0)

        action = chasing_melee(self.handler)

        self.assertEqual(action["kind"], "attack")
        self.assertIs(action["target"], self.char1)

    def test_an_attacker_out_of_reach_is_approached(self):
        self._stand_player_at(5)

        action = chasing_melee(self.handler)

        self.assertEqual(action["kind"], "approach")
        self.assertIs(action["target"], self.char1)

    def test_a_step_moves_the_npc_one_tile_closer(self):
        self._stand_player_at(5)
        before = reach.room_distance(self.npc.location, self.char1.location)

        reach.step_toward(self.npc, self.char1)

        after = reach.room_distance(self.npc.location, self.char1.location)

        self.assertEqual(after, before - 1)

    def test_repeated_steps_arrive(self):
        """The greedy chooser has to actually get there, not oscillate."""
        self._stand_player_at(4)

        for _step in range(4):
            reach.step_toward(self.npc, self.char1)

        self.assertIs(self.npc.location, self.char1.location)

    def test_a_step_with_nowhere_closer_to_go_reports_it(self):
        """A dead end is not an error. The fight ends through the grace."""
        self._stand_player_at(0)

        self.assertFalse(reach.step_toward(self.npc, self.char1))

    def test_no_attacker_means_no_action(self):
        self.assertIsNone(chasing_melee(self.handler))


class TestTheLeash(_ChaseFixture):
    """A chase has a limit, measured from where the chase began."""

    def test_the_origin_is_recorded_on_the_first_chase_step(self):
        self._stand_player_at(5)
        chasing_melee(self.handler)

        self.assertIs(getattr(self.npc.db, LEASH_ORIGIN_ATTR), self.tiles[0])

    def test_an_attacker_past_the_leash_is_not_chased(self):
        """Measured from the ORIGIN to the target, not from the NPC. Measured
        from the NPC it would reset with every step and never bite."""
        self._stand_player_at(0)
        chasing_melee(self.handler)  # records the origin

        self._stand_player_at(self.tile_count - 1)

        self.assertGreater(
            reach.room_distance(self.tiles[0], self.char1.location),
            LEASH_DISTANCE_TILES,
        )
        self.assertIsNone(chasing_melee(self.handler))

    def test_a_leashed_npc_walks_back_toward_its_origin(self):
        """One step per consultation, through the same greedy chooser the
        chase uses, so a returning NPC walks the map rather than teleporting
        across it."""
        self._stand_player_at(5)
        chasing_melee(self.handler)

        for _step in range(5):
            reach.step_toward(self.npc, self.char1)

        self._stand_player_at(self.tile_count - 1)
        before = reach.room_distance(self.npc.location, self.tiles[0])

        chasing_melee(self.handler)

        after = reach.room_distance(self.npc.location, self.tiles[0])

        self.assertEqual(after, before - 1)

    def test_attacking_releases_the_leash(self):
        """The NPC is where it needs to be, so the next chase measures from
        here rather than from wherever the last one started."""
        self._stand_player_at(5)
        chasing_melee(self.handler)

        self.char1.location = self.npc.location
        chasing_melee(self.handler)

        self.assertIsNone(getattr(self.npc.db, LEASH_ORIGIN_ATTR))

    def test_a_dead_attacker_sends_the_npc_home(self):
        self._stand_player_at(5)
        chasing_melee(self.handler)

        for _step in range(3):
            reach.step_toward(self.npc, self.char1)

        away = self.npc.location
        setattr(self.npc.ndb, LAST_ATTACKER_ID_ATTR, None)

        action = chasing_melee(self.handler)

        self.assertIsNone(action)
        self.assertIsNot(self.npc.location, away)


class TestTheStallSeam(_ChaseFixture):
    """The tick loop holds a stalled action rather than resolving it.

    That hold is what gives the behaviour a tick to act on. Without it the
    attack re-resolves forever, the controller is never consulted, and no
    NPC ever chases anything.
    """

    def test_an_attack_on_an_unreachable_target_reads_as_stalled(self):
        from systems.gameplay.combat.combat import ActionAttack

        self._stand_player_at(5)
        action = ActionAttack(self.char1.id)

        self.assertTrue(action.is_stalled(self.handler))

    def test_an_attack_on_a_reachable_target_does_not(self):
        from systems.gameplay.combat.combat import ActionAttack

        self._stand_player_at(0)
        action = ActionAttack(self.char1.id)

        self.assertFalse(action.is_stalled(self.handler))

    def test_a_gone_target_is_invalid_rather_than_stalled(self):
        """One is waited out and the other is not, so they cannot share an
        answer.

        A second raider stands in for the target here rather than char1: a
        puppeted Character does not delete cleanly, so the row would still
        resolve and the case would prove nothing.
        """
        from systems.gameplay.combat.combat import ActionAttack

        other = spawn_mutant_raider(self.tiles[5])
        action = ActionAttack(other.id)
        other.delete()

        self.assertFalse(action.is_stalled(self.handler))

    def test_a_stalled_action_charges_no_cooldown(self):
        """A combatant whose target walked away has not acted. Charging it a
        weapon cycle would make a chase cost one cycle per tile."""
        from systems.gameplay.combat.combat import ActionAttack

        self._stand_player_at(5)
        self.handler.init_runtime_state()
        self.handler.ndb.pending_action = ActionAttack(self.char1.id)
        self.handler.ndb.cooldown_ticks = 0

        self.handler.tick()

        self.assertEqual(self.handler.ndb.cooldown_ticks, 0)
