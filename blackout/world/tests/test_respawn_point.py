"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/25/2026
Description: The world chunks place exactly one respawn point, on a tile that
             a character can stand on. world/respawn.py reads it.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py world.tests.test_respawn_point
"""

import os
import unittest

from django.conf import settings

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid.world import TileWorld
from world.object_kinds import OBJECT_KINDS
from world.respawn import RESPAWN_KIND, respawn_tile


def _live_world() -> TileWorld:
    """The chunk files of world/chunks/, with no room index."""
    directory = os.path.join(settings.GAME_DIR, tile_const.CHUNK_DIRECTORY)

    return TileWorld(chunkfile.load_directory(directory))


class TestTheRespawnPoint(unittest.TestCase):
    """The respawn point is data. These tests hold the data to the rule."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.world = _live_world()

    def test_the_kind_is_a_landmark_with_a_name(self):
        kind = OBJECT_KINDS[RESPAWN_KIND]

        self.assertEqual(kind.category, tile_const.OBJECT_CATEGORY_LANDMARK)
        self.assertTrue(kind.name)
        self.assertFalse(kind.spawner or kind.label)

    def test_the_world_places_exactly_one(self):
        placed = [obj for obj in self.world.placed_objects()
                  if obj[0] == RESPAWN_KIND]

        self.assertEqual(len(placed), 1, placed)

    def test_a_character_can_stand_on_it(self):
        x, y = respawn_tile(self.world)
        flags = self.world.grid.flags_at(x, y)

        self.assertFalse(flags & tile_const.FLAGS_UNWALKABLE)

    def test_it_is_not_on_a_transition(self):
        """A respawn onto a transition tile would not teleport, and the next
        step off it would. Keep the two apart."""
        tile = respawn_tile(self.world)
        kinds = [OBJECT_KINDS[key].category for key in self.world.kinds_at(*tile)
                 if key in OBJECT_KINDS]

        self.assertNotIn(tile_const.OBJECT_CATEGORY_TRANSITION, kinds)
