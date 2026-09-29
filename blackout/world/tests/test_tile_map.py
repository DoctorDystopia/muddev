"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for the telnet map of the tile world (`world/tile_map.py`)
             and for the look of a tile room: its Exits line and its map.
"""

import unittest
from unittest import mock

from evennia.utils.create import create_object
from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from systems.gameplay.combat.auras.targeting import within_metric
from systems.interface.ui.colors import TAG_AURA_TILE
from world import tile_map
from world.object_kinds import OBJECT_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE
_RADIUS = 3
_CENTER = (10, 10)

_BLOCKED = (11, 10)
_WATER = (9, 10)
_NORTH_WALLED = (10, 11)
_OBJECT_TILE = (10, 8)

_FACILITY = next(key for key, kind in OBJECT_KINDS.items()
                 if kind.category == tile_const.OBJECT_CATEGORY_FACILITY)
_NPC_KIND = next(key for key, kind in OBJECT_KINDS.items()
                 if kind.category == tile_const.OBJECT_CATEGORY_NPC)

# The spawn tile of the NPC kind, and the tile where the NPC stands now.
_NPC_SPAWN = (12, 8)
_NPC_NOW = (8, 12)


# ─── Private helper routines ─────────────────────────────────────────────────

def _world(extra_objects=()) -> TileWorld:
    tile_count = _SIZE * _SIZE
    flags = [0] * tile_count
    marks = {_BLOCKED: tile_const.FLAG_BLOCKED,
             _WATER: tile_const.FLAG_WATER,
             _NORTH_WALLED: tile_const.FLAG_WALL_NORTH}

    for (x, y), bits in marks.items():
        flags[y * _SIZE + x] = bits

    chunk_file = chunkfile.ChunkFile(
        cx=0, cy=0, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=flags, areas=[0] * tile_count,
        objects=[chunkfile.ChunkObject(_FACILITY, *_OBJECT_TILE),
                 *extra_objects])

    return TileWorld([chunk_file])


def _cell(lines: list, row: int, column: int) -> str:
    """Return one character of the map, or a space past a cut line end."""
    line = lines[row] if row < len(lines) else ""

    return line[column] if column < len(line) else " "


def _tile_cell(lines, tile) -> str:
    row = 2 * (_CENTER[1] + _RADIUS - tile[1])
    column = 2 * (tile[0] - (_CENTER[0] - _RADIUS))

    return _cell(lines, row, column)


# ─── Tests ───────────────────────────────────────────────────────────────────

class TileMapRenderTests(unittest.TestCase):

    def setUp(self):
        self.lines = tile_map.render(_world(), _CENTER, _RADIUS).split("\n")

    def test_the_map_has_a_line_for_each_row_and_each_gap(self):
        rows = 2 * _RADIUS + 1

        self.assertEqual(len(self.lines), 2 * rows - 1)

    def test_each_tile_shows_its_glyph(self):
        cases = (
            (_CENTER, tile_map.LOOKER_GLYPH),
            (_BLOCKED, tile_map.VOID_GLYPH),
            (_WATER, tile_map.WATER_GLYPH),
            (_OBJECT_TILE, tile_map.CATEGORY_GLYPHS[
                tile_const.OBJECT_CATEGORY_FACILITY]),
            ((12, 12), tile_map.GROUND_GLYPH),
        )

        for tile, glyph in cases:
            with self.subTest(tile=tile):
                self.assertEqual(_tile_cell(self.lines, tile), glyph)

    def test_a_north_wall_shows_in_the_gap_above_the_tile(self):
        row = 2 * (_CENTER[1] + _RADIUS - _NORTH_WALLED[1]) - 1
        column = 2 * (_NORTH_WALLED[0] - (_CENTER[0] - _RADIUS))

        self.assertEqual(_cell(self.lines, row, column),
                         tile_map._WALL_BETWEEN_ROWS)

    def test_every_category_has_a_glyph(self):
        for category in tile_const.OBJECT_CATEGORIES:
            with self.subTest(category=category):
                self.assertIn(category, tile_map.CATEGORY_GLYPHS)

    def test_the_edge_of_the_world_draws_as_void(self):
        lines = tile_map.render(_world(), (0, 0), _RADIUS).split("\n")
        west = _cell(lines, 2 * _RADIUS, 0)

        self.assertEqual(west, tile_map.VOID_GLYPH)


class TileMapAuraTests(unittest.TestCase):
    """The aura tint follows the metric that the caller gives."""

    def _render(self, aura_radius: int, metric=within_metric) -> str:
        return tile_map.render(_world(), _CENTER, _RADIUS,
                               aura_radius=aura_radius, aura_metric=metric)

    def _tinted_count(self, text: str) -> int:
        return text.count(TAG_AURA_TILE)

    def test_no_aura_draws_no_tint(self):
        self.assertEqual(self._tinted_count(self._render(0)), 0)

    def test_the_tint_matches_the_metric_of_the_damage_path(self):
        world = _world()
        expected = 0

        for dy in range(-1, 2):
            for dx in range(-1, 2):
                tile = (_CENTER[0] + dx, _CENTER[1] + dy)
                void = world.grid.flags_at(*tile) & tile_const.FLAG_BLOCKED

                if (dx, dy) != (0, 0) and not void and within_metric(dx, dy, 1):
                    expected += 1

        self.assertEqual(self._tinted_count(self._render(1)), expected)

    def test_the_looker_and_a_void_tile_stay_plain(self):
        lines = self._render(1).split("\n")
        centre_row = lines[2 * _RADIUS]

        self.assertIn(tile_map.LOOKER_GLYPH, centre_row)
        self.assertNotIn(f"{TAG_AURA_TILE}{tile_map.LOOKER_GLYPH}", centre_row)
        self.assertNotIn(f"{TAG_AURA_TILE}{tile_map.VOID_GLYPH}", centre_row)

    def test_a_metric_that_refuses_every_tile_draws_no_tint(self):
        text = self._render(2, metric=lambda dx, dy, radius: False)

        self.assertEqual(self._tinted_count(text), 0)


class TileMapLiveNpcTests(EvenniaTestCase):
    """An NPC draws where it stands now, not on its spawn tile (debt 14)."""

    def setUp(self):
        super().setUp()
        spawn = chunkfile.ChunkObject(_NPC_KIND, *_NPC_SPAWN)
        self.world = _world(extra_objects=[spawn])
        self.world.rooms.load()
        self.npc = create_object(key="wanderer")
        self.npc.db.npc_key = _NPC_KIND
        movement.place(self.world.rooms, self.npc, *_NPC_NOW, quiet=True)

    def _lines(self) -> list:
        return tile_map.render(self.world, _CENTER, _RADIUS).split("\n")

    def test_the_npc_draws_on_the_tile_where_it_stands(self):
        npc_glyph = tile_map.CATEGORY_GLYPHS[tile_const.OBJECT_CATEGORY_NPC]

        self.assertEqual(_tile_cell(self._lines(), _NPC_NOW), npc_glyph)

    def test_the_empty_spawn_tile_draws_as_ground(self):
        self.assertEqual(_tile_cell(self._lines(), _NPC_SPAWN),
                         tile_map.GROUND_GLYPH)

    def test_a_plain_object_draws_no_npc_glyph(self):
        self.npc.attributes.remove("npc_key")

        self.assertEqual(_tile_cell(self._lines(), _NPC_NOW),
                         tile_map.GROUND_GLYPH)


class TileRoomLookTests(EvenniaTest):

    def setUp(self):
        super().setUp()
        self.world = _world()
        self.world.rooms.load()
        set_world(self.world)
        movement.place(self.world.rooms, self.char1, *_CENTER, quiet=True)

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def test_the_exits_line_names_each_open_direction(self):
        # Blocked east, water west: both diagonals on each side cut a corner.
        # Only north and south stay open.
        text = self.char1.location.get_display_exits(self.char1)
        named = set(text.split(":|n", 1)[1].replace(" and ", ", ")
                    .replace(",", " ").split())

        self.assertEqual(named, {"north", "south"})

    def test_a_look_sends_the_tile_map(self):
        self.char1.msg = mock.Mock()
        self.char1.location.return_appearance(self.char1)
        sent = [str(call.kwargs.get("text", "")) for call in
                self.char1.msg.call_args_list]

        self.assertTrue(any(tile_map.LOOKER_GLYPH in text for text in sent))

    def test_a_look_with_a_burning_aura_tints_the_map(self):
        room = self.char1.location
        self.char1.msg = mock.Mock()

        with mock.patch.object(type(room), "_active_aura_radius", return_value=1):
            room.return_appearance(self.char1)

        sent = [str(call.kwargs.get("text", "")) for call in
                self.char1.msg.call_args_list]

        self.assertTrue(any(TAG_AURA_TILE in text for text in sent))
