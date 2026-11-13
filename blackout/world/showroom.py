"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/03/2026
Description: The showroom: a generated world that holds one of each item and
             one of each object kind, side by side, to compare them.

Why a separate world
--------------------
A developer compares every model of the game in one place (Nick,
11/03/2026). The showroom runs on its own server. `showroom_settings.py`
gives it a separate database, a separate chunk directory
(`TILE_WORLD_DIR`), and separate play ports. Thus, the live world and the
live database never change.

This module makes the chunk files and writes nothing by itself.
`scripts/showroom.py` writes them, and with `--apply` it runs the tile sync
into the showroom database.

The layout
----------
One aisle for each group, from south to north. A signpost at the west end
of each aisle names the group and counts it. The item aisles come first, one
for each item family, in the order of ITEM_FAMILY_PRIORITY. The aisles of
the object kinds follow, one for each category, in the order of
OBJECT_KINDS. An aisle that is too long for one row continues on the next
row. The respawn point stands at the entrance, in the south-west corner.
Each object faces south, toward the entrance.

Each tile has the default floor type and the default area, with no height
and no wall. A layout that is taller than one chunk continues in the chunk
to the north.

Each item lies on an item spawn with the minimum respawn. A taken item thus
comes back after one tick, plus at most one sweep of the respawn queue.

What it leaves out
------------------
| What | Why |
|---|---|
| A dev tool | `spawn_items.item_rows` leaves it out. No item spawn may name one |
| A transition | Its target is a tile of the real world |
| A climb | It needs a second plane |

New content needs no edit here. A new item, family, object kind, or
category gets into the showroom at the next run.
"""

import os
from dataclasses import dataclass, field

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.interface.statefeed import constants as feed_const
from world import areas
from world import floor_types
from world import object_kinds


# ─── Public constant definitions ─────────────────────────────────────────────

# The rotation of each object: south, toward the entrance. An index of
# ROTATION_STEPS.
FACING: int = tile_const.ROTATION_STEPS.index((0, -1))

# The respawn of each item spawn, in ticks: the minimum.
RESPAWN_TICKS: int = tile_const.SPAWN_RESPAWN_MIN

# The categories that the showroom leaves out, with the reason.
SKIPPED_CATEGORIES: dict = {
    tile_const.OBJECT_CATEGORY_TRANSITION:
        "its target is a tile of the real world",
    tile_const.OBJECT_CATEGORY_CLIMB: "it needs a second plane",
}

# The kinds that the layout places itself: the label of each aisle, the item
# of each spawn, and the entrance.
LAYOUT_KINDS: frozenset = frozenset({
    object_kinds.SIGNPOST_KIND,
    object_kinds.ITEM_SPAWN_KIND,
    object_kinds.RESPAWN_KIND,
})


# ─── Private constant definitions ────────────────────────────────────────────

# The x of the signpost of each aisle, and the last x that an object may use.
_WEST_X: int = 2
_EAST_X: int = tile_const.CHUNK_SIZE - 3

# The tile of the respawn point, and the y of the first aisle.
_ENTRANCE: tuple = (2, 1)
_FIRST_AISLE_Y: int = 4

# The tiles between two items in a row, and between two rows of items.
_ITEM_STEP: int = 2
_ITEM_ROW_STEP: int = 3

# The same for the object kinds. An NPC or a facility is larger than an item.
_KIND_STEP: int = 4
_KIND_ROW_STEP: int = 5

# The word between the words of a family key.
_KEY_SEPARATOR: str = "_"


# ─── Public classes ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Aisle:
    """
    One group of the showroom. Each entry is (kind, spawn). The spawn is {}
    for a kind that is not an item spawn. `step` is the tiles between two
    entries, and `row_step` the tiles between two rows.
    """

    label: str
    entries: tuple
    step: int
    row_step: int


@dataclass(frozen=True)
class Placement:
    """One object of the showroom, at world tiles of plane 0."""

    kind: str
    x: int
    y: int
    text: str = ""
    spawn: dict = field(default_factory=dict)


@dataclass
class Showroom:
    """
    The chunk files of the showroom, the aisles that they hold, and each
    kind that the showroom leaves out, as (kind, reason).
    """

    chunk_files: list
    aisles: list
    skipped_kinds: list


# ─── Private helper routines ─────────────────────────────────────────────────

def _words(key: str) -> str:
    """Return a key as words: "crafting_material" gives "Crafting material"."""
    words = key.replace(_KEY_SEPARATOR, " ")
    sentence = words.capitalize()

    return sentence


def _sign_text(name: str, count: int) -> str:
    """Return the words of the signpost of an aisle: its name and its count."""
    return f"{name} ({count})"


def _family_order(families: set) -> list:
    """
    Return the families in the order of ITEM_FAMILY_PRIORITY, then the
    generic family, then each other family by name.
    """
    known = list(feed_const.ITEM_FAMILY_PRIORITY)
    known.append(feed_const.ITEM_FAMILY_GENERIC)
    ordered = [family for family in known if family in families]
    others = sorted(families - set(known))

    return ordered + others


def _category_label(category: str) -> str:
    """Return the editor label of a category, or the category as words."""
    fallback = _words(category)
    label = tile_const.OBJECT_CATEGORY_LABELS.get(category, fallback)

    return label


def _blank_chunk(cy: int) -> chunkfile.ChunkFile:
    """Return chunk (0, cy) of plane 0: flat, open, with no object."""
    tiles = tile_const.CHUNK_SIZE * tile_const.CHUNK_SIZE
    corners = tile_const.CORNERS_PER_SIDE * tile_const.CORNERS_PER_SIDE

    chunk = chunkfile.ChunkFile(
        cx=0, cy=cy, plane=0,
        floor_names=[floor_types.DEFAULT_FLOOR_TYPE],
        area_names=[areas.DEFAULT_AREA],
        heights=[tile_const.DEFAULT_HEIGHT] * corners,
        floors=[0] * tiles, flags=[tile_const.FLAG_NONE] * tiles,
        areas=[0] * tiles)

    return chunk


def _same_directory(first: str, second: str) -> bool:
    """Return True if two paths name one directory."""
    first_path = os.path.normcase(os.path.abspath(first))
    second_path = os.path.normcase(os.path.abspath(second))

    return first_path == second_path


# ─── Public routines ─────────────────────────────────────────────────────────

def item_aisles(item_rows: list) -> list:
    """
    Purpose: Give one aisle for each item family.

    Entry:
        item_rows - the rows of `spawn_items.item_rows()`: {key, name,
                    family, stackable}, sorted by key.

    Exit/Returns:
        Returns a list of Aisle. Each entry is an item spawn of one item,
        with the respawn RESPAWN_TICKS.

    Module Globals:
        RESPAWN_TICKS read.

    Author: Nick Hobar
    Creation date: 11/03/2026
    """
    by_family = {}

    for row in item_rows:
        spawn = {tile_const.SPAWN_ITEM_KEY: row["key"],
                 tile_const.SPAWN_RESPAWN_KEY: RESPAWN_TICKS}
        entry = (object_kinds.ITEM_SPAWN_KIND, spawn)
        by_family.setdefault(row["family"], []).append(entry)

    aisles = []

    for family in _family_order(set(by_family)):
        entries = tuple(by_family[family])
        label = _sign_text(_words(family), len(entries))
        aisles.append(Aisle(label, entries, _ITEM_STEP, _ITEM_ROW_STEP))

    return aisles


def kind_aisles(kinds: dict) -> tuple:
    """
    Purpose: Give one aisle for each category of object kinds.

    Entry:
        kinds - {kind key: ObjectKind}, in the order of the editor, as
                OBJECT_KINDS.

    Exit/Returns:
        Returns (aisles, skipped). `aisles` is a list of Aisle. `skipped`
        is a list of (kind key, reason) for each kind of SKIPPED_CATEGORIES.

    Module Globals:
        LAYOUT_KINDS and SKIPPED_CATEGORIES read.

    Methodology:
        A kind of LAYOUT_KINDS is no entry: the layout places it. Each other
        kind is one entry, in the aisle of its category. The aisles keep the
        order in which their categories first come in `kinds`.

    Author: Nick Hobar
    Creation date: 11/03/2026
    """
    by_category = {}
    skipped = []

    for key, kind in kinds.items():
        if key in LAYOUT_KINDS:
            continue

        reason = SKIPPED_CATEGORIES.get(kind.category)

        if reason is not None:
            skipped.append((key, reason))
            continue

        by_category.setdefault(kind.category, []).append((key, {}))

    aisles = []

    for category, entries in by_category.items():
        label = _sign_text(_category_label(category), len(entries))
        aisles.append(Aisle(label, tuple(entries), _KIND_STEP, _KIND_ROW_STEP))

    return aisles, skipped


def lay_out(aisles: list) -> list:
    """
    Purpose: Give each object of the showroom its tile.

    Entry:
        aisles - a list of Aisle, from south to north.

    Exit/Returns:
        Returns a list of Placement: the respawn point, then for each aisle
        its signpost and its entries.

    Module Globals:
        None.

    Methodology:
        The signpost of an aisle stands at _WEST_X. Its entries follow to
        the east, `step` tiles apart. An entry past _EAST_X starts a new row,
        `row_step` tiles to the north. The next aisle starts `row_step` tiles
        north of the last row.

    Author: Nick Hobar
    Creation date: 11/03/2026
    """
    entrance_x, entrance_y = _ENTRANCE
    placed = [Placement(object_kinds.RESPAWN_KIND, entrance_x, entrance_y)]
    y = _FIRST_AISLE_Y

    for aisle in aisles:
        placed.append(Placement(object_kinds.SIGNPOST_KIND, _WEST_X, y,
                                text=aisle.label))
        first_x = _WEST_X + aisle.step
        x = first_x

        for kind, spawn in aisle.entries:
            if x > _EAST_X:
                x = first_x
                y += aisle.row_step

            placed.append(Placement(kind, x, y, spawn=dict(spawn)))
            x += aisle.step

        y += aisle.row_step

    return placed


def chunk_files_of(placements: list) -> list:
    """
    Purpose: Put each placement into the chunk file that holds its tile.

    Entry:
        placements - a list of Placement, each at x < CHUNK_SIZE and y >= 0.

    Exit/Returns:
        Returns a list of ChunkFile, chunk (0, 0) first, up to the chunk of
        the most northern placement. A chunk with no placement is still
        there, so the world has no gap.

    Module Globals:
        FACING read.

    Author: Nick Hobar
    Creation date: 11/03/2026
    """
    size = tile_const.CHUNK_SIZE
    top_row = max(placement.y for placement in placements) // size
    files = [_blank_chunk(cy) for cy in range(top_row + 1)]

    for placement in placements:
        thing = chunkfile.ChunkObject(
            kind=placement.kind, x=placement.x % size, y=placement.y % size,
            rotation=FACING, text=placement.text, spawn=dict(placement.spawn))
        files[placement.y // size].objects.append(thing)

    return files


def build(item_rows: list, kinds: dict = None) -> Showroom:
    """
    Purpose: Make the showroom of the given items and kinds.

    Entry:
        item_rows - the rows of `spawn_items.item_rows()`.
        kinds     - {kind key: ObjectKind}. None is OBJECT_KINDS.

    Exit/Returns:
        Returns a Showroom. Writes nothing.

    Author: Nick Hobar
    Creation date: 11/03/2026
    """
    if kinds is None:
        kinds = object_kinds.OBJECT_KINDS

    aisles = item_aisles(item_rows)
    object_aisles, skipped = kind_aisles(kinds)
    aisles.extend(object_aisles)
    placements = lay_out(aisles)
    files = chunk_files_of(placements)

    return Showroom(chunk_files=files, aisles=aisles, skipped_kinds=skipped)


def write(showroom: Showroom, directory: str, world_directory: str) -> list:
    """
    Purpose: Replace the chunk files of the showroom directory.

    Entry:
        showroom        - from `build`.
        directory       - the showroom chunk directory. It may not exist.
        world_directory - the chunk directory of the live world.

    Exit/Returns:
        Returns the paths that it wrote. Raises ValueError, and changes
        nothing, if the two directories are one.

    Module Globals:
        None.

    Methodology:
        1. Refuse the live chunk directory. A mistake in the settings must
           not replace the live world.
        2. Make the directory, and delete each chunk file in it. A file of a
           chunk that the new layout does not hold would stay in the world.
        3. Write each chunk file in the canonical layout.

    Notes/References:
        Only names of `chunkfile.is_chunk_file_name` go. A README or another
        file in the directory stays.

    Author: Nick Hobar
    Creation date: 11/03/2026
    """
    is_live = _same_directory(directory, world_directory)

    if is_live:
        raise ValueError(f"the showroom directory is the live chunk "
                         f"directory: {directory}")

    os.makedirs(directory, exist_ok=True)

    for name in os.listdir(directory):
        is_chunk = chunkfile.is_chunk_file_name(name)

        if is_chunk:
            os.remove(os.path.join(directory, name))

    written = []

    for chunk_file in showroom.chunk_files:
        path = os.path.join(directory, chunk_file.file_name())
        chunkfile.write_file(path, chunk_file)
        written.append(path)

    return written
