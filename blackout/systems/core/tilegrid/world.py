"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The tile world of this server: every chunk file, loaded one time,
             as one `TilePlane` for each plane.

What this module owns
---------------------
The step rule, the path search, and the room pool each take a grid or a room
index as an argument. Thus, a test can build a small world by hand. The live
game needs one world, loaded from `world/chunks/`, and one place to ask for it.
`get_world` is that place.

The world loads on first use, not at server start. A server with no chunk
file thus pays nothing.

What a tile has, beside its flags
---------------------------------
The grid holds the heights, the floor indexes, and the flags. It does not hold
the names of the floors and the areas, nor the placed objects. The chunk file
holds them. A plane keeps each of its chunk files, and it reads a name through
the chunk file of the tile.

Planes
------
DESIGN-0011 Phase 7. A `TilePlane` is one plane: its grid, its rooms (with
their own Z, `planes.plane_z`), its chunk files, and its placed objects. It
has the interface that `TileWorld` had before planes. Thus, a routine that
took the world (the tile map, `open_directions`, `tiles_named`) takes a plane
with no edit.

`TileWorld` holds a plane for every plane number, 0 to PLANE_MAX, with or
without chunk files. A plane with no chunk file has an empty grid, so every
tile of it reads as blocked, and a climb to it is refused. Its reads of
plane 0 (`grid`, `rooms`, `kinds_at`, and the rest) stay, for the code and
the tests of one plane.

DESIGN-0011 section 6.1, step 1, and section 6.9.
"""

import os

from . import chunkfile
from . import constants as const
from .planes import plane_of_z, plane_z
from .rooms import TileRooms


# ─── Private module globals ──────────────────────────────────────────────────

# The world of this process. None until the first `get_world`.
_WORLD = None


# ─── Private helper routines ─────────────────────────────────────────────────

def chunk_directory() -> str:
    """
    Return the path of the world chunk directory. `settings.TILE_WORLD_DIR`
    overrides it. The test settings point it at a directory that does not
    exist. Thus, a test with no world of its own gets an empty world.
    The world is a module global. A real world in one test keeps the rooms
    of a rolled-back transaction. The next test then moves a character into
    a room that is gone.
    """
    from django.conf import settings

    override = getattr(settings, "TILE_WORLD_DIR", None)

    if override:
        return override

    return os.path.join(settings.GAME_DIR, const.CHUNK_DIRECTORY)


def _local(x: int, y: int) -> tuple:
    """Return (chunk key, lx, ly) of a global tile."""
    size = const.CHUNK_SIZE

    return ((x // size, y // size), x % size, y % size)


# ─── Public routines / Classes ───────────────────────────────────────────────

class TilePlane:
    """
    One plane of a tile world: the grid, the rooms, and the chunk files
    behind them.

    `grid` and `rooms` are the objects that `movement.step` and
    `pathfind.find_path` take. The name reads go through the chunk files.

    `unpinned` holds the object kinds whose placement pins no room: the decor
    kinds (`world.object_kinds.UNPINNED_KINDS`). This package does not know
    the kinds, so the caller gives them. An empty set pins every placed tile.
    """

    def __init__(self, chunk_files: list, plane: int = const.GROUND_PLANE,
                 world_z: str = const.WORLD_Z, unpinned=frozenset()):
        mine = [f for f in chunk_files if f.plane == plane]
        self.plane = plane
        self.grid = chunkfile.build_grid(mine, plane)
        self.rooms = TileRooms(plane_z(plane, world_z))
        self._files = {(f.cx, f.cy): f for f in mine}
        self._wire = {}
        self._objects = {}

        for chunk_file in mine:
            origin_x = chunk_file.cx * const.CHUNK_SIZE
            origin_y = chunk_file.cy * const.CHUNK_SIZE

            for thing in chunk_file.objects:
                tile = (origin_x + thing.x, origin_y + thing.y)
                self._objects.setdefault(tile, []).append(
                    (thing.kind, thing.rotation, thing.text))

        # A tile with a placed object keeps its room (TileRooms.pin). A tile
        # that holds only unpinned kinds does not.
        self.rooms.pin(tile for tile, placed in self._objects.items()
                       if any(kind not in unpinned for kind, _r, _t in placed))

    @property
    def world_z(self) -> str:
        """Return the Z of every live room of this plane."""
        return self.rooms.world_z

    def has_chunks(self) -> bool:
        """Return True if a chunk file of this plane is loaded."""
        return bool(self._files)

    def has_tile(self, x: int, y: int) -> bool:
        """Return True if a loaded chunk holds tile (x, y)."""
        return self.grid.has_tile(x, y)

    def area_at(self, x: int, y: int):
        """Return the area name of a tile, or None off the loaded grid."""
        key, lx, ly = _local(x, y)
        chunk_file = self._files.get(key)

        if chunk_file is None:
            return None

        return chunk_file.area_name(lx, ly)

    def floor_at(self, x: int, y: int):
        """Return the floor type name of a tile, or None off the grid."""
        key, lx, ly = _local(x, y)
        chunk_file = self._files.get(key)

        if chunk_file is None:
            return None

        return chunk_file.floor_name(lx, ly)

    def kinds_at(self, x: int, y: int) -> list:
        """Return the object kinds placed on a tile, in file order."""
        placed = self._objects.get((x, y), ())
        kinds = [kind for kind, _rotation, _text in placed]

        return kinds

    def texts_at(self, x: int, y: int) -> list:
        """
        Return (kind, text) of each object placed on a tile, in file order.
        The text is "" for an object that carries none.
        """
        placed = self._objects.get((x, y), ())
        texts = [(kind, text) for kind, _rotation, text in placed]

        return texts

    def placed_at(self, x: int, y: int) -> list:
        """
        Return (kind, rotation, text) of each object placed on a tile, in
        file order. The tile sync gives the rotation to the entity that a
        kind stands up.
        """
        placed = self._objects.get((x, y), ())

        return list(placed)

    def placed_objects(self) -> list:
        """Return (kind, x, y, rotation) of every placed object."""
        found = []

        for (x, y), placed in sorted(self._objects.items()):
            for kind, rotation, _text in placed:
                found.append((kind, x, y, rotation))

        return found

    def chunk_keys(self) -> list:
        """Return the (cx, cy) of every loaded chunk, sorted."""
        return sorted(self._files)

    def block_keys(self, x: int, y: int,
                   radius: int = const.STREAM_RADIUS_CHUNKS) -> list:
        """
        Return the (cx, cy) of each loaded chunk in the block around the
        chunk of tile (x, y), sorted. The statefeed streams this block.
        """
        key, _lx, _ly = _local(x, y)
        found = []

        for cx in range(key[0] - radius, key[0] + radius + 1):
            for cy in range(key[1] - radius, key[1] + radius + 1):
                if (cx, cy) in self._files:
                    found.append((cx, cy))

        return sorted(found)

    def chunk_dict(self, key: tuple) -> dict:
        """
        Return the wire form of one loaded chunk (`chunkfile.to_dict`). Built
        one time for each chunk, because every player near it gets the same.
        """
        cached = self._wire.get(key)

        if cached is None:
            cached = chunkfile.to_dict(self._files[key])
            self._wire[key] = cached

        return cached

    def chunk_file(self, key: tuple):
        """
        Return the loaded ChunkFile at (cx, cy). Raises KeyError for a chunk
        that is not loaded. The world map summary reads it. Do not change it.
        """
        return self._files[key]


class TileWorld:
    """
    One tile world: a TilePlane for each plane number, 0 to PLANE_MAX.

    The reads of plane 0 stay on the world itself, for the code that knows
    one plane. A routine that acts for a walker asks for the plane of the
    walker (`world/tile_travel.plane_view`).
    """

    def __init__(self, chunk_files: list, world_z: str = const.WORLD_Z,
                 unpinned=frozenset()):
        self.name = world_z
        self._planes = {
            plane: TilePlane(chunk_files, plane, world_z, unpinned)
            for plane in range(const.GROUND_PLANE, const.PLANE_MAX + 1)
        }

    # ── Planes ───────────────────────────────────────────────────────────

    def plane(self, plane: int) -> TilePlane:
        """Return one plane. Raises KeyError for a number past PLANE_MAX."""
        return self._planes[plane]

    def planes(self) -> list:
        """Return every plane, plane 0 first."""
        return [self._planes[plane] for plane in sorted(self._planes)]

    def plane_for_z(self, z):
        """Return the plane whose rooms have Z `z`, or None."""
        plane = plane_of_z(z, self.name)

        if plane is None:
            return None

        return self._planes[plane]

    def load_rooms(self) -> None:
        """Rebuild the room index of every plane from the database."""
        for tile_plane in self.planes():
            tile_plane.rooms.load()

    def block_chunks(self, x: int, y: int, first_plane: int = const.GROUND_PLANE,
                     radius: int = const.STREAM_RADIUS_CHUNKS) -> list:
        """
        Return (cx, cy, plane) of each loaded chunk of every plane in the
        block around the chunk of tile (x, y). The chunks of `first_plane`
        come first, because the ground under a walker is on its own plane.
        The statefeed streams this list (Phase 7b).
        """
        found = []

        for tile_plane in self.planes():
            for cx, cy in tile_plane.block_keys(x, y, radius):
                found.append((cx, cy, tile_plane.plane))

        found.sort(key=lambda key: (key[2] != first_plane, key[2], key[0], key[1]))

        return found

    def sweep_rooms(self) -> int:
        """Sweep the rooms of every plane. Return how many rooms went back."""
        released = 0

        for tile_plane in self.planes():
            released += tile_plane.rooms.sweep()

        return released

    # ── Plane 0 ──────────────────────────────────────────────────────────

    @property
    def ground(self) -> TilePlane:
        """Return plane 0."""
        return self._planes[const.GROUND_PLANE]

    @property
    def grid(self):
        """Return the grid of plane 0."""
        return self.ground.grid

    @property
    def rooms(self):
        """Return the rooms of plane 0."""
        return self.ground.rooms

    @property
    def world_z(self) -> str:
        """Return the Z of every live room of plane 0."""
        return self.ground.world_z

    def has_tile(self, x: int, y: int) -> bool:
        """Plane 0: see TilePlane.has_tile."""
        return self.ground.has_tile(x, y)

    def area_at(self, x: int, y: int):
        """Plane 0: see TilePlane.area_at."""
        return self.ground.area_at(x, y)

    def floor_at(self, x: int, y: int):
        """Plane 0: see TilePlane.floor_at."""
        return self.ground.floor_at(x, y)

    def kinds_at(self, x: int, y: int) -> list:
        """Plane 0: see TilePlane.kinds_at."""
        return self.ground.kinds_at(x, y)

    def texts_at(self, x: int, y: int) -> list:
        """Plane 0: see TilePlane.texts_at."""
        return self.ground.texts_at(x, y)

    def placed_objects(self) -> list:
        """Plane 0: see TilePlane.placed_objects."""
        return self.ground.placed_objects()

    def chunk_keys(self) -> list:
        """Plane 0: see TilePlane.chunk_keys."""
        return self.ground.chunk_keys()

    def block_keys(self, x: int, y: int,
                   radius: int = const.STREAM_RADIUS_CHUNKS) -> list:
        """Plane 0: see TilePlane.block_keys."""
        return self.ground.block_keys(x, y, radius)

    def chunk_dict(self, key: tuple) -> dict:
        """Plane 0: see TilePlane.chunk_dict."""
        return self.ground.chunk_dict(key)


def load_world(directory: str = None, world_z: str = const.WORLD_Z):
    """
    Purpose: Read a chunk directory into a new TileWorld, and rebuild its
             room index from the database.

    Entry:
        directory - a path. None means `world/chunks/` of the game.
        world_z   - the name of this world, the Z of its plane-0 rooms.

    Exit/Returns:
        A TileWorld. Raises chunkfile.ChunkFileError for a bad chunk file.

    Module Globals:
        None.

    Methodology:
        `chunkfile.load_directory` reads and checks each file. The room index
        of each plane then loads with two queries (`TileRooms.load`). A decor
        kind pins no room (`world.object_kinds.UNPINNED_KINDS`).

    Notes/References:
        A test that needs no database builds `TileWorld(chunk_files)` itself
        and skips the room load. The import of the kinds is here, as the
        import of `typeclasses.rooms` is late in `rooms.py`: the kinds import
        the statefeed constants, and the tile grid must not need them.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    from world.object_kinds import UNPINNED_KINDS

    path = directory or chunk_directory()
    chunk_files = chunkfile.load_directory(path)
    world = TileWorld(chunk_files, world_z, UNPINNED_KINDS)
    world.load_rooms()

    return world


def get_world() -> TileWorld:
    """
    Return the tile world of this process. The first call loads it, and
    attaches the sweep of its empty rooms to the tick (`sweep.py`). The
    import is here because `sweep.py` imports this module.
    """
    global _WORLD

    if _WORLD is None:
        _WORLD = load_world()

        from . import sweep

        sweep.attach()

    return _WORLD


def loaded_world():
    """
    Return the tile world of this process, or None if nothing loaded it yet.
    A caller on the tick uses this, so that the tick never reads the chunk
    files.
    """
    return _WORLD


def set_world(world) -> None:
    """
    Replace the tile world of this process. A test passes its own world, and
    passes None after, so the next `get_world` loads the real one.
    """
    global _WORLD

    _WORLD = world
