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


def _transition_node(x, y, target=(8, 10, "oasis_outskirts")):
    """Return a stand-in MapTransitionNode -- a node that spawns no room."""
    return SimpleNamespace(X=x, Y=y, target_map_xyz=target)


def _mapped_room(x, y, z="oasis", exits=(), links=None):
    """
    Purpose: Return a stand-in room that also carries a parsed map.

    Entry:
        x, y, z - the room's grid position.
        exits   - stand-in exits, as for _room.
        links   - {direction: node} for the observer's OWN map node, which is
                  where a transition node is found.

    Exit/Returns:
        A room whose `xymap` answers get_node_from_coord for its own tile.

    Module Globals:
        None

    Methodology:
        Only the two things _transition_tile touches are modelled --
        get_node_from_coord and the node's links -- for the same reason the
        rooms here are namespaces: a real XYMap would need a grid, a Script and
        a parse to answer one lookup.

    Notes/References:
        None
    """
    room = _room(x, y, z, exits)
    node = SimpleNamespace(X=x, Y=y, links=links or {})

    def _get_node_from_coord(xy, _node=node):
        if tuple(xy) == (_node.X, _node.Y):
            return _node

        return None

    room.xymap = SimpleNamespace(get_node_from_coord=_get_node_from_coord)

    return room


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
        returned keys, so it says what it means rather than what the map
        happened to contain on the day it was written.
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

    def test_a_broken_exit_leaves_its_direction_absent(self):
        """
        The other half of the same case. A north exit leading nowhere names no
        tile at all, so the tile north of here falls through to the map node's
        own `goto` -- which is right: the room is still there, and the
        pathfinder either finds another way in or declines out loud.
        """
        room = _room(1, 1, exits=[_exit("north", None)])
        actions = serializers.tile_actions(room)

        self.assertNotIn("1:2", actions)

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

    def test_a_cardinal_with_no_exit_is_absent_too(self):
        """
        The fix of 08/28/2026, and the same rule as the diagonal above rather
        than an exception to it. This used to answer with an empty command
        meaning "a wall you can see", on the theory that no direct link means
        no way through. On the oasis, (6,3) carries the foundry furnace, is
        joined to four DIAGONAL neighbours and to no cardinal one, and so the
        theory made a tile two steps away, in plain view, permanently
        unclickable from (6,2) directly below it.
        """
        room = _room(4, 6, exits=[_exit("north", _room(4, 7))])
        actions = serializers.tile_actions(room)

        self.assertNotIn("5:6", actions)

    def test_a_cardinal_with_an_exit_is_still_a_step(self):
        """
        The exit must win. The one direction the player can actually walk must
        not be the one tile they cannot click.
        """
        room = _room(4, 6, exits=[_exit("north", _room(4, 7))])
        actions = serializers.tile_actions(room)

        self.assertEqual(actions["4:7"]["kind"], const.TILE_ACTION_KIND_STEP)

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

        # Eight exits plus the observer's own tile, and never more.
        self.assertEqual(len(actions), 9)

    def test_the_worst_case_is_one_entry(self):
        """
        A room with no exits at all carries its own tile and nothing else --
        the floor, now that the wall markers are gone. The eight above are
        still the ceiling, and that is the number justifying a field sent every
        time anyone moves.
        """
        self.assertEqual(len(serializers.tile_actions(_room(0, 0))), 1)


class TransitionTileTests(unittest.TestCase):
    """An exit onto ANOTHER map is drawn on this one, at the `T` node."""

    def test_a_cross_map_exit_is_filed_under_the_transition_tile(self):
        """
        The oasis teleporter. Its exit's destination is a room at
        (8,10,oasis_outskirts), because the contrib's TransitionMapNode hands
        the builder the TARGET's coordinates -- the `T` itself spawns no room.
        The tile the player clicks is therefore the `T` at (0,2) on THIS map.
        """
        far = _room(8, 10, z="oasis_outskirts")
        node = _transition_node(0, 2)
        room = _mapped_room(1, 2, exits=[_exit("west", far)],
                            links={"w": node})
        actions = serializers.tile_actions(room)

        self.assertEqual(actions["0:2"], {
            "command": "west", "kind": const.TILE_ACTION_KIND_STEP})

    def test_a_cross_map_exit_claims_no_tile_on_this_map(self):
        """
        The other half, and the one that was actively wrong rather than merely
        missing: read literally, the destination put a `west` step on the oasis
        tile at (8,10) -- a real tile, nowhere near the teleporter.
        """
        far = _room(8, 10, z="oasis_outskirts")
        node = _transition_node(0, 2)
        room = _mapped_room(1, 2, exits=[_exit("west", far)],
                            links={"w": node})
        actions = serializers.tile_actions(room)

        self.assertNotIn("8:10", actions)

    def test_the_transition_matched_is_the_one_leading_there(self):
        """
        A room with two doorways off the map files each under its own tile.
        Matched on target_map_xyz rather than on link order, because a link
        dict has no order worth trusting.
        """
        far = _room(8, 10, z="oasis_outskirts")
        wrong = _transition_node(0, 2, target=(1, 1, "neo_cairo"))
        right = _transition_node(2, 3)
        room = _mapped_room(1, 2, exits=[_exit("west", far)],
                            links={"w": wrong, "ne": right})
        actions = serializers.tile_actions(room)

        self.assertIn("2:3", actions)
        self.assertNotIn("0:2", actions)

    def test_a_cross_map_exit_with_no_transition_node_is_skipped(self):
        """
        A room with no parsed map behind it must not guess. Guessing is what
        put the teleporter's step on an arbitrary tile in the first place.
        """
        far = _room(8, 10, z="oasis_outskirts")
        room = _room(1, 2, exits=[_exit("west", far)])
        actions = serializers.tile_actions(room)

        self.assertEqual(list(actions), ["1:2"])
