"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/25/2026
Description: Tests for world/tile_cutover.py, the move of every character from
             the xyzgrid maps to the tile world.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py world.tests.test_tile_cutover
"""

from evennia.contrib.grid.xyzgrid.xyzgrid import XYZGrid
from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom
from evennia.utils.create import create_script
from evennia.utils.test_resources import EvenniaTest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid.world import TileWorld, set_world
from typeclasses.characters import PRELOGOUT_TILE_ATTR
from typeclasses.rooms import GridTile
from world import tile_cutover
from world.respawn import RESPAWN_KIND


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE

# The fixture world is chunk (0, 0), the chunk of the oasis map. Thus, a tile
# of that map is the same world tile.
_MAP = "oasis"
_RESPAWN = (3, 4)
_BLOCKED = (5, 5)
_OPEN = (2, 2)


# ─── Private helper routines ─────────────────────────────────────────────────

def _world(with_respawn: bool = True) -> TileWorld:
    """One chunk of open ground, with one blocked tile."""
    tile_count = _SIZE * _SIZE
    flags = [0] * tile_count
    flags[_BLOCKED[1] * _SIZE + _BLOCKED[0]] = tile_const.FLAG_BLOCKED
    objects = []

    if with_respawn:
        objects.append(chunkfile.ChunkObject(RESPAWN_KIND, *_RESPAWN))

    chunk_file = chunkfile.ChunkFile(
        cx=0, cy=0, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=flags, areas=[0] * tile_count,
        objects=objects)
    world = TileWorld([chunk_file])
    world.rooms.load()

    return world


def _map_room(x: int, y: int, zcoord: str = _MAP):
    """One room of an xyzgrid map."""
    return GridTile.create(key="map tile", xyz=(x, y, zcoord))[0]


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestTargetTile(EvenniaTest):
    """Where a place on a map lands in the tile world."""

    def setUp(self):
        super().setUp()
        self.world = _world()

    def test_a_map_tile_keeps_its_place(self):
        tile = tile_cutover.target_tile(self.world, ("2", "2", _MAP), _RESPAWN)

        self.assertEqual(tile, _OPEN)

    def test_a_map_with_no_chunk_goes_to_the_respawn_point(self):
        tile = tile_cutover.target_tile(self.world, (2, 2, "neo_cairo"), _RESPAWN)

        self.assertEqual(tile, _RESPAWN)

    def test_a_blocked_tile_goes_to_the_respawn_point(self):
        tile = tile_cutover.target_tile(self.world, (*_BLOCKED, _MAP), _RESPAWN)

        self.assertEqual(tile, _RESPAWN)

    def test_a_chunk_that_is_not_loaded_goes_to_the_respawn_point(self):
        other = next(z for z, chunk in tile_cutover.MAP_CHUNKS.items()
                     if chunk != (0, 0))
        tile = tile_cutover.target_tile(self.world, (1, 1, other), _RESPAWN)

        self.assertEqual(tile, _RESPAWN)


class TestCutover(EvenniaTest):
    """The plan and the apply, on a small world and one map."""

    def setUp(self):
        super().setUp()
        self.world = _world()
        set_world(self.world)

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def _log_out_on(self, character, room):
        character.location = None
        character.db.prelogout_location = room

    def test_the_plan_needs_a_respawn_point(self):
        with self.assertRaises(tile_cutover.CutoverError):
            tile_cutover.plan(_world(with_respawn=False))

    def test_the_plan_changes_nothing(self):
        room = _map_room(*_OPEN)
        self.char1.move_to(room, quiet=True)

        tile_cutover.plan(self.world)

        self.assertEqual(self.char1.location, room)
        self.assertTrue(XYZRoom.objects.filter_family(id=room.id).exists())

    def test_an_online_character_moves_to_its_tile(self):
        self.char1.move_to(_map_room(*_OPEN), quiet=True)

        tile_cutover.apply(self.world, tile_cutover.plan(self.world))

        x, y, z = self.char1.location.xyz
        self.assertEqual((int(x), int(y)), _OPEN)
        self.assertEqual(z, self.world.world_z)

    def test_a_logged_out_character_gets_its_login_tile(self):
        self._log_out_on(self.char1, _map_room(*_OPEN))

        tile_cutover.apply(self.world, tile_cutover.plan(self.world))

        self.assertEqual(self.char1.attributes.get(PRELOGOUT_TILE_ATTR), list(_OPEN))
        self.assertIsNone(self.char1.db.prelogout_location)

    def test_a_character_on_a_map_home_gets_the_respawn_point(self):
        self.char1.home = _map_room(*_OPEN)

        tile_cutover.apply(self.world, tile_cutover.plan(self.world))

        self.assertEqual(tuple(int(v) for v in self.char1.home.xyz[:2]), _RESPAWN)

    def test_a_character_off_the_maps_stays(self):
        _map_room(*_OPEN)

        cutover = tile_cutover.plan(self.world)

        moved = [move.character for move in cutover.moves]
        self.assertNotIn(self.char1, moved)
        self.assertNotIn(self.char1, cutover.rehome)

    def test_every_map_room_goes_and_no_tile_room_does(self):
        _map_room(*_OPEN)
        _map_room(1, 1, "neo_cairo")
        tile_room = self.world.rooms.ensure_room(*_RESPAWN)

        tile_cutover.apply(self.world, tile_cutover.plan(self.world))

        remaining = list(XYZRoom.objects.filter_family())
        self.assertEqual(remaining, [tile_room])

    def test_the_grid_script_goes_without_a_read_of_its_maps(self):
        """The trap of world/maps/gridstate.py: an unreadable row."""
        grid = create_script(XYZGrid, key="XYZGrid")
        grid.db.map_data = "not a dict"

        tile_cutover.apply(self.world, tile_cutover.plan(self.world))

        self.assertEqual(XYZGrid.objects.filter_family().count(), 0)

    def test_a_second_run_finds_nothing(self):
        self.char1.move_to(_map_room(*_OPEN), quiet=True)
        tile_cutover.apply(self.world, tile_cutover.plan(self.world))

        self.assertTrue(tile_cutover.plan(self.world).is_empty())
