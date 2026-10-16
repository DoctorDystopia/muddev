"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/26/2026
Description: Builds the fixture world of the content check parity test, and
             the list of findings that it must give.

The files in `fixtures/checks/` are the output of `build_fixtures`, written by
`chunkfile.to_text`. `test_tile_checks` rebuilds them and fails if a
committed file differs. Thus, this builder is the owner, and a hand edit of a
fixture fails at once.

`EXPECTED` is the list of findings, written by hand here. It is the intent,
not the output of `check_world`. `expected.json` holds the same list, and
both `test_tile_checks.py` and `godot/tests/test_terrain_checks.gd` compare
their findings with it.

To change the fixture, change this module, then run from `blackout/`:

    DJANGO_SETTINGS_MODULE=server.conf.settings ../evenv/Scripts/python.exe
        -c "import django; django.setup();
            from world.tests import check_fixture_builder as b; b.write_fixtures()"

Type it as one line. `object_kinds` imports the statefeed constants, and
their package imports Evennia, so Django must start first. Then run
`test_terrain_checks.tscn` in Godot.

Every name of a table file comes from its table, in the order of the table:
the area, the floor types, the roof, and the decor kind (10/14/2026). The
Tables tab of the terrain editor renames a key in these files in place.
Thus, a rename gives the same files as a fresh build.

The fixture world
-----------------
| File | Holds |
|---|---|
| chunk_0_0_p0.json | Sand, a few Blocked tiles, two respawn points, one object that breaks each object rule, decor on a Blocked tile, and three closed pockets |
| chunk_0_0_p1.json | Void and Blocked, but two tiles of the default floor, one void tile with no Blocked flag, one void tile with a wall, and two roof tiles |

Every rule gives at least one finding. Every good case gives none. The good
cases are a ladder that lands, the down way of a ladder, a sign with words,
a roof tile with the Blocked flag, decor on a Blocked tile, and a flight of
stairs whose two ways land.

The two flights test the landing ahead of `climb_landing` in both
languages (Nick, 10/16/2026). The good flight faces north. The tile over
its foot is void, so a check that looks on the same tile fails it. The bad
flight faces east. The tile over its foot is open, but its landing is void.
A wall on the stairwell of the good flight tests the stairwell exception of
`wall_on_void`.

The open roof tile is north of the open void tile, so one step joins the
two. Thus they make one `unreachable` pocket, not two.

The three pockets test the step rule of `unreachable` in both languages.
The first is a walled room. The second is a tile with Blocked sides, which
only a diagonal step could reach. The third is too high for the walk limit.
"""

import json
import os

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as const
from systems.core.tilegrid import syncstamp
from world import areas
from world import decor_kinds
from world import floor_types
from world import object_kinds
from world import tile_checks


# ─── Public constant definitions ─────────────────────────────────────────────

FIXTURE_DIRECTORY: str = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "fixtures", "checks")

EXPECTED_FILE: str = "expected.json"

# A tile sync stamp of the fixture files (`syncstamp.py`). The GDScript
# `TerrainSyncState` must find no changed file against it: the parity of the
# digest in the two languages.
STAMP_FILE: str = "sync_stamp.json"

# The two flights of stairs: the tile of each foot, and its rotation. The
# landing comes from the rule, so a new run of the kind moves it.
FLIGHT_KIND: str = "stairs_up"
GOOD_FLIGHT_FOOT: tuple = (14, 10)
GOOD_FLIGHT_TURN: int = 0
BAD_FLIGHT_FOOT: tuple = (16, 10)
BAD_FLIGHT_TURN: int = 1
GOOD_FLIGHT_LANDING: tuple = object_kinds.climb_landing(
    object_kinds.OBJECT_KINDS[FLIGHT_KIND], GOOD_FLIGHT_FOOT, GOOD_FLIGHT_TURN,
    const.CLIMB_UP)

# A stairwell tile of the good flight on plane 1: the tile over its top
# step. It carries a wall, as the wall of an upper room over the opening.
GOOD_FLIGHT_WELL: tuple = object_kinds.flight_tiles(
    object_kinds.OBJECT_KINDS[FLIGHT_KIND], GOOD_FLIGHT_FOOT, GOOD_FLIGHT_TURN,
    const.CLIMB_UP)[-1]

# (rule, x, y, plane) of each finding, sorted as check_world sorts them.
EXPECTED: list = sorted([
    (tile_checks.RULE_UNKNOWN_KIND, 20, 20, 0),
    (tile_checks.RULE_OBJECT_UNWALKABLE, 3, 3, 0),
    (tile_checks.RULE_TRANSITION_LANDING, 5, 5, 0),
    (tile_checks.RULE_CLIMB_LANDING, 11, 10, 0),
    (tile_checks.RULE_CLIMB_LANDING, 12, 10, 0),
    (tile_checks.RULE_CLIMB_LANDING, 10, 10, 1),
    (tile_checks.RULE_CLIMB_LANDING, *BAD_FLIGHT_FOOT, 0),
    (tile_checks.RULE_VOID_OPEN, 30, 30, 1),
    (tile_checks.RULE_RESPAWN_COUNT, 1, 1, 0),
    (tile_checks.RULE_RESPAWN_COUNT, 2, 1, 0),
    (tile_checks.RULE_SIGN_TEXT, 22, 20, 0),
    (tile_checks.RULE_SIGN_TEXT, 24, 20, 0),
    (tile_checks.RULE_WALL_ON_VOID, 31, 31, 1),
    (tile_checks.RULE_ROOF_WALKABLE, 30, 31, 1),
    # The three pockets of plane 0: walls, corners, and a slope.
    (tile_checks.RULE_UNREACHABLE, 40, 40, 0),
    (tile_checks.RULE_UNREACHABLE, 50, 50, 0),
    (tile_checks.RULE_UNREACHABLE, 56, 56, 0),
    # Plane 1: the down ladder of plane 0 at (12, 10) leads no one up, and
    # the open void tile is walkable. The bad flight lands past its top step,
    # so it leads no one to the open tile over its foot.
    (tile_checks.RULE_UNREACHABLE, 12, 10, 1),
    (tile_checks.RULE_UNREACHABLE, 30, 30, 1),
    (tile_checks.RULE_UNREACHABLE, *BAD_FLIGHT_FOOT, 1),
], key=lambda row: (row[0], row[3], row[2], row[1]))

# The 2 x 2 room of the wall pocket: its south-west tile.
WALLED_ROOM: tuple = (40, 40)

# The tile of the corner pocket. Its four side tiles are Blocked, and its
# four corner tiles are open. No diagonal step cuts a corner.
CORNER_POCKET: tuple = (50, 50)

# The tile of the slope pocket: all four corners at SLOPE_POCKET_HEIGHT.
SLOPE_POCKET: tuple = (56, 56)
SLOPE_POCKET_HEIGHT: int = const.WALK_LIMIT * 3

# A decor kind on a Blocked tile. The `object_unwalkable` rule exempts decor,
# so it gives no finding. The first decor kind of the table.
DECOR_KIND: str = next(iter(decor_kinds.DECOR_KINDS))
DECOR_ON_BLOCKED: tuple = (4, 3)


# ─── Private helper routines ─────────────────────────────────────────────────

def _blank(plane: int, floor_names: list) -> chunkfile.ChunkFile:
    tiles = const.CHUNK_SIZE * const.CHUNK_SIZE

    return chunkfile.ChunkFile(
        cx=0, cy=0, plane=plane, floor_names=floor_names,
        area_names=[areas.DEFAULT_AREA],
        heights=[0] * const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tiles, flags=[0] * tiles, areas=[0] * tiles)


def _index(x: int, y: int) -> int:
    return y * const.CHUNK_SIZE + x


def _add_pockets(ground: chunkfile.ChunkFile) -> None:
    """Close the three pockets of plane 0. See WALLED_ROOM and the others."""
    x, y = WALLED_ROOM
    ground.flags[_index(x, y)] = const.FLAG_WALL_SOUTH | const.FLAG_WALL_WEST
    ground.flags[_index(x + 1, y)] = const.FLAG_WALL_SOUTH | const.FLAG_WALL_EAST
    ground.flags[_index(x, y + 1)] = const.FLAG_WALL_NORTH | const.FLAG_WALL_WEST
    ground.flags[_index(x + 1, y + 1)] = (const.FLAG_WALL_NORTH
                                         | const.FLAG_WALL_EAST)

    x, y = CORNER_POCKET

    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ground.flags[_index(x + dx, y + dy)] = const.FLAG_BLOCKED

    x, y = SLOPE_POCKET

    for i, j in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)):
        ground.heights[j * const.CORNERS_PER_SIDE + i] = SLOPE_POCKET_HEIGHT


def _ground() -> chunkfile.ChunkFile:
    """Plane 0. Each object sits at its tile of EXPECTED, or is good."""
    ground = _blank(0, [floor_types.DEFAULT_FLOOR_TYPE])
    ground.flags[_index(3, 3)] = const.FLAG_BLOCKED
    ground.flags[_index(*DECOR_ON_BLOCKED)] = const.FLAG_BLOCKED
    _add_pockets(ground)
    ground.objects = [
        chunkfile.ChunkObject("respawn_point", 1, 1),
        chunkfile.ChunkObject("respawn_point", 2, 1),
        # Blocked tile.
        chunkfile.ChunkObject("bank", 3, 3),
        # Its target (72, 10) is in chunk (1, 0), which this world lacks.
        chunkfile.ChunkObject("transition_oasis_to_outskirts", 5, 5),
        # Lands on a floor of plane 1: good.
        chunkfile.ChunkObject("ladder_up", 10, 10),
        # Lands on void of plane 1.
        chunkfile.ChunkObject("ladder_up", 11, 10),
        # Leads under plane 0.
        chunkfile.ChunkObject("ladder_down", 12, 10),
        # Lands past its top step, on a floor of plane 1: good.
        chunkfile.ChunkObject(FLIGHT_KIND, *GOOD_FLIGHT_FOOT,
                              rotation=GOOD_FLIGHT_TURN),
        # Lands past its top step, on void of plane 1.
        chunkfile.ChunkObject(FLIGHT_KIND, *BAD_FLIGHT_FOOT,
                              rotation=BAD_FLIGHT_TURN),
        chunkfile.ChunkObject("no_such_kind", 20, 20),
        # A sign with no words.
        chunkfile.ChunkObject(object_kinds.SIGNPOST_KIND, 22, 20),
        # Words on a kind that is not a sign.
        chunkfile.ChunkObject("metal_pole", 24, 20, text="Cut me"),
        # A sign with words: good.
        chunkfile.ChunkObject(object_kinds.SIGNPOST_KIND, 26, 20,
                              text="Oasis Market"),
        # Decor on a Blocked tile: good (DESIGN-0013 section 6.5).
        chunkfile.ChunkObject(DECOR_KIND, *DECOR_ON_BLOCKED),
    ]

    return ground


def _upper() -> chunkfile.ChunkFile:
    """Plane 1: void and Blocked, but floors, roofs, and one open void tile."""
    roof = floor_types.ROOF_FLOOR_TYPES[0]
    upper = _blank(1, [floor_types.VOID_FLOOR_TYPE,
                       floor_types.DEFAULT_FLOOR_TYPE, roof])
    upper.flags = [const.FLAG_BLOCKED] * len(upper.flags)

    for x, y in ((10, 10), (12, 10), GOOD_FLIGHT_LANDING, BAD_FLIGHT_FOOT):
        upper.floors[_index(x, y)] = 1
        upper.flags[_index(x, y)] = 0

    # A roof with no Blocked flag, and a good roof.
    upper.floors[_index(30, 31)] = 2
    upper.flags[_index(30, 31)] = 0
    upper.floors[_index(34, 34)] = 2
    upper.flags[_index(30, 30)] = 0
    upper.flags[_index(31, 31)] = const.FLAG_BLOCKED | const.FLAG_WALL_NORTH
    # A wall on the stairwell of the good flight: void, but no finding.
    upper.flags[_index(*GOOD_FLIGHT_WELL)] |= const.FLAG_WALL_EAST
    # Down lands on plane 0, up on plane 2, which has no file.
    upper.objects = [
        chunkfile.ChunkObject("ladder_both", 10, 10),
        # The twin of the good flight. Down lands on its foot: good.
        chunkfile.ChunkObject("stairs_down", *GOOD_FLIGHT_LANDING,
                              rotation=GOOD_FLIGHT_TURN),
    ]

    return upper


# ─── Public routines ─────────────────────────────────────────────────────────

def build_fixtures() -> list:
    """Return the ChunkFile objects of the fixture world."""
    return [_ground(), _upper()]


def expected_text() -> str:
    """Return the text of expected.json: one finding on each line."""
    rows = [json.dumps(list(row)) for row in EXPECTED]

    return "[\n" + ",\n".join(rows) + "\n]\n"


def write_fixtures() -> None:
    """Write the fixture files and expected.json."""
    os.makedirs(FIXTURE_DIRECTORY, exist_ok=True)

    for chunk_file in build_fixtures():
        path = os.path.join(FIXTURE_DIRECTORY, chunk_file.file_name())
        chunkfile.write_file(path, chunk_file)

    path = os.path.join(FIXTURE_DIRECTORY, EXPECTED_FILE)

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(expected_text())

    syncstamp.write_stamp(FIXTURE_DIRECTORY,
                          os.path.join(FIXTURE_DIRECTORY, STAMP_FILE))


if __name__ == "__main__":
    write_fixtures()
