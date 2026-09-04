"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: A memo over the neighbourhood lookup every feed event opens with.

What this is fixing
-------------------
`events._visible_rooms` calls `targeting.rooms_within_radius`, which issues one
bounding-box tag join and then re-reads `room.xyz` on every candidate to trim
the box to the metric. At STATEFEED_ENTITY_RADIUS = 10 that is a 21x21 box --
on every live map, the whole map -- and it measured 1.778 ms per call.

It is called three times per player move (the room left, the room entered, and
again for that room's contents rebuild) and once per observer on a resync. With
24 observers standing in one room, PERF-0002 measured **48 queries of which 46
were exact duplicates**: every observer independently asking the same question
about the same room and getting the same answer.

Why the answer is cacheable at all
----------------------------------
A neighbourhood is a fact about the MAP, not about who is standing in it.
Objects moving in and out do not change which rooms are within N tiles of a
room; only creating or destroying rooms does. So the cache is keyed by
(room id, radius) and invalidated wholesale whenever any tile is built or
demolished.

Why generation invalidation and not a tick lifetime
---------------------------------------------------
The obvious design -- hold the memo for one tick, clear it on flush, reusing
the seam `buffer.py` already has -- is wrong here, and it is worth writing down
why so nobody re-proposes it.

`buffer.py` deliberately holds NOTHING that a player's own command produced:

> Anything a player typed flushes immediately, because making `get sword` wait
> up to 600ms for its inventory update would trade a real problem for a worse
> one.

Movement is a command. So is resync. Those are exactly the paths that pay this
cost, and a tick-scoped memo would be empty every time one of them ran -- it
would cache the cheap case and miss the expensive one entirely.

Invalidating on room lifecycle instead makes the memo correct for any caller at
any time, which is what the callers actually are.

What invalidates it, and what does not
--------------------------------------
`GridTile.at_object_creation` and `GridTile.at_object_delete` call
`invalidate()`. CLAUDE.md records that the delete hook is "the only point
common to every way a tile dies" -- the manifest purge, `XYZGrid.remove_map`,
and the contrib deleting a tile that fell off the map -- which is precisely the
property a cache invalidator needs and no operator script could offer.

NOT covered: a room deleted by a DIFFERENT PROCESS while this one is running,
which is what `scripts/map_sync.py` does. That was already true of every caller
here before this module existed -- targeting.py's own docstring says callers
"must re-resolve rather than hold these objects indefinitely" -- and a map
rebuild requires a server reload anyway, which drops this module's state with
everything else's.

Why the whole cache is cleared rather than the affected keys
------------------------------------------------------------
Working out which cached neighbourhoods contained a demolished tile means
asking, for every key, whether the dead room was within radius of it -- which
is the query being cached, run once per entry. Clearing costs one dict
assignment and the next lookup rebuilds only what is asked for again. A map
rebuild is rare; a lookup is not.
"""

from evennia.utils import logger


# ─── Module globals ──────────────────────────────────────────────────────────

# (room id, radius) -> tuple of room objects. A tuple rather than a list so a
# caller cannot mutate the cached answer and quietly corrupt every later
# reader's copy -- serialize_area only ever iterates it.
_cache: dict = {}

# Counters, for tests and for `stats()`. Not for any decision: nothing in this
# module branches on them, so they cannot change behaviour if they drift.
_hits: int = 0
_misses: int = 0
_invalidations: int = 0


# ─── Public routines ─────────────────────────────────────────────────────────

def visible_rooms(room, radius: int) -> list:
    """
    Purpose: Return the rooms within `radius` of `room`, from cache when the
             map has not changed since the last time this was asked.

    Entry:
        room   - the origin room, or None.
        radius - the radius to cover. Passed in rather than read here, because
                 events._visible_rooms is documented as the single place
                 STATEFEED_ENTITY_RADIUS is read and that must stay true.

    Exit/Returns:
        Returns a list of room objects, always including `room` itself. Returns
        [] for a None room, matching rooms_within_radius.

        A LIST is returned, freshly built from the cached tuple, because
        callers have always received a list and one of them could append to it.
        The copy is 441 pointer writes against a 1.8 ms query.

    Module Globals:
        _cache, _hits, _misses written.

    Methodology:
        Never raises. This sits on the same gameplay paths emit() does, and the
        module contract there is that a cosmetic side-channel cannot break a
        move. A cache failure falls through to the uncached lookup rather than
        propagating, so the worst outcome of a bug here is the performance the
        game had before this module existed.

        Rooms with no id are not cached. A room mid-creation has no primary key
        to key on, and inventing one would put an entry in the cache that
        nothing could ever invalidate.

    Notes/References:
        See the module header for why invalidation is by room lifecycle rather
        than by tick.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    global _hits, _misses

    if room is None:
        return []

    from systems.combat.auras.targeting import rooms_within_radius

    room_id = getattr(room, "id", None)

    if room_id is None:
        return rooms_within_radius(room, radius)

    key = (room_id, radius)

    try:
        cached = _cache.get(key)

        if cached is not None:
            _hits += 1
            return list(cached)

        found = rooms_within_radius(room, radius)
        _cache[key] = tuple(found)
        _misses += 1

        return found
    except Exception:
        logger.log_trace()

        return rooms_within_radius(room, radius)


def invalidate() -> int:
    """
    Purpose: Drop every cached neighbourhood, because the map changed.

    Entry:
        No conditions. Safe to call when the cache is already empty, and safe
        to call from a room hook during server startup before anything has been
        cached.

    Exit/Returns:
        Returns how many entries were dropped, for logging and for tests.

    Module Globals:
        _cache, _invalidations written.

    Methodology:
        Wholesale, for the reason in the module header: deciding which entries
        a demolished tile appears in costs the query this module exists to
        avoid, once per entry.

        Never raises. Called from GridTile.at_object_delete, which runs inside
        a map rebuild that must not be able to fail because a cache did.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    global _invalidations

    try:
        dropped = len(_cache)
        _cache.clear()
        _invalidations += 1

        return dropped
    except Exception:
        logger.log_trace()

        return 0


def stats() -> dict:
    """Return hit/miss/size counters. For tests and diagnostics only."""
    return {"hits": _hits,
            "misses": _misses,
            "invalidations": _invalidations,
            "size": len(_cache)}


def reset() -> None:
    """Drop the cache and the counters. For tests, and after a reload."""
    global _hits, _misses, _invalidations

    _cache.clear()
    _hits = 0
    _misses = 0
    _invalidations = 0
