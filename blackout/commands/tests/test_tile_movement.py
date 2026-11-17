"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for movement on the tile world: the direction commands,
             a transition, the `goto` walk, the run, and the speed with a
             tile bonus (11/14/2026). The world is two chunks, built in
             memory. No tick engine runs: a test moves the
             walkers with `walk.advance_all`, one call for each tick.
"""

from fractions import Fraction
from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import rules as augmentation_rules
from systems.gameplay.augmentation.handler import ensure_augment_handler
from systems.gameplay.augmentation.registry import augments_in_order
from systems.gameplay.movement import constants as walk_const
from systems.gameplay.movement import walk
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed_events
from typeclasses.characters import Character as BlackoutCharacter
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

# A tile 4 tiles east of _BLOCKED. A `goto` to _BLOCKED from here walks to
# the nearest tile that a walk reaches, as in OSRS.
_EAST_OF_BLOCKED = (_BLOCKED[0] + 4, _BLOCKED[1])

# A tile so far off the world that the search reaches no tile near it.
_FAR_OFF_GRID = (-_SIZE * 100, _START[1])

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

    def _moments(self, *lines) -> list:
        """Type each line and move one tick. Return the moments sent."""
        with mock.patch.object(feed_events, "emit_moment") as emitted:
            for line in lines:
                self.char1.execute_cmd(line)
                _tick()

        return [call.args for call in emitted.call_args_list]

    def test_a_step_onto_a_transition_sends_its_moment(self):
        """The client plays the transition sound one time."""
        moments = self._moments("north", "north")

        self.assertEqual(moments,
                         [(self.char1, feed_const.MOMENT_TRANSITION)])

    def test_a_run_onto_a_transition_sends_its_moment(self):
        walk.set_running(self.char1, True)

        moments = self._moments("north")

        self.assertEqual(self._tile(),
                         tuple(OBJECT_KINDS[_TRANSITION].target))
        self.assertEqual(moments,
                         [(self.char1, feed_const.MOMENT_TRANSITION)])

    def test_a_step_with_no_transition_sends_no_moment(self):
        moments = self._moments("west", "west")

        self.assertEqual(moments, [])

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

    def test_goto_a_tile_with_no_tile_near_it_says_so(self):
        self.char1.execute_cmd("goto (%d,%d)" % _FAR_OFF_GRID)

        self.assertEqual(self._tile(), _START)
        self.assertIn("cannot find a way", self._said())

    def test_goto_a_blocked_tile_walks_next_to_it(self):
        # The OSRS rule: the walk ends on the nearest tile that it reaches.
        movement.place(self.world.rooms, self.char1, *_EAST_OF_BLOCKED,
                       quiet=True)
        self.char1.execute_cmd("goto (%d,%d)" % _BLOCKED)
        _walk_out()
        here = self._tile()

        self.assertEqual(max(abs(here[0] - _BLOCKED[0]),
                             abs(here[1] - _BLOCKED[1])), 1)
        self.assertIn("as close", self._said())
        self.assertNotIn("reached", self._said())

    def test_goto_a_blocked_tile_from_its_side_stays(self):
        # _START is next to _BLOCKED and is the nearest reached tile.
        self.char1.execute_cmd("goto (%d,%d)" % _BLOCKED)
        _walk_out()

        self.assertEqual(self._tile(), _START)
        self.assertIn("as close", self._said())

    def test_a_short_walk_skips_its_follow_up_and_says_so(self):
        movement.place(self.world.rooms, self.char1, *_EAST_OF_BLOCKED,
                       quiet=True)

        with mock.patch.object(self.char1, "execute_cmd",
                               wraps=self.char1.execute_cmd) as typed:
            self.char1.execute_cmd("goto (%d,%d) then look" % _BLOCKED)
            _walk_out()

        lines = [call.args[0] for call in typed.call_args_list]
        self.assertNotIn("look", lines)
        self.assertIn("cannot reach", self._said())
        self.assertNotEqual(self._tile(), _EAST_OF_BLOCKED)


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

    def _paced_goto(self, pace: str, tile: tuple) -> None:
        """Type the paced walk that a Ctrl + left click sends."""
        self.char1.execute_cmd(feed_const.TILE_COMMAND_GOTO_PACED_TEMPLATE
                               .format(pace=pace, x=tile[0], y=tile[1]))

    def test_a_walk_switch_walks_with_run_on(self):
        walk.set_running(self.char1, True)
        self._paced_goto(feed_const.GOTO_PACE_WALK, self._west(4))

        self.assertEqual(_walk_out(), 4)
        self.assertEqual(self._tile(), self._west(4))
        self.assertTrue(walk.is_running(self.char1))

    def test_a_run_switch_runs_with_run_off(self):
        self._paced_goto(feed_const.GOTO_PACE_RUN, self._west(4))

        self.assertEqual(_walk_out(), 2)
        self.assertEqual(self._tile(), self._west(4))
        self.assertFalse(walk.is_running(self.char1))

    def _tiles_left(self) -> int:
        return len(walk.current(self.char1).path)

    def test_the_run_toggle_ends_the_pace_of_a_walk(self):
        # Run on, then a walk. The walk takes one tile. Then run goes off
        # and on again: the newest command wins, so the walk runs. A* can
        # start with a diagonal, so this counts the tiles left on the path.
        walk.set_running(self.char1, True)
        self._paced_goto(feed_const.GOTO_PACE_WALK, self._west(5))
        start = self._tiles_left()
        _tick()

        self.assertEqual(self._tiles_left(),
                         start - walk_const.WALK_TILES_PER_TICK)

        self.char1.execute_cmd("run off")
        self.char1.execute_cmd("run on")
        before = self._tiles_left()
        _tick()

        self.assertEqual(self._tiles_left(),
                         before - walk_const.RUN_TILES_PER_TICK)

    def test_a_switch_that_is_not_a_pace_starts_nothing(self):
        self.char1.execute_cmd("goto/fly (%d,%d)" % self._west(4))

        self.assertIsNone(walk.current(self.char1))
        self.assertIn("usage", self._said())


# The tile bonus of the speed tests: a third of a tile, as Nitro gives at
# power level 1 of 3. The walk rule holds for any part, so the number is the
# test's own, not a read of the augment.
_PARTS = 3
_PART_OF_A_TILE = Fraction(1, _PARTS)

# Far more tiles than the speed cap, for the cap test.
_A_HUGE_BONUS = Fraction(walk_const.MAX_TILES_PER_TICK * 2)


class SpeedTests(EvenniaTest):
    """
    The tile bonus, the speed cap, and the tile carry (11/14/2026). The
    tests patch the tile bonus of the augmentation rules, so they prove the
    walk alone. NitroWalkTests lights a real Nitro.
    """

    def setUp(self):
        super().setUp()
        self.world = _world()
        set_world(self.world)
        movement.place(self.world.rooms, self.char1, *_START, quiet=True)
        self.char1.msg = mock.Mock()
        walk.set_running(self.char1, True)

    def tearDown(self):
        walk.forget_all()
        set_world(None)
        super().tearDown()

    def _tile(self):
        x, y, _z = self.char1.location.xyz

        return (int(x), int(y))

    def _west(self, tiles: int) -> tuple:
        return (_START[0] - tiles, _START[1])

    def _bonus(self, tiles):
        return mock.patch.object(augmentation_rules, "tile_bonus", return_value=tiles)

    def _held_west(self, ticks: int) -> list:
        """Hold the west key for `ticks` ticks. Return the tile after each."""
        tiles = []

        for _ in range(ticks):
            self.char1.execute_cmd("west")
            _tick()
            tiles.append(self._tile())

        return tiles

    def test_a_whole_bonus_adds_its_tiles_to_each_tick(self):
        bonus = Fraction(1)
        expected = min(walk_const.RUN_TILES_PER_TICK + bonus, walk_const.MAX_TILES_PER_TICK)

        with self._bonus(bonus):
            self.char1.execute_cmd("west")
            _tick()

        self.assertEqual(self._tile(), self._west(int(expected)))

    def test_the_speed_stops_at_the_cap(self):
        with self._bonus(_A_HUGE_BONUS):
            self.assertEqual(walk.speed(self.char1), walk_const.MAX_TILES_PER_TICK)
            tiles = self._held_west(1)

        self.assertEqual(tiles, [self._west(walk_const.MAX_TILES_PER_TICK)])

    def test_a_goto_takes_a_part_of_a_tile_as_a_whole_tile_later(self):
        # A* can start with a diagonal, so this counts the tiles walked.
        run = walk_const.RUN_TILES_PER_TICK
        expected = [tick * run + tick // _PARTS for tick in range(1, _PARTS + 1)]

        with self._bonus(_PART_OF_A_TILE):
            self.char1.execute_cmd("goto (%d,%d)" % self._west(9))
            start = len(walk.current(self.char1).path)
            walked = []

            for _ in range(_PARTS):
                _tick()
                walked.append(start - len(walk.current(self.char1).path))

        self.assertEqual(walked, expected)

    def test_a_held_key_keeps_the_carry_across_its_walks(self):
        # A held key makes a new walk two times a tick. The carry lives on
        # the character, so the part of a tile still adds up.
        run = walk_const.RUN_TILES_PER_TICK
        expected = [self._west(tick * run + tick // _PARTS) for tick in range(1, _PARTS + 1)]

        with self._bonus(_PART_OF_A_TILE):
            tiles = self._held_west(_PARTS)

        self.assertEqual(tiles, expected)

    def test_a_whole_speed_clears_the_carry(self):
        # Fill the carry to one part short of a tile. A tick with no bonus
        # clears it, so the next tick with the bonus gives no extra tile.
        run = walk_const.RUN_TILES_PER_TICK

        with self._bonus(_PART_OF_A_TILE):
            self._held_west(_PARTS - 1)

        with self._bonus(Fraction(0)):
            self._held_west(1)

        with self._bonus(_PART_OF_A_TILE):
            tiles = self._held_west(1)

        self.assertEqual(tiles, [self._west((_PARTS + 1) * run)])

    def test_a_direction_line_covers_the_part_of_a_tile(self):
        with self._bonus(_PART_OF_A_TILE):
            self.char1.execute_cmd("west")

        line = walk.current(self.char1).path

        self.assertEqual(len(line), walk_const.RUN_TILES_PER_TICK + 1)


class NitroWalkTests(EvenniaTest):
    """A real Nitro, lit at the top power level, on a run (Nick, 11/14/2026)."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.world = _world()
        set_world(self.world)
        movement.place(self.world.rooms, self.char1, *_START, quiet=True)
        self.char1.msg = mock.Mock()
        self.handler = ensure_augment_handler(self.char1)
        self.nitro = next(augment for augment in augments_in_order()
                          if augment.modifies == aug_const.MODIFIES_SPEED)

    def tearDown(self):
        self.handler.stop_handler()
        walk.forget_all()
        set_world(None)
        super().tearDown()

    def _tile(self):
        x, y, _z = self.char1.location.xyz

        return (int(x), int(y))

    def test_a_run_with_nitro_at_the_top_power_level_reaches_its_speed(self):
        self.handler.light(self.nitro, aug_const.AUG_POWER_LEVELS)
        walk.set_running(self.char1, True)
        top = self.nitro.tiles_for(aug_const.AUG_POWER_LEVELS)
        expected = min(walk_const.RUN_TILES_PER_TICK + top, walk_const.MAX_TILES_PER_TICK)

        self.char1.execute_cmd("west")
        _tick()

        self.assertEqual(self._tile(), (_START[0] - int(expected), _START[1]))

    def test_a_put_out_nitro_runs_at_run_speed_again(self):
        self.handler.light(self.nitro, aug_const.AUG_POWER_LEVELS)
        self.handler.put_out(self.nitro.key)
        walk.set_running(self.char1, True)

        self.char1.execute_cmd("west")
        _tick()

        self.assertEqual(self._tile(), (_START[0] - walk_const.RUN_TILES_PER_TICK, _START[1]))


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
