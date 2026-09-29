"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Turn an xyzgrid map module into one chunk file of the tile grid.
             A one-time tool of DESIGN-0011 Phase 4. It goes with the xyzgrid
             maps in Phase 4b.

What it keeps
-------------
Nick chose a converter over a redraw on 09/24/2026, so that the gameplay of
each map stays the same. One xyzgrid node becomes one tile. The rules:

1. A node is a walkable tile.
2. A link that passes over a node position (the middle of `#---#`, or a `+`
   crossing) makes that tile walkable too.
3. Two walkable neighbours with a link between them have an open edge. Two
   walkable neighbours with no link between them get a wall on each side.
4. Every other tile of the chunk is blocked.
5. A prototype row with a spawner key becomes an object of the kind with that
   spawner. A signpost label becomes the sign kind with that label.
6. A transition node becomes the transition kind whose target is the target
   of the node, at the chunk of its map.

What it cannot keep
-------------------
The tile grid refuses a diagonal step unless both tiles beside the corner are
open (the OSRS rule, `TileGrid.check_step`). An xyzgrid diagonal has no such
rule. For each diagonal link, the converter thus opens both corner tiles and
the four edges around them. Each edge that it opens this way goes into
`Conversion.added_edges`, so a test and a person can see every join that the
xyzgrid map did not have. A crossing also becomes a junction: a walker can
turn there.

A prototype key with no kind (for example "Oasis Entrance") names a tile
only. It goes into `Conversion.unmatched`, because a tile room has no stored
name (Phase 4 decision, 09/24/2026).

The floors: "dirt" on each walkable tile, "sand" on the rest. The heights are
all 0. Nick shapes the ground in the editor after the conversion.
"""

from dataclasses import dataclass, field

from evennia.contrib.grid.xyzgrid.xymap import XYMap
from evennia.contrib.grid.xyzgrid.xymap_legend import MapTransitionNode

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from typeclasses.signs import SIGNPOST_LABEL_ATTR
from world.object_kinds import OBJECT_KINDS
from world.tile_cutover import MAP_CHUNKS


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE

# Index 0 is the ground, index 1 the old map. See the module docstring.
_FLOOR_NAMES: list = ["sand", "dirt"]
_GROUND_FLOOR: int = 0
_WALKABLE_FLOOR: int = 1

# A cardinal offset, and the wall bit on the tile on its near side.
_CARDINAL_WALLS: tuple = tuple(tile_const.EDGE_WALL_LEAVING.items())

# The string grid of an xyzgrid map puts one node on each even column and row.
_STRING_STEP: int = 2


# ─── Public classes ──────────────────────────────────────────────────────────

@dataclass
class Conversion:
    """
    The result of one map. `added_edges` holds each edge that a diagonal
    link opened, as a frozenset of two local tiles. `unmatched` holds
    (x, y, key) of each prototype key that no kind has.
    """

    zcoord: str
    chunk_file: chunkfile.ChunkFile
    walkable: set
    added_edges: set = field(default_factory=set)
    unmatched: list = field(default_factory=list)


# ─── Private helper routines ─────────────────────────────────────────────────

def _edge(first: tuple, second: tuple) -> frozenset:
    """Return the edge between two neighbour tiles, in either order."""
    return frozenset((first, second))


def _tile_of_string(x: int, y: int):
    """Return the tile of a string position, or None between two tiles."""
    if x % _STRING_STEP or y % _STRING_STEP:
        return None

    return (x // _STRING_STEP, y // _STRING_STEP)


def _tile_chain(node, direction: str) -> list:
    """
    Return the tiles that the link from `node` in `direction` passes, from
    the node to the end node. Raises ValueError if two of them are not
    neighbours.
    """
    end = node.links[direction]
    string_points = [(node.x, node.y)]
    string_points += [(link.x, link.y) for link in node.xy_steps_to_node[direction]]
    string_points.append((end.x, end.y))
    chain = []

    for x, y in string_points:
        tile = _tile_of_string(x, y)

        if tile is not None and (not chain or chain[-1] != tile):
            chain.append(tile)

    for here, there in zip(chain, chain[1:]):
        if max(abs(there[0] - here[0]), abs(there[1] - here[1])) != 1:
            raise ValueError("link %s of %s jumps from %s to %s"
                             % (direction, (node.X, node.Y), here, there))

    return chain


def link_chains(xymap) -> list:
    """Return (start tile, end tile, chain) for every link of every node."""
    found = []

    for node in xymap.node_index_map.values():
        for direction, end in node.links.items():
            chain = _tile_chain(node, direction)
            found.append(((node.X, node.Y), (end.X, end.Y), chain))

    return found


def _open_diagonal(here: tuple, there: tuple, walkable: set, edges: set,
                   added: set) -> None:
    """Open both corner tiles of a diagonal move and their four edges."""
    corners = ((there[0], here[1]), (here[0], there[1]))

    for corner in corners:
        walkable.add(corner)

        for end in (here, there):
            edge = _edge(corner, end)

            if edge not in edges:
                edges.add(edge)
                added.add(edge)


def _open_moves(chains: list) -> tuple:
    """
    Return (walkable tiles, open edges, added edges) of every link chain.
    Rules 1 to 3 of the module docstring, and the diagonal rule.
    """
    walkable = set()
    edges = set()
    added = set()

    for _start, _end, chain in chains:
        walkable.update(chain)

        for here, there in zip(chain, chain[1:]):
            if here[0] != there[0] and here[1] != there[1]:
                _open_diagonal(here, there, walkable, edges, added)
            else:
                edges.add(_edge(here, there))

    # An edge that a real link opens is not an added one.
    added -= {_edge(a, b) for _s, _e, chain in chains
              for a, b in zip(chain, chain[1:])}

    return walkable, edges, added


def _flag_grid(walkable: set, edges: set) -> list:
    """Return the flags of the chunk: rules 3 and 4 of the module docstring."""
    flags = [tile_const.FLAG_BLOCKED] * (_SIZE * _SIZE)

    for x, y in walkable:
        bits = tile_const.FLAG_NONE

        for (dx, dy), wall in _CARDINAL_WALLS:
            neighbour = (x + dx, y + dy)

            if neighbour in walkable and _edge((x, y), neighbour) not in edges:
                bits |= wall

        flags[y * _SIZE + x] = bits

    return flags


def _world_tile(zcoord: str, x: int, y: int) -> tuple:
    """Return the world tile of a local tile of a map."""
    cx, cy = MAP_CHUNKS[zcoord]

    return (cx * _SIZE + x, cy * _SIZE + y)


def _label_of(prototype: dict) -> str:
    """Return the signpost label in a prototype, or ""."""
    for attribute in prototype.get("attrs", ()) or ():
        if attribute[0] == SIGNPOST_LABEL_ATTR:
            return attribute[1]

    return ""


def _kinds_of_node(node) -> tuple:
    """
    Return (kind keys, unmatched key or "") of one node. Rules 5 and 6 of the
    module docstring.
    """
    if isinstance(node, MapTransitionNode):
        tx, ty, tz = node.target_map_xyz
        target = _world_tile(tz, tx, ty)
        kinds = [kind.key for kind in OBJECT_KINDS.values()
                 if kind.target == target]

        return kinds, ("" if kinds else "transition to %s" % (target,))

    prototype = node.prototype or {}
    room_key = prototype.get("key", "")
    label = _label_of(prototype)
    kinds = [kind.key for kind in OBJECT_KINDS.values()
             if kind.spawner and kind.spawner == room_key]
    kinds += [kind.key for kind in OBJECT_KINDS.values()
              if label and kind.label == label]
    unmatched = "" if kinds or not room_key else room_key

    return kinds, unmatched


def _objects(xymap, default_key: str) -> tuple:
    """Return (chunk objects, unmatched rows) of the nodes of a map."""
    objects = []
    unmatched = []
    nodes = sorted(xymap.node_index_map.values(), key=lambda n: (n.Y, n.X))

    for node in nodes:
        kinds, missing = _kinds_of_node(node)

        for kind in kinds:
            objects.append(chunkfile.ChunkObject(kind, node.X, node.Y))

        if missing and missing != default_key:
            unmatched.append((node.X, node.Y, missing))

    return objects, unmatched


# ─── Public routines ─────────────────────────────────────────────────────────

def parse_map(map_data: dict):
    """Return the parsed XYMap of one entry of a map's XYMAP_DATA_LIST."""
    xymap = XYMap(map_data, Z=map_data["zcoord"])
    xymap.parse()

    return xymap


def convert_map(map_data: dict) -> Conversion:
    """
    Purpose: Convert one xyzgrid map into one chunk file.

    Entry:
        map_data - one entry of a map module's XYMAP_DATA_LIST. Its Z must be
                   a key of MAP_CHUNKS and of the area table.

    Exit/Returns:
        A Conversion. Raises ValueError for a link that the tile grid cannot
        hold, or for a map larger than one chunk.

    Module Globals:
        MAP_CHUNKS, _FLOOR_NAMES read.

    Methodology:
        The rules in the module docstring, in order: the link chains, the
        open moves, the flags, then the objects.

    Notes/References:
        scripts/convert_maps_to_chunks.py writes the result.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    zcoord = map_data["zcoord"]
    xymap = parse_map(map_data)

    if xymap.max_X >= _SIZE or xymap.max_Y >= _SIZE:
        raise ValueError("map %s is larger than one chunk" % zcoord)

    walkable, edges, added = _open_moves(link_chains(xymap))
    default_key = (map_data["prototypes"].get(("*", "*")) or {}).get("key", "")
    objects, unmatched = _objects(xymap, default_key)
    floors = [_GROUND_FLOOR] * (_SIZE * _SIZE)

    for x, y in walkable:
        floors[y * _SIZE + x] = _WALKABLE_FLOOR

    cx, cy = MAP_CHUNKS[zcoord]
    chunk_file = chunkfile.ChunkFile(
        cx=cx, cy=cy, plane=0,
        floor_names=list(_FLOOR_NAMES), area_names=[zcoord],
        heights=[tile_const.DEFAULT_HEIGHT] * (tile_const.CORNERS_PER_SIDE ** 2),
        floors=floors, flags=_flag_grid(walkable, edges),
        areas=[0] * (_SIZE * _SIZE), objects=objects)

    return Conversion(zcoord, chunk_file, walkable, added, unmatched)
