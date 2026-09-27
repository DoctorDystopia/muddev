"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/26/2026
Description: Tests for planes on the tile world (DESIGN-0011 Phase 7, step
             7a): `climb`, a walk on plane 1, the login plane, `tiletp` with
             a plane, the room text, the tile action, and the readers that
             must not mix two planes.

             The world is built in memory: open ground on plane 0, and a
             short corridor on plane 1 over it. Everything else on plane 1
             is blocked, as an upper floor covers only its building.
"""

from types import SimpleNamespace
from unittest import mock

from evennia.utils.create import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from systems.gameplay.combat import reach
from systems.interface.statefeed import neighbourhood
from systems.interface.statefeed import serializers
from world import tile_travel


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE
_GROUND = tile_const.GROUND_PLANE
_UPPER = tile_const.GROUND_PLANE + 1

# The ladder: up from plane 0, down from plane 1, on the same tile.
_LADDER = (10, 10)

# The corridor of plane 1: the ladder tile and the three tiles east of it.
_CORRIDOR = [(x, 10) for x in range(10, 14)]
_CORRIDOR_END = (13, 10)

# A ladder up whose landing on plane 1 is blocked.
_DEAD_LADDER = (20, 20)

# A tile of plane 0 with nothing to climb.
_PLAIN = (5, 5)

_RADIUS = 5


# ─── Private helper routines ─────────────────────────────────────────────────

def _chunk(plane: int, open_tiles, objects: list) -> chunkfile.ChunkFile:
    """
    One chunk (0, 0) on a plane. `open_tiles` None means all open. Else
    every tile is blocked but those.
    """
    tile_count = _SIZE * _SIZE
    closed = open_tiles is not None
    flags = [tile_const.FLAG_BLOCKED if closed else 0] * tile_count

    for x, y in open_tiles or ():
        flags[y * _SIZE + x] = 0

    return chunkfile.ChunkFile(
        cx=0, cy=0, plane=plane, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=flags, areas=[0] * tile_count,
        objects=objects)


def _world() -> TileWorld:
    ground = _chunk(_GROUND, None, [
        chunkfile.ChunkObject("ladder_up", *_LADDER),
        chunkfile.ChunkObject("ladder_up", *_DEAD_LADDER),
    ])
    upper = _chunk(_UPPER, _CORRIDOR,
                   [chunkfile.ChunkObject("ladder_down", *_LADDER)])
    world = TileWorld([ground, upper])
    world.load_rooms()

    return world


def _run_now(_seconds, callback, *args):
    """Stand in for `delay`: run the callback at once."""
    callback(*args)

    return SimpleNamespace(active=lambda: False, cancel=lambda: None)


# ─── Tests ───────────────────────────────────────────────────────────────────

class _PlaneTestBase(EvenniaTest):

    def setUp(self):
        super().setUp()
        self.world = _world()
        set_world(self.world)
        movement.place(self.world.rooms, self.char1, *_LADDER, quiet=True)
        self.char1.msg = mock.Mock()

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def _where(self):
        return (tile_travel.tile_of(self.char1),
                tile_travel.plane_of(self.char1))

    def _said(self) -> str:
        texts = [str(call.args[0]) if call.args else str(call.kwargs)
                 for call in self.char1.msg.call_args_list]

        return " ".join(texts).lower()

    def _go_up(self):
        self.char1.execute_cmd("climb up")
        self.char1.msg.reset_mock()


class ClimbTests(_PlaneTestBase):

    def test_climb_up_lands_on_the_same_tile_one_plane_up(self):
        self.char1.execute_cmd("climb up")

        self.assertEqual(self._where(), (_LADDER, _UPPER))
        self.assertIn("climb up", self._said())

    def test_the_only_way_needs_no_word(self):
        self.char1.execute_cmd("climb")

        self.assertEqual(self._where(), (_LADDER, _UPPER))

    def test_climb_down_returns_to_the_ground(self):
        self._go_up()
        self.char1.execute_cmd("climb down")

        self.assertEqual(self._where(), (_LADDER, _GROUND))

    def test_nothing_to_climb_says_so(self):
        movement.place(self.world.rooms, self.char1, *_PLAIN, quiet=True)
        self.char1.execute_cmd("climb up")

        self.assertEqual(self._where(), (_PLAIN, _GROUND))
        self.assertIn("nothing to climb", self._said())

    def test_a_ladder_up_does_not_go_down(self):
        self.char1.execute_cmd("climb down")

        self.assertEqual(self._where(), (_LADDER, _GROUND))
        self.assertIn("does not go", self._said())

    def test_a_blocked_landing_refuses_the_climb(self):
        movement.place(self.world.rooms, self.char1, *_DEAD_LADDER,
                       quiet=True)
        self.char1.execute_cmd("climb up")

        self.assertEqual(self._where(), (_DEAD_LADDER, _GROUND))
        self.assertIn("blocked", self._said())


class WalkOnAPlaneTests(_PlaneTestBase):

    def test_a_step_reads_the_grid_of_its_own_plane(self):
        # West of the ladder is open ground on plane 0 and blocked on
        # plane 1.
        self._go_up()
        self.char1.execute_cmd("west")

        self.assertEqual(self._where(), (_LADDER, _UPPER))

        self.char1.execute_cmd("east")

        self.assertEqual(self._where(), ((_LADDER[0] + 1, _LADDER[1]), _UPPER))

    def test_goto_walks_on_the_plane_of_the_walker(self):
        self._go_up()

        with mock.patch("commands.tile_movement.delay", _run_now):
            self.char1.execute_cmd("goto (%d,%d)" % _CORRIDOR_END)

        self.assertEqual(self._where(), (_CORRIDOR_END, _UPPER))

    def test_goto_off_the_corridor_finds_no_way(self):
        self._go_up()
        self.char1.execute_cmd("goto (%d,%d)" % _PLAIN)

        self.assertEqual(self._where(), (_LADDER, _UPPER))
        self.assertIn("cannot find a way", self._said())

    def test_a_login_returns_to_the_plane(self):
        self._go_up()
        self.char1._remember_tile()
        self.char1.location = None
        self.char1.db.prelogout_location = None

        self.char1.at_pre_puppet(self.account)

        self.assertEqual(self.char1.db.prelogout_location.xyz[2],
                         self.world.plane(_UPPER).world_z)

    def test_tiletp_takes_a_plane(self):
        self.char1.permissions.add("Builder")
        self.char1.execute_cmd("tiletp %d,%d,%d" % (*_CORRIDOR_END, _UPPER))

        self.assertEqual(self._where(), (_CORRIDOR_END, _UPPER))

    def test_tiletp_refuses_a_plane_past_the_top(self):
        self.char1.permissions.add("Builder")
        self.char1.execute_cmd("tiletp %d,%d,%d" % (*_LADDER,
                                                   tile_const.PLANE_MAX + 1))

        self.assertEqual(self._where(), (_LADDER, _GROUND))
        self.assertIn("no plane", self._said())


class PlaneReaderTests(_PlaneTestBase):

    def test_look_on_plane_one_names_the_ladder_and_the_plane(self):
        self._go_up()
        self.char1.execute_cmd("look")

        self.assertIn("ladder", self._said())
        self.assertIn("plane 1", self._said())

    def test_the_tile_action_on_a_ladder_is_the_climb(self):
        actions = serializers.tile_actions(self.char1.location)
        mine = actions[serializers.tile_key(*_LADDER)]

        self.assertEqual(mine["command"], "climb " + tile_const.CLIMB_UP)

    def test_a_figure_one_plane_down_is_not_near(self):
        below = self.char1.location
        self._go_up()

        near = neighbourhood.visible_rooms(self.char1.location, _RADIUS)

        self.assertIn(self.char1.location, near)
        self.assertNotIn(below, near)

    def test_no_reach_and_no_walk_across_planes(self):
        target = create_object("typeclasses.objects.Object", key="dummy")
        movement.place(self.world.rooms, target, *_LADDER, quiet=True)
        self._go_up()

        self.assertFalse(reach.can_strike(self.char1, target, _RADIUS))
        self.assertIsNone(
            reach.nearest_tile_in_reach(self.char1, target, _RADIUS))

    def test_the_sweep_covers_every_plane(self):
        upper = self.world.plane(_UPPER)
        empty = upper.rooms.ensure_room(*_CORRIDOR_END)

        self.world.sweep_rooms()

        self.assertIsNone(upper.rooms.room_at(*_CORRIDOR_END))
        self.assertNotEqual(empty.xyz[2], upper.world_z)
