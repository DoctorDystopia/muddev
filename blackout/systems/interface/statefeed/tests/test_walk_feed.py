"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/28/2026
Description: Tests for the walk channel: `events.emit_walk`, and the proof
             that every write of the walk and of the run toggle
             (systems/gameplay/movement/walk.py) sends it. The world is one
             chunk, built in memory. `emit` is replaced by a recorder. No
             tick engine runs: a test calls `walk.advance` for each tick.
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from commands import tile_movement
from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from systems.gameplay.movement import walk
from systems.interface.statefeed import constants as const
from systems.interface.statefeed import events, resync


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE

_HOME_TILE = (5, 5)
_FAR_TILE = (12, 5)
_BLOCKED_TILE = (6, 5)


def _chunk_file():
    tile_count = _SIZE * _SIZE
    flags = [0] * tile_count
    flags[_BLOCKED_TILE[1] * _SIZE + _BLOCKED_TILE[0]] = tile_const.FLAG_BLOCKED

    return chunkfile.ChunkFile(
        cx=0, cy=0, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=flags, areas=[0] * tile_count)


class WalkChannelTests(EvenniaTest):

    def setUp(self):
        super().setUp()
        self.world = TileWorld([_chunk_file()])
        self.world.load_rooms()
        set_world(self.world)
        self.walks = []
        self.channels = []

        patcher = mock.patch.object(events, "emit", side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)

        movement.place(self.world.rooms, self.char1, *_HOME_TILE, quiet=True)
        self.walks.clear()

    def tearDown(self):
        walk.forget_all()
        set_world(None)
        super().tearDown()

    def _record(self, obj, payload, force=False):
        self.channels.append(payload.channel)

        if payload.channel == const.CHANNEL_WALK:
            self.walks.append(payload)

        return 1

    def test_a_walk_sends_its_goal_and_its_whole_path_one_time(self):
        tile_movement.run_goto(self.char1, "(%d,%d)" % _FAR_TILE)
        walk.advance(self.char1)

        self.assertEqual(len(self.walks), 1)
        sent = self.walks[0]
        self.assertEqual(sent.goal, list(_FAR_TILE))
        self.assertEqual(sent.path[-1], list(_FAR_TILE))
        self.assertEqual(sent.z, tile_const.WORLD_Z)

        # The first step ran. The message still holds the whole path, because
        # the walk drops tiles from its own list, not from the copy it sent.
        self.assertEqual(len(sent.path), len(walk.current(self.char1).path) + 1)

    def test_an_arrival_sends_no_walk(self):
        tile_movement.run_goto(self.char1, "(%d,%d)" % _FAR_TILE)
        tile_movement.run_goto(self.char1, "(%d,%d)" % _HOME_TILE)

        self.assertEqual(self.walks[-1].goal, [])
        self.assertIsNone(walk.current(self.char1))

    def test_a_stop_sends_no_walk(self):
        tile_movement.run_goto(self.char1, "(%d,%d)" % _FAR_TILE)
        self.walks.clear()
        tile_movement.run_goto(self.char1, "")

        self.assertEqual(len(self.walks), 1)
        self.assertEqual(self.walks[0].goal, [])

    def test_a_new_goto_sends_only_the_new_walk(self):
        tile_movement.run_goto(self.char1, "(%d,%d)" % _FAR_TILE)
        self.walks.clear()
        tile_movement.run_goto(self.char1, "(%d,%d)" % (5, 12))

        self.assertEqual(len(self.walks), 1)
        self.assertEqual(self.walks[0].goal, [5, 12])

    def test_a_path_that_does_not_start_next_to_the_walker_ends_the_walk(self):
        walk.set_walk(self.char1, walk.TileWalk(path=[_FAR_TILE],
                                                goal=_FAR_TILE))
        walk.advance(self.char1)

        self.assertEqual(self.walks[-1].goal, [])
        self.assertIsNone(walk.current(self.char1))

    def test_a_refused_step_ends_the_walk(self):
        walk.set_walk(self.char1, walk.TileWalk(path=[_BLOCKED_TILE],
                                                goal=_BLOCKED_TILE))
        walk.advance(self.char1)

        self.assertEqual(self.walks[-1].goal, [])
        self.assertIsNone(walk.current(self.char1))

    def test_a_held_key_sends_no_walk(self):
        # A direction walk has no destination marker, so a key that the
        # client sends two times a tick puts nothing on the feed.
        self.char1.execute_cmd("west")
        self.char1.execute_cmd("west")
        walk.advance(self.char1)

        self.assertEqual(self.walks, [])

    def test_a_held_key_clears_the_marker_of_a_goto(self):
        tile_movement.run_goto(self.char1, "(%d,%d)" % _FAR_TILE)
        self.walks.clear()
        self.char1.execute_cmd("west")

        self.assertEqual(len(self.walks), 1)
        self.assertEqual(self.walks[0].goal, [])

    def test_the_run_toggle_sends_the_walk_with_its_state(self):
        walk.set_running(self.char1, True)
        self.assertTrue(self.walks[-1].running)

        walk.set_running(self.char1, False)
        self.assertFalse(self.walks[-1].running)

    def test_a_walk_carries_the_run_toggle(self):
        walk.set_running(self.char1, True)
        tile_movement.run_goto(self.char1, "(%d,%d)" % _FAR_TILE)

        self.assertTrue(self.walks[-1].running)
        self.assertEqual(self.walks[-1].goal, list(_FAR_TILE))

    def test_a_resync_sends_the_walk(self):
        tile_movement.run_goto(self.char1, "(%d,%d)" % _FAR_TILE)
        self.walks.clear()
        resync.send_full_state(self.char1)

        self.assertEqual(self.walks[-1].goal, list(_FAR_TILE))

    def test_an_observer_with_no_walk_sends_an_empty_goal(self):
        events.emit_walk(self.char1)

        self.assertEqual(self.walks[-1].goal, [])
        self.assertEqual(self.walks[-1].path, [])
        self.assertFalse(self.walks[-1].running)
