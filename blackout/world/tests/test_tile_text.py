"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for the room text of a tile: `world/tile_text.py`, and
             `TileRoom`, which reads it. Each expectation comes from the
             data tables, not from a typed name.
"""

import unittest

from evennia.utils.test_resources import EvenniaTestCase

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid.rooms import TileRooms
from systems.core.tilegrid.world import TileWorld, set_world
from world import tile_text
from world.areas import AREAS, DEFAULT_AREA
from world.object_kinds import OBJECT_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE

# The kinds that name a tile, and the kinds that do not.
_NAMED = [kind for kind in OBJECT_KINDS.values() if kind.name]
_UNNAMED = [kind for kind in OBJECT_KINDS.values() if not kind.name]

_FALLBACK = "fallback name"

# A key that no area has.
_NO_AREA = "no_such_area"

# The tiles of the one-chunk test world, and the kind on the named tile.
_NAMED_TILE = (3, 4)
_PLAIN_TILE = (10, 10)


# ─── Private helper routines ─────────────────────────────────────────────────

def _one_chunk_world(kind_key: str) -> TileWorld:
    """A world of chunk (0, 0) in the default area, with one placed kind."""
    tile_count = _SIZE * _SIZE
    corner_count = tile_const.CORNERS_PER_SIDE ** 2
    chunk_file = chunkfile.ChunkFile(
        cx=0, cy=0, plane=0,
        floor_names=["sand"], area_names=[DEFAULT_AREA],
        heights=[0] * corner_count, floors=[0] * tile_count,
        flags=[0] * tile_count, areas=[0] * tile_count,
        objects=[chunkfile.ChunkObject(kind_key, *_NAMED_TILE)])

    return TileWorld([chunk_file])


# ─── Tests ───────────────────────────────────────────────────────────────────

class TileTextRuleTests(unittest.TestCase):

    def test_a_named_kind_names_its_tile(self):
        for kind in _NAMED:
            with self.subTest(kind=kind.key):
                self.assertEqual(
                    tile_text.tile_name([kind.key], DEFAULT_AREA), kind.name)
                self.assertEqual(
                    tile_text.tile_desc([kind.key], DEFAULT_AREA), kind.desc)

    def test_an_unnamed_kind_leaves_the_name_to_the_next_kind(self):
        named = _NAMED[0]

        for kind in _UNNAMED:
            with self.subTest(kind=kind.key):
                kinds = [kind.key, named.key]
                self.assertEqual(tile_text.tile_name(kinds, DEFAULT_AREA),
                                 named.name)
                self.assertEqual(tile_text.tile_desc(kinds, DEFAULT_AREA),
                                 named.desc)

    def test_a_tile_with_no_named_kind_takes_its_area_texts(self):
        unnamed = [kind.key for kind in _UNNAMED]

        for key, area in AREAS.items():
            with self.subTest(area=key):
                self.assertEqual(tile_text.tile_name(unnamed, key), area.name)
                self.assertEqual(tile_text.tile_desc(unnamed, key), area.desc)

    def test_no_kind_and_no_area_gives_the_fallback(self):
        self.assertEqual(tile_text.tile_name([], None, _FALLBACK), _FALLBACK)
        self.assertEqual(tile_text.tile_name([], _NO_AREA, _FALLBACK),
                         _FALLBACK)
        self.assertEqual(tile_text.tile_desc([], None), "")


class TileRoomTextTests(EvenniaTestCase):

    def setUp(self):
        super().setUp()
        self.kind = _NAMED[0]
        self.world = _one_chunk_world(self.kind.key)
        set_world(self.world)
        self.rooms = TileRooms()

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def test_a_room_on_a_named_tile_shows_the_kind(self):
        room = self.rooms.ensure_room(*_NAMED_TILE)

        self.assertEqual(room.get_display_name(None), self.kind.name)
        self.assertEqual(room.get_display_desc(None), self.kind.desc)

    def test_a_room_on_a_plain_tile_shows_the_area(self):
        room = self.rooms.ensure_room(*_PLAIN_TILE)
        area = AREAS[DEFAULT_AREA]

        self.assertEqual(room.get_display_name(None), area.name)
        self.assertEqual(room.get_display_desc(None), area.desc)

    def test_a_pooled_room_shows_its_key(self):
        room = self.rooms.ensure_room(*_PLAIN_TILE)
        self.rooms.release(room)

        self.assertEqual(room.get_display_name(None), room.key)
