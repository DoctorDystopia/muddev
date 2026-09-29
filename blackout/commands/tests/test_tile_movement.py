"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for movement on the tile world: the direction commands,
             a transition, the `goto` walk, and the run. The world is two
             chunks, built in memory. No tick engine runs: a test moves the
             walkers with `walk.advance_all`, one call for each tick.
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from systems.gameplay.movement import constants as walk_const
from systems.gameplay.movement import walk
from world import tile_text
from world.object_kinds import OBJECT_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE

_START = (10, 10)

# A wall on the north edge of this tile, and a blocked tile east of the start.
_WALLED = (20, 20)
_BLOCKED = (11, 10)

# The tile of the transition, and of a named kind.
_TRANSITION_TILE = (10, 12)
_NAMED_TILE = (30, 30)

_TRANSITION = next(key for key, kind in OBJECT_KINDS.items()
                   if kind.category == tile_const.OBJECT_CATEGORY_TRANSITION)
_NAMED = next(key for key, kind in OBJECT_KINDS.items() if kind.name)


# ─── Private helper routines ─────────────────────────────────────────────────

def _chunk(cx: int, cy: int, flags: dict, objects: list):
    """One chunk file: open ground, with flags by local tile."""
    tile_count = _SIZE * _SIZE
    grid_flags = [0] * tile_count

    for (x, y), bits in flags.items():
        grid_flags[y * _SIZE + x] = bits

    return chunkfile.ChunkFile(
        cx=cx, cy=cy, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=grid_flags, areas=[0] * tile_count,
        objects=objects)


def _world() -> TileWorld:
    """The chunk of the start, and the chunk of the transition target."""
    target = OBJECT_KINDS[_TRANSITION].target
    target_chunk = (target[0] // _SIZE, target[1] // _SIZE)
    home = _chunk(0, 0,
                  {_WALLED: tile_const.FLAG_WALL_NORTH,
                   _BLOCKED: tile_const.FLAG_BLOCKED},
                  [chunkfile.ChunkObject(_TRANSITION, *_TRANSITION_TILE),
                   chunkfile.ChunkObject(_NAMED, *_NAMED_TILE)])
    files = [home]

    if target_chunk != (0, 0):
        files.append(_chunk(target_chunk[0], target_chunk[1], {}, []))

    world = TileWorld(files)
    world.rooms.load()

    return world


# More ticks than any walk of these tests takes.
_TICK_CAP = 200


def _tick(count: int = 1) -> None:
    """Move every walker for `count` ticks."""
    for _ in range(count):
        walk.advance_all()


def _walk_out() -> int:
    """Tick until no walk is left. Return the number of ticks."""
    for ticks in range(_TICK_CAP):
        if not walk.walker_count():
            return ticks

        walk.advance_all()

    raise AssertionError("a walk did not end")


# ─── Tests ───────────────────────────────────────────────────────────────────

class TileMovementTests(EvenniaTest):

    def setUp(self):
        super().setUp()
        self.world = _world()
        set_world(self.world)
        movement.place(self.world.rooms, self.char1, *_START, quiet=True)
        self.char1.msg = mock.Mock()

    def tearDown(self):
        walk.forget_all()
        set_world(None)
        super().tearDown()

    def _tile(self):
        x, y, _z = self.char1.location.xyz

        return (int(x), int(y))

    def _said(self) -> str:
        texts = [str(call.args[0]) if call.args else str(call.kwargs)
                 for call in self.char1.msg.call_args_list]

        return " ".join(texts).lower()

    def test_each_direction_and_alias_moves_one_tile(self):
        for name, offset in tile_const.DIRECTION_OFFSETS.items():
            for word in (name, tile_const.DIRECTION_ALIASES[name]):
                with self.subTest(word=word):
                    movement.place(self.world.rooms, self.char1, 40, 40,
                                   quiet=True)
                    self.char1.execute_cmd(word)
                    _tick()
                    self.assertEqual(self._tile(),
                                     (40 + offset[0], 40 + offset[1]))

    def test_a_blocked_tile_refuses_the_step(self):
        self.char1.execute_cmd("east")

        self.assertEqual(self._tile(), _START)
        self.assertIn("blocks", self._said())

    def test_a_wall_refuses_the_step(self):
        movement.place(self.world.rooms, self.char1, *_WALLED, quiet=True)
        self.char1.execute_cmd("north")

        self.assertEqual(self._tile(), _WALLED)
        self.assertIn("wall", self._said())

    def test_a_step_onto_a_transition_lands_on_its_target(self):
        self.char1.execute_cmd("north")
        _tick()
        self.char1.execute_cmd("north")
        _tick()

        self.assertEqual(self._tile(),
                         tuple(OBJECT_KINDS[_TRANSITION].target))

    def test_goto_a_coordinate_walks_there(self):
        goal = (_START[0] - 3, _START[1] - 5)

        self.char1.execute_cmd("goto (%d,%d)" % goal)
        _walk_out()

        self.assertEqual(self._tile(), goal)
        self.assertIn("reached", self._said())

    def test_goto_a_name_walks_to_the_named_tile(self):
        name = tile_text.tile_name([_NAMED], None)

        self.char1.execute_cmd("goto %s" % name.lower())
        _walk_out()

        self.assertEqual(self._tile(), _NAMED_TILE)

    def test_goto_then_runs_the_follow_up_on_arrival(self):
        goal = (_START[0], _START[1] - 2)

        with mock.patch.object(self.char1, "execute_cmd",
                               wraps=self.char1.execute_cmd) as typed:
            self.char1.execute_cmd("goto (%d,%d) then look" % goal)
            _walk_out()

        lines = [call.args[0] for call in typed.call_args_list]
        self.assertEqual(lines[-1], "look")

    def test_goto_an_unknown_name_says_so(self):
        self.char1.execute_cmd("goto no such place anywhere")

        self.assertEqual(self._tile(), _START)
        self.assertIn("no place", self._said())

    def test_goto_a_tile_with_no_way_there_says_so(self):
        self.char1.execute_cmd("goto (%d,%d)" % _BLOCKED)

        self.assertEqual(self._tile(), _START)
        self.assertIn("cannot find a way", self._said())


class WalkAndRunTests(EvenniaTest):
    """The tick moves every step: a held key, a click, and a run."""

    def setUp(self):
        super().setUp()
        self.world = _world()
        set_world(self.world)
        movement.place(self.world.rooms, self.char1, *_START, quiet=True)
        self.char1.msg = mock.Mock()

    def tearDown(self):
        walk.forget_all()
        set_world(None)
        super().tearDown()

    def _tile(self):
        x, y, _z = self.char1.location.xyz

        return (int(x), int(y))

    def _said(self) -> str:
        return " ".join(str(call.args[0]) for call in
                        self.char1.msg.call_args_list if call.args).lower()

    def _west(self, tiles: int) -> tuple:
        return (_START[0] - tiles, _START[1])

    def test_a_direction_waits_for_the_tick(self):
        self.char1.execute_cmd("west")

        self.assertEqual(self._tile(), _START)
        _tick()
        self.assertEqual(self._tile(), self._west(1))

    def test_a_held_key_does_not_stack_its_steps(self):
        # The client sends a held key two times a tick.
        self.char1.execute_cmd("west")
        self.char1.execute_cmd("west")
        _tick(3)

        self.assertEqual(self._tile(), self._west(1))

    def test_a_run_moves_two_tiles_each_tick(self):
        walk.set_running(self.char1, True)
        self.char1.execute_cmd("west")
        _tick()

        self.assertEqual(self._tile(),
                         self._west(walk_const.RUN_TILES_PER_TICK))

    def test_a_run_skips_the_middle_tile(self):
        walk.set_running(self.char1, True)

        with mock.patch.object(self.char1, "move_to",
                               wraps=self.char1.move_to) as moved:
            self.char1.execute_cmd("west")
            _tick()

        self.assertEqual(moved.call_count, 1)
        self.assertEqual(self._tile(), self._west(2))

    def test_a_goto_runs_two_tiles_a_tick_and_ends_with_one(self):
        walk.set_running(self.char1, True)
        self.char1.execute_cmd("goto (%d,%d)" % self._west(5))

        self.assertEqual(_walk_out(), 3)
        self.assertEqual(self._tile(), self._west(5))

    def test_a_walk_and_a_held_key_have_one_speed(self):
        self.char1.execute_cmd("goto (%d,%d)" % self._west(4))

        self.assertEqual(_walk_out(), 4)

    def test_a_click_on_the_next_tile_moves_one_tile_with_run_on(self):
        walk.set_running(self.char1, True)
        self.char1.execute_cmd("goto (%d,%d)" % self._west(1))
        _walk_out()

        self.assertEqual(self._tile(), self._west(1))
        self.assertNotIn("reached", self._said())

    def test_a_run_into_a_block_stops_after_one_tile(self):
        # The blocked tile is east of the start. Two tiles west of it, a run
        # east has room for one tile only.
        movement.place(self.world.rooms, self.char1, *self._west(1),
                       quiet=True)
        walk.set_running(self.char1, True)
        self.char1.execute_cmd("east")
        _tick()

        self.assertEqual(self._tile(), _START)

    def test_a_direction_replaces_a_goto_walk(self):
        self.char1.execute_cmd("goto (%d,%d)" % self._west(6))
        _tick()
        x, y = self._tile()
        self.char1.execute_cmd("south")
        _tick(3)

        self.assertEqual(self._tile(), (x, y - 1))
        self.assertIsNone(walk.current(self.char1))

    def test_a_refusal_says_it_one_time_for_a_held_key(self):
        self.char1.execute_cmd("east")
        self.char1.execute_cmd("east")

        self.assertEqual(self._said().count("blocks"), 1)

    def test_a_walker_that_fails_does_not_stop_the_others(self):
        movement.place(self.world.rooms, self.char2, *self._west(3),
                       quiet=True)
        self.char1.execute_cmd("west")
        walk.set_walk(self.char2, walk.TileWalk(path=[self._west(4)],
                                                goal=self._west(4)))
        real_advance = walk.advance

        def _advance(character):
            if character is self.char2:
                raise RuntimeError("a broken walker")

            real_advance(character)

        with mock.patch.object(walk, "advance", _advance), \
                mock.patch.object(walk.logger, "log_trace"):
            walk.advance_all()

        self.assertEqual(self._tile(), self._west(1))
        self.assertIsNone(walk.current(self.char2))

    def test_run_turns_the_toggle_each_way(self):
        self.char1.execute_cmd("run")
        self.assertTrue(walk.is_running(self.char1))

        self.char1.execute_cmd("run")
        self.assertFalse(walk.is_running(self.char1))

        self.char1.execute_cmd("run on")
        self.assertTrue(walk.is_running(self.char1))

        self.char1.execute_cmd("run off")
        self.assertFalse(walk.is_running(self.char1))

    def test_run_with_a_bad_word_changes_nothing(self):
        self.char1.execute_cmd("run fast")

        self.assertFalse(walk.is_running(self.char1))
        self.assertIn("usage", self._said())


class TileLogoutTests(EvenniaTest):

    def setUp(self):
        super().setUp()
        self.world = _world()
        set_world(self.world)
        movement.place(self.world.rooms, self.char1, *_START, quiet=True)

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def test_a_login_lands_on_the_tile_even_after_the_room_moved(self):
        room = self.char1.location
        self.char1._remember_tile()
        self.char1.db.prelogout_location = room
        self.char1.location = None

        # Another walker empties the tile: the room goes to the pool, then
        # the pool gives it to a different tile.
        self.world.rooms.release(room)
        elsewhere = self.world.rooms.ensure_room(40, 40)
        self.assertIs(elsewhere, room)

        self.char1.at_pre_puppet(self.account)
        x, y, _z = self.char1.location.xyz

        self.assertEqual((int(x), int(y)), _START)


class TileTeleportTests(EvenniaTest):

    def setUp(self):
        super().setUp()
        self.world = _world()
        set_world(self.world)
        self.char1.msg = mock.Mock()
        self.char1.permissions.add("Builder")

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def _said(self) -> str:
        return " ".join(str(call.args[0]) for call in
                        self.char1.msg.call_args_list if call.args).lower()

    def test_a_builder_lands_on_a_walkable_tile(self):
        self.char1.execute_cmd("tiletp 12,12")
        x, y, z = self.char1.location.xyz

        self.assertEqual((int(x), int(y), z),
                         (12, 12, self.world.world_z))

    def test_a_blocked_tile_is_refused(self):
        start = self.char1.location
        self.char1.execute_cmd("tiletp %d,%d" % _BLOCKED)

        self.assertIs(self.char1.location, start)
        self.assertIn("blocked", self._said())

    def test_a_tile_off_the_world_is_refused(self):
        start = self.char1.location
        self.char1.execute_cmd("tiletp 9000,9000")

        self.assertIs(self.char1.location, start)
        self.assertIn("no chunk", self._said())


class OffTileWorldTests(EvenniaTest):

    def test_a_direction_with_no_exit_says_no_way(self):
        self.char1.msg = mock.Mock()
        self.char1.execute_cmd("northwest")

        said = " ".join(str(call.args[0]) for call in
                        self.char1.msg.call_args_list if call.args)
        self.assertIn("cannot go that way", said.lower())

    def test_goto_off_the_tile_world_says_no_way(self):
        # A character in Limbo has no tile. The search used to get None as
        # its start and raise.
        self.char1.msg = mock.Mock()
        self.char1.execute_cmd("goto (4,7)")

        said = " ".join(str(call.args[0]) for call in
                        self.char1.msg.call_args_list if call.args)
        self.assertIn("cannot find a way", said.lower())
