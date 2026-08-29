"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Regression tests for what a room takes with it when it dies.

Evennia's `clear_contents` does not delete a room's contents -- it moves them
to their home, rewriting that home to settings.DEFAULT_HOME when the home IS
the room being deleted. Nothing the spawners create passes `home=`, so every
map rebuild exiled the whole grid's furniture to Limbo instead of destroying
it: 623 objects standing there with 197 more nested inside them, against 23
real ones on the live grid, by 08/28/2026.

The tests below are written against the RULE rather than against that count:
a player character survives its room, everything else does not, and a
container is emptied before it is deleted.
"""

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.spawning import teardown
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.items import BaseItem
from typeclasses.npcs import TalkativeNPC
from typeclasses.rooms import GridTile

TEST_ZCOORD = "teardown_testmap"


class TestTeardownPredicates(EvenniaTest):
    """Who is spared when a room is destroyed."""

    character_typeclass = BlackoutCharacter

    def test_a_player_character_is_spared(self):
        """A rebuild must never destroy a player."""
        spared = teardown.survives_teardown(self.char1)

        self.assertTrue(spared)

    def test_an_npc_is_not_spared(self):
        """NPCs are world furniture, and go with the tile they stand on."""
        npc = create_object(TalkativeNPC, key="test wanderer", location=self.room1)

        spared = teardown.survives_teardown(npc)

        self.assertFalse(spared)

    def test_an_unpuppeted_character_is_still_spared(self):
        """`has_account` reports live puppeting, so it cannot be the test.

        A character standing in a room while its player is logged out has no
        session. Keying on that would read it as furniture and destroy it.
        """
        self.char1.sessions.clear()

        spared = teardown.survives_teardown(self.char1)

        self.assertTrue(spared)

    def test_an_exit_is_left_to_clear_exits(self):
        """Exits are not this module's to destroy.

        `clear_exits` takes them moments later and is the only caller that can
        also find the exits pointing back AT the room.
        """
        spared = teardown.survives_teardown(self.exit)

        self.assertTrue(spared)

    def test_the_exemption_tag_spares_an_ordinary_object(self):
        """The escape hatch for a prop that must survive a rebuild."""
        prop = create_object(BaseItem, key="landmark", location=self.room1)
        prop.tags.add(
            teardown.TEARDOWN_EXEMPT_TAG,
            category=teardown.TEARDOWN_EXEMPT_TAG_CATEGORY,
        )

        spared = teardown.survives_teardown(prop)

        self.assertTrue(spared)


class TestDemolishIsDepthFirst(EvenniaTest):
    """A container must be emptied before it is deleted, never after."""

    character_typeclass = BlackoutCharacter

    def test_contents_of_a_demolished_npc_are_destroyed_not_rehomed(self):
        """This is how 197 of the 820 stranded objects got stranded.

        `obj.delete()` runs `clear_contents` on the object's OWN contents, so
        deleting a shopkeep evicts its stock to Limbo rather than destroying
        it. A sweep that deleted containers first would remove 623 rows and
        create 197 new orphans in the same pass.
        """
        npc = create_object(TalkativeNPC, key="test trader", location=self.room1)
        stock = create_object(BaseItem, key="test trinket", location=npc)
        stock_id = stock.id

        destroyed = teardown.demolish(npc)

        self.assertEqual(destroyed, 2)
        self.assertIsNone(npc.pk)
        self.assertFalse(BaseItem.objects.filter(id=stock_id).exists())

    def test_a_character_inside_a_container_is_still_spared(self):
        """The reprieve applies at every level, not only the top one."""
        container = create_object(TalkativeNPC, key="test hauler", location=self.room1)
        self.char1.location = container

        teardown.demolish(container)

        self.assertIsNotNone(self.char1.pk)


class TestGridTileTeardown(EvenniaTest):
    """The whole chain, through the hook that map rebuilds actually run."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.tile, errors = GridTile.create("test tile", xyz=(0, 0, TEST_ZCOORD))
        self.assertFalse(errors, f"could not build the test tile: {errors}")

    def test_deleting_a_tile_destroys_its_furniture(self):
        """The bug, stated as the rule it broke."""
        npc = create_object(TalkativeNPC, key="test local", location=self.tile)
        node = create_object(BaseItem, key="test node", location=self.tile)
        npc_id = npc.id
        node_id = node.id

        self.tile.delete()

        self.assertFalse(TalkativeNPC.objects.filter(id=npc_id).exists())
        self.assertFalse(BaseItem.objects.filter(id=node_id).exists())

    def test_nothing_is_exiled_to_default_home(self):
        """The failure mode was relocation, not survival -- assert on that.

        A test that only checked the object was gone from the tile would have
        passed against the broken behaviour, which moved it to Limbo.
        """
        from django.conf import settings

        npc = create_object(TalkativeNPC, key="test local", location=self.tile)
        home = npc.home

        self.tile.delete()

        self.assertIsNotNone(home, "the fixture NPC should have had a home to be exiled to")
        self.assertEqual(f"#{home.id}", settings.DEFAULT_HOME)
        self.assertNotIn(npc, home.contents)

    def test_a_player_standing_on_a_deleted_tile_goes_home(self):
        """Rebuilding the grid must not kill whoever is standing on it."""
        self.char1.location = self.tile

        self.tile.delete()

        self.assertIsNotNone(self.char1.pk)
        self.assertIsNotNone(self.char1.location)
        self.assertNotEqual(self.char1.location, self.tile)

    def test_what_a_player_carries_travels_with_them(self):
        """Held items are not direct contents of the room and never were."""
        self.char1.location = self.tile
        carried = create_object(BaseItem, key="test keepsake", location=self.char1)

        self.tile.delete()

        self.assertIsNotNone(carried.pk)
        self.assertEqual(carried.location, self.char1)
