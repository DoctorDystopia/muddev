"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: The one owner of the fact "where does a dead player come back".
             Exposes RESPAWN_KIND, respawn_tile() and get_respawn_room().
             Nowhere may hard-code a respawn coordinate.

Blackout sets neither START_LOCATION nor DEFAULT_HOME in settings.py, so before
this module there was no respawn-room fact anywhere in the codebase and
CombatEntity.respawn could only refill HP where the body fell.

THE RESPAWN POINT IS AN OBJECT IN A CHUNK FILE. The object kind
`respawn_point` (world/object_kinds.py) marks the tile. An author moves it in
the terrain editor, and no code changes. Until 09/25/2026 this module held the
constant (0, 0, "oasis"), the "Oasis Entrance" room of the xyzgrid map. The
object now stands on the same tile, and its kind carries the same room name.
Nick chose the object over a constant tile, 09/25/2026.

The tile of a chunk object is pinned (`TileRooms.pin`). Thus, the pool never
moves the room of the respawn point to another tile, and a character's
`home` can hold that room.

Three callers read it: Character.respawn (a death), Account.create_character
(a new character), and Character.at_pre_puppet (a login with no tile). The
tile must be far from a fight, so that a player cannot respawn inside the
fight that just killed them. See docs/2026-08-23-DESIGN-0003, section 5,
"Player death loop".
"""

from evennia.utils import logger

from systems.core.tilegrid.world import get_world
from world.object_kinds import RESPAWN_KIND


# ─── Public routines ─────────────────────────────────────────────────────────

def respawn_tile(world):
    """
    Purpose: Find the tile of the respawn point in a tile world.

    Entry:
        world - a TileWorld.

    Exit/Returns:
        The world tile (x, y) of the first `RESPAWN_KIND` object, in tile
        order. None if no chunk file places one.

    Module Globals:
        RESPAWN_KIND read.

    Methodology:
        `placed_objects` sorts by tile, so two respawn points give the same
        answer on every call. world/tests/test_respawn_point.py asserts that
        the world chunks place exactly one.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/25/2026
    """
    for kind, x, y, _rotation in world.placed_objects():
        if kind == RESPAWN_KIND:
            return (x, y)

    return None


def get_respawn_room(world=None):
    """
    Purpose: Resolve the respawn point to a live room object.

    Entry:
        world - a TileWorld. None means the tile world of this process.

    Exit/Returns:
        The tile room at the respawn point, or None if it could not be
        resolved.

    Module Globals:
        None.

    Methodology:
        `ensure_room` gives the live room of the tile, or makes one. The pin
        of the chunk object keeps that room on the tile.

        Returning None rather than raising is the entire point of this
        function. Character.respawn runs inside at_death. An exception there
        would abort the death sequence mid-way, and leave a player at 0 HP
        with combat already torn down. A missing respawn point must degrade
        to "you wake where you fell", never to a traceback.

    Notes/References:
        DESIGN-0011, Phase 4b.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    try:
        loaded = world or get_world()
        tile = respawn_tile(loaded)

        if tile is None:
            logger.log_err(f"get_respawn_room: no chunk file places {RESPAWN_KIND}")
            return None

        room = loaded.rooms.ensure_room(tile[0], tile[1])
    except Exception as exc:
        logger.log_err(f"get_respawn_room: no room at the respawn point: {exc!r}")
        return None

    return room
