"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/28/2026
Description: Tests for the world map feed: the world map summary of a chunk,
             the index, and `events.emit_world_map`. The worlds are built in
             memory.
"""

import unittest
from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from systems.interface.statefeed import constants as const
from systems.interface.statefeed import events, worldmap
from world import areas as area_table
from world import floor_types as floor_table


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE
_TILE_COUNT = _SIZE * _SIZE

_AREA_KEYS = tuple(area_table.AREAS)
_WATER_FLOOR = "water_bed"
_WATER_INDEX = 5          # a local tile index, row 0
_OBJECT_KIND = "bank"


def _chunk_file(cx: int, cy: int, plane: int = 0, floors=None, flags=None,
                areas=None, area_names=None, floor_names=None, objects=()):
    return chunkfile.ChunkFile(
        cx=cx, cy=cy, plane=plane,
        floor_names=floor_names or ["sand", _WATER_FLOOR],
        area_names=area_names or [_AREA_KEYS[0]],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=floors or [0] * _TILE_COUNT,
        flags=flags or [0] * _TILE_COUNT,
        areas=areas or [0] * _TILE_COUNT,
        objects=list(objects))


def _decode(character: str) -> tuple:
    """Return (floor name, unwalkable) of one character of a summary."""
    tile_class = const.WORLD_MAP_ALPHABET.index(character)
    names = list(floor_table.FLOOR_TYPES)

    return names[tile_class // 2], bool(tile_class % 2)


class WorldMapSummaryTests(unittest.TestCase):
    """The encoding and the index. No database."""

    def test_the_alphabet_holds_every_floor_type(self):
        self.assertTrue(worldmap.alphabet_holds_every_floor())

    def test_each_tile_decodes_to_its_floor_and_its_walkability(self):
        floors = [0] * _TILE_COUNT
        flags = [0] * _TILE_COUNT
        floors[_WATER_INDEX] = 1
        flags[_WATER_INDEX] = tile_const.FLAG_WATER
        blocked_index = _WATER_INDEX + 1
        flags[blocked_index] = tile_const.FLAG_BLOCKED
        chunk_file = _chunk_file(0, 0, floors=floors, flags=flags)

        tiles = worldmap.encode_tiles(chunk_file)

        self.assertEqual(len(tiles), _TILE_COUNT)
        self.assertEqual(_decode(tiles[0]), ("sand", False))
        self.assertEqual(_decode(tiles[_WATER_INDEX]), (_WATER_FLOOR, True))
        self.assertEqual(_decode(tiles[blocked_index]), ("sand", True))

    def test_a_wall_alone_leaves_a_tile_walkable(self):
        flags = [tile_const.FLAG_WALL_NORTH] * _TILE_COUNT
        tiles = worldmap.encode_tiles(_chunk_file(0, 0, flags=flags))

        self.assertEqual(_decode(tiles[0]), ("sand", False))

    def test_the_objects_of_a_summary_stand_at_world_tiles(self):
        placed = chunkfile.ChunkObject(kind=_OBJECT_KIND, x=3, y=4)
        world = TileWorld([_chunk_file(1, 2, objects=[placed])])

        summary = worldmap.summary_of(world.plane(0), (1, 2))

        self.assertEqual(summary["chunk"], [1, 2])
        self.assertEqual(summary["plane"], 0)
        self.assertEqual(summary["objects"], [
            {"kind": _OBJECT_KIND, "x": _SIZE + 3, "y": 2 * _SIZE + 4}])

    def test_each_area_gets_one_label_on_a_tile_of_that_area(self):
        # The east half of the chunk is the second area.
        areas = [0 if index % _SIZE < _SIZE // 2 else 1
                 for index in range(_TILE_COUNT)]
        names = [_AREA_KEYS[0], _AREA_KEYS[-1]]
        world = TileWorld([_chunk_file(0, 0, areas=areas, area_names=names)])
        tile_plane = world.plane(0)

        labels = worldmap.area_labels(tile_plane)

        self.assertEqual(sorted(label["text"] for label in labels),
                         sorted(area_table.AREAS[key].name for key in names))

        for label in labels:
            with self.subTest(label=label["text"]):
                area = tile_plane.area_at(label["x"], label["y"])
                self.assertEqual(area_table.AREAS[area].name, label["text"])

    def test_a_void_tile_counts_for_no_label(self):
        void_index = list(floor_table.FLOOR_TYPES).index(
            floor_table.VOID_FLOOR_TYPE)
        names = list(floor_table.FLOOR_TYPES)
        floors = [void_index] * _TILE_COUNT
        world = TileWorld([_chunk_file(0, 0, plane=1, floors=floors,
                                       floor_names=names)])

        self.assertEqual(worldmap.area_labels(world.plane(1)), [])

    def test_the_index_names_every_chunk_and_only_planes_with_chunks(self):
        files = [_chunk_file(0, 0), _chunk_file(1, 0), _chunk_file(0, 0, 1)]
        world = TileWorld(files)

        index = worldmap.index_of(world, first_plane=1)

        self.assertEqual(index["planes"], [0, 1])
        self.assertEqual(index["chunks"][0], [0, 0, 1])
        self.assertEqual(sorted(map(tuple, index["chunks"])),
                         sorted((f.cx, f.cy, f.plane) for f in files))


class WorldMapChannelTests(EvenniaTest):
    """`events.emit_world_map`, with `emit` replaced by a recorder."""

    def setUp(self):
        super().setUp()
        self.world = TileWorld([_chunk_file(0, 0), _chunk_file(1, 0)])
        self.world.load_rooms()
        set_world(self.world)
        self.sent = []
        self.reach = 1

        patcher = mock.patch.object(events, "emit", side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)

        movement.place(self.world.rooms, self.char1, 5, 5, quiet=True)
        self.sent.clear()

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def _record(self, obj, payload, force=False):
        if payload.channel == const.CHANNEL_WORLD_MAP:
            self.sent.append("index")
        elif payload.channel == const.CHANNEL_WORLD_MAP_CHUNK:
            self.sent.append(tuple(payload.chunk) + (payload.plane,))

        return self.reach

    def test_the_index_comes_first_then_every_chunk(self):
        events.emit_world_map(self.char1)

        self.assertEqual(self.sent[0], "index")
        self.assertEqual(sorted(self.sent[1:]), [(0, 0, 0), (1, 0, 0)])

    def test_a_second_request_sends_only_the_index(self):
        events.emit_world_map(self.char1)
        self.sent.clear()
        events.emit_world_map(self.char1)

        self.assertEqual(self.sent, ["index"])

    def test_a_resync_sends_every_chunk_again(self):
        events.emit_world_map(self.char1)
        events.forget_world_map(self.char1)
        self.sent.clear()
        events.emit_world_map(self.char1)

        self.assertEqual(len(self.sent), 3)

    def test_a_send_that_reached_no_session_is_tried_again(self):
        self.reach = 0
        events.emit_world_map(self.char1)
        self.reach = 1
        self.sent.clear()
        events.emit_world_map(self.char1)

        self.assertEqual(len(self.sent), 3)
