"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/10/2026
Description: The feed's remove-delta must fire when an entity is DELETED, not
             only when one walks out of a room.

Why this file exists
--------------------
The remove half of the entity delta was wired to Room.at_object_leave, which
Evennia fires from move_to. `delete()` does not move anything -- it assigns
`self.location = None` directly (evennia/objects/objects.py,
DefaultObject.delete) -- so nothing announced an object that left the world by
being destroyed.

That is the two commonest events in the game. A killed NPC is deleted by
HostileNPC.respawn; a butchered corpse is deleted by
GatheringSkill.consume_node. Both stayed drawn on every client that had been
told about them, accumulated over a session, and stayed CLICKABLE -- so a click
aimed at the live raider on a tile could land on the previous raider's ghost,
or on last kill's uncollected loot, and send that entity's verb. The verbs were
all correct; the client was answering about entities the server had forgotten.

These tests assert the announcement, not the redraw. What a client does with a
remove-delta is the client's business; what the server owes it is the delta.
"""

from unittest import mock

from evennia.utils import create
from evennia.utils.test_resources import EvenniaTest

from world.item_database import ITEM_DB
from world.npc_database import NPC_DB


_CORPSE_KEY = "mutant_raider_corpse"



class EntityRemovalOnDeleteTest(EvenniaTest):
    """One assertion, applied to everything that dies rather than walks."""

    def _removed_ids(self, mocked):
        return [call.args[1] for call in mocked.emit_entity_left.call_args_list]


    def test_deleting_a_plain_object_announces_it(self):
        obj = create.create_object(
            "typeclasses.objects.Object", key="crate", location=self.room1)
        obj_id = obj.id

        with mock.patch("systems.interface.statefeed.events") as mocked:
            obj.delete()

        self.assertIn(obj_id, self._removed_ids(mocked))


    def test_a_killed_npc_announces_it(self):
        """HostileNPC.respawn deletes the row. Nothing else would say so."""
        npc = NPC_DB["mutant_raider"].create(location=self.room1)
        npc_id = npc.id

        with mock.patch("systems.interface.statefeed.events") as mocked:
            npc.at_death(killer=self.char1)

        self.assertIn(npc_id, self._removed_ids(mocked))


    def test_a_consumed_corpse_announces_it(self):
        """The playtest report: the body stayed on screen after butchering."""
        corpse = ITEM_DB[_CORPSE_KEY].create(location=self.room1)
        corpse_id = corpse.id

        with mock.patch("systems.interface.statefeed.events") as mocked:
            corpse.delete()

        self.assertIn(corpse_id, self._removed_ids(mocked))


    def test_the_announcement_names_the_room_it_was_standing_in(self):
        """Read BEFORE deletion, which is the whole reason this is a hook on
        at_object_delete rather than anything that runs after delete()."""
        corpse = ITEM_DB[_CORPSE_KEY].create(location=self.room1)

        with mock.patch("systems.interface.statefeed.events") as mocked:
            corpse.delete()

        room = mocked.emit_entity_left.call_args_list[0].args[0]
        self.assertIs(room, self.room1)


    def test_an_exit_is_not_announced(self):
        """The feed never reported exits, so removing one would name an id no
        client was ever given."""
        with mock.patch("systems.interface.statefeed.events") as mocked:
            self.exit.delete()

        self.assertEqual(self._removed_ids(mocked), [])


    def test_a_room_is_not_announced(self):
        """A room has no location, so nobody could have been told about it as
        an entity in the first place."""
        room = create.create_object("typeclasses.rooms.Room", key="void")

        with mock.patch("systems.interface.statefeed.events") as mocked:
            room.delete()

        self.assertEqual(self._removed_ids(mocked), [])


    def test_a_broken_feed_cannot_veto_a_deletion(self):
        """A skipped removal is a ghost. A raised one would leave a 0-hp NPC
        standing and hang the fight that killed it."""
        corpse = ITEM_DB[_CORPSE_KEY].create(location=self.room1)

        with mock.patch("systems.interface.statefeed.events") as mocked:
            mocked.emit_entity_left.side_effect = RuntimeError("feed is down")
            deleted = corpse.delete()

        self.assertTrue(deleted)
        self.assertIsNone(corpse.pk)


    def test_deletion_still_happens(self):
        """The hook returns the parent's answer and never invents its own."""
        corpse = ITEM_DB[_CORPSE_KEY].create(location=self.room1)

        self.assertTrue(corpse.delete())
        self.assertIsNone(corpse.pk)


class RespawnArrivalTest(EvenniaTest):
    """The mirror of the removal bug: a respawn nobody was told about.

    NpcDef.create goes through create_object(location=...), and Evennia fires
    at_object_receive only for move_to -- so Room.at_object_receive, where
    emit_entity_arrived hangs, never ran for a respawn. The raider came back
    invisible to anyone standing on the tile and stayed invisible until they
    walked far enough away to be re-sent a whole contents list.
    """

    def test_a_respawn_announces_the_arrival(self):
        from systems.gameplay.spawning.respawn import get_respawn_manager

        manager = get_respawn_manager()
        manager.schedule("mutant_raider", self.room1, 0)

        with mock.patch("systems.interface.statefeed.events") as mocked:
            spawned = manager.sweep(now=10 ** 12)

        self.assertEqual(spawned, 1)
        self.assertTrue(mocked.emit_entity_arrived.called)

        room, npc = mocked.emit_entity_arrived.call_args.args
        self.assertIs(room, self.room1)
        self.assertEqual(npc.attributes.get("npc_key"), "mutant_raider")


    def test_a_broken_feed_does_not_lose_the_npc(self):
        """A missed announcement costs one invisible NPC until the observer
        moves. A raise would drop the queue entry and cost the NPC entirely."""
        from systems.gameplay.spawning.respawn import (
            get_respawn_manager, npc_present,
        )

        manager = get_respawn_manager()
        manager.schedule("mutant_raider", self.room1, 0)

        with mock.patch("systems.interface.statefeed.events") as mocked:
            mocked.emit_entity_arrived.side_effect = RuntimeError("feed down")
            manager.sweep(now=10 ** 12)

        self.assertTrue(npc_present("mutant_raider", self.room1))
