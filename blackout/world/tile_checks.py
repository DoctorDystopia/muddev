"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/26/2026
Description: The content rules of a tile world, checked over its chunk files.

             A chunk file reader checks the FORMAT of one file. This module
             checks what the files MEAN together: a transition must land on
             an open tile, a climb must land on a walkable tile of the next
             plane, and so on. Each rule that fails gives one `Finding`.

             TWO CALLERS, TWO LANGUAGES. `world/tests/test_tile_content.py`
             runs this over `world/chunks/`, so a bad world fails the suite.
             The Godot terrain editor runs the same rules over the block that
             the author edits, before a save ("Check world" in the dock).
             `godot/addons/blackout_terrain/terrain_checks.gd` is the GDScript
             twin. Both check the fixtures in `world/tests/fixtures/checks/`
             and compare with one `expected.json`, so the two cannot drift.
             The rule names are generated into `blackout_constants.gd`.

             A finding names a tile, not a file. The message is for a person
             and is not part of the parity: each language writes its own.

             This module imports no game code and no Evennia, because the
             client export reads it.

             DESIGN-0011 Phase 7c.
"""

from dataclasses import dataclass, field

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from world import floor_types
from world import object_kinds


# ─── Public constant definitions ─────────────────────────────────────────────

# An object names a kind that is not a row of world/object_kinds.py.
RULE_UNKNOWN_KIND: str = "unknown_kind"

# An object stands on a Blocked or water tile. A player must stand on the tile
# of a facility, a climb, and a transition, and an NPC spawns on its tile.
RULE_OBJECT_UNWALKABLE: str = "object_unwalkable"

# A transition target is off the loaded world or unwalkable, on the plane of
# the transition.
RULE_TRANSITION_LANDING: str = "transition_landing"

# A way of a climb leads past the top or bottom plane, or to a tile of the
# next plane that is off the world or unwalkable.
RULE_CLIMB_LANDING: str = "climb_landing"

# A void tile has no Blocked flag. A walker would stand on nothing.
RULE_VOID_OPEN: str = "void_open"

# The world has no respawn point, or more than one. Each one is a finding. No
# respawn point at all is one finding at tile (0, 0) of plane 0.
RULE_RESPAWN_COUNT: str = "respawn_count"

# A sign has no text, or an object of another kind has text. A sign with no
# words stands nothing in the tile sync, and the text of another kind has no
# reader.
RULE_SIGN_TEXT: str = "sign_text"

# Every rule, in the order the editor lists them.
RULES: tuple = (
    RULE_UNKNOWN_KIND,
    RULE_OBJECT_UNWALKABLE,
    RULE_TRANSITION_LANDING,
    RULE_CLIMB_LANDING,
    RULE_VOID_OPEN,
    RULE_RESPAWN_COUNT,
    RULE_SIGN_TEXT,
)


@dataclass(frozen=True, order=True)
class Finding:
    """One broken rule at one world tile. Sorts by rule, plane, y, x."""

    rule: str
    plane: int
    y: int
    x: int
    message: str = field(default="", compare=False)

    def key(self) -> tuple:
        """Return (rule, x, y, plane), the part that the parity compares."""
        return (self.rule, self.x, self.y, self.plane)


# ─── Private helper routines ─────────────────────────────────────────────────

def _walkable(grids: dict, plane: int, x: int, y: int) -> bool:
    """Return True if (x, y) of `plane` is loaded and holds a walker."""
    grid = grids.get(plane)

    if grid is None or not grid.has_tile(x, y):
        return False

    flags = grid.flags_at(x, y)

    return not flags & tile_const.FLAGS_UNWALKABLE


def _check_object(grids: dict, plane: int, kind_key: str, x: int,
                  y: int, text: str) -> list:
    """Return the findings of one placed object."""
    kind = object_kinds.OBJECT_KINDS.get(kind_key)
    where = f"{kind_key} at ({x}, {y}) plane {plane}"

    if kind is None:
        return [Finding(RULE_UNKNOWN_KIND, plane, y, x,
                        f"{where}: no such object kind")]

    found = []
    takes_text = kind.category == tile_const.OBJECT_TEXT_CATEGORY

    if takes_text != bool(text):
        problem = "has no text" if takes_text else "has text, but is no sign"
        found.append(Finding(RULE_SIGN_TEXT, plane, y, x, f"{where}: {problem}"))

    if not _walkable(grids, plane, x, y):
        found.append(Finding(RULE_OBJECT_UNWALKABLE, plane, y, x,
                             f"{where}: stands on a Blocked or water tile"))

    if kind.target and not _walkable(grids, plane, *kind.target):
        found.append(Finding(RULE_TRANSITION_LANDING, plane, y, x,
                             f"{where}: target {kind.target} is not open"))

    for way in kind.climbs:
        landing = plane + tile_const.CLIMB_PLANE_STEPS[way]

        if not _walkable(grids, landing, x, y):
            found.append(Finding(RULE_CLIMB_LANDING, plane, y, x,
                                 f"{where}: climb {way} lands on no open "
                                 f"tile of plane {landing}"))

    return found


def _check_void(chunk_file) -> list:
    """Return a finding for each void tile of a file with no Blocked flag."""
    names = chunk_file.floor_names

    if floor_types.VOID_FLOOR_TYPE not in names:
        return []

    void = names.index(floor_types.VOID_FLOOR_TYPE)
    size = tile_const.CHUNK_SIZE
    found = []

    for index, floor in enumerate(chunk_file.floors):
        if floor != void or chunk_file.flags[index] & tile_const.FLAG_BLOCKED:
            continue

        x = chunk_file.cx * size + index % size
        y = chunk_file.cy * size + index // size
        found.append(Finding(RULE_VOID_OPEN, chunk_file.plane, y, x,
                             f"void at ({x}, {y}) plane {chunk_file.plane} "
                             f"is not Blocked"))

    return found


def _check_respawn(respawns: list) -> list:
    """Return the findings of the respawn point count."""
    if len(respawns) == 1:
        return []

    if not respawns:
        return [Finding(RULE_RESPAWN_COUNT, tile_const.GROUND_PLANE, 0, 0,
                        "the world has no respawn point")]

    return [Finding(RULE_RESPAWN_COUNT, plane, y, x,
                    f"one of {len(respawns)} respawn points, at ({x}, {y}) "
                    f"plane {plane}")
            for plane, x, y in respawns]


# ─── Public routines ─────────────────────────────────────────────────────────

def check_world(chunk_files: list) -> list:
    """
    Purpose: Check the content rules over every chunk file of a world.

    Entry:
        chunk_files - checked ChunkFile objects, of any planes. A world with
                      no file gives one finding: no respawn point.

    Exit/Returns:
        A sorted list of Finding. Empty means the world is good.

    Module Globals:
        RULE_* read.

    Methodology:
        1. Build one grid for each plane (chunkfile.build_grid).
        2. Check each placed object: its kind, its tile, the landing of a
           transition on the same plane, and the landing of each climb way.
        3. Check each void tile of each file.
        4. Count the respawn points of the whole world.

    Notes/References:
        The GDScript twin is TerrainChecks.check_world. The world has no
        chunk outside the files given, so a landing in a missing chunk fails.

    Author: Nick Hobar
    Creation date: 09/26/2026
    """
    planes = {chunk_file.plane for chunk_file in chunk_files}
    grids = {plane: chunkfile.build_grid(chunk_files, plane) for plane in planes}
    found = []
    respawns = []

    for chunk_file in chunk_files:
        found.extend(_check_void(chunk_file))

        for kind_key, x, y, text in chunk_file.global_texts():
            found.extend(_check_object(grids, chunk_file.plane, kind_key, x, y,
                                       text))

            if kind_key == object_kinds.RESPAWN_KIND:
                respawns.append((chunk_file.plane, x, y))

    found.extend(_check_respawn(respawns))

    return sorted(found)
