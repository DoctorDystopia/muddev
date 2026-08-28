"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: Tests for the Z-level grid export.

             Built against stand-in XYMap objects rather than parsed map
             modules. The export reads only node_index_map, prototypes and Z,
             so a stand-in exercises every branch while keeping the tests free
             of the map files -- which would otherwise couple these assertions
             to the current shape of the oasis.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.statefeed
"""

import unittest
from types import SimpleNamespace

from systems.statefeed import constants as const
from systems.statefeed.mapexport import build_map_chunks


# ─── Private helper routines ─────────────────────────────────────────────────

def _node(x, y):
    """Return a stand-in MapNode with no links yet."""
    return SimpleNamespace(X=x, Y=y, links={})


def _transition_node(x, y, target=(8, 10, "oasis_outskirts")):
    """Return a stand-in MapTransitionNode -- a node that spawns no room."""
    return SimpleNamespace(X=x, Y=y, links={}, target_map_xyz=target)


def _link(node_a, node_b, direction="e", reverse="w"):
    """Join two stand-in nodes the way a two-way map link does -- both ways."""
    node_a.links[direction] = node_b
    node_b.links[reverse] = node_a


def _xymap(nodes, prototypes=None, zcoord="oasis"):
    """Return a stand-in XYMap holding the given nodes."""
    index_map = {}

    for index, node in enumerate(nodes):
        index_map[index] = node

    return SimpleNamespace(
        node_index_map=index_map,
        prototypes=prototypes or {},
        Z=zcoord,
    )


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestNodeExport(unittest.TestCase):
    """World coordinates and room kinds leave; xygrid internals do not."""

    def test_an_empty_map_produces_no_chunks(self):
        chunks = build_map_chunks(_xymap([]))

        self.assertEqual(chunks, [])

    def test_every_node_is_exported(self):
        nodes = [_node(0, 0), _node(1, 0), _node(2, 0)]
        chunks = build_map_chunks(_xymap(nodes))

        self.assertEqual(len(chunks[0].nodes), 3)

    def test_nodes_carry_world_coordinates_not_xygrid_ones(self):
        chunks = build_map_chunks(_xymap([_node(3, 4)]))
        node = chunks[0].nodes[0]

        # The xygrid would place this node at (6, 8); a client must never see
        # that transform.
        self.assertEqual(node["x"], 3)
        self.assertEqual(node["y"], 4)

    def test_the_zcoord_rides_on_every_chunk(self):
        chunks = build_map_chunks(_xymap([_node(0, 0)], zcoord="trade town sector 1"))

        self.assertEqual(chunks[0].z, "trade town sector 1")


class TestRoomKindLookup(unittest.TestCase):
    """room_kind must agree with the room the player actually walks into."""

    def test_an_exact_coordinate_override_wins(self):
        prototypes = {
            ("*", "*"): {"key": "Oasis"},
            (2, 3): {"key": "Bank"},
        }
        chunks = build_map_chunks(_xymap([_node(2, 3)], prototypes))

        self.assertEqual(chunks[0].nodes[0]["room_kind"], "Bank")

    def test_the_wildcard_covers_everything_else(self):
        prototypes = {
            ("*", "*"): {"key": "Oasis"},
            (2, 3): {"key": "Bank"},
        }
        chunks = build_map_chunks(_xymap([_node(9, 9)], prototypes))

        self.assertEqual(chunks[0].nodes[0]["room_kind"], "Oasis")

    def test_a_map_with_no_prototypes_falls_back_to_the_default(self):
        chunks = build_map_chunks(_xymap([_node(0, 0)]))

        self.assertEqual(chunks[0].nodes[0]["room_kind"], const.ROOM_KIND_DEFAULT)

    def test_a_prototype_entry_with_no_key_falls_back_to_the_default(self):
        prototypes = {("*", "*"): {"desc": "sand...everywhere."}}
        chunks = build_map_chunks(_xymap([_node(0, 0)], prototypes))

        self.assertEqual(chunks[0].nodes[0]["room_kind"], const.ROOM_KIND_DEFAULT)


class TestTransitionNodes(unittest.TestCase):
    """The one tile leading off the map must not report as the ground."""

    def test_a_transition_node_reports_its_own_kind(self):
        chunks = build_map_chunks(_xymap([_transition_node(0, 2)]))
        kind = chunks[0].nodes[0]["room_kind"]

        self.assertEqual(kind, const.ROOM_KIND_TRANSITION)

    def test_the_wildcard_prototype_does_not_win_over_it(self):
        prototypes = {("*", "*"): {"key": "Oasis"}}
        chunks = build_map_chunks(
            _xymap([_transition_node(0, 2)], prototypes))
        kind = chunks[0].nodes[0]["room_kind"]

        self.assertEqual(kind, const.ROOM_KIND_TRANSITION)

    def test_a_transition_with_no_target_map_is_not_one(self):
        unset = _transition_node(0, 2, target=(None, None, None))
        prototypes = {("*", "*"): {"key": "Oasis"}}
        chunks = build_map_chunks(_xymap([unset], prototypes))
        kind = chunks[0].nodes[0]["room_kind"]

        self.assertEqual(kind, "Oasis")

    def test_ordinary_nodes_are_untouched_by_the_check(self):
        prototypes = {("*", "*"): {"key": "Oasis"}}
        chunks = build_map_chunks(_xymap([_node(4, 4)], prototypes))
        kind = chunks[0].nodes[0]["room_kind"]

        self.assertEqual(kind, "Oasis")


class TestLinkExport(unittest.TestCase):
    """A two-way corridor is one edge, not two."""

    def test_a_two_way_link_is_emitted_once(self):
        node_a = _node(0, 0)
        node_b = _node(1, 0)
        _link(node_a, node_b)
        chunks = build_map_chunks(_xymap([node_a, node_b]))

        self.assertEqual(len(chunks[0].links), 1)

    def test_a_link_names_both_endpoints(self):
        node_a = _node(0, 0)
        node_b = _node(1, 0)
        _link(node_a, node_b)
        chunks = build_map_chunks(_xymap([node_a, node_b]))
        edge = chunks[0].links[0]

        self.assertEqual(edge["from"], [0, 0])
        self.assertEqual(edge["to"], [1, 0])

    def test_a_one_way_link_survives_deduplication(self):
        node_a = _node(0, 0)
        node_b = _node(1, 0)
        node_a.links["e"] = node_b
        chunks = build_map_chunks(_xymap([node_a, node_b]))

        self.assertEqual(len(chunks[0].links), 1)

    def test_unlinked_nodes_produce_no_edges(self):
        chunks = build_map_chunks(_xymap([_node(0, 0), _node(5, 5)]))

        self.assertEqual(chunks[0].links, [])


class TestChunking(unittest.TestCase):
    """Bounded payloads, because Godot truncates oversized frames silently."""

    def setUp(self):
        self.node_count = const.MAP_NODES_PER_CHUNK + 1
        nodes = []

        for index in range(self.node_count):
            nodes.append(_node(index, 0))

        self.chunks = build_map_chunks(_xymap(nodes))

    def test_an_oversized_map_splits(self):
        self.assertEqual(len(self.chunks), 2)

    def test_no_chunk_exceeds_the_configured_size(self):
        for chunk in self.chunks:
            self.assertLessEqual(len(chunk.nodes), const.MAP_NODES_PER_CHUNK)

    def test_every_node_survives_the_split(self):
        total = 0

        for chunk in self.chunks:
            total += len(chunk.nodes)

        self.assertEqual(total, self.node_count)

    def test_every_chunk_reports_the_same_total(self):
        for chunk in self.chunks:
            self.assertEqual(chunk.chunk_count, 2)

    def test_chunks_are_indexed_in_order(self):
        indices = []

        for chunk in self.chunks:
            indices.append(chunk.chunk_index)

        self.assertEqual(indices, [0, 1])

    def test_a_map_that_fits_reports_a_single_chunk(self):
        chunks = build_map_chunks(_xymap([_node(0, 0)]))

        self.assertEqual(chunks[0].chunk_count, 1)


class TestLinksRideOnTheFirstChunk(unittest.TestCase):
    """Chunk 0 alone is enough to draw the topology."""

    def setUp(self):
        nodes = []

        for index in range(const.MAP_NODES_PER_CHUNK + 1):
            nodes.append(_node(index, 0))

        _link(nodes[0], nodes[1])
        self.chunks = build_map_chunks(_xymap(nodes))

    def test_the_first_chunk_carries_the_links(self):
        self.assertEqual(len(self.chunks[0].links), 1)

    def test_later_chunks_carry_none(self):
        self.assertEqual(self.chunks[1].links, [])


class TestNodeActions(unittest.TestCase):
    """Every node carries the pathfinder walk to itself."""

    def test_a_node_carries_a_walk_action(self):
        """
        Stamped on the MAP rather than resent on room_info, because the walk to
        (6,3) is `goto (6,3)` from anywhere on the same map. This is what the
        client falls through to for any tile that is not an immediate exit.
        """
        chunks = build_map_chunks(_xymap([_node(6, 3)]))
        node = chunks[0].nodes[0]

        self.assertEqual(node["action"], {
            "command": "goto (6,3)",
            "kind": const.TILE_ACTION_KIND_WALK,
        })

    def test_the_action_names_the_nodes_own_coordinates(self):
        """
        A node whose action pointed anywhere but at itself would walk the
        player to the wrong tile, and would look correct in every screenshot.
        """
        nodes = [_node(0, 0), _node(4, 1), _node(10, 7)]
        chunks = build_map_chunks(_xymap(nodes))

        for entry in chunks[0].nodes:
            with self.subTest(x=entry["x"], y=entry["y"]):
                self.assertEqual(
                    entry["action"]["command"],
                    "goto (%s,%s)" % (entry["x"], entry["y"]))

    def test_a_transition_node_carries_no_walk(self):
        """
        A transition node spawns NO room -- that is the contrib's design for
        it, and why get_spawn_xyz returns the target's coordinates instead of
        its own. `goto` resolves a room BY coordinate, so `goto (9,10)` at a
        transition answers "Could not find a room at (9,10)". Stamping one here
        made the tile look clickable and do nothing.

        The way onto a transition is the ordinary exit from the tile beside it,
        which serializers.tile_actions names once the player is standing there.
        """
        chunks = build_map_chunks(_xymap([_transition_node(9, 10)]))
        node = chunks[0].nodes[0]

        self.assertEqual(node["room_kind"], const.ROOM_KIND_TRANSITION)
        self.assertNotIn("action", node)

    def test_the_action_key_is_absent_rather_than_empty(self):
        """
        Asserted separately because the two clients differ in how forgiving
        they are, and neither re-tests the command on this path: the browser
        pane returns `tile.action || null` and Godot returns
        `level.actions.get(cell, {})`. An empty action here would be SENT.
        """
        nodes = [_node(1, 1), _transition_node(9, 10)]
        chunks = build_map_chunks(_xymap(nodes))

        for entry in chunks[0].nodes:
            with self.subTest(x=entry["x"], y=entry["y"]):
                self.assertNotEqual(entry.get("action", None), {})
