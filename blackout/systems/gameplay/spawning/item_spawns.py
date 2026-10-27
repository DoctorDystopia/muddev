"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/21/2026
Description: The item spawn: an item that lies on its tile, and a new one a
             number of ticks after a player takes it.

The rules (Nick, 10/21/2026)
----------------------------
1. Each placement holds its own spawn: the `spawn` of its chunk object, as a
   signpost holds its words. One kind, `item_spawn`, serves every
   placement.
2. The respawn is a count of game ticks, as OSRS gives a ground spawn.
3. The clock starts when the item leaves its tile. Any move starts it: a
   `get`, or a staff `teleport`. A player who drops an item of the same kind
   on the tile does not stop the clock.
4. Each new item rolls its quantity in the range of the spawn.

The chunk file is the one owner
-------------------------------
The item of a spawn carries one attribute, `SPAWN_ITEM_ATTR`: the item key of
its spawn. It carries no respawn and no quantity. When the clock comes due,
`respawn` reads the spawn from the tile world. Thus, an edit of the respawn
or the quantity reaches the next item with no tile sync. A spawn that the
chunk file no longer holds gives no item.

The item drops the attribute, the facing, and the look when it leaves the
tile. In a bag, it is an item like any other. Thus, a drop on another tile
starts no clock, and a scale of the placement does not follow the item.

The sweep of the respawn queue runs every RESPAWN_SWEEP_SECONDS. Thus, an
item can come that much late.

Who calls what
--------------
| Caller | Routine |
|---|---|
| The tile sync (`tile_sync.py`) | `place`, `clear_stale` |
| `TileRoom.at_object_leave` (`typeclasses/rooms.py`) | `on_leave` |
| The respawn queue (`respawn.py`) | `respawn` |

Nothing here raises. A bad spawn is logged and gives no item.
"""

import random

from evennia.utils import logger

from systems.core.tick.constants import TICK_SECONDS
from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid.world import get_world


# ─── Private constant definitions ────────────────────────────────────────────

# The attributes that a placement gives the item, and that the item drops
# when it leaves the tile.
_PLACEMENT_ATTRS: tuple = (tile_const.SPAWN_ITEM_ATTR, tile_const.FACING_ATTR,
                           tile_const.LOOK_ATTR)

# The RNG of the quantity roll in the game. A test gives its own seeded RNG.
_RNG = random.Random()


# ─── Private helper routines ─────────────────────────────────────────────────

def _spawn_items_in(room, item_key: str) -> list:
    """Return each item in `room` that the spawn of `item_key` put down."""
    found = []

    for obj in room.contents:
        if obj.attributes.get(tile_const.SPAWN_ITEM_ATTR) == item_key:
            found.append(obj)

    return found


def _tile_spawn(room, item_key: str):
    """
    Return (rotation, look, spawn) of the spawn of `item_key` on the tile of
    `room`, or None. A room off the tile world gives None.
    """
    if room is None or getattr(room, "pk", None) is None:
        return None

    coordinates = room.xyz
    view = get_world().plane_for_z(coordinates[2])

    if view is None:
        return None

    return view.spawn_at(int(coordinates[0]), int(coordinates[1]), item_key)


def _respawn_seconds(spawn: dict) -> int:
    """Return the respawn of a spawn in whole seconds, from its ticks."""
    ticks = spawn[tile_const.SPAWN_RESPAWN_KEY]

    return int(round(ticks * TICK_SECONDS))


def _create(room, spawn: dict, facing, look, rng):
    """
    Purpose: Make the item of a spawn and put it on the tile of `room`.

    Entry:
        room   - the tile room.
        spawn  - the spawn table of the chunk object.
        facing - the rotation of the chunk object, or None.
        look   - the look of the chunk object, or None for none.
        rng    - the RNG of the quantity roll.

    Exit/Returns:
        The item, or None for an item key that is not in ITEM_DB.

    Module Globals:
        None.

    Methodology:
        1. Roll the quantity in the range of the spawn. An item that does
           not stack takes one, whatever the range: tile_checks refuses a
           range on it, and this is the guard of a hand edit.
        2. Make the item detached, give it the attributes of the placement,
           then move it. The move fires `at_object_receive`, so each client
           near the tile gets the item. The first row already holds the
           facing and the look.

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    from world.item_database import ITEM_DB

    item_key = spawn[tile_const.SPAWN_ITEM_KEY]
    item_def = ITEM_DB.get(item_key)

    if item_def is None:
        logger.log_err(f"item spawn: no item {item_key!r} in ITEM_DB.")
        return None

    low, high = chunkfile.spawn_quantity(spawn)
    quantity = rng.randint(low, high) if item_def.stackable else low
    item = item_def.create(location=None, home=room, quantity=quantity)

    item.attributes.add(tile_const.SPAWN_ITEM_ATTR, item_key)

    if facing is not None:
        item.attributes.add(tile_const.FACING_ATTR, facing)

    if look:
        item.attributes.add(tile_const.LOOK_ATTR, dict(look))

    item.move_to(room, quiet=True)

    return item


# ─── Public routines ─────────────────────────────────────────────────────────

def place(room, spawn: dict, facing=None, look=None, rng=None):
    """
    Purpose: Put the item of a spawn on its tile, if the spawn is empty.

    Entry:
        room   - the tile room of the spawn.
        spawn  - the spawn table of the chunk object.
        facing - the rotation of the chunk object, or None.
        look   - the look of the chunk object, or None for none.
        rng    - the RNG of the quantity roll, or None for the game RNG.

    Exit/Returns:
        The item on the tile: the one that lies there, or a new one. None
        while the clock runs, and for a bad item key.

    Module Globals:
        _RNG read.

    Methodology:
        Idempotent, because the tile sync runs it on each refresh. An item
        of the spawn on the tile wins. A queued respawn waits for its clock,
        so a sync does not cut the respawn short. Only an empty spawn with
        no clock gets a new item.

    Notes/References:
        The tile sync then gives the item on the tile its facing and its
        look, as for each entity that it stands up. A new item gets them
        before its move, so the first row of a client holds them.

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    from systems.gameplay.spawning.respawn import get_respawn_manager

    item_key = spawn[tile_const.SPAWN_ITEM_KEY]
    lying = _spawn_items_in(room, item_key)

    if lying:
        return lying[0]

    if get_respawn_manager().is_item_queued(item_key, room):
        return None

    return _create(room, spawn, facing, look, rng or _RNG)


def clear_stale(room, item_keys) -> int:
    """
    Purpose: Remove the items and the clocks of spawns that a tile lost.

    Entry:
        room      - a tile room.
        item_keys - the item key of each spawn that the tile holds now.

    Exit/Returns:
        The number of items deleted.

    Module Globals:
        None.

    Methodology:
        An author can change the item of a spawn. The tile sync plans that
        as a refresh, because the kind did not change. The item of the old
        spawn then lies on the tile, and no spawn owns it. This deletes it,
        and drops the clock of the old item.

        Only a tile that still holds a spawn reads the queue. A tile that
        lost its last spawn has a new kind list. The sync plans it as a
        change or a removal, and `_demolish` drops each clock of the room.

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    from systems.gameplay.spawning.respawn import get_respawn_manager

    keep = set(item_keys)
    deleted = 0

    for obj in list(room.contents):
        owner = obj.attributes.get(tile_const.SPAWN_ITEM_ATTR)

        if owner and owner not in keep:
            obj.delete()
            deleted += 1

    if keep:
        get_respawn_manager().cancel_items(room, keep)

    return deleted


def on_leave(room, item) -> bool:
    """
    Purpose: Start the clock of a spawn when its item leaves the tile.

    Entry:
        room - the tile room that the item leaves.
        item - an object that carries SPAWN_ITEM_ATTR.

    Exit/Returns:
        True if a respawn was queued.

    Module Globals:
        None.

    Methodology:
        1. Take the attributes of the placement off the item. It is now an
           item like any other.
        2. Find the spawn of its item key on the tile. A spawn that the
           chunk file lost queues nothing.
        3. Queue the respawn after the ticks of the spawn, in seconds.

    Notes/References:
        Evennia fires `at_object_leave` before the item moves, and a
        `delete` fires no leave. Thus, the teardown of a tile starts no
        clock.

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    from systems.gameplay.spawning.respawn import schedule_item_respawn

    item_key = item.attributes.get(tile_const.SPAWN_ITEM_ATTR)

    for attr in _PLACEMENT_ATTRS:
        item.attributes.remove(attr)

    found = _tile_spawn(room, item_key)

    if found is None:
        return False

    _rotation, _look, spawn = found

    return schedule_item_respawn(item_key, room, _respawn_seconds(spawn))


def respawn(item_key: str, room, rng=None) -> bool:
    """
    Purpose: Put a new item on the tile of a spawn whose clock came due.

    Entry:
        item_key - the item key of the spawn.
        room     - the tile room of the spawn.
        rng      - the RNG of the quantity roll, or None for the game RNG.

    Exit/Returns:
        True if an item was made.

    Module Globals:
        _RNG read.

    Methodology:
        Read the spawn from the tile world, not from the queue. A spawn that
        the chunk file lost gives nothing. An item of the spawn that already
        lies there gives nothing, so a tile sync during the clock cannot
        make two.

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    found = _tile_spawn(room, item_key)

    if found is None or _spawn_items_in(room, item_key):
        return False

    rotation, look, spawn = found
    item = _create(room, spawn, rotation, look, rng or _RNG)

    return item is not None
