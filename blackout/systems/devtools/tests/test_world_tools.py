"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Tests for the three effects that act on the world around a
             character rather than on the character's numbers -- spawning
             hostiles, teleporting to a person, and destroying belongings.

             The load-bearing test in this module is the one asserting that
             clear_inventory refuses to delete a staff item. A moderator
             emptying their OWN bag would otherwise destroy the egg they were
             holding to do it with, and the only way back is a `py` call.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.devtools
"""

from evennia.utils.test_resources import EvenniaTest

from systems.devtools import actions as dev_actions
from systems.devtools import constants as dev_constants
from world.item_database import ITEM_DB
from world.npc_database import NPC_DB


_EGG_KEY = "moderator_egg"



def _any_equippable_key() -> str:
    """Name any ItemDef that occupies an equipment slot."""
    for key in sorted(ITEM_DB.keys()):
        item_def = ITEM_DB[key]

        if item_def.use_slot is not None:
            return key

    return ""


def _any_plain_key() -> str:
    """Name any ItemDef that is not a staff item."""
    for key in sorted(ITEM_DB.keys()):
        if key != _EGG_KEY:
            return key

    return ""



class NpcSpawnTests(EvenniaTest):
    """Hostiles land in the TARGET's room, not the moderator's."""

    def test_an_unknown_npc_key_is_refused(self):
        succeeded, message = dev_actions.spawn_npc(
            self.char2, self.char1, "no_such_npc", 1
        )

        self.assertFalse(succeeded)
        self.assertIn("no_such_npc", message)

    def test_spawning_places_the_npc_in_the_targets_room(self):
        """
        The moderator's room and the target's are the same when testing on
        yourself and different when reproducing a player's report. The second
        is the case worth getting right.
        """
        self.char1.move_to(self.room2, quiet=True)
        npc_key = sorted(NPC_DB.keys())[0]
        before = len(self.room2.contents)
        succeeded, _message = dev_actions.spawn_npc(
            self.char2, self.char1, npc_key, 1
        )

        self.assertTrue(succeeded)
        self.assertEqual(len(self.room2.contents), before + 1)

    def test_the_spawned_npc_carries_its_combat_block(self):
        """
        Routed through NpcDef.create, so a spawned raider is the same object
        the map builder would have placed. A hand-rolled create_object would
        make something that fights but never respawns and answers to no
        behaviour.
        """
        npc_key = sorted(NPC_DB.keys())[0]
        dev_actions.spawn_npc(self.char2, self.char1, npc_key, 1)
        spawned = [obj for obj in self.char1.location.contents
                   if getattr(obj.db, "npc_key", None) == npc_key]

        self.assertEqual(len(spawned), 1)
        self.assertGreater(spawned[0].max_hp, 0)
        self.assertTrue(spawned[0].is_alive())

    def test_the_spawn_room_is_stamped_where_it_landed(self):
        """Not where its map placement would have put it: a spawned hostile
        with a respawn timer must come back HERE."""
        npc_key = sorted(NPC_DB.keys())[0]
        dev_actions.spawn_npc(self.char2, self.char1, npc_key, 1)
        spawned = [obj for obj in self.char1.location.contents
                   if getattr(obj.db, "npc_key", None) == npc_key]

        self.assertIs(spawned[0].db.spawn_room, self.char1.location)

    def test_several_can_be_spawned_at_once(self):
        npc_key = sorted(NPC_DB.keys())[0]
        dev_actions.spawn_npc(self.char2, self.char1, npc_key, 3)
        spawned = [obj for obj in self.char1.location.contents
                   if getattr(obj.db, "npc_key", None) == npc_key]

        self.assertEqual(len(spawned), 3)

    def test_the_count_is_clamped_to_the_npc_ceiling(self):
        """
        Two orders of magnitude below the item ceiling, because every hostile
        is a live combatant joining the tick -- the cost of a fat-fingered
        zero is a room nobody in it can survive.
        """
        npc_key = sorted(NPC_DB.keys())[0]
        over = dev_constants.MAX_NPC_SPAWN + 50
        dev_actions.spawn_npc(self.char2, self.char1, npc_key, over)
        spawned = [obj for obj in self.char1.location.contents
                   if getattr(obj.db, "npc_key", None) == npc_key]

        self.assertEqual(len(spawned), dev_constants.MAX_NPC_SPAWN)

    def test_a_target_with_no_location_is_refused(self):
        self.char1.location = None
        succeeded, message = dev_actions.spawn_npc(
            self.char2, self.char1, sorted(NPC_DB.keys())[0], 1
        )

        self.assertFalse(succeeded)
        self.assertIn(self.char1.key, message)

    def test_every_registered_npc_is_offered(self):
        offered = dev_actions.npc_keys()

        self.assertEqual(sorted(offered), sorted(NPC_DB.keys()))



class TeleportToCharacterTests(EvenniaTest):
    """One function, both directions, by swapping the arguments."""

    def test_the_target_lands_in_the_other_characters_room(self):
        self.char2.move_to(self.room2, quiet=True)
        succeeded, _message = dev_actions.teleport_to_character(
            self.char1, self.char1, self.char2
        )

        self.assertTrue(succeeded)
        self.assertIs(self.char1.location, self.room2)

    def test_bringing_someone_to_the_moderator_is_the_same_call_swapped(self):
        self.char2.move_to(self.room2, quiet=True)
        succeeded, _message = dev_actions.teleport_to_character(
            self.char1, self.char2, self.char1
        )

        self.assertTrue(succeeded)
        self.assertIs(self.char2.location, self.room1)

    def test_a_destination_character_with_no_location_is_refused(self):
        """Every logged-out player is one, and "teleport to <name>" typed
        from memory is exactly when that happens."""
        self.char2.location = None
        succeeded, message = dev_actions.teleport_to_character(
            self.char1, self.char1, self.char2
        )

        self.assertFalse(succeeded)
        self.assertIn(self.char2.key, message)

    def test_teleporting_into_the_room_already_occupied_is_a_no_op(self):
        """
        A no-op move still fires at_object_receive and would announce an
        arrival about someone who never left.
        """
        start_location = self.char1.location
        succeeded, message = dev_actions.teleport_to_character(
            self.char1, self.char1, self.char2
        )

        self.assertFalse(succeeded)
        self.assertIs(self.char1.location, start_location)
        self.assertIn("already", message.lower())



class ClearInventoryTests(EvenniaTest):
    """The only irreversible thing on the tool."""

    def test_carried_items_are_destroyed(self):
        item_key = _any_plain_key()
        ITEM_DB[item_key].create(location=self.char1, home=self.char1)
        succeeded, _message = dev_actions.clear_inventory(self.char2, self.char1)

        self.assertTrue(succeeded)
        self.assertEqual(self.char1.inventory.count_used(), 0)

    def test_equipped_items_are_destroyed_too(self):
        """`purge` already treats carried and equipped as one surface, and a
        moderator who found the weapon still wielded would just run it twice."""
        item_key = _any_equippable_key()
        item = ITEM_DB[item_key].create(location=self.char1, home=self.char1)
        self.char1.equipment.equip(item)
        succeeded, _message = dev_actions.clear_inventory(self.char2, self.char1)

        self.assertTrue(succeeded)
        self.assertEqual(self.char1.equipment.count_equipped(), 0)

    def test_an_equipped_item_leaves_no_slot_naming_a_destroyed_row(self):
        """
        The slot is cleared BEFORE the object is deleted. Deleting out from
        under a live slot would leave the handler naming a destroyed row and
        the equipment pane drawing it.
        """
        item_key = _any_equippable_key()
        item = ITEM_DB[item_key].create(location=self.char1, home=self.char1)
        self.char1.equipment.equip(item)
        dev_actions.clear_inventory(self.char2, self.char1)
        equipped = self.char1.equipment.all()

        self.assertEqual(equipped, [])

    def test_the_moderator_egg_survives_being_cleared(self):
        """
        THE test in this module. A moderator emptying their own bag must not
        destroy the egg they are holding to do it with -- the only way back
        from that is a `py` call.
        """
        egg = ITEM_DB[_EGG_KEY].create(location=self.char1, home=self.char1)
        ITEM_DB[_any_plain_key()].create(location=self.char1, home=self.char1)
        succeeded, message = dev_actions.clear_inventory(self.char1, self.char1)

        self.assertTrue(succeeded)
        self.assertIsNotNone(egg.pk)
        self.assertIn(egg, self.char1.contents)
        self.assertIn("staff item", message.lower())

    def test_a_kept_staff_item_is_reported_not_silently_passed_over(self):
        """A moderator who expected an empty bag and got one item needs to be
        told which rule kept it."""
        ITEM_DB[_EGG_KEY].create(location=self.char1, home=self.char1)
        ITEM_DB[_any_plain_key()].create(location=self.char1, home=self.char1)
        _succeeded, message = dev_actions.clear_inventory(self.char1, self.char1)

        self.assertIn("1", message)

    def test_an_egg_only_bag_reports_nothing_to_clear(self):
        """Nothing deletable is not the same as a successful clear."""
        ITEM_DB[_EGG_KEY].create(location=self.char1, home=self.char1)
        succeeded, message = dev_actions.clear_inventory(self.char1, self.char1)

        self.assertFalse(succeeded)
        self.assertIn("nothing", message.lower())

    def test_an_empty_bag_reports_nothing_to_clear(self):
        succeeded, message = dev_actions.clear_inventory(self.char2, self.char1)

        self.assertFalse(succeeded)
        self.assertIn("nothing", message.lower())

    def test_the_grid_is_left_consistent_afterwards(self):
        """A slot map naming deleted rows reads back as occupied slots the
        character cannot see or use."""
        item_key = _any_plain_key()
        made = 0

        while made < 3:
            ITEM_DB[item_key].create(location=self.char1, home=self.char1)
            made += 1

        dev_actions.clear_inventory(self.char2, self.char1)
        self.char1.inventory.sync()

        self.assertEqual(self.char1.inventory.all_items(), [])
        self.assertEqual(self.char1.inventory.count_used(), 0)

    def test_clearing_does_not_touch_another_character(self):
        item_key = _any_plain_key()
        ITEM_DB[item_key].create(location=self.char2, home=self.char2)
        ITEM_DB[item_key].create(location=self.char1, home=self.char1)
        dev_actions.clear_inventory(self.char2, self.char1)

        self.assertEqual(self.char2.inventory.count_used(), 1)
