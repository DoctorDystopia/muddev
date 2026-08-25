"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: Export a Z-level's room graph as chunked Blackout.Map payloads.

             This reads the PARSED, IN-MEMORY XYMap, never the database. That
             is not an optimisation, it is a correctness decision: the grid
             stores coordinates as string Tags, so "10" sorts before "9" and a
             range query over them silently returns the wrong rooms. The parsed
             map already holds ints. systems/combat/auras/targeting.py:80
             documents the same trap from the other direction.

             It also means the map can be exported before any room is spawned,
             costs no queries, and cannot be wrong about a room that exists in
             the map file but failed to build.

             World coordinates are what leave this module. The xygrid puts a
             world node at (2X, 2Y) and reserves the odd cells for link glyphs;
             that transform is the map layer's business and a client never sees
             it.
"""

from evennia.utils import logger

from . import constants as const
from . import serializers
from .payloads import MapChunkPayload


# ─── Private helper routines ─────────────────────────────────────────────────

def _is_transition_node(node) -> bool:
    """
    Purpose: Say whether a node is a transition to another map.

    Entry:
        node - a MapNode belonging to a parsed XYMap.

    Exit/Returns:
        Returns True for a configured map transition and False for every
        ordinary node.

    Module Globals:
        None.

    Methodology:
        `target_map_xyz` is what MAKES a node a transition -- the contrib's
        MapTransitionNode declares it and nothing else does -- so this reads the
        attribute rather than importing the contrib to isinstance against it,
        which would put a map-layer import inside a statefeed module for one
        type test.

        A node carrying the attribute unset still holds (None, None, None), so
        the Z slot is checked too. That is the map NAME, and a transition
        without one leads nowhere; reporting it as a transition would put a
        teleporter on a tile that cannot teleport.

    Notes/References:
        evennia/contrib/grid/xyzgrid/xymap_legend.py:1180 declares the node.
        Note the base class carries the attribute MISSPELLED (`taget_map_xyz`)
        and MapTransitionNode redeclares it correctly; this reads the spelling
        every map in world/maps/ actually sets.

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    target = getattr(node, "target_map_xyz", None)

    if not target:
        return False

    map_name = target[-1]
    named = bool(map_name)

    return named


def _node_room_kind(xymap, node) -> str:
    """
    Purpose: Name the room type for one map node, without touching the DB.

    Entry:
        xymap - a parsed XYMap.
        node  - a MapNode belonging to it.

    Exit/Returns:
        Returns ROOM_KIND_TRANSITION for a map-transition node, and otherwise
        the prototype's "key" for that coordinate, falling back to the map's
        ('*', '*') wildcard entry, then to ROOM_KIND_DEFAULT.

    Module Globals:
        const.ROOM_KIND_TRANSITION, const.ROOM_KIND_DEFAULT read.

    Methodology:
        Mirrors the lookup order the xyzgrid builder itself uses when spawning
        (xymap.py:522): exact coordinate first, wildcard second. Matching that
        order is what makes the exported room_kind agree with the room a player
        actually walks into.

        A transition node is answered BEFORE that lookup, because for it the
        lookup has no right answer to find: it spawns no room, so it owns no
        prototype key, and the wildcard it would otherwise inherit describes
        the ground around it rather than the way off the map.

    Notes/References:
        A map with no PROTOTYPES table at all is valid, hence the guard.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    transition = _is_transition_node(node)

    if transition:
        return const.ROOM_KIND_TRANSITION

    prototypes = getattr(xymap, "prototypes", None)

    if not prototypes:
        return const.ROOM_KIND_DEFAULT

    coord = (node.X, node.Y)
    entry = prototypes.get(coord)

    if entry is None:
        entry = prototypes.get(("*", "*"))

    if not entry:
        return const.ROOM_KIND_DEFAULT

    room_key = entry.get("key")

    if not room_key:
        return const.ROOM_KIND_DEFAULT

    return str(room_key)


def _node_entries(xymap) -> list:
    """
    Purpose: Return [{x, y, room_kind, action}, ...] for every node on the map.

    Entry:
        xymap - a parsed XYMap.

    Exit/Returns:
        One entry per node. `action` is the pathfinder walk to that node.

    Module Globals:
        None.

    Methodology:
        `action` is stamped HERE, once per map per session, rather than sent
        per move on room_info, because it does not depend on where the observer
        is: the walk to (6,3) is `goto (6,3)` from anywhere on the same map.
        Only the immediate exits change as a player walks, and those are the
        at-most-eight entries room_info carries.

        Named `action` rather than `interact` on purpose. An ENTITY's
        `interact` is a bare command string; a tile's action is
        {command, kind}, because the client tracks the walk it started and has
        to be told whether a command begins one, ends one, or does neither. Two
        shapes should not share a field name.

    Notes/References:
        A node's action is valid only from within its own map. Blackout's maps
        are joined by transition NODES (the `T` glyph -- oasis and
        oasis_outskirts each have one), which are walked onto like any other
        tile; `goto` itself does not cross maps, and the server answers "target
        outside of area" if asked to. A client therefore uses this only for a
        tile on the map it is standing on.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    index_map = getattr(xymap, "node_index_map", None)

    if not index_map:
        return []

    entries = []

    for node in index_map.values():
        kind = _node_room_kind(xymap, node)
        entries.append({
            "x": node.X,
            "y": node.Y,
            "room_kind": kind,
            "action": serializers.goto_action(node.X, node.Y),
        })

    return entries


def _link_entries(xymap) -> list:
    """
    Purpose: Return the map's edges as [{"from": [x, y], "to": [x, y]}, ...].

    Entry:
        xymap - a parsed XYMap.

    Exit/Returns:
        Returns one entry per undirected edge. A two-way corridor appears once,
        not twice.

    Module Globals:
        None.

    Methodology:
        node.links is {direction: end_node} and is populated on BOTH endpoints
        of a two-way link, so a naive walk emits every corridor twice. Edges
        are keyed by their sorted endpoint pair and collected in a set first.

        One-way links survive this: they exist on only one endpoint, so their
        single entry is kept. A client drawing undirected geometry loses
        nothing by it -- and a client that later wants direction has
        RoomInfoPayload.exits, which is per-room and directional.

    Notes/References:
        Diagonal links are ordinary edges here; the map format supports them
        via the \\ and / glyphs.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    index_map = getattr(xymap, "node_index_map", None)

    if not index_map:
        return []

    seen = set()

    for node in index_map.values():
        for end_node in node.links.values():
            start = (node.X, node.Y)
            end = (end_node.X, end_node.Y)
            edge = tuple(sorted((start, end)))
            seen.add(edge)

    entries = []

    for start, end in sorted(seen):
        entries.append({"from": list(start), "to": list(end)})

    return entries


# ─── Public routines ─────────────────────────────────────────────────────────

def build_map_chunks(xymap) -> list:
    """
    Purpose: Render one Z-level as a list of ready-to-send MapChunkPayloads.

    Entry:
        xymap - a parsed XYMap, as returned by XYZGrid.get_map(zcoord).

    Exit/Returns:
        Returns a list of MapChunkPayload, each carrying at most
        MAP_NODES_PER_CHUNK nodes and every chunk stamped with the same
        chunk_count so a client knows when it has the whole map. Returns an
        empty list for a map with no nodes.

    Module Globals:
        const.MAP_NODES_PER_CHUNK read.

    Methodology:
        Every link rides on the FIRST chunk rather than being split alongside
        the nodes. Links are a fraction of the payload, and splitting them
        would force a client to buffer partial geometry; this way chunk 0 is
        enough to draw the topology and later chunks only add tiles.

    Notes/References:
        Chunking exists because Godot's WebSocketPeer defaults to a 65535-byte
        inbound buffer and historically truncated oversized JSON SILENTLY
        rather than erroring. A Blackout map is ~95 nodes and would fit today;
        this removes a failure mode that would otherwise appear only once a map
        grew past it.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    nodes = _node_entries(xymap)

    if not nodes:
        return []

    links = _link_entries(xymap)
    zcoord = str(getattr(xymap, "Z", ""))
    chunk_size = const.MAP_NODES_PER_CHUNK
    chunk_count = -(-len(nodes) // chunk_size)   # ceiling division
    chunks = []

    for index in range(chunk_count):
        start = index * chunk_size
        slice_nodes = nodes[start:start + chunk_size]
        slice_links = links if index == 0 else []

        chunks.append(
            MapChunkPayload(
                z=zcoord,
                chunk_index=index,
                chunk_count=chunk_count,
                nodes=slice_nodes,
                links=slice_links,
            )
        )

    return chunks


def build_all_map_chunks() -> list:
    """
    Purpose: Render every Z-level the grid knows about.

    Entry:
        No conditions. Safe to call before the grid exists.

    Exit/Returns:
        Returns a flat list of MapChunkPayload across all maps, or an empty
        list when there is no grid.

    Module Globals:
        None.

    Methodology:
        The grid is looked up directly through the manager rather than through
        the contrib's get_xyzgrid() helper, which CREATES the XYZGrid global
        Script when none exists. Creating a Script as a side effect of a client
        subscribing would be wrong on a live server and would fire inside every
        test that touches this module. A grid-less server correctly reports no
        maps instead.

        The contrib imports inside the routine, not at module scope: this
        module is reached from the emission paths, and a module-scope import
        would pull a Script model into every server start.

    Notes/References:
        Blackout's maps are separate ISLANDS to a renderer even though they
        are joined in play: oasis and oasis_outskirts each carry a `T`
        transition node onto the other, but a transition is a node you walk
        ONTO rather than an edge between two maps, so nothing here relates one
        map's coordinates to another's. A client receives independent islands
        and needs an authored z -> world-offset table to place them.

        (This note previously said no transition nodes existed at all. They
        do -- see ToOasisOutskirtsNode in world/maps/oasis.py.)

        Reading .all_maps() parses the map modules on first access if the
        grid's cache is cold. That is once per server lifetime and only on the
        subscribe path, never per tick.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    from evennia.contrib.grid.xyzgrid.xyzgrid import XYZGrid

    try:
        grid = XYZGrid.objects.all().first()

        if grid is None:
            return []

        maps = grid.all_maps()
    except Exception:
        logger.log_trace()
        return []

    chunks = []

    for xymap in maps:
        built = build_map_chunks(xymap)
        chunks.extend(built)

    return chunks
