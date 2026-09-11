"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/10/2026
Description: Regression cover for the pocketable-NPC bug.

             A player could `get mutant raider` and walk off with a live
             enemy. It never died in its room, so HostileNPC.respawn never
             ran, so nothing was ever queued on BlackoutRespawnManager and the
             tile stayed empty permanently. The respawn queue itself was
             healthy -- these tests assert both halves of that, so a future
             change cannot "fix" the queue in response to a symptom that was
             never the queue's.
"""

from evennia.utils import create
from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.spawning.respawn import get_respawn_manager, npc_present
from world.npc_database import NPC_DB


# Far enough past any deadline that a sweep fires every queued entry without
# the test having to know the NpcDef's respawn_seconds.
_LONG_AFTER = 10 ** 12



class NpcPocketingTest(EvenniaTest):
    """
    Purpose: Assert that no NPC can be picked up, however old the instance.
    """

    def _hostile(self):
        return NPC_DB["mutant_raider"].create(location=self.room1)


    def test_a_hostile_npc_refuses_to_be_picked_up(self):
        npc = self._hostile()

        allowed = npc.at_pre_get(self.char1)

        self.assertFalse(allowed)


    def test_a_talkative_npc_refuses_to_be_picked_up(self):
        npc = create.create_object(
            "typeclasses.npcs.TalkativeNPC",
            key="lone android",
            location=self.room1,
        )

        allowed = npc.at_pre_get(self.char1)

        self.assertFalse(allowed)


    def test_the_refusal_names_the_npc(self):
        npc = self._hostile()
        seen = []
        self.char1.msg = lambda text=None, **kwargs: seen.append(text)

        npc.at_pre_get(self.char1)

        self.assertIn(npc.key, seen[0][0])


    def test_the_refusal_reaches_an_npc_created_before_the_rule_existed(self):
        """The whole reason this is a hook and not a get:false() lock.

        at_object_creation runs once, so a lock written there would leave
        every NPC already on the grid pocketable. Stripping the locks off a
        live instance stands in for one created months ago.
        """
        npc = self._hostile()
        npc.locks.clear()

        allowed = npc.at_pre_get(self.char1)

        self.assertFalse(allowed)


    def test_a_gathering_node_is_still_refused_by_its_lock(self):
        """The lock route must keep working for the things that use it."""
        node = create.create_object(
            "typeclasses.gathering_nodes.RustyPole",
            key="rusty pole",
            location=self.room1,
        )

        self.assertFalse(node.access(self.char1, "get"))



class PocketedNpcRespawnTest(EvenniaTest):
    """
    Purpose: Pin the actual failure the pocketing bug produced, and the
             queue behaviour that was wrongly suspected of causing it.
    """

    def _hostile(self):
        return NPC_DB["mutant_raider"].create(location=self.room1)


    def test_carrying_an_npc_away_queues_no_respawn(self):
        """The bug, stated directly: a live NPC in a bag is a dead tile.

        Nothing here is a queue failure -- there is no entry to sweep,
        because the NPC never died.
        """
        npc = self._hostile()
        npc.move_to(self.char1, quiet=True)

        manager = get_respawn_manager()

        self.assertEqual(manager.db.respawn_queue or [], [])
        self.assertFalse(npc_present("mutant_raider", self.room1))


    def test_an_ordinary_kill_respawns(self):
        npc = self._hostile()
        npc.at_death(killer=self.char1)

        get_respawn_manager().sweep(now=_LONG_AFTER)

        self.assertTrue(npc_present("mutant_raider", self.room1))


    def test_a_kill_after_a_pickup_and_drop_respawns(self):
        npc = self._hostile()
        npc.move_to(self.char1, quiet=True)
        npc.move_to(self.room1, quiet=True)
        npc.at_death(killer=self.char1)

        get_respawn_manager().sweep(now=_LONG_AFTER)

        self.assertTrue(npc_present("mutant_raider", self.room1))


    def test_a_kill_while_carried_respawns_in_the_spawn_room(self):
        """db.spawn_room, not db.location, is what respawn() reads.

        A carried NPC dies inside a Character, so a respawn keyed on its
        location would try to spawn the replacement into the player's bag.
        """
        npc = self._hostile()
        npc.move_to(self.char1, quiet=True)
        npc.at_death(killer=self.char1)

        get_respawn_manager().sweep(now=_LONG_AFTER)

        self.assertTrue(npc_present("mutant_raider", self.room1))
