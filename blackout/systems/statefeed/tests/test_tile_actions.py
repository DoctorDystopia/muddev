"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: Tests for the tile affordances the server now names.

             These replace rules that used to live in blackout3d.js's
             tileAction: which tile is a step, which is a walk, which is
             neither. Moving them here is the point -- the JavaScript had no
             test and its diagonal rule was wrong for a while, refusing exactly
             the tiles nearest the player.

             Built against stand-in rooms, in the style of test_mapexport.py.
             The serializers read only `exits`, `xyz` and each exit's
             `destination`, so a stand-in exercises every branch without
             coupling these assertions to the shape of the oasis.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.statefeed.tests.test_tile_actions
"""

import unittest
from types import SimpleNamespace

from systems.statefeed import constants as const
from systems.statefeed import serializers


# ─── Private helper routines ─────────────────────────────────────────────────

def _room(x=0, y=0, z="oasis", exits=()):
    """
    Purpose: Return a stand-in room carrying coordinates and exits.

    Entry:
        x, y, z - the room's grid position. Pass z=None for a room off-grid.
        exits   - an iterable of stand-in exit objects.

    Exit/Returns:
        A SimpleNamespace shaped like the parts of a room the serializers read.

    Module Globals:
        None

    Methodology:
        `xyz` is what serializers.room_coords reads. A room off the grid simply
        has no `xyz`, which is the real behaviour for a non-XYZRoom.

    Notes/References:
        None
    """
    room = SimpleNamespace(exits=list(exits))

    if z is not None:
        room.xyz = (x, y, z)

    return room


def _exit(key, destination):
    """Return a stand-in exit with a name and a destination room."""
    return SimpleNamespace(key=key, destination=destination)


# ─── Test cases ──────────────────────────────────────────────────────────────

class TileKeyTests(unittest.TestCase):
    """One spelling for a tile's key, on both sides of the wire."""

    def test_key_is_x_colon_y(self):
        self.assertEqual(serializers.tile_key(6, 3), "6:3")

    def test_negative_coordinates_survive(self):
        """
        Maps are authored from (0,0) up today, but nothing enforces that and a
        key that mangled a negative would fail as a silently unclickable tile.
        """
        self.assertEqual(serializers.tile_key(-2, -1), "-2:-1")

    def test_the_key_does_not_carry_the_map_name(self):
        """
        A tile-action map is always about ONE map -- the observer's. Including
        z would make every key longer for a distinction the container already
        makes.
        """
        self.assertNotIn("oasis", serializers.tile_key(1, 1))


class TileActionShapeTests(unittest.TestCase):
    """Every affordance is {command, kind}, with the command already whole."""

    def test_an_action_carries_a_command_and_a_kind(self):
        action = serializers.tile_action("north", const.TILE_ACTION_KIND_STEP)

        self.assertEqual(action, {
            "command": "north", "kind": const.TILE_ACTION_KIND_STEP})

    def test_goto_names_the_whole_command(self):
        """
        Nothing is left for a client to substitute. The coordinate syntax is
        the server's and no client should have to know it.
        """
        action = serializers.goto_action(6, 3)

        self.assertEqual(action["command"], "goto (6,3)")
        self.assertEqual(action["kind"], const.TILE_ACTION_KIND_WALK)

    def test_cancel_is_bare_goto(self):
        action = serializers.cancel_action()

        self.assertEqual(action["command"], const.TILE_COMMAND_GOTO)
        self.assertEqual(action["kind"], const.TILE_ACTION_KIND_CANCEL)

    def test_every_kind_is_a_declared_constant(self):
        """
        The kinds are generated into both clients. A kind produced here that is
        not one of the four exported names would reach a client that has no
        branch for it, and the click would silently do nothing to the tracked
        walk.
        """
        known = {
            const.TILE_ACTION_KIND_STEP,
            const.TILE_ACTION_KIND_WALK,
            const.TILE_ACTION_KIND_LOOK,
            const.TILE_ACTION_KIND_CANCEL,
            const.TILE_ACTION_KIND_NONE,
        }
        produced = [
            serializers.goto_action(1, 1),
            serializers.cancel_action(),
        ]
        produced.extend(serializers.tile_actions(
            _room(0, 0, exits=[_exit("north", _room(0, 1))])).values())

        for action in produced:
            with self.subTest(action=action):
                self.assertIn(action["kind"], known)


class TileActionsTests(unittest.TestCase):
    """What the tiles near the observer afford, from where they stand."""

    def test_the_observers_own_tile_affords_look(self):
        actions = serializers.tile_actions(_room(4, 6))

        self.assertEqual(actions["4:6"], {
            "command": const.TILE_COMMAND_LOOK,
            "kind": const.TILE_ACTION_KIND_LOOK,
        })

    def test_an_exit_names_the_direction_a_player_would_type(self):
        """
        The command is the exit's own key, which is what a telnet player types.
        Deriving it from a grid delta instead is what the client used to do,
        and it could not survive a map whose geometry and directions disagree.
        """
        room = _room(4, 6, exits=[_exit("north", _room(4, 7))])
        actions = serializers.tile_actions(room)

        self.assertEqual(actions["4:7"], {
            "command": "north", "kind": const.TILE_ACTION_KIND_STEP})

    def test_a_diagonal_exit_is_a_step_like_any_other(self):
        """
        The client used to special-case diagonals, because it was reasoning
        from deltas. Read off a real exit there is no special case.
        """
        room = _room(4, 6, exits=[_exit("northeast", _room(5, 7))])
        actions = serializers.tile_actions(room)

        self.assertEqual(actions["5:7"]["command"], "northeast")

    def test_an_exit_whose_geometry_is_not_adjacent_still_works(self):
        """
        Nothing requires an exit's destination to be a neighbouring TILE. A map
        may link distant coordinates, and the affordance is still one step.
        This is the case a delta table could not express at all.
        """
        room = _room(0, 0, exits=[_exit("north", _room(0, 9))])
        actions = serializers.tile_actions(room)

        self.assertEqual(actions["0:9"]["kind"], const.TILE_ACTION_KIND_STEP)

    def test_a_room_off_the_grid_affords_nothing(self):
        self.assertEqual(serializers.tile_actions(_room(z=None)), {})

    def test_a_missing_room_affords_nothing(self):
        self.assertEqual(serializers.tile_actions(None), {})

    def test_a_broken_exit_contributes_no_step(self):
        """
        Asserted as "no step was produced" rather than as a census of the
        returned keys: the cardinal wall markers are also in there, and a test
        that counted them would have to be rewritten every time the shape of
        the map changed rather than when its meaning did.
        """
        room = _room(1, 1, exits=[_exit("north", None)])
        actions = serializers.tile_actions(room)
        kinds = [action["kind"] for action in actions.values()]

        self.assertNotIn(const.TILE_ACTION_KIND_STEP, kinds)

    def test_an_exit_to_an_off_grid_room_contributes_no_step(self):
        """
        A room with no coordinates cannot be drawn as a tile, so there is no
        key to file it under. Guessing one would put a clickable tile somewhere
        arbitrary.
        """
        room = _room(1, 1, exits=[_exit("north", _room(z=None))])
        actions = serializers.tile_actions(room)
        kinds = [action["kind"] for action in actions.values()]

        self.assertNotIn(const.TILE_ACTION_KIND_STEP, kinds)

    def test_a_broken_exit_leaves_its_direction_walled(self):
        """
        The other half of the same case. A north exit that leads nowhere must
        not leave the tile north of here looking walkable -- it falls into the
        cardinal sweep like any other unlinked neighbour.
        """
        room = _room(1, 1, exits=[_exit("north", None)])
        actions = serializers.tile_actions(room)

        self.assertEqual(actions["1:2"]["kind"], const.TILE_ACTION_KIND_NONE)

    def test_an_exit_looping_back_does_not_overwrite_look(self):
        """
        A room whose exit leads to itself must not turn the observer's own tile
        into a step -- clicking where you stand would then walk you nowhere and
        cancel a tracked walk as a side effect.
        """
        room = _room(2, 2)
        room.exits = [_exit("north", room)]
        actions = serializers.tile_actions(room)

        self.assertEqual(actions["2:2"]["kind"], const.TILE_ACTION_KIND_LOOK)

    def test_a_diagonal_with_no_exit_is_absent_and_falls_through(self):
        """
        Absence is the mechanism for everything beyond the exits: the client
        falls through to the map node's own `goto`. A diagonal neighbour is
        ordinarily two cardinal steps away rather than a barrier, and refusing
        it was the bug that left the tiles nearest the player unclickable.
        """
        room = _room(4, 6, exits=[_exit("north", _room(4, 7))])
        actions = serializers.tile_actions(room)

        self.assertNotIn("5:7", actions)

    def test_a_cardinal_with_no_exit_is_a_wall_said_out_loud(self):
        """
        Not absent -- absent would mean "walk there the long way round". This
        is the client's old wall rule, moved rather than dropped: a click on a
        visible barrier should not send the player around it.
        """
        room = _room(4, 6, exits=[_exit("north", _room(4, 7))])
        actions = serializers.tile_actions(room)

        self.assertEqual(actions["5:6"], {
            "command": "", "kind": const.TILE_ACTION_KIND_NONE})

    def test_a_cardinal_with_an_exit_is_not_marked_a_wall(self):
        """
        The exit must win. Marking a real exit as a wall would make the one
        direction the player can actually walk the one tile they cannot click.
        """
        room = _room(4, 6, exits=[_exit("north", _room(4, 7))])
        actions = serializers.tile_actions(room)

        self.assertEqual(actions["4:7"]["kind"], const.TILE_ACTION_KIND_STEP)

    def test_every_cardinal_neighbour_is_accounted_for(self):
        """
        All four, or the rule has a hole: an unlisted cardinal falls through to
        `goto` and the barrier becomes walkable again from one side only.
        """
        actions = serializers.tile_actions(_room(0, 0))

        for key in ("0:1", "1:0", "0:-1", "-1:0"):
            with self.subTest(tile=key):
                self.assertEqual(
                    actions[key]["kind"], const.TILE_ACTION_KIND_NONE)

    def test_the_map_stays_small(self):
        """
        Near tiles only. This channel fires on every room change, and the
        reason the whole reachable map is NOT here is that it would make
        room_info kilobytes per move to say something that had not changed.
        """
        exits = [_exit("north", _room(0, 1)), _exit("east", _room(1, 0)),
                 _exit("south", _room(0, -1)), _exit("west", _room(-1, 0)),
                 _exit("northeast", _room(1, 1)),
                 _exit("southeast", _room(1, -1)),
                 _exit("southwest", _room(-1, -1)),
                 _exit("northwest", _room(-1, 1))]
        actions = serializers.tile_actions(_room(0, 0, exits=exits))

        # Eight exits plus the observer's own tile, and never more -- every
        # cardinal is already claimed by an exit, so no wall markers are added.
        self.assertEqual(len(actions), 9)

    def test_the_worst_case_is_still_small(self):
        """
        A room with no exits at all: its own tile plus four wall markers. That
        is the ceiling for this field, and it is the number that justifies
        sending it on a channel that fires every time anyone moves.
        """
        self.assertEqual(len(serializers.tile_actions(_room(0, 0))), 5)
