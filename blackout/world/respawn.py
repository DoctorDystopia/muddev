"""
Purpose: The one owner of the fact "where does a dead player come back".

Entry:
    Imported by typeclasses/characters.py (Character.respawn). Nothing else
    should hard-code a respawn coordinate.

Exit/Returns:
    Exposes RESPAWN_XYZ and get_respawn_room().

Module Globals:
    RESPAWN_XYZ - the (x, y, zcoord) tuple a dead player returns to.

Methodology:
    Blackout sets neither START_LOCATION nor DEFAULT_HOME in settings.py, so
    before this module there was no respawn-room fact anywhere in the codebase
    and CombatEntity.respawn could only refill HP where the body fell.

    The anchor is a COORDINATE, not a map module name. world/maps/oasis.py was
    called world/maps/test_oasis.py until recently, and scripts/map_manifest.json
    is what binds a module to its zcoord -- so a module rename moves the
    manifest row, not the zcoord. Naming (0, 0, "oasis") survives that rename;
    naming "world.maps.test_oasis" would not have.

Notes/References:
    (0, 0) on the oasis map is "Oasis Entrance" -- a named landmark with no NPC
    prototype on the tile, and far enough from the Mutant Raider tile at (2, 3)
    that a player cannot respawn inside the fight that just killed them. That
    last property is the load-bearing one: see docs/2026-08-23-DESIGN-0003, §5,
    "Player death loop".

    Deliberately NOT an Evennia Attribute or a settings value. A constant in
    world/ is greppable, is version-controlled next to the map that defines the
    tile, and cannot drift per-database the way a stamped Attribute can.

Author: Nick Hobar
Creation date: 08/23/2026
"""

from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom
from evennia.utils import logger


# (x, y, zcoord). The zcoord is the map name assigned in
# scripts/map_manifest.json, NOT the module path that defines the map.
RESPAWN_XYZ = (0, 0, "oasis")


def get_respawn_room():
    """
    Purpose: Resolve RESPAWN_XYZ to a live room object.

    Entry:
        None. Reads the module-global RESPAWN_XYZ.

    Exit/Returns:
        The room at RESPAWN_XYZ, or None if it could not be resolved.

    Module Globals:
        RESPAWN_XYZ read.

    Methodology:
        get_xyz raises rather than returning None -- DoesNotExist when the grid
        has not been built (a fresh database, or a test that never ran
        map_sync), MultipleObjectsReturned if a rebuild left duplicate rows at
        one coordinate. Both are caught here and reported as None.

        Returning None rather than raising is the entire point of this
        function. Its only caller is Character.respawn, which runs inside
        at_death; an exception escaping there would abort the death sequence
        mid-way, leaving a player at 0 HP with combat already torn down. A
        missing respawn room must degrade to "you wake where you fell", never
        to a traceback.

    Notes/References:
        get_xyz matches subclasses of XYZRoom, so the GridTile rows the map
        builder actually creates are found. See the installed contrib at
        evennia/contrib/grid/xyzgrid/xyzroom.py.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    try:
        room = XYZRoom.objects.get_xyz(xyz=RESPAWN_XYZ)
    except Exception as exc:
        logger.log_err(
            f"get_respawn_room: no room at {RESPAWN_XYZ}: {exc!r}"
        )
        return None

    return room
