"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Make the objects on the tile grid match the chunk files: a
             facility, a gathering node, an NPC, or a sign for each placed
             object that stands something up.

Why an operator step
--------------------
Nick chose an operator script over a sync on each server start (09/24/2026).
A sync can delete objects, and a server start must not. Thus, `plan` changes
nothing, and `apply` does what a plan says.
`scripts/sync_tile_objects.py` prints the plan, and it applies the plan only
with `--apply`.

What a tile remembers
---------------------
A tile room that holds chunk objects stores the kind list of its last sync in
the attribute `TILE_KINDS_ATTR`. The attribute is safe on this room, because
a pin keeps the room on its tile (`TileRooms.pin`). The pool never moves it.

A signpost entry holds its words too: `signpost:Bank`
(`ENTRY_TEXT_SEPARATOR`). No kind name holds the separator
(CHUNK_NAME_PATTERN), so the first separator splits the entry.

New words on a sign are a refresh, not a change. `place_signpost` corrects
the words of the sign that stands, so a typo fix demolishes nothing. A
change would demolish the whole tile, and a sign often stands on the tile of
a facility. A sign that loses all of its words is a change, because
`place_signpost` cannot take the words away. `_entry_shape` holds this rule.

The four verbs
--------------
| Verb | When | What `apply` does |
|---|---|---|
| new | The chunk file places kinds on a tile with no record | Stand up each kind. Write the record |
| refresh | The kinds equal the record. Only the words of a sign may differ | Stand up each kind again. Each spawner does nothing if its object stands. A sign takes its new words. Write the record |
| changed | The kinds differ from the record | Demolish the contents, then stand up each kind. Write the record |
| removed | A record, but the chunk file places nothing | Demolish the contents. Delete the record. Unpin and release the room |

"Demolish" is `teardown.demolish_contents`, the rule that a deleted xyzgrid
tile follows today. It spares player characters at every level. A changed
tile thus loses what lay on its floor, as a rebuilt xyzgrid tile does.

The server keeps the room index in memory (`systems/core/tilegrid/rooms.py`).
Thus, run the script while the server is down, or reload the server after.
"""

from dataclasses import dataclass

from systems.core.tilegrid import constants as tile_const
from systems.gameplay.spawning import teardown
from world.object_kinds import OBJECT_KINDS


# ─── Public constant definitions ─────────────────────────────────────────────

# The room attribute that holds the kind list of the last sync.
TILE_KINDS_ATTR: str = "tile_kinds"

# Between the kind and the words of a sign entry in the kind list.
ENTRY_TEXT_SEPARATOR: str = ":"

VERB_NEW: str = "new"
VERB_REFRESH: str = "refresh"
VERB_CHANGED: str = "changed"
VERB_REMOVED: str = "removed"


# ─── Public classes ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TileAction:
    """
    One tile of a plan: its verb, its kinds now, its kinds before, and the
    plane of the tile (DESIGN-0011 Phase 7).
    """

    tile: tuple
    verb: str
    kinds: tuple
    previous: tuple
    plane: int = tile_const.GROUND_PLANE


# ─── Private helper routines ─────────────────────────────────────────────────

def _is_sign(kind) -> bool:
    """Return True if a kind stands a signpost with the text of its object."""
    return kind.category == tile_const.OBJECT_TEXT_CATEGORY


def _stands_something(kind) -> bool:
    """
    Return True if a kind stands an object up: a spawner or a sign. A
    transition and a landmark stand up nothing.
    """
    return bool(kind.spawner) or _is_sign(kind)


def _entry(key: str, text: str) -> str:
    """Return the kind list entry of one object: the key, and any words."""
    if not text:
        return key

    return key + ENTRY_TEXT_SEPARATOR + text


def _entry_shape(entry: str) -> str:
    """
    Return an entry without its words: the key, and the separator if the
    entry had words. Two kind lists of the same shapes differ only in the
    words of a sign, and the sync refreshes them (see the module docstring).
    """
    key, separator, _text = entry.partition(ENTRY_TEXT_SEPARATOR)

    return key + separator


def _same_shapes(kinds: tuple, previous: tuple) -> bool:
    """Return True if two kind lists differ at most in the words of signs."""
    shapes = tuple(_entry_shape(entry) for entry in kinds)
    previous_shapes = tuple(_entry_shape(entry) for entry in previous)

    return shapes == previous_shapes


def _standing_kinds(world, x: int, y: int) -> tuple:
    """
    Return the entries of the kinds on a tile that stand something up, in
    file order. A name that is not a row is left to
    `world/tests/test_tile_content.py`.
    """
    found = []

    for key, text in world.texts_at(x, y):
        kind = OBJECT_KINDS.get(key)

        if kind is None or not _stands_something(kind):
            continue

        found.append(_entry(key, text))

    return tuple(found)


def _records(world) -> dict:
    """Return tile -> (room, recorded kinds) of each live room with a record."""
    found = {}

    for tile, room in world.rooms.live_rooms():
        recorded = room.attributes.get(TILE_KINDS_ATTR, default=None)

        if recorded is not None:
            found[tile] = (room, tuple(recorded))

    return found


def _stand_up(room, entry: str) -> None:
    """
    Run the spawner of one kind list entry in a room, or stand its sign.
    Each spawner is idempotent. A sign with no words stands nothing, and
    `world/tile_checks.py` reports it.
    """
    from typeclasses.signs import place_signpost
    from typeclasses.spawners import SPAWNER_REGISTRY, load_all_spawners

    load_all_spawners()
    key, _separator, text = entry.partition(ENTRY_TEXT_SEPARATOR)
    kind = OBJECT_KINDS[key]

    if kind.spawner:
        SPAWNER_REGISTRY[kind.spawner](room)
    elif _is_sign(kind):
        place_signpost(room, text)


def _demolish(room) -> int:
    """
    Destroy the contents of a tile room, and drop its queued respawns. The
    room survives, so a queued NPC would come back on a changed tile.
    """
    from systems.gameplay.spawning.respawn import get_respawn_manager

    get_respawn_manager().cancel_room(room)

    return teardown.demolish_contents(room)


def _stand_up_all(room, kinds: tuple) -> None:
    """Stand up each kind list entry, and record the list on the room."""
    for entry in kinds:
        _stand_up(room, entry)

    room.attributes.add(TILE_KINDS_ATTR, list(kinds))


# ─── Public routines ─────────────────────────────────────────────────────────

def plan(world) -> list:
    """
    Purpose: Say what a sync would do on each tile. Change nothing.

    Entry:
        world - a TileWorld, with its room index loaded.

    Exit/Returns:
        A list of TileAction, sorted by plane, then by tile.

    Module Globals:
        TILE_KINDS_ATTR read.

    Methodology:
        Compare the standing kinds of each tile with the record on its room,
        one plane at a time. The four verbs are in the module docstring.

    Notes/References:
        One attribute read for each live room.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    actions = []

    for view in world.planes():
        actions.extend(_plan_plane(view))

    return actions


def _plan_plane(view) -> list:
    """The TileActions of one TilePlane, sorted by tile. See `plan`."""
    records = _records(view)
    actions = []
    placed = {(x, y) for _kind, x, y, _rotation in view.placed_objects()}

    for tile in sorted(placed | set(records)):
        kinds = _standing_kinds(view, *tile)
        previous = records.get(tile, (None, ()))[1]

        if not kinds and tile not in records:
            continue

        if not kinds:
            verb = VERB_REMOVED
        elif tile not in records:
            verb = VERB_NEW
        elif _same_shapes(kinds, previous):
            verb = VERB_REFRESH
        else:
            verb = VERB_CHANGED

        actions.append(TileAction(tile, verb, kinds, previous, view.plane))

    return actions


def apply(world, actions: list) -> int:
    """
    Purpose: Do what a plan says.

    Entry:
        world   - the TileWorld that `plan` read.
        actions - the list that `plan` returned.

    Exit/Returns:
        The number of objects that teardown destroyed.

    Module Globals:
        TILE_KINDS_ATTR read.

    Methodology:
        The table in the module docstring, one row for each verb.

    Notes/References:
        scripts/sync_tile_objects.py calls this with --apply.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    destroyed = 0

    for action in actions:
        x, y = action.tile
        rooms = world.plane(action.plane).rooms

        if action.verb == VERB_REMOVED:
            room = rooms.room_at(x, y)
            destroyed += _demolish(room)
            room.attributes.remove(TILE_KINDS_ATTR)
            rooms.unpin([action.tile])
            rooms.release(room)
            continue

        room = rooms.ensure_room(x, y)

        if action.verb == VERB_CHANGED:
            destroyed += _demolish(room)

        _stand_up_all(room, action.kinds)

    return destroyed
