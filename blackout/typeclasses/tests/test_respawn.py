"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: Tests for the player death policy — Character.respawn and the
             world/respawn.py location fact.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py typeclasses

Before this policy existed, a player killed by an NPC had their HP silently
refilled where they fell while the NPC's handler kept swinging: they were a
punching bag until they walked away. Every case below pins one part of the fix.
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.combat.combat import ensure_combat_handler, get_handler_for
from typeclasses.npc_combat import spawn_mutant_raider
from typeclasses.rooms import GridTile
from world.respawn import RESPAWN_XYZ, get_respawn_room


def _make_respawn_room() -> GridTile:
    """Build the grid tile world/respawn.py points at.

    EvenniaTest gives us room1/room2, but no xyzgrid — the map is built by an
    operator script against the live database, never in a test. So the tests
    that need a destination create exactly the one coordinate under test.
    """
    x, y, z = RESPAWN_XYZ
    room = GridTile.create(key="Oasis Entrance", xyz=(x, y, z))[0]

    return room


class TestRespawnRoomResolution(EvenniaTestCase):
    """world/respawn.py — the one owner of 'where does a dead player go'."""

    def test_resolves_the_room_at_the_named_coordinate(self):
        room = _make_respawn_room()

        self.assertEqual(get_respawn_room(), room)

    def test_missing_room_degrades_to_none(self):
        """No grid built. Must report None, not raise.

        This is the load-bearing case: get_respawn_room is called from inside
        at_death, and an exception escaping there would abandon the death
        sequence with combat already torn down and the player still at 0 HP.
        """
        with mock.patch("world.respawn.logger.log_err") as mocked_log:
            room = get_respawn_room()

        self.assertIsNone(room)
        self.assertTrue(mocked_log.called, "an unresolvable respawn room must be logged")

    def test_the_coordinate_is_anchored_on_a_zcoord_not_a_module(self):
        """Regression guard for the fact that made this a decision at all.

        world/maps/oasis.py was world/maps/test_oasis.py until recently.
        scripts/map_manifest.json binds a MODULE to a zcoord, so a module
        rename moves the manifest row and leaves the zcoord alone. Anchoring
        the respawn point on the zcoord survives that; anchoring it on the
        module path would not have.
        """
        _x, _y, zcoord = RESPAWN_XYZ

        self.assertEqual(zcoord, "oasis")
        self.assertNotIn("maps", zcoord)


class TestCharacterRespawn(EvenniaTest):
    """The Character.respawn override itself."""

    def test_respawn_moves_the_character_and_refills_hp(self):
        room = _make_respawn_room()
        self.char1.db.hp = 0

        self.char1.respawn()

        self.assertEqual(self.char1.location, room)
        self.assertEqual(self.char1.hp, self.char1.max_hp)

    def test_respawn_without_a_room_still_refills_hp(self):
        """Degrade to the base mixin's behaviour rather than raising."""
        origin = self.char1.location
        self.char1.db.hp = 0

        self.char1.respawn()

        self.assertEqual(self.char1.location, origin)
        self.assertEqual(self.char1.hp, self.char1.max_hp)

    def test_a_failed_move_still_leaves_a_live_character(self):
        """HP is restored BEFORE the move for exactly this case."""
        _make_respawn_room()
        self.char1.db.hp = 0

        with mock.patch.object(
            type(self.char1), "move_to", side_effect=RuntimeError("boom")
        ):
            self.char1.respawn()

        self.assertEqual(self.char1.hp, self.char1.max_hp)

    def test_respawning_where_you_already_stand_is_not_a_move(self):
        room = _make_respawn_room()
        self.char1.location = room
        self.char1.db.hp = 0

        with mock.patch.object(type(self.char1), "move_to") as mocked_move:
            self.char1.respawn()

        mocked_move.assert_not_called()
        self.assertEqual(self.char1.hp, self.char1.max_hp)


class TestPlayerKilledByAnNpc(EvenniaTest):
    """The whole death path, end to end, in the direction that never ran."""

    def _kill_char1_with_an_npc(self):
        """Land a fatal NPC blow on char1 and return the NPC."""
        npc = spawn_mutant_raider(self.room1)
        ensure_combat_handler(npc)
        ensure_combat_handler(self.char1)

        self.char1.db.hp = 2
        self.char1.at_damage(50, attacker=npc)

        return npc

    def test_the_player_lands_in_the_respawn_room_at_full_hp(self):
        room = _make_respawn_room()

        self._kill_char1_with_an_npc()

        self.assertEqual(self.char1.location, room)
        self.assertEqual(self.char1.hp, self.char1.max_hp)
        self.assertTrue(self.char1.is_alive())

    def test_the_players_combat_is_torn_down(self):
        _make_respawn_room()

        self._kill_char1_with_an_npc()

        self.assertIsNone(get_handler_for(self.char1))

    def test_the_npc_stops_fighting_on_its_next_tick(self):
        """The punching-bag bug.

        The NPC's handler survives the player's death — leave_combat only
        drops the dying side. It has to notice on its own that the room is
        empty, which is check_stop_combat's job and only runs on a tick.
        """
        _make_respawn_room()

        npc = self._kill_char1_with_an_npc()
        handler = get_handler_for(npc)

        self.assertIsNotNone(handler, "precondition: the NPC is still in combat")

        handler.tick()

        self.assertIsNone(get_handler_for(npc))

    def test_death_survives_an_unresolvable_respawn_room(self):
        """No grid, so no respawn room. Death must still complete."""
        self._kill_char1_with_an_npc()

        self.assertEqual(self.char1.hp, self.char1.max_hp)
        self.assertIsNone(get_handler_for(self.char1))
