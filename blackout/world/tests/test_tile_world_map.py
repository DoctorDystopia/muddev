"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/28/2026
Description: Tests for the world map of a telnet player
             (world/tile_world_map.py) and the `worldmap` command. The world
             is built in memory.
"""

import unittest
from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from commands import world_map_cmds
from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from world import tile_map, tile_world_map
from world.object_kinds import OBJECT_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE
_TILE_COUNT = _SIZE * _SIZE
_BLOCK = tile_world_map.OVERVIEW_BLOCK
_SQUARES = _SIZE // _BLOCK

_FACILITY = next(key for key, kind in OBJECT_KINDS.items()
                 if kind.category == tile_const.OBJECT_CATEGORY_FACILITY)
_NPC = next(key for key, kind in OBJECT_KINDS.items()
            if kind.category == tile_const.OBJECT_CATEGORY_NPC)


def _chunk_file(cx: int, cy: int, flags=None, objects=()):
    return chunkfile.ChunkFile(
        cx=cx, cy=cy, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * _TILE_COUNT, flags=flags or [0] * _TILE_COUNT,
        areas=[0] * _TILE_COUNT, objects=list(objects))


def _square_flags(square_x: int, square_y: int, bits: int) -> list:
    """Flags with every tile of one local square set to `bits`."""
    flags = [0] * _TILE_COUNT

    for y in range(square_y * _BLOCK, (square_y + 1) * _BLOCK):
        for x in range(square_x * _BLOCK, (square_x + 1) * _BLOCK):
            flags[y * _SIZE + x] = bits

    return flags


def _glyph_at(drawn: str, square_x: int, square_y: int) -> str:
    """The glyph of a square, from a map of one chunk at (0, 0). North is up."""
    lines = drawn.split("\n")
    line = lines[_SQUARES - 1 - square_y].ljust(_SQUARES)

    return line[square_x]


class OverviewTests(unittest.TestCase):

    def test_one_chunk_draws_one_line_for_each_row_of_squares(self):
        world = TileWorld([_chunk_file(0, 0)])
        drawn = tile_world_map.render_overview(world.plane(0), None)

        self.assertEqual(len(drawn.split("\n")), _SQUARES)
        self.assertEqual(_glyph_at(drawn, 0, 0), tile_map.GROUND_GLYPH)

    def test_the_looker_square_shows_the_looker(self):
        world = TileWorld([_chunk_file(0, 0)])
        drawn = tile_world_map.render_overview(world.plane(0), (_BLOCK * 2, 1))

        self.assertEqual(_glyph_at(drawn, 2, 0), tile_map.LOOKER_GLYPH)
        self.assertEqual(drawn.count(tile_map.LOOKER_GLYPH), 1)

    def test_north_is_up(self):
        world = TileWorld([_chunk_file(0, 0)])
        north_square = (0, _SQUARES - 1)
        drawn = tile_world_map.render_overview(
            world.plane(0), (1, north_square[1] * _BLOCK + 1))

        self.assertTrue(drawn.startswith(tile_map.LOOKER_GLYPH))

    def test_a_square_of_water_draws_water(self):
        flags = _square_flags(3, 3, tile_const.FLAG_WATER)
        world = TileWorld([_chunk_file(0, 0, flags=flags)])
        drawn = tile_world_map.render_overview(world.plane(0), None)

        self.assertEqual(_glyph_at(drawn, 3, 3), tile_map.WATER_GLYPH)

    def test_a_placed_facility_draws_its_category_glyph_and_an_npc_does_not(self):
        placed = [chunkfile.ChunkObject(_FACILITY, 1, 1),
                  chunkfile.ChunkObject(_NPC, _BLOCK + 1, 1)]
        world = TileWorld([_chunk_file(0, 0, objects=placed)])
        drawn = tile_world_map.render_overview(world.plane(0), None)
        facility_glyph = tile_map.CATEGORY_GLYPHS[
            tile_const.OBJECT_CATEGORY_FACILITY]

        self.assertEqual(_glyph_at(drawn, 0, 0), facility_glyph)
        self.assertEqual(_glyph_at(drawn, 1, 0), tile_map.GROUND_GLYPH)

    def test_a_plane_with_no_chunk_draws_nothing(self):
        world = TileWorld([_chunk_file(0, 0)])

        self.assertEqual(
            tile_world_map.render_overview(world.plane(1), None), "")


class WorldMapCommandTests(EvenniaTest):

    def setUp(self):
        super().setUp()
        self.world = TileWorld([_chunk_file(0, 0)])
        self.world.load_rooms()
        set_world(self.world)
        movement.place(self.world.rooms, self.char1, 5, 5, quiet=True)
        self.char1.msg = mock.Mock()

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def _run(self, subscribed: bool):
        with mock.patch.object(world_map_cmds, "_wants_feed",
                               return_value=subscribed), \
                mock.patch.object(world_map_cmds.feed,
                                  "emit_world_map") as emitter:
            self.char1.execute_cmd("worldmap")

        return emitter

    def test_a_session_with_the_feed_gets_the_feed_and_no_text(self):
        emitter = self._run(subscribed=True)

        emitter.assert_called_once_with(self.char1)
        self.char1.msg.assert_not_called()

    def test_a_text_session_gets_the_overview(self):
        emitter = self._run(subscribed=False)

        emitter.assert_not_called()
        text, _kwargs = self.char1.msg.call_args.kwargs["text"]
        header, _newline, drawn = text.partition("\n")
        self.assertIn(tile_map.LOOKER_GLYPH, drawn)
        self.assertIn("plane 0", header.lower())
