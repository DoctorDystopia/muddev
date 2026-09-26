"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/25/2026
Description: Tests for the chunk channel of the tile world:
             `events.emit_tile_chunks`. The world is four chunks in a row,
             built in memory. `emit` is replaced by a recorder.
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from systems.interface.statefeed import constants as const
from systems.interface.statefeed import events


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE

# Four chunks in a row. Chunk (3, 0) is outside the block of chunk (0, 0).
_CHUNKS = ((0, 0), (1, 0), (2, 0), (3, 0))

_HOME_TILE = (5, 5)
_EAST_TILE = (_SIZE + 5, 5)


def _chunk_file(cx: int, cy: int):
    tile_count = _SIZE * _SIZE

    return chunkfile.ChunkFile(
        cx=cx, cy=cy, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[cx] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=[0] * tile_count,
        areas=[0] * tile_count)


class TileChunkChannelTests(EvenniaTest):

    def setUp(self):
        super().setUp()
        self.files = {key: _chunk_file(*key) for key in _CHUNKS}
        self.world = TileWorld(list(self.files.values()))
        self.world.rooms.load()
        set_world(self.world)
        self.sent = []
        self.reach = 1

        patcher = mock.patch.object(events, "emit", side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def _record(self, obj, payload, force=False):
        if payload.channel == const.CHANNEL_TILE_CHUNK:
            self.sent.append(tuple(payload.chunk_file["chunk"]))

        return self.reach

    def _place(self, tile):
        movement.place(self.world.rooms, self.char1, *tile, quiet=True)
        self.sent.clear()

    def test_an_observer_off_the_tile_world_gets_no_chunk(self):
        events.emit_tile_chunks(self.char1, force=True)

        self.assertEqual(self.sent, [])

    def test_the_block_is_sent_and_nothing_past_it(self):
        self._place(_HOME_TILE)
        events.emit_tile_chunks(self.char1, force=True)

        self.assertEqual(sorted(self.sent), [(0, 0), (1, 0)])

    def test_a_chunk_goes_one_time_until_a_resync(self):
        self._place(_HOME_TILE)
        events.emit_tile_chunks(self.char1, force=True)
        self.sent.clear()
        events.emit_tile_chunks(self.char1)

        self.assertEqual(self.sent, [])

        events.emit_tile_chunks(self.char1, force=True)
        self.assertEqual(sorted(self.sent), [(0, 0), (1, 0)])

    def test_a_move_into_a_new_chunk_sends_only_the_new_ones(self):
        self._place(_HOME_TILE)
        events.emit_tile_chunks(self.char1, force=True)
        self._place(_EAST_TILE)
        events.emit_tile_chunks(self.char1)

        self.assertEqual(self.sent, [(2, 0)])

    def test_a_chunk_left_behind_is_sent_again_on_return(self):
        far_tile = (3 * _SIZE + 5, 5)
        self._place(_HOME_TILE)
        events.emit_tile_chunks(self.char1, force=True)
        self._place(far_tile)
        events.emit_tile_chunks(self.char1)
        self._place(_HOME_TILE)
        events.emit_tile_chunks(self.char1)

        self.assertEqual(sorted(self.sent), [(0, 0), (1, 0)])

    def test_a_send_that_reached_no_session_is_tried_again(self):
        self._place(_HOME_TILE)
        self.reach = 0
        events.emit_tile_chunks(self.char1, force=True)
        self.reach = 1
        self.sent.clear()
        events.emit_tile_chunks(self.char1)

        self.assertEqual(sorted(self.sent), [(0, 0), (1, 0)])

    def test_the_room_info_of_a_move_carries_the_block(self):
        self._place(_HOME_TILE)
        events.emit_room_info(self.char1, force=True)

        self.assertEqual(sorted(self.sent), [(0, 0), (1, 0)])

    def test_each_legal_step_is_a_near_tile_action(self):
        from systems.interface.statefeed import serializers
        from world import tile_travel

        self._place(_HOME_TILE)
        actions = serializers.tile_actions(self.char1.location)
        open_names = tile_travel.open_directions(self.world, _HOME_TILE)

        for name in open_names:
            dx, dy = tile_const.DIRECTION_OFFSETS[name]
            key = serializers.tile_key(_HOME_TILE[0] + dx, _HOME_TILE[1] + dy)

            with self.subTest(direction=name):
                self.assertEqual(actions[key]["command"], name)
                self.assertEqual(actions[key]["kind"],
                                 const.TILE_ACTION_KIND_STEP)

        own = serializers.tile_key(*_HOME_TILE)
        self.assertEqual(actions[own]["kind"], const.TILE_ACTION_KIND_LOOK)

    def test_the_wire_form_reads_back_as_the_same_chunk_file(self):
        for key, chunk_file in self.files.items():
            with self.subTest(chunk=key):
                wire = self.world.chunk_dict(key)
                self.assertEqual(chunkfile.from_dict(wire), chunk_file)
