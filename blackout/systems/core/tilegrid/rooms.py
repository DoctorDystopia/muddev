"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The rooms of the tile grid: a room only where something stands,
             an index from tile to room, and a pool of empty rooms.

The rule this keeps
-------------------
"A thing's location is its tile." Reach, the statefeed neighbourhood, facility
spawners, and the teardown hook all read it. DESIGN-0011 section 6.1 picks
option B to keep it: every tile that holds a thing has a real Evennia room,
and every other tile has none.

Why a pool
----------
A step onto an empty tile needs a room there, and the step off the old tile
leaves an empty room behind. Without a pool, that is one create and one delete
for each step. With a pool, the empty room waits, and the next step moves it to
the new tile by a change of its coordinate tags. The spike measures both. The
Evennia wilderness contrib reuses rooms for the same reason.

Why an index in memory
----------------------
`room_at` runs on every step and `rooms_near` on every statefeed event. A tag
query for each would put the xyzgrid's cost back. The index is a dict. It is
correct while this process is the only writer, which is the same condition
that `systems/interface/statefeed/neighbourhood.py` states for its cache.
`load` rebuilds it from the database after a reload.

The coordinate tags
-------------------
A tile room carries the same three tags as an xyzgrid tile, so `room.xyz` and
`XYZRoom.objects.filter_xyz` work on it. The Z is the world name. A pooled
room keeps its last x and y tags, and its Z becomes the pool name. Thus, no
search on the world finds it, and a move out of the pool often changes one
coordinate and the Z only.

Why the tags are written past the TagHandler
--------------------------------------------
The first spike run moved a pooled room with `tags.remove` and `tags.add`. Each
call re-reads every tag of the room, and a pooled step cost 47 queries. This
module writes the join rows itself: one DELETE for the old tags and one INSERT
for the new ones. Then it resets the handler cache, so the next read through
`room.tags` sees the rows. It also stores `_xyz` on the room, which is the
cache that `XYZRoom.xyz` reads first.
"""

from evennia.contrib.grid.xyzgrid.xyzroom import (
    MAP_X_TAG_CATEGORY,
    MAP_Y_TAG_CATEGORY,
    MAP_Z_TAG_CATEGORY,
)
from evennia.objects.models import ObjectDB
from evennia.utils.create import create_object

from . import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

# The three coordinate categories, in xyz order.
_COORDINATE_CATEGORIES: tuple = (
    MAP_X_TAG_CATEGORY,
    MAP_Y_TAG_CATEGORY,
    MAP_Z_TAG_CATEGORY,
)

# The instance attribute that XYZRoom fills with the map of the room. A room
# that moves must forget it.
_CACHED_MAP_ATTR: str = "_xymap"

# The instance attribute that XYZRoom.xyz reads before it reads any tag.
_CACHED_XYZ_ATTR: str = "_xyz"

# The join table between an object and its tags.
_TAG_LINK = ObjectDB.db_tags.through


# ─── Private helper routines ─────────────────────────────────────────────────

def _room_typeclass():
    """
    Return the TileRoom class. Imported here and not at module scope, because
    typeclasses/rooms.py imports the statefeed, and the statefeed must stay
    free to import this package later.
    """
    from typeclasses.rooms import TileRoom

    return TileRoom


def _chunk_of(x: int, y: int) -> tuple:
    """Return the chunk coordinates of tile (x, y)."""
    return (x // const.CHUNK_SIZE, y // const.CHUNK_SIZE)


def _chebyshev_metric(dx: int, dy: int, radius: int) -> bool:
    """Return True if the offset is inside a square of this radius."""
    return max(abs(dx), abs(dy)) <= radius


# ─── Public routines / Classes ───────────────────────────────────────────────

class TileRooms:
    """
    The live rooms of one tile world, and its pool of empty rooms.

    A caller asks for the room at a tile with `ensure_room`, and gives an
    empty room back with `release`. Nothing else makes or frees a TileRoom.
    """

    def __init__(self, world_z: str = const.WORLD_Z,
                 pool_capacity: int = const.POOL_CAPACITY):
        self.world_z = world_z
        self.pool_z = world_z + const.POOL_Z_SUFFIX
        self.pool_capacity = pool_capacity
        self._live = {}
        self._by_chunk = {}
        self._pool = []
        self._tags = {}
        self._pinned = set()

    # ── Pins ─────────────────────────────────────────────────────────────

    def pin(self, tiles) -> None:
        """
        Keep the room of each tile out of the pool, even when it is empty.

        A tile that holds a chunk object is pinned. An NPC stores its spawn
        room as a reference (`db.spawn_room`). If the pool moved that room,
        the NPC would respawn on another tile. A pin makes no room. It only
        stops `release`.
        """
        self._pinned.update(tuple(tile) for tile in tiles)

    def unpin(self, tiles) -> None:
        """Let the room of each tile go back to the pool when it is empty."""
        self._pinned.difference_update(tuple(tile) for tile in tiles)

    def is_pinned(self, x: int, y: int) -> bool:
        """Return True if the room of tile (x, y) never goes to the pool."""
        return (x, y) in self._pinned

    # ── Reads ────────────────────────────────────────────────────────────

    def room_at(self, x: int, y: int):
        """Return the live room at tile (x, y), or None."""
        return self._live.get((x, y))

    def live_rooms(self) -> list:
        """Return ((x, y), room) of every live room, sorted by tile."""
        return sorted(self._live.items(), key=lambda item: item[0])

    def live_count(self) -> int:
        """Return how many tiles have a room now."""
        return len(self._live)

    def pool_count(self) -> int:
        """Return how many empty rooms wait in the pool."""
        return len(self._pool)

    def rooms_near(self, x: int, y: int, radius: int, metric=None) -> list:
        """
        Purpose: Return every live room within `radius` of tile (x, y).

        Entry:
            (x, y) - global tile coordinates. Need not have a room.
            radius - non-negative radius in tiles.
            metric - `(dx, dy, radius) -> bool`. None means Chebyshev. The
                     statefeed passes `targeting.within_metric`, so the tile
                     grid and the aura overlay use one metric.

        Exit/Returns:
            A list of rooms, in no fixed order. No database query.

        Module Globals:
            const.CHUNK_SIZE read.

        Methodology:
            1. List the chunks that the box of the radius touches.
            2. Test each live tile in those chunks against the metric.
            The cost follows the live rooms near the tile, not the tile count.

        Notes/References:
            The port of `neighbourhood.visible_rooms` to the tile grid.
            DESIGN-0011 section 6.1.

        Author: Nick Hobar
        Creation date: 09/24/2026
        """
        inside = metric or _chebyshev_metric
        low_chunk = _chunk_of(x - radius, y - radius)
        high_chunk = _chunk_of(x + radius, y + radius)
        found = []

        for cx in range(low_chunk[0], high_chunk[0] + 1):
            for cy in range(low_chunk[1], high_chunk[1] + 1):
                for tile in self._by_chunk.get((cx, cy), ()):
                    if inside(tile[0] - x, tile[1] - y, radius):
                        found.append(self._live[tile])

        return found

    # ── Writes ───────────────────────────────────────────────────────────

    def ensure_room(self, x: int, y: int):
        """
        Purpose: Return the room at tile (x, y), and make one if it has none.

        Entry:
            (x, y) - global tile coordinates. The caller checked that a thing
                     may stand there. This routine checks nothing.

        Exit/Returns:
            The live TileRoom at the tile.

        Module Globals:
            None.

        Methodology:
            An existing room first. Then a room from the pool, moved to this
            tile. Then a new room.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 09/24/2026
        """
        room = self._live.get((x, y))

        if room is not None:
            return room

        if self._pool:
            room = self._pool.pop()
            self._retag(room, (x, y, self.world_z))
        else:
            room = self._create(x, y)

        self._index(room, x, y)

        return room

    def release(self, room) -> bool:
        """
        Purpose: Give back a room whose tile holds nothing now.

        Entry:
            room - a live TileRoom of this world, or any other room.

        Exit/Returns:
            True if the room left the index. Else False, and nothing changes.
            The room stays if it holds a thing or a pin holds its tile. It
            also stays if it is not a live room of this world.

        Module Globals:
            None.

        Methodology:
            An empty room goes to the pool, with the pool Z. If the pool is
            full, the room is deleted.

        Notes/References:
            `room.contents` is Evennia's cached list, so this costs no query
            for a room that the caller just left.

        Author: Nick Hobar
        Creation date: 09/24/2026
        """
        tile = self._tile_of(room)

        if tile is None or tile in self._pinned or room.contents:
            return False

        self._unindex(tile)

        if len(self._pool) >= self.pool_capacity:
            room.delete()
            return True

        self._retag(room, (tile[0], tile[1], self.pool_z))
        self._pool.append(room)

        return True

    def sweep(self) -> int:
        """
        Purpose: Give back every live room that holds nothing now.

        Entry:
            No conditions.

        Exit/Returns:
            The number of rooms that left the index.

        Module Globals:
            None.

        Methodology:
            1. Drop a deleted room from the index. A staff `destroy` deletes
               a room, and the index does not see it.
            2. `release` each other room. It keeps a room that holds a thing
               or that a pin holds.

        Notes/References:
            Handoff debt 13. Only `movement.step` and `movement.place` call
            `release` at the move. A teleport, a logout, and a delete leave an
            empty room behind. `systems/core/tilegrid/sweep.py` calls this on
            the tick. No query for a room with cached contents.

        Author: Nick Hobar
        Creation date: 09/26/2026
        """
        released = 0

        for tile, room in self.live_rooms():
            if room.pk is None:
                self._unindex(tile)
                released += 1
            elif self.release(room):
                released += 1

        return released

    def load(self) -> None:
        """
        Purpose: Rebuild the index and the pool from the database.

        Entry:
            No conditions. Call it once after a reload, before the first step.

        Exit/Returns:
            None. The previous index and pool are dropped.

        Module Globals:
            None.

        Notes/References:
            Two queries: the live rooms of this world, and its pooled rooms.

        Author: Nick Hobar
        Creation date: 09/24/2026
        """
        manager = _room_typeclass().objects
        live = manager.filter_xyz(xyz=("*", "*", self.world_z))
        pooled = manager.filter_xyz(xyz=("*", "*", self.pool_z))

        self._live = {}
        self._by_chunk = {}
        self._pool = list(pooled)

        for room in live:
            x, y, _z = room.xyz
            self._index(room, x, y)

    # ── Private ──────────────────────────────────────────────────────────

    def _tile_of(self, room):
        """Return the indexed tile of this room, or None."""
        coordinates = getattr(room, "xyz", None)

        if not coordinates:
            return None

        tile = (coordinates[0], coordinates[1])

        if self._live.get(tile) is not room:
            return None

        return tile

    def _index(self, room, x: int, y: int) -> None:
        self._live[(x, y)] = room
        self._by_chunk.setdefault(_chunk_of(x, y), set()).add((x, y))

    def _unindex(self, tile: tuple) -> None:
        del self._live[tile]
        chunk_tiles = self._by_chunk.get(_chunk_of(tile[0], tile[1]))

        if chunk_tiles is not None:
            chunk_tiles.discard(tile)

    def _create(self, x: int, y: int):
        """Make a new TileRoom at tile (x, y)."""
        tags = [(str(x), MAP_X_TAG_CATEGORY),
                (str(y), MAP_Y_TAG_CATEGORY),
                (self.world_z, MAP_Z_TAG_CATEGORY)]

        return create_object(_room_typeclass(), key=const.ROOM_KEY, tags=tags)

    def _tag(self, value, category: str):
        """Return the Tag row for one coordinate value. Cached."""
        cache_key = (str(value), category)
        tag = self._tags.get(cache_key)

        if tag is None:
            tag = _room_typeclass().objects.create_tag(
                key=cache_key[0], category=category)
            self._tags[cache_key] = tag

        return tag

    def _retag(self, room, new_xyz: tuple) -> None:
        """
        Purpose: Change the coordinate tags of a room to `new_xyz`.

        Entry:
            room    - a TileRoom whose `xyz` is its present coordinates.
            new_xyz - (x, y, z), with int x and y.

        Exit/Returns:
            None. `room.xyz` is `new_xyz` after the call.

        Module Globals:
            _TAG_LINK, _COORDINATE_CATEGORIES read.

        Methodology:
            1. Compare each coordinate with the present one.
            2. Delete the join rows of the changed ones, in one query.
            3. Insert the join rows of the new ones, in one query.
            4. Reset the tag cache, and store the new `_xyz`.

        Notes/References:
            See "Why the tags are written past the TagHandler" above.

        Author: Nick Hobar
        Creation date: 09/24/2026
        """
        old_xyz = room.xyz
        dropped = []
        added = []

        for old, new, category in zip(old_xyz, new_xyz, _COORDINATE_CATEGORIES):
            if str(old) != str(new):
                dropped.append(self._tag(old, category).id)
                added.append(_TAG_LINK(objectdb_id=room.id,
                                       tag_id=self._tag(new, category).id))

        if dropped:
            _TAG_LINK.objects.filter(objectdb_id=room.id,
                                     tag_id__in=dropped).delete()
            _TAG_LINK.objects.bulk_create(added)

        room.tags.reset_cache()
        room.__dict__.pop(_CACHED_MAP_ATTR, None)
        setattr(room, _CACHED_XYZ_ATTR, tuple(new_xyz))
