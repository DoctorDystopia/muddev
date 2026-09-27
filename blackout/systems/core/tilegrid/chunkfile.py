"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The chunk file: read it, check it, and write it in the one
             canonical layout.

DESIGN-0011 section 6.2. One file holds every fact about one chunk on one
plane. The Godot editor (Phase 3) writes it, and the server reads it. Nothing
copies it. `godot/world/terrain/chunk_file.gd` is the GDScript twin of this
module, and the parity test holds the two to the same answers.

The layout, format 1
--------------------
A JSON object with these keys, in this order::

    format       1
    chunk        [cx, cy], global chunk coordinates
    plane        0 to PLANE_MAX. Plane 0 is the ground
    size         CHUNK_SIZE
    floor_names  the floor types. `floors` holds indexes into this list
    area_names   the areas. `areas` holds indexes into this list
    heights      CORNERS_PER_SIDE rows of CORNERS_PER_SIDE corner heights
    floors       CHUNK_SIZE rows of CHUNK_SIZE floor indexes
    flags        CHUNK_SIZE rows of CHUNK_SIZE walk flag ints
    areas        CHUNK_SIZE rows of CHUNK_SIZE area indexes
    objects      [{"kind", "x", "y", "rotation"}, ...]

Row 0 is the south edge (y = 0), and item 0 of a row is the west edge. That is
the order of the lists in memory, so no reader flips an axis. An object stands
at LOCAL coordinates, 0 to CHUNK_SIZE - 1, as an OSRS object does in its map
square. Thus, a chunk that moves keeps its objects in place.

The canonical layout
--------------------
`to_text` writes one row on each line, so a git diff shows the rows that an
author changed. The GDScript writer writes the same bytes, and a test in each
language reads each fixture and writes it back byte for byte. Names are
limited to CHUNK_NAME_PATTERN, so no name needs an escape.

Strict on purpose
-----------------
A reader refuses an unknown key, a missing key, a flag bit that no reader
knows, and an index past the end of its name list. A chunk file that one
reader accepts and the other refuses is the bug that the parity test exists
for. A strict rule is easy to make the same in two languages.

An integral float, for example 3.0, counts as an int. GDScript's JSON parser
returns every number as a float, so it cannot tell 3 from 3.0. The Python
reader accepts both, so that the two readers agree.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass, field

from . import constants as const
from .grid import Chunk, TileGrid


# ─── Public constant definitions ─────────────────────────────────────────────

# The keys of a chunk file, in the order that the writer writes them.
CHUNK_FILE_KEYS: tuple = ("format", "chunk", "plane", "size", "floor_names",
                          "area_names", "heights", "floors", "flags", "areas",
                          "objects")

# The keys of one object, in the order that the writer writes them.
OBJECT_KEYS: tuple = ("kind", "x", "y", "rotation")


# ─── Private constant definitions ────────────────────────────────────────────

_NAME_RE = re.compile(const.CHUNK_NAME_PATTERN)

# The file name, as a pattern, for `load_directory`.
_FILE_NAME_RE = re.compile(r"^chunk_(-?\d+)_(-?\d+)_p(\d+)\.json$")

_INDENT = "  "
_ROW_INDENT = "    "


# ─── Public classes ──────────────────────────────────────────────────────────

class ChunkFileError(ValueError):
    """A chunk file that does not follow format 1."""


@dataclass
class ChunkObject:
    """One placed object, at local tile coordinates."""

    kind: str
    x: int
    y: int
    rotation: int = 0


@dataclass
class ChunkFile:
    """
    Every fact in one chunk file. The grids are flat lists, row 0 first, in
    the same order as `grid.Chunk`.
    """

    cx: int
    cy: int
    plane: int
    floor_names: list
    area_names: list
    heights: list
    floors: list
    flags: list
    areas: list
    objects: list = field(default_factory=list)

    def to_chunk(self) -> Chunk:
        """Return the grid.Chunk of this file. The lists are copied."""
        return Chunk(self.cx, self.cy, heights=list(self.heights),
                     floors=list(self.floors), flags=list(self.flags))

    def corner_heights(self, lx: int, ly: int) -> tuple:
        """Return (southwest, southeast, northwest, northeast) of a tile."""
        side = const.CORNERS_PER_SIDE
        south = ly * side + lx
        north = south + side
        heights = self.heights

        return (heights[south], heights[south + 1],
                heights[north], heights[north + 1])

    def tile_height(self, lx: int, ly: int) -> int:
        """Return the gameplay height of a tile: its lowest corner."""
        corners = self.corner_heights(lx, ly)
        lowest = min(corners)

        return lowest

    def floor_name(self, lx: int, ly: int) -> str:
        """Return the floor type name of a local tile."""
        index = self.floors[ly * const.CHUNK_SIZE + lx]

        return self.floor_names[index]

    def area_name(self, lx: int, ly: int) -> str:
        """Return the area name of a local tile."""
        index = self.areas[ly * const.CHUNK_SIZE + lx]

        return self.area_names[index]

    def global_objects(self) -> list:
        """Return (kind, x, y, rotation) of each object, at world tiles."""
        origin_x = self.cx * const.CHUNK_SIZE
        origin_y = self.cy * const.CHUNK_SIZE
        placed = []

        for thing in self.objects:
            placed.append((thing.kind, origin_x + thing.x, origin_y + thing.y,
                           thing.rotation))

        return placed

    def file_name(self) -> str:
        """Return the file name that this chunk must have."""
        return chunk_file_name(self.cx, self.cy, self.plane)


# ─── Private helper routines ─────────────────────────────────────────────────

def _fail(message: str, *args) -> None:
    raise ChunkFileError(message % args)


def _as_int(value, what: str) -> int:
    """Return `value` as an int, or refuse it. An integral float counts."""
    if isinstance(value, bool):
        _fail("%s must be an integer, not %r", what, value)

    if isinstance(value, float) and value.is_integer():
        return int(value)

    if not isinstance(value, int):
        _fail("%s must be an integer, not %r", what, value)

    return value


def _int_in(value, low: int, high: int, what: str) -> int:
    """Return `value` as an int in low..high, or refuse it."""
    number = _as_int(value, what)

    if number < low or number > high:
        _fail("%s is %d, outside %d..%d", what, number, low, high)

    return number


def _names(value, what: str) -> list:
    """Return a checked list of unique names, or refuse it."""
    if not isinstance(value, list) or not value:
        _fail("%s must be a list with at least one name", what)

    for name in value:
        if not isinstance(name, str) or not _NAME_RE.match(name):
            _fail("%s holds %r, which does not match %s", what, name,
                  const.CHUNK_NAME_PATTERN)

    if len(set(value)) != len(value):
        _fail("%s holds a name two times", what)

    return list(value)


def _grid(value, side: int, low: int, high: int, what: str) -> list:
    """Return `side` rows of `side` ints in low..high as one flat list."""
    if not isinstance(value, list) or len(value) != side:
        _fail("%s must hold %d rows", what, side)

    flat = []

    for row_index, row in enumerate(value):
        if not isinstance(row, list) or len(row) != side:
            _fail("%s row %d must hold %d values", what, row_index, side)

        for column, item in enumerate(row):
            label = "%s[%d][%d]" % (what, row_index, column)
            flat.append(_int_in(item, low, high, label))

    return flat


def _flags(value) -> list:
    """Return the flag grid, and refuse a bit that no reader knows."""
    size = const.CHUNK_SIZE
    flat = _grid(value, size, 0, const.FLAGS_ALL, "flags")

    for index, bits in enumerate(flat):
        if bits & ~const.FLAGS_ALL:
            _fail("flags tile %d holds an unknown bit", index)

    return flat


def _objects(value) -> list:
    """Return the checked objects, or refuse them."""
    if not isinstance(value, list):
        _fail("objects must be a list")

    last = const.CHUNK_SIZE - 1
    found = []

    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != set(OBJECT_KEYS):
            _fail("object %d must have exactly the keys %s", index,
                  ", ".join(OBJECT_KEYS))

        kind = item["kind"]

        if not isinstance(kind, str) or not _NAME_RE.match(kind):
            _fail("object %d has the kind %r", index, kind)

        found.append(ChunkObject(
            kind=kind,
            x=_int_in(item["x"], 0, last, "object %d x" % index),
            y=_int_in(item["y"], 0, last, "object %d y" % index),
            rotation=_int_in(item["rotation"], 0, const.ROTATION_COUNT - 1,
                             "object %d rotation" % index)))

    return found


def _header(data: dict) -> tuple:
    """Check the keys and the scalar fields. Return (cx, cy, plane)."""
    if not isinstance(data, dict):
        _fail("a chunk file must hold one JSON object")

    keys = set(data)
    expected = set(CHUNK_FILE_KEYS)

    if keys != expected:
        missing = sorted(expected - keys)
        unknown = sorted(keys - expected)
        _fail("keys wrong: missing %s, unknown %s", missing, unknown)

    version = _as_int(data["format"], "format")

    if version != const.CHUNK_FORMAT_VERSION:
        _fail("format %d is not %d", version, const.CHUNK_FORMAT_VERSION)

    size = _as_int(data["size"], "size")

    if size != const.CHUNK_SIZE:
        _fail("size %d is not %d", size, const.CHUNK_SIZE)

    chunk = data["chunk"]

    if not isinstance(chunk, list) or len(chunk) != 2:
        _fail("chunk must be [cx, cy]")

    cx = _as_int(chunk[0], "chunk x")
    cy = _as_int(chunk[1], "chunk y")
    plane = _int_in(data["plane"], 0, const.PLANE_MAX, "plane")

    return cx, cy, plane


def _row_text(row: list) -> str:
    """Return one row as `[a,b,c]`, with no spaces."""
    return "[" + ",".join(str(value) for value in row) + "]"


def _grid_lines(key: str, flat: list, side: int, last: bool) -> list:
    """Return the lines of one grid key, one row on each line."""
    lines = ['%s"%s": [' % (_INDENT, key)]

    for row_index in range(side):
        row = flat[row_index * side:(row_index + 1) * side]
        comma = "," if row_index < side - 1 else ""
        lines.append(_ROW_INDENT + _row_text(row) + comma)

    lines.append(_INDENT + "]" + ("" if last else ","))

    return lines


def _name_list_text(names: list) -> str:
    return "[" + ",".join('"%s"' % name for name in names) + "]"


def _object_text(thing: ChunkObject) -> str:
    return '{"kind":"%s","x":%d,"y":%d,"rotation":%d}' % (
        thing.kind, thing.x, thing.y, thing.rotation)


# ─── Public routines ─────────────────────────────────────────────────────────

def chunk_file_name(cx: int, cy: int, plane: int) -> str:
    """Return the file name of the chunk at (cx, cy) on a plane."""
    return const.CHUNK_FILE_TEMPLATE.format(cx=cx, cy=cy, plane=plane)


def from_dict(data) -> ChunkFile:
    """
    Purpose: Check a parsed chunk file and return it as a ChunkFile.

    Entry:
        data - what json.loads returned for the file.

    Exit/Returns:
        A ChunkFile. Raises ChunkFileError for any break of format 1.

    Module Globals:
        CHUNK_FILE_KEYS read.

    Methodology:
        1. Check the keys, the format, the size, the chunk, and the plane.
        2. Check the two name lists.
        3. Check each grid: its shape, its range, and its indexes.
        4. Check the objects.

    Notes/References:
        `godot/world/terrain/chunk_file.gd` `from_dict` must refuse the same
        files. `test_chunkfile.INVALID_CASES` names the cases that both check.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    cx, cy, plane = _header(data)
    floor_names = _names(data["floor_names"], "floor_names")
    area_names = _names(data["area_names"], "area_names")
    size = const.CHUNK_SIZE

    return ChunkFile(
        cx=cx, cy=cy, plane=plane,
        floor_names=floor_names,
        area_names=area_names,
        heights=_grid(data["heights"], const.CORNERS_PER_SIDE,
                      const.HEIGHT_MIN, const.HEIGHT_MAX, "heights"),
        floors=_grid(data["floors"], size, 0, len(floor_names) - 1, "floors"),
        flags=_flags(data["flags"]),
        areas=_grid(data["areas"], size, 0, len(area_names) - 1, "areas"),
        objects=_objects(data["objects"]))


def parse_text(text: str) -> ChunkFile:
    """Parse and check the text of a chunk file. Raises ChunkFileError."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ChunkFileError("not JSON: %s" % error) from error

    return from_dict(data)


def to_text(chunk_file: ChunkFile) -> str:
    """
    Purpose: Write a ChunkFile in the canonical layout.

    Entry:
        chunk_file - a ChunkFile whose values follow format 1.

    Exit/Returns:
        The text of the file, "\\n" line ends, with a final "\\n".

    Module Globals:
        _INDENT, _ROW_INDENT read.

    Methodology:
        Each scalar key on one line. Each grid row on one line. Each object
        on one line. The GDScript writer writes the same bytes.

    Notes/References:
        The fixtures in `tests/fixtures/` are in this layout, and a test reads
        each one and writes it back byte for byte.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    size = const.CHUNK_SIZE
    lines = ["{",
             '%s"format": %d,' % (_INDENT, const.CHUNK_FORMAT_VERSION),
             '%s"chunk": [%d,%d],' % (_INDENT, chunk_file.cx, chunk_file.cy),
             '%s"plane": %d,' % (_INDENT, chunk_file.plane),
             '%s"size": %d,' % (_INDENT, size),
             '%s"floor_names": %s,' % (
                 _INDENT, _name_list_text(chunk_file.floor_names)),
             '%s"area_names": %s,' % (
                 _INDENT, _name_list_text(chunk_file.area_names))]

    lines += _grid_lines("heights", chunk_file.heights,
                         const.CORNERS_PER_SIDE, False)
    lines += _grid_lines("floors", chunk_file.floors, size, False)
    lines += _grid_lines("flags", chunk_file.flags, size, False)
    lines += _grid_lines("areas", chunk_file.areas, size, False)

    if not chunk_file.objects:
        lines.append('%s"objects": []' % _INDENT)
    else:
        lines.append('%s"objects": [' % _INDENT)
        count = len(chunk_file.objects)

        for index, thing in enumerate(chunk_file.objects):
            comma = "," if index < count - 1 else ""
            lines.append(_ROW_INDENT + _object_text(thing) + comma)

        lines.append(_INDENT + "]")

    lines.append("}")

    return "\n".join(lines) + "\n"


def to_dict(chunk_file: ChunkFile) -> dict:
    """
    Return the chunk file as the JSON value of its canonical text. The
    statefeed sends this dict, so the client reads exactly the file format
    with `ChunkFile.from_dict`, and no second layout exists.
    """
    text = to_text(chunk_file)
    data = json.loads(text)

    return data


def read_file(path: str) -> ChunkFile:
    """Read, parse, and check one chunk file. Raises ChunkFileError."""
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()

    return parse_text(text)


def write_file(path: str, chunk_file: ChunkFile) -> None:
    """Write one chunk file in the canonical layout, with "\\n" line ends."""
    text = to_text(chunk_file)

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def is_chunk_file_name(name: str) -> bool:
    """Return True if `name` has the form `chunk_<cx>_<cy>_p<plane>.json`."""
    return _FILE_NAME_RE.match(name) is not None


def load_directory(directory: str) -> list:
    """
    Purpose: Read every chunk file in a directory.

    Entry:
        directory - a path. A missing directory holds no chunks.

    Exit/Returns:
        A list of ChunkFile, sorted by file name. Raises ChunkFileError for a
        bad file, or for a file whose name does not match its content.

    Module Globals:
        _FILE_NAME_RE read.

    Methodology:
        Only names that match `chunk_<cx>_<cy>_p<plane>.json` are read. The
        name must equal `ChunkFile.file_name()`, so two files cannot hold one
        chunk.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    if not os.path.isdir(directory):
        return []

    found = []

    for name in sorted(os.listdir(directory)):
        if not _FILE_NAME_RE.match(name):
            continue

        path = os.path.join(directory, name)

        try:
            chunk_file = read_file(path)
        except ChunkFileError as error:
            raise ChunkFileError("%s: %s" % (name, error)) from error

        if chunk_file.file_name() != name:
            _fail("%s holds chunk %s", name, chunk_file.file_name())

        found.append(chunk_file)

    return found


def seam_mismatches(chunk_files: list) -> list:
    """
    Purpose: Find each seam where two neighbour chunks disagree on a corner.

    Entry:
        chunk_files - ChunkFile objects, on any planes.

    Exit/Returns:
        A list of (file name, neighbour file name, corner index). Empty when
        every seam matches.

    Module Globals:
        const.CORNERS_PER_SIDE read.

    Methodology:
        A chunk holds its own east and north edge corners. The east chunk
        holds the same corners as its west edge, and the north chunk as its
        south edge. Compare the two copies of each shared corner.

    Notes/References:
        grid.Chunk explains why each chunk holds its own edge corners.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    side = const.CORNERS_PER_SIDE
    last = side - 1
    by_key = {(f.cx, f.cy, f.plane): f for f in chunk_files}
    mismatches = []

    for chunk_file in chunk_files:
        east = by_key.get((chunk_file.cx + 1, chunk_file.cy, chunk_file.plane))
        north = by_key.get((chunk_file.cx, chunk_file.cy + 1, chunk_file.plane))

        for index in range(side):
            if east is not None and (chunk_file.heights[index * side + last]
                                     != east.heights[index * side]):
                mismatches.append((chunk_file.file_name(), east.file_name(),
                                   index))

            if north is not None and (chunk_file.heights[last * side + index]
                                      != north.heights[index]):
                mismatches.append((chunk_file.file_name(), north.file_name(),
                                   index))

    return mismatches


def build_grid(chunk_files: list, plane: int = 0) -> TileGrid:
    """Return a TileGrid that holds every chunk file of one plane."""
    grid = TileGrid()

    for chunk_file in chunk_files:
        if chunk_file.plane == plane:
            grid.add_chunk(chunk_file.to_chunk())

    return grid


def semantic_dump(chunk_file: ChunkFile) -> str:
    """
    Purpose: Write what a chunk file MEANS, one fact on each line.

    Entry:
        chunk_file - a checked ChunkFile.

    Exit/Returns:
        Text with "\\n" line ends. The GDScript `semantic_dump` writes the
        same text for the same file.

    Module Globals:
        const.CHUNK_SIZE read.

    Methodology:
        One line for the chunk, one for each name list, one for each tile in
        row order, and one for each object. A tile line gives its world
        coordinates, its four corners, its tile height, its flags, and its
        floor and area names. A reader that swaps x and y, loses a corner, or
        adds the chunk offset wrong writes a different line.

    Notes/References:
        The parity test compares the SHA-256 of this text with a committed
        digest, in Python and in GDScript.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    size = const.CHUNK_SIZE
    origin_x = chunk_file.cx * size
    origin_y = chunk_file.cy * size
    lines = ["chunk %d %d plane %d" % (chunk_file.cx, chunk_file.cy,
                                       chunk_file.plane),
             "floors " + " ".join(chunk_file.floor_names),
             "areas " + " ".join(chunk_file.area_names)]

    for ly in range(size):
        for lx in range(size):
            corners = chunk_file.corner_heights(lx, ly)
            lines.append("tile %d %d %d %d %d %d %d %d %s %s" % (
                origin_x + lx, origin_y + ly,
                corners[0], corners[1], corners[2], corners[3],
                chunk_file.tile_height(lx, ly),
                chunk_file.flags[ly * size + lx],
                chunk_file.floor_name(lx, ly),
                chunk_file.area_name(lx, ly)))

    for kind, x, y, rotation in chunk_file.global_objects():
        lines.append("object %s %d %d %d" % (kind, x, y, rotation))

    return "\n".join(lines) + "\n"


def semantic_digest(chunk_file: ChunkFile) -> str:
    """Return the SHA-256 hex digest of `semantic_dump`."""
    dump = semantic_dump(chunk_file)

    return hashlib.sha256(dump.encode("utf-8")).hexdigest()
