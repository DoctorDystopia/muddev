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

             A rule in NOTE_RULES gives a NOTE, not a finding: it warns, and
             no test fails on it (DESIGN-0013 section 6.7). The world may hold
             a closed pocket on purpose.

             DESIGN-0011 Phase 7c. DESIGN-0013 Phase S1 added `wall_on_void`
             and `unreachable`, and Phase S2 added `roof_walkable`. Phase S4
             exempts decor from `object_unwalkable`.
"""

from collections import deque
from dataclasses import dataclass, field

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from world import floor_types
from world import object_kinds


# ─── Public constant definitions ─────────────────────────────────────────────

# An object names a kind that is not a row of world/object_kinds.py.
RULE_UNKNOWN_KIND: str = "unknown_kind"

# An object stands on a Blocked or water tile. A player must stand on the tile
# of a facility, a climb, and a transition, and an NPC spawns on its tile. A
# decor kind is exempt, because it is a look. A Blocked tile under a table
# stops a walk through it (DESIGN-0013 section 6.5).
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

# A void tile carries a wall bit. No wall draws on a void tile, and no walker
# stands beside it. A Build tool or a hand edit left it there.
RULE_WALL_ON_VOID: str = "wall_on_void"

# A pocket of walkable tiles that no walk from the respawn point reaches,
# through steps, transitions, and climbs. One note for each pocket, at its
# first tile (lowest y, then x). A pocket is a set of unreached tiles that
# steps join on one plane. A NOTE: a sealed room with no doorway, or an upper
# level with no stairs.
RULE_UNREACHABLE: str = "unreachable"

# A tile with a roof floor type has no Blocked flag. A roof is the ground of
# the plane above a structure, and no walk may reach it (DESIGN-0013 section
# 6.2). The Roof tool sets both at once.
RULE_ROOF_WALKABLE: str = "roof_walkable"

# Every rule, in the order the editor lists them.
RULES: tuple = (
    RULE_UNKNOWN_KIND,
    RULE_OBJECT_UNWALKABLE,
    RULE_TRANSITION_LANDING,
    RULE_CLIMB_LANDING,
    RULE_VOID_OPEN,
    RULE_RESPAWN_COUNT,
    RULE_SIGN_TEXT,
    RULE_WALL_ON_VOID,
    RULE_UNREACHABLE,
    RULE_ROOF_WALKABLE,
)

# The rules that give a note. A note warns and fails no test. Nick may make
# `unreachable` a finding later (DESIGN-0013 section 6.7).
NOTE_RULES: tuple = (RULE_UNREACHABLE,)

# The eight steps of a walker, as (dx, dy).
_STEPS: tuple = tuple(tile_const.DIRECTION_OFFSETS.values())


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

    def is_note(self) -> bool:
        """Return True for a note: a warning that fails no test."""
        return self.rule in NOTE_RULES


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

    is_decor = kind.category == tile_const.OBJECT_CATEGORY_DECOR

    if not is_decor and not _walkable(grids, plane, x, y):
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


def _floor_findings(floor: str, flags: int, plane: int, x: int,
                    y: int) -> list:
    """
    Return the findings of one tile by its floor: a void tile with no Blocked
    flag or with a wall bit, and a roof tile with no Blocked flag.
    """
    where = f"{floor} at ({x}, {y}) plane {plane}"
    blocked = flags & tile_const.FLAG_BLOCKED
    found = []

    if floor == floor_types.VOID_FLOOR_TYPE:
        if not blocked:
            found.append(Finding(RULE_VOID_OPEN, plane, y, x,
                                 f"{where} is not Blocked"))

        if flags & tile_const.FLAGS_WALLS:
            found.append(Finding(RULE_WALL_ON_VOID, plane, y, x,
                                 f"{where} carries a wall"))

    if floor in floor_types.ROOF_FLOOR_TYPES and not blocked:
        found.append(Finding(RULE_ROOF_WALKABLE, plane, y, x,
                             f"{where} is a roof, but is not Blocked"))

    return found


def _check_floors(chunk_file) -> list:
    """Return the findings of _floor_findings for each tile of a file."""
    size = tile_const.CHUNK_SIZE
    names = chunk_file.floor_names
    found = []

    for index, floor in enumerate(chunk_file.floors):
        x = chunk_file.cx * size + index % size
        y = chunk_file.cy * size + index // size
        found.extend(_floor_findings(names[floor], chunk_file.flags[index],
                                     chunk_file.plane, x, y))

    return found


def _walkable_tiles(chunk_files: list) -> list:
    """Return (plane, y, x) of every walkable tile, sorted."""
    size = tile_const.CHUNK_SIZE
    tiles = []

    for chunk_file in chunk_files:
        for index, flags in enumerate(chunk_file.flags):
            if not flags & tile_const.FLAGS_UNWALKABLE:
                tiles.append((chunk_file.plane,
                              chunk_file.cy * size + index // size,
                              chunk_file.cx * size + index % size))

    return sorted(tiles)


def _links(chunk_files: list, grids: dict) -> dict:
    """
    Return (plane, x, y) -> [(plane, x, y), ...]: where the transitions and
    the climbs of each tile lead. Only a walkable landing counts.
    """
    links = {}

    for chunk_file in chunk_files:
        plane = chunk_file.plane

        for kind_key, x, y, _text in chunk_file.global_texts():
            kind = object_kinds.OBJECT_KINDS.get(kind_key)

            if kind is None:
                continue

            ends = [(plane, *kind.target)] if kind.target else []
            ends += [(plane + tile_const.CLIMB_PLANE_STEPS[way], x, y)
                     for way in kind.climbs]
            links.setdefault((plane, x, y), []).extend(
                end for end in ends if _walkable(grids, *end))

    return links


def _step_ends(grids: dict, plane: int, x: int, y: int) -> list:
    """Return (plane, x, y) of each tile that one legal step reaches."""
    grid = grids[plane]
    ends = []

    for dx, dy in _STEPS:
        result = grid.check_step((x, y), (x + dx, y + dy))

        if result == tile_const.STEP_OK:
            ends.append((plane, x + dx, y + dy))

    return ends


def _reached(grids: dict, links: dict, starts: list) -> set:
    """Return (plane, x, y) of every tile that a walk from `starts` reaches."""
    reached = {point for point in starts if _walkable(grids, *point)}
    queue = deque(reached)

    while queue:
        point = queue.popleft()

        for end in _step_ends(grids, *point) + links.get(point, []):
            if end not in reached:
                reached.add(end)
                queue.append(end)

    return reached


def _flood_pocket(grids: dict, start: tuple, reached: set, seen: set) -> int:
    """Mark each unreached tile that steps join to `start`. Return the count."""
    seen.add(start)
    queue = deque([start])
    count = 0

    while queue:
        point = queue.popleft()
        count += 1

        for end in _step_ends(grids, *point):
            if end not in reached and end not in seen:
                seen.add(end)
                queue.append(end)

    return count


def _check_reach(chunk_files: list, grids: dict, respawns: list) -> list:
    """Return one unreachable note for each pocket. See RULE_UNREACHABLE."""
    if not respawns:
        return []

    reached = _reached(grids, _links(chunk_files, grids), respawns)
    seen = set()
    found = []

    # Sorted by plane, y, x: the first tile of a pocket is its lowest.
    for plane, y, x in _walkable_tiles(chunk_files):
        point = (plane, x, y)

        if point in reached or point in seen:
            continue

        count = _flood_pocket(grids, point, reached, seen)
        found.append(Finding(RULE_UNREACHABLE, plane, y, x,
                             f"{count} walkable tile(s) from ({x}, {y}) plane "
                             f"{plane} that no walk from the respawn point "
                             f"reaches"))

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
        A sorted list of Finding, notes included. Empty means the world is
        good. Finding.is_note picks out the notes.

    Module Globals:
        RULE_* read.

    Methodology:
        1. Build one grid for each plane (chunkfile.build_grid).
        2. Check each placed object: its kind, its tile, the landing of a
           transition on the same plane, and the landing of each climb way.
        3. Check each tile by its floor: a void tile is Blocked and has no
           wall, and a roof tile is Blocked.
        4. Count the respawn points of the whole world.
        5. Walk from each respawn point through steps, transitions, and
           climbs. Give one note for each pocket of walkable tiles that the
           walk does not reach.

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
        found.extend(_check_floors(chunk_file))

        for kind_key, x, y, text in chunk_file.global_texts():
            found.extend(_check_object(grids, chunk_file.plane, kind_key, x, y,
                                       text))

            if kind_key == object_kinds.RESPAWN_KIND:
                respawns.append((chunk_file.plane, x, y))

    found.extend(_check_respawn(respawns))
    found.extend(_check_reach(chunk_files, grids, respawns))

    return sorted(found)
