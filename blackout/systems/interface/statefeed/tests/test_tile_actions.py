"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: Tests for the tile affordances the server names.

             These replace rules that used to live in blackout3d.js's
             tileAction: which tile is a step, which is a walk, which is
             neither. Moving them here is the point -- the JavaScript had no
             test and its diagonal rule was wrong for a while, refusing exactly
             the tiles nearest the player.

             Built against stand-in rooms on a one-chunk tile world, with no
             database. The serializers read only the `xyz` of the room and the
             step rule of the world. The exit-based tests of the xyzgrid maps
             went with the maps in DESIGN-0011 Phase 4b.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.statefeed.tests.test_tile_actions
"""

import unittest
from types import SimpleNamespace

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid.world import TileWorld, set_world
from systems.interface.statefeed import constants as const
from systems.interface.statefeed import serializers
from world import tile_travel


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE

# Open ground, with one blocked tile east of the start.
_START = (10, 10)
_BLOCKED = (11, 10)


# ─── Private helper routines ─────────────────────────────────────────────────

def _world() -> TileWorld:
    """One chunk of open ground with one blocked tile. No database."""
    tile_count = _SIZE * _SIZE
    flags = [0] * tile_count
    flags[_BLOCKED[1] * _SIZE + _BLOCKED[0]] = tile_const.FLAG_BLOCKED
    chunk_file = chunkfile.ChunkFile(
        cx=0, cy=0, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=flags, areas=[0] * tile_count,
        objects=[])

    return TileWorld([chunk_file])


def _room(x: int, y: int, z: str = tile_const.WORLD_Z):
    """A stand-in room: only its coordinates. z=None is a room off the grid."""
    room = SimpleNamespace()

    if z is not None:
        room.xyz = (x, y, z)

    return room


# ─── Tests ───────────────────────────────────────────────────────────────────

class TileKeyTests(unittest.TestCase):
    """One spelling for a tile's key, on both sides of the wire."""

    def test_key_is_x_colon_y(self):
        self.assertEqual(serializers.tile_key(6, 3), "6:3")

    def test_negative_coordinates_survive(self):
        """
        Nothing keeps the world at x, y >= 0, and a key that mangled a
        negative would fail as a silently unclickable tile.
        """
        self.assertEqual(serializers.tile_key(-2, -1), "-2:-1")


class TileActionShapeTests(unittest.TestCase):
    """Every affordance is {command, kind}, with the command already whole."""

    def test_an_action_carries_a_command_and_a_kind(self):
        action = serializers.tile_action("north", const.TILE_ACTION_KIND_STEP)

        self.assertEqual(action, {
            "command": "north", "kind": const.TILE_ACTION_KIND_STEP})

    def test_cancel_is_bare_goto(self):
        action = serializers.cancel_action()

        self.assertEqual(action["command"], const.TILE_COMMAND_GOTO)
        self.assertEqual(action["kind"], const.TILE_ACTION_KIND_CANCEL)


class TileActionsTests(unittest.TestCase):
    """What the tiles near the observer afford, from where they stand."""

    def setUp(self):
        self.world = _world()
        set_world(self.world)

    def tearDown(self):
        set_world(None)

    def test_the_observers_own_tile_affords_look(self):
        actions = serializers.tile_actions(_room(*_START))
        own = actions[serializers.tile_key(*_START)]

        self.assertEqual(own["command"], const.TILE_COMMAND_LOOK)
        self.assertEqual(own["kind"], const.TILE_ACTION_KIND_LOOK)

    def test_each_legal_step_is_a_goto_of_that_one_tile(self):
        # Not the direction word: a direction is one tick of movement, and a
        # run moves two tiles a tick. A click on the next tile moves one.
        actions = serializers.tile_actions(_room(*_START))

        for name in tile_travel.open_directions(self.world, _START):
            dx, dy = tile_const.DIRECTION_OFFSETS[name]
            x, y = _START[0] + dx, _START[1] + dy
            command = const.TILE_COMMAND_GOTO_TEMPLATE.format(x=x, y=y)

            with self.subTest(direction=name):
                self.assertEqual(
                    actions[serializers.tile_key(x, y)],
                    serializers.tile_action(command,
                                            const.TILE_ACTION_KIND_STEP))

    def test_a_blocked_neighbour_affords_nothing(self):
        actions = serializers.tile_actions(_room(*_START))

        self.assertNotIn(serializers.tile_key(*_BLOCKED), actions)

    def test_the_map_stays_small(self):
        """The own tile and at most eight steps. A far tile is the client's
        TILE_WALK_TEMPLATE, never an entry here."""
        actions = serializers.tile_actions(_room(*_START))

        self.assertLessEqual(len(actions), 9)

    def test_every_kind_is_a_declared_constant(self):
        """
        The kinds are generated into the client. A kind produced here that is
        not one of the exported names would reach a client that has no branch
        for it, and the click would silently do nothing.
        """
        known = {
            const.TILE_ACTION_KIND_STEP,
            const.TILE_ACTION_KIND_WALK,
            const.TILE_ACTION_KIND_LOOK,
            const.TILE_ACTION_KIND_CANCEL,
        }
        produced = list(serializers.tile_actions(_room(*_START)).values())
        produced.append(serializers.cancel_action())

        for action in produced:
            with self.subTest(action=action):
                self.assertIn(action["kind"], known)

    def test_a_room_off_the_grid_affords_nothing(self):
        self.assertEqual(serializers.tile_actions(_room(0, 0, z=None)), {})

    def test_a_missing_room_affords_nothing(self):
        self.assertEqual(serializers.tile_actions(None), {})

    def test_a_room_of_another_z_affords_only_look(self):
        actions = serializers.tile_actions(_room(*_START, z="some_other_z"))

        self.assertEqual(list(actions), [serializers.tile_key(*_START)])
