"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/28/2026
Description: The world map feed: the index of the world, and the world map
             summary of each chunk.

Why a summary, not the chunk file
---------------------------------
The 3D pane needs the heights, so the block around the player streams whole
chunk files (about 35 KB each). The world map shows every chunk of a plane,
and it needs only one colour for each tile. A summary holds one character for
each tile, so a chunk costs about 4 KB. The world of 09/28/2026 has 18 chunks,
about 80 KB in all, and the server sends it one time for each session.

The encoding
------------
`tiles` is a string of CHUNK_SIZE * CHUNK_SIZE characters, row 0 (the south
edge) first, west to east in each row. That is the order of the chunk file
lists. The character of one tile is

    WORLD_MAP_ALPHABET[floor_index * 2 + unwalkable]

`floor_index` is the index of the floor type in `world/floor_types.py`
(`TILE_FLOOR_TYPES` in the client). `unwalkable` is 1 when a flag in
FLAGS_UNWALKABLE is set. The client owns the colour of each class. The server
names the class.

The labels
----------
Each area of a plane gets one label: the `name` of its row in
`world/areas.py`, on the tile of the area nearest to the centre of its tiles.
The nearest tile, not the centre itself, so the label of an area with a bent
shape stays on the area. A void tile has no floor, so it counts for no label.

Both the summaries and the labels are built one time for each loaded plane.
The world loads one time, and every player gets the same bytes.
"""

import weakref

from systems.core.tilegrid import constants as tile_const
from world import areas as area_table
from world import floor_types as floor_table

from . import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

# Floor type name -> its index in the client's TILE_FLOOR_TYPES.
_FLOOR_INDEX: dict = {name: index
                      for index, name in enumerate(floor_table.FLOOR_TYPES)}

# The class of a floor that the table does not know. A content error, drawn as
# the default floor rather than refused, so one bad tile cannot hide a chunk.
_FALLBACK_FLOOR_INDEX: int = _FLOOR_INDEX[floor_table.DEFAULT_FLOOR_TYPE]

# How many classes each floor type takes: walkable and unwalkable.
_CLASSES_PER_FLOOR: int = 2

# The built summaries and labels, for each loaded TilePlane. Weak, so a test
# that installs its own world drops the cache with the world.
_SUMMARIES = weakref.WeakKeyDictionary()
_LABELS = weakref.WeakKeyDictionary()


# ─── Private helper routines ─────────────────────────────────────────────────

def _tile_class(floor_name: str, flags: int) -> int:
    """Return the class of one tile: floor_index * 2 + unwalkable."""
    floor_index = _FLOOR_INDEX.get(floor_name, _FALLBACK_FLOOR_INDEX)
    unwalkable = 1 if flags & tile_const.FLAGS_UNWALKABLE else 0

    return floor_index * _CLASSES_PER_FLOOR + unwalkable


def _area_tiles(tile_plane) -> dict:
    """Return area name -> [(x, y), ...] of each tile with a floor."""
    size = tile_const.CHUNK_SIZE
    found = {}

    for key in tile_plane.chunk_keys():
        chunk_file = tile_plane.chunk_file(key)
        origin_x = chunk_file.cx * size
        origin_y = chunk_file.cy * size

        for index, area_index in enumerate(chunk_file.areas):
            floor = chunk_file.floor_names[chunk_file.floors[index]]

            if floor == floor_table.VOID_FLOOR_TYPE:
                continue

            tile = (origin_x + index % size, origin_y + index // size)
            name = chunk_file.area_names[area_index]
            found.setdefault(name, []).append(tile)

    return found


def _nearest_to_centre(tiles: list) -> tuple:
    """Return the tile of `tiles` nearest to their mean. Ties go to the first."""
    count = len(tiles)
    mean_x = sum(x for x, _y in tiles) / count
    mean_y = sum(y for _x, y in tiles) / count

    return min(tiles, key=lambda t: (t[0] - mean_x) ** 2 + (t[1] - mean_y) ** 2)


# ─── Public routines ─────────────────────────────────────────────────────────

def alphabet_holds_every_floor() -> bool:
    """Return True if WORLD_MAP_ALPHABET has a character for every class."""
    needed = len(floor_table.FLOOR_TYPES) * _CLASSES_PER_FLOOR

    return needed <= len(const.WORLD_MAP_ALPHABET)


def encode_tiles(chunk_file) -> str:
    """
    Purpose: Encode the tiles of one chunk file as one character each.

    Entry:
        chunk_file - a chunkfile.ChunkFile.

    Exit/Returns:
        A string of CHUNK_SIZE * CHUNK_SIZE characters, in the order of the
        chunk file lists.

    Module Globals:
        const.WORLD_MAP_ALPHABET read.

    Methodology:
        One class for each tile (the module docstring, "The encoding"), then
        one character for each class.

    Notes/References:
        godot/world/world_map_state.gd decodes it.

    Author: Nick Hobar
    Creation date: 09/28/2026
    """
    alphabet = const.WORLD_MAP_ALPHABET
    names = chunk_file.floor_names
    flags = chunk_file.flags
    characters = []

    for index, floor_index in enumerate(chunk_file.floors):
        tile_class = _tile_class(names[floor_index], flags[index])
        characters.append(alphabet[tile_class])

    return "".join(characters)


def summary_of(tile_plane, key: tuple) -> dict:
    """
    Purpose: Return the world map summary of one loaded chunk.

    Entry:
        tile_plane - a tilegrid.world.TilePlane.
        key        - the (cx, cy) of a loaded chunk of that plane.

    Exit/Returns:
        {"chunk": [cx, cy], "plane": int, "tiles": str, "objects": [...]}.
        Each object is {"kind", "x", "y"} at world tiles.

    Module Globals:
        _SUMMARIES read and written.

    Methodology:
        Built one time for each chunk of each loaded plane, then cached.

    Notes/References:
        The fields are those of payloads.WorldMapChunkPayload.

    Author: Nick Hobar
    Creation date: 09/28/2026
    """
    built = _SUMMARIES.setdefault(tile_plane, {})
    summary = built.get(key)

    if summary is not None:
        return summary

    chunk_file = tile_plane.chunk_file(key)
    objects = [{"kind": kind, "x": x, "y": y}
               for kind, x, y, _rotation in chunk_file.global_objects()]
    summary = {
        "chunk": [chunk_file.cx, chunk_file.cy],
        "plane": chunk_file.plane,
        "tiles": encode_tiles(chunk_file),
        "objects": objects,
    }
    built[key] = summary

    return summary


def area_labels(tile_plane) -> list:
    """
    Purpose: Return one label for each area of one plane.

    Entry:
        tile_plane - a tilegrid.world.TilePlane.

    Exit/Returns:
        [{"text", "x", "y", "plane"}, ...], sorted by area name.

    Module Globals:
        _LABELS read and written. area_table.AREAS read.

    Methodology:
        The module docstring, "The labels". An area with no row in AREAS
        shows its key.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/28/2026
    """
    labels = _LABELS.get(tile_plane)

    if labels is not None:
        return labels

    labels = []

    for name, tiles in sorted(_area_tiles(tile_plane).items()):
        row = area_table.AREAS.get(name)
        text = row.name if row is not None else name
        x, y = _nearest_to_centre(tiles)
        labels.append({"text": text, "x": x, "y": y,
                       "plane": tile_plane.plane})

    _LABELS[tile_plane] = labels

    return labels


def chunk_keys(world, first_plane: int = tile_const.GROUND_PLANE) -> list:
    """
    Return (cx, cy, plane) of every loaded chunk. The chunks of
    `first_plane` come first, so the plane of the player draws first.
    """
    keys = []

    for tile_plane in world.planes():
        for cx, cy in tile_plane.chunk_keys():
            keys.append((cx, cy, tile_plane.plane))

    keys.sort(key=lambda k: (k[2] != first_plane, k[2], k[1], k[0]))

    return keys


def index_of(world, first_plane: int = tile_const.GROUND_PLANE) -> dict:
    """
    Purpose: Return the index of the world map.

    Entry:
        world       - a tilegrid.world.TileWorld.
        first_plane - the plane whose chunks come first.

    Exit/Returns:
        {"planes": [int, ...], "chunks": [[cx, cy, plane], ...],
        "labels": [...]}. The fields of payloads.WorldMapPayload.

    Module Globals:
        None.

    Methodology:
        A plane with no loaded chunk is not in the index.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/28/2026
    """
    planes = []
    labels = []

    for tile_plane in world.planes():
        if not tile_plane.has_chunks():
            continue

        planes.append(tile_plane.plane)
        labels.extend(area_labels(tile_plane))

    chunks = [list(key) for key in chunk_keys(world, first_plane)]

    return {"planes": planes, "chunks": chunks, "labels": labels}
