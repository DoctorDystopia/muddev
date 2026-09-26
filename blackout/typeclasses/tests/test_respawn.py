"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: Tests for the player death policy — Character.respawn and the
             world/respawn.py location fact.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py typeclasses

Before this policy existed, a player killed by an NPC had their HP silently
refilled where they fell while the NPC's handler kept swinging: they were a
punching bag until they walked away. Every case below pins one part of the fix.
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.core.tilegrid.world import get_world
from systems.gameplay.combat.combat import ensure_combat_handler, get_handler_for
from typeclasses.npc_combat import spawn_mutant_raider
from typeclasses.tests import respawn_fixture
from typeclasses.tests.respawn_fixture import RESPAWN_TILE, make_respawn_room
from world.respawn import get_respawn_room


class _EmptyWorldMixin:
    """Every test starts on a tile world with no respawn point."""

    def setUp(self):
        super().setUp()
        self.world = respawn_fixture.install_empty_world()

    def tearDown(self):
        respawn_fixture.remove_world()
        super().tearDown()


class TestRespawnRoomResolution(_EmptyWorldMixin, EvenniaTestCase):
    """world/respawn.py — the one owner of 'where does a dead player go'."""

    def test_resolves_the_room_at_the_respawn_point(self):
        room = make_respawn_room()

        self.assertEqual(tuple(room.xyz[:2]), RESPAWN_TILE)

    def test_the_respawn_point_is_pinned(self):
        """A character's home holds this room, so the pool must not move it."""
        make_respawn_room()

        self.assertTrue(get_world().rooms.is_pinned(*RESPAWN_TILE))

    def test_missing_respawn_point_degrades_to_none(self):
        """No respawn point placed. Must report None, not raise.

        This is the load-bearing case: get_respawn_room is called from inside
        at_death, and an exception escaping there would abandon the death
        sequence with combat already torn down and the player still at 0 HP.
        """
        with mock.patch("world.respawn.logger.log_err") as mocked_log:
            room = get_respawn_room()

        self.assertIsNone(room)
        self.assertTrue(mocked_log.called, "an unresolvable respawn room must be logged")

    def test_a_broken_world_degrades_to_none(self):
        with mock.patch("world.respawn.get_world", side_effect=RuntimeError("boom")):
            with mock.patch("world.respawn.logger.log_err"):
                room = get_respawn_room()

        self.assertIsNone(room)


class TestCharacterRespawn(_EmptyWorldMixin, EvenniaTest):
    """The Character.respawn override itself."""

    def test_respawn_moves_the_character_and_refills_hp(self):
        room = make_respawn_room()
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
        make_respawn_room()
        self.char1.db.hp = 0

        with mock.patch.object(
            type(self.char1), "move_to", side_effect=RuntimeError("boom")
        ):
            self.char1.respawn()

        self.assertEqual(self.char1.hp, self.char1.max_hp)

    def test_respawning_where_you_already_stand_is_not_a_move(self):
        room = make_respawn_room()
        self.char1.location = room
        self.char1.db.hp = 0

        with mock.patch.object(type(self.char1), "move_to") as mocked_move:
            self.char1.respawn()

        mocked_move.assert_not_called()
        self.assertEqual(self.char1.hp, self.char1.max_hp)


class TestLoginWithNoRoom(_EmptyWorldMixin, EvenniaTest):
    """The cutover deletes the xyzgrid rooms. A character that logged out on
    one has no room of its logout and maybe no home."""

    def _log_out_nowhere(self):
        self.char1.location = None
        self.char1.db.prelogout_location = None
        self.char1.home = None

    def test_a_login_with_no_room_and_no_home_lands_on_the_respawn_point(self):
        room = make_respawn_room()
        self._log_out_nowhere()

        self.char1.at_pre_puppet(self.account)

        self.assertEqual(self.char1.location, room)

    def test_a_home_still_wins_over_the_respawn_point(self):
        make_respawn_room()
        self._log_out_nowhere()
        self.char1.home = self.room2

        self.char1.at_pre_puppet(self.account)

        self.assertEqual(self.char1.location, self.room2)


class TestPlayerKilledByAnNpc(_EmptyWorldMixin, EvenniaTest):
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
        room = make_respawn_room()

        self._kill_char1_with_an_npc()

        self.assertEqual(self.char1.location, room)
        self.assertEqual(self.char1.hp, self.char1.max_hp)
        self.assertTrue(self.char1.is_alive())

    def test_the_players_combat_is_torn_down(self):
        make_respawn_room()

        self._kill_char1_with_an_npc()

        self.assertIsNone(get_handler_for(self.char1))

    def test_the_npc_stops_fighting_on_its_next_tick(self):
        """The punching-bag bug.

        The NPC's handler survives the player's death — leave_combat only
        drops the dying side. It has to notice on its own that the room is
        empty, which is check_stop_combat's job and only runs on a tick.
        """
        make_respawn_room()

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
