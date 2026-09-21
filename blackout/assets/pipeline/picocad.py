"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Turns a picoCAD save file into glTF, for the model pipeline.

             Moved here from assets/picocad_to_gltf.py on 09/18/2026. The
             build (build.py) calls convert() for a model record whose `file`
             is a picoCAD save (.txt), and writes the result into
             assets/.build/. Nothing in the source directory changes. The
             history below names the packer and the front-steps that the
             pipeline replaced.

             THE PROBLEM THIS FIXES. Every model served so far arrived as
             somebody else's download -- a glTF from Sketchfab, an FBX from
             itch.io -- and both front-steps in this directory exist to
             manufacture the one shape the packer reads. A model built HERE,
             in picoCAD, arrives as neither: picoCAD saves a single text file
             holding a Lua table of objects and a 128x120 sheet of PICO-8
             palette indices, and exports nothing this pipeline can point at.
             This is that step, and like split_tileset.py it is deliberately
             the only new thing -- what it writes is an ordinary source
             directory (scene.gltf + scene.bin + textures/), and everything
             downstream is the pipeline that already exists.

             WHAT A PICOCAD FILE IS. One header line, then a Lua table of
             objects, then `}%` alone and 120 lines of 128 hex digits:

                 picocad;<name>;<zoom>;<background>;<alpha colour>
                 { { name='cylinder', pos={x,y,z}, rot={x,y,z},
                     v={ {x,y,z}, ... },
                     f={ {1,2,3,4, c=6, uv={u,v, ...}}, ... } }, ... }%
                 <120 rows of 128 palette indices>

             Vertices are stored relative to their object's `pos` and UVs in
             units of eight texels, the PICO-8 sprite grid. Faces are convex
             polygons of three to eight corners with per-corner UVs.

             THE THREE JUDGEMENTS THIS MAKES, none of which the file states:

             1. AXES. picoCAD's Y points DOWN, the way a PICO-8 screen does,
                and its Z points AWAY from the viewer; glTF is Y-up and Z
                toward the viewer. The conversion is therefore (x, -y, -z),
                which is a half turn about X -- a ROTATION, not a mirror, so
                face winding carries over untouched and normals stay outward.
             2. NOTEX FACES. A picoCAD face can opt out of the texture and
                take a flat palette colour instead. glTF has no per-face
                colour, so the sheet is padded from 128x120 to 128x128 and the
                eight new rows are written as sixteen 8x8 palette swatches; a
                flat face is UV-mapped onto the middle of its own swatch.
                One image, one material, and no primitive per colour. Padding
                is why UVs divide by 128 rather than 120 -- the texels the
                sheet's own faces land on do not move.
             3. DOUBLE SIDED. picoCAD carries `dbl` per FACE and glTF carries
                it per MATERIAL, so honouring it exactly would mean splitting
                every mesh in two. Everything is drawn from both sides
                instead: the flag only ever makes a face MORE visible, these
                are props a few dozen pixels across, and a picoCAD solid built
                inside-out reads as holes rather than as anything a reviewer
                would recognise.

             WHAT IS DELIBERATELY NOT HONOURED. `noshade` (per-face unlit) has
             nowhere to go in a core glTF material. The header's alpha colour
             is REPORTED and not applied: punching every texel of one palette
             index out of the sheet turns a model somebody painted black into
             a model full of holes, and a solid pixel where transparency was
             wanted is the failure a person can see and fix.

             The save file is never written to. Re-running produces the same
             bytes.

             Pure file transformation. Importing this module touches no
             database and boots no Evennia -- but it sits outside the game
             package anyway, because it is a build tool and not game code.
"""

import json
import math
import os
import re
import struct
from collections import namedtuple
from io import BytesIO

from PIL import Image


# ─── Private constant definitions ────────────────────────────────────────────

_GLTF_FILENAME = "scene.gltf"
_BUFFER_FILENAME = "scene.bin"
_TEXTURES_DIRNAME = "textures"
_TEXTURE_FILENAME = "texture.png"
_TEXTURE_URI = _TEXTURES_DIRNAME + "/" + _TEXTURE_FILENAME

# The generator string written into what this produces. A file that does not
# say where it came from is one nobody can regenerate.
_GENERATOR = "blackout assets/pipeline/picocad.py"
_GLTF_VERSION = "2.0"
_MESH_NAME = "picocad"
_MATERIAL_NAME = "picocad"

# The header line, and where the pieces sit in it.
_HEADER_PREFIX = "picocad"
_HEADER_SEPARATOR = ";"
_HEADER_NAME_FIELD = 1
_HEADER_ALPHA_FIELD = 4
_HEADER_FIELD_COUNT = 5

# What separates the object table from the texture sheet. Its own line.
_TEXTURE_MARKER = "}%"

# The sheet picoCAD always writes: 128 wide, 120 tall, one hex digit a texel.
_SHEET_WIDTH = 128
_SHEET_HEIGHT = 120

# UVs are in PICO-8 sprite units -- one unit is an 8x8 cell of the sheet.
_UV_UNIT_TEXELS = 8

# The sheet is padded to a square so the flat-colour swatches have somewhere to
# live. See judgement 2 in the module docstring.
_IMAGE_HEIGHT = 128
_SWATCH_EDGE = 8
_SWATCH_CENTRE = _SWATCH_EDGE // 2

# The PICO-8 palette, in index order. Every texel of the sheet and every `c=`
# on a face is one of these sixteen.
_PALETTE = (
    (0, 0, 0), (29, 43, 83), (126, 37, 83), (0, 135, 81),
    (171, 82, 54), (95, 87, 79), (194, 195, 199), (255, 241, 232),
    (255, 0, 77), (255, 163, 0), (255, 236, 39), (0, 228, 54),
    (41, 173, 255), (131, 118, 156), (255, 119, 168), (255, 204, 170),
)
_PALETTE_SIZE = len(_PALETTE)

# Object and face fields read out of the parsed table.
_FIELD_NAME = "name"
_FIELD_POSITION = "pos"
_FIELD_ROTATION = "rot"
_FIELD_VERTICES = "v"
_FIELD_FACES = "f"
_FIELD_COLOUR = "c"
_FIELD_UV = "uv"
_FIELD_NO_TEXTURE = "notex"

# picoCAD angles are PICO-8 angles: a full turn is 1.0, not 360 and not 2*pi.
_TURNS_TO_RADIANS = 2.0 * math.pi

_AXES = 3                               # x, y, z, everywhere a point appears
_UV_COMPONENTS = 2
_TRIANGLE_CORNERS = 3
_MINIMUM_FACE_CORNERS = 3

# glTF vocabulary. Spelled out rather than left as bare numbers, because a
# reader who has to look 5126 up is one who cannot check this file.
_COMPONENT_TYPE_FLOAT = 5126
_TYPE_VEC3 = "VEC3"
_TYPE_VEC2 = "VEC2"
_TARGET_ARRAY_BUFFER = 34962
_MODE_TRIANGLES = 4
_FILTER_NEAREST = 9728
_WRAP_CLAMP_TO_EDGE = 33071
_MIME_PNG = "image/png"
_PNG_FORMAT = "PNG"
_MODE_RGB = "RGB"
_METALLIC_NONE = 0
_ROUGHNESS_MATTE = 1

# Lua fragments this parser understands. A picoCAD file is a table of tables
# holding numbers, single-quoted strings and `key=` fields, and nothing else.
_BLANK_CHARACTERS = " \t\r\n"
_TABLE_OPEN = "{"
_TABLE_CLOSE = "}"
_VALUE_SEPARATOR = ","
_STRING_QUOTE = "'"
_KEY_PATTERN = re.compile(r"([A-Za-z_][A-Za-z_0-9]*)\s*=\s*")
_NUMBER_PATTERN = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


# A Lua table has an array part and a named part and picoCAD uses both in the
# same table -- a face is its corner indices AND its `c`, `uv` and flags.
_Table = namedtuple("_Table", ("items", "fields"))


class PicoCADError(RuntimeError):
    """Raised when a save file is not a shape this converter can read."""


# ─── Private routines: reading the save file ─────────────────────────────────

def _split_source(text):
    """
    Purpose: Cut one picoCAD save file into its three parts.

    Entry:
        text is the whole file, decoded. Expected to start with the picocad
        header line and to hold the `}%` marker on a line of its own.

    Exit/Returns:
        Returns (header_fields, body, rows): the header split on `;`, the Lua
        table as text, and the texture as a list of row strings. Raises
        PicoCADError when the file is not that shape or the sheet is not
        128x120.

    Module Globals:
        _HEADER_PREFIX, _HEADER_SEPARATOR, _HEADER_FIELD_COUNT,
        _TEXTURE_MARKER, _SHEET_WIDTH, _SHEET_HEIGHT read.

    Methodology:
        Split the first line off, then split what remains on the marker. The
        marker cannot appear inside the table -- the table is closed by the `}`
        the marker starts with -- so one split is enough.

    Notes/References:
        The shape is drawn out in full in the module docstring.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    lines = text.splitlines()

    if not lines or not lines[0].startswith(_HEADER_PREFIX):
        raise PicoCADError("not a picoCAD save file: no picocad header line")

    header_fields = lines[0].split(_HEADER_SEPARATOR)

    if len(header_fields) != _HEADER_FIELD_COUNT:
        raise PicoCADError(
            "header has %d fields, expected %d: %s"
            % (len(header_fields), _HEADER_FIELD_COUNT, lines[0]))

    marker_line = -1

    for index, line in enumerate(lines):
        if line.strip() == _TEXTURE_MARKER:
            marker_line = index

            break

    if marker_line < 0:
        raise PicoCADError("no %s marker; the texture sheet is missing"
                           % _TEXTURE_MARKER)

    body = "\n".join(lines[1:marker_line]) + _TABLE_CLOSE
    rows = [row for row in lines[marker_line + 1:] if row.strip()]
    _check_sheet(rows)

    return header_fields, body, rows


def _check_sheet(rows):
    """
    Purpose: Refuse a texture sheet that is not the size picoCAD writes.

    Entry:
        rows is the list of texture lines, already stripped of blanks.

    Exit/Returns:
        Returns None. Raises PicoCADError describing the first thing wrong.

    Module Globals:
        _SHEET_WIDTH, _SHEET_HEIGHT read.

    Methodology:
        Height first, then every row's width, because a truncated file fails
        both and the height is the more useful thing to be told.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    if len(rows) != _SHEET_HEIGHT:
        raise PicoCADError("texture sheet is %d rows, expected %d"
                           % (len(rows), _SHEET_HEIGHT))

    for index, row in enumerate(rows):
        if len(row) != _SHEET_WIDTH:
            raise PicoCADError(
                "texture row %d is %d characters, expected %d"
                % (index, len(row), _SHEET_WIDTH))


def _skip_blanks(text, index):
    """
    Purpose: Advance past whitespace and separators between Lua values.

    Entry:
        text is the table source. 0 <= index <= len(text).

    Exit/Returns:
        Returns the first index at or after `index` holding something other
        than whitespace or a comma.

    Module Globals:
        _BLANK_CHARACTERS, _VALUE_SEPARATOR read.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    position = index

    while position < len(text):
        if text[position] not in _BLANK_CHARACTERS + _VALUE_SEPARATOR:
            break

        position += 1

    return position


def _read_value(text, index):
    """
    Purpose: Read one Lua value -- a table, a string or a number.

    Entry:
        text is the table source and index points at the value's first
        character, whitespace already skipped.

    Exit/Returns:
        Returns (value, next_index). A table comes back as a _Table, a string
        as str and a number as float. Raises PicoCADError at anything else.

    Module Globals:
        _TABLE_OPEN, _STRING_QUOTE, _NUMBER_PATTERN read.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    if text[index] == _TABLE_OPEN:
        return _parse_table(text, index)

    if text[index] == _STRING_QUOTE:
        closing = text.index(_STRING_QUOTE, index + 1)

        return text[index + 1:closing], closing + 1

    number = _NUMBER_PATTERN.match(text, index)

    if number is None:
        raise PicoCADError("cannot read a value at %r"
                           % text[index:index + 24])

    return float(number.group()), number.end()


def _parse_table(text, index):
    """
    Purpose: Parse one `{ ... }` Lua table, with both its parts.

    Entry:
        text is the table source and text[index] is `{`.

    Exit/Returns:
        Returns (_Table, next_index). `items` holds the positional values in
        order and `fields` the `key=value` ones. Raises PicoCADError on an
        unterminated table.

    Module Globals:
        _TABLE_OPEN, _TABLE_CLOSE, _KEY_PATTERN read.

    Methodology:
        Loop: skip blanks and commas, stop at `}`, try to match `key=` at the
        cursor, then read one value and file it under the key or append it.
        Recursion handles nesting, which is only ever three deep here.

    Notes/References:
        Deliberately not a Lua interpreter -- no operators, comments, or
        double-quoted strings, none of which picoCAD writes.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    items = []
    fields = {}
    position = index + 1

    while True:
        position = _skip_blanks(text, position)

        if position >= len(text):
            raise PicoCADError("unterminated table")

        if text[position] == _TABLE_CLOSE:
            return _Table(items, fields), position + 1

        key = _KEY_PATTERN.match(text, position)

        if key is not None:
            position = key.end()

        value, position = _read_value(text, position)

        if key is None:
            items.append(value)
        else:
            fields[key.group(1)] = value


# ─── Private routines: geometry ──────────────────────────────────────────────

def _spun(first, second, radians):
    """
    Purpose: Rotate one pair of axes about the third.

    Entry:
        first and second are the two coordinates in the rotation plane.
        radians is the angle.

    Exit/Returns:
        Returns the rotated (first, second).

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    cosine = math.cos(radians)
    sine = math.sin(radians)

    return (first * cosine - second * sine, first * sine + second * cosine)


def _placed(vertex, position, rotation):
    """
    Purpose: Put one of an object's vertices where the model has it.

    Entry:
        vertex, position and rotation are three-number sequences straight out
        of the save file: the vertex relative to its object, the object's
        origin, and the object's rotation in PICO-8 turns.

    Exit/Returns:
        Returns (x, y, z) in glTF axes -- Y up, Z toward the viewer.

    Module Globals:
        _TURNS_TO_RADIANS read.

    Methodology:
        Spin about X, then Y, then Z around the object's own origin, add the
        origin, then apply the half turn about X that judgement 1 in the module
        docstring describes: (x, -y, -z).

    Notes/References:
        THE ROTATION ORDER IS UNVERIFIED, which is why _convert warns about a
        rotated object rather than converting one quietly. Every picoCAD file
        this has been run against carries rot={0,0,0}: picoCAD bakes an edited
        object's turn into its vertices, so the field stays zero unless
        something sets it. The translation and the axis swap are checked --
        see the README -- and a single-axis turn cannot be wrong about order
        either way.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    x, y, z = vertex

    if any(rotation):
        y, z = _spun(y, z, rotation[0] * _TURNS_TO_RADIANS)
        z, x = _spun(z, x, rotation[1] * _TURNS_TO_RADIANS)
        x, y = _spun(x, y, rotation[2] * _TURNS_TO_RADIANS)

    return (x + position[0], -(y + position[1]), -(z + position[2]))


def _face_corners(face, vertices):
    """
    Purpose: Gather one face's corners as (position, uv) pairs.

    Entry:
        face is a parsed face table -- 1-based vertex indices in `items`, `c`,
        `uv` and the flags in `fields`. vertices holds the object's placed
        vertices.

    Exit/Returns:
        Returns a list of ((x, y, z), (u, v)) in the face's own order, the UVs
        normalised against the padded image. Raises PicoCADError for an index
        outside the object or a face with fewer than three corners.

    Module Globals:
        _FIELD_UV, _FIELD_NO_TEXTURE, _FIELD_COLOUR, _UV_UNIT_TEXELS,
        _SHEET_WIDTH, _IMAGE_HEIGHT, _MINIMUM_FACE_CORNERS read.

    Methodology:
        A flat-shaded face takes its colour's swatch instead of its own UVs,
        which is the whole reason the image is padded.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    if len(face.items) < _MINIMUM_FACE_CORNERS:
        raise PicoCADError("face with %d corners" % len(face.items))

    flat = bool(face.fields.get(_FIELD_NO_TEXTURE, 0))
    colour = int(face.fields.get(_FIELD_COLOUR, 0))
    swatch = _swatch_uv(colour)
    coordinates = face.fields.get(_FIELD_UV, _Table([], {})).items
    corners = []

    for corner, index in enumerate(face.items):
        vertex = int(index) - 1

        if vertex < 0 or vertex >= len(vertices):
            raise PicoCADError("face names vertex %d of %d"
                               % (vertex + 1, len(vertices)))

        uv = swatch

        if not flat and len(coordinates) > corner * _UV_COMPONENTS + 1:
            u = coordinates[corner * _UV_COMPONENTS] * _UV_UNIT_TEXELS
            v = coordinates[corner * _UV_COMPONENTS + 1] * _UV_UNIT_TEXELS
            uv = (u / _SHEET_WIDTH, v / _IMAGE_HEIGHT)

        corners.append((vertices[vertex], uv))

    return corners


def _swatch_uv(colour):
    """
    Purpose: Where in the padded sheet one flat palette colour lives.

    Entry:
        colour is a PICO-8 palette index; anything outside 0..15 is wrapped
        rather than refused, because a colour is a look and not a rule.

    Exit/Returns:
        Returns the (u, v) of the middle of that colour's swatch, normalised.

    Module Globals:
        _PALETTE_SIZE, _SWATCH_EDGE, _SWATCH_CENTRE, _SHEET_HEIGHT,
        _SHEET_WIDTH, _IMAGE_HEIGHT read.

    Methodology:
        The strip runs along the first padded row, one 8x8 swatch per index.
        The MIDDLE of the swatch, not its corner, so nothing a sampler does at
        an edge can reach the neighbouring colour.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    index = colour % _PALETTE_SIZE
    u = index * _SWATCH_EDGE + _SWATCH_CENTRE
    v = _SHEET_HEIGHT + _SWATCH_CENTRE

    return (u / _SHEET_WIDTH, v / _IMAGE_HEIGHT)


def _normal_of(first, second, third):
    """
    Purpose: The outward normal of one triangle.

    Entry:
        Three (x, y, z) corners in winding order.

    Exit/Returns:
        Returns the unit normal, or (0, 1, 0) for a degenerate triangle --
        a zero normal renders black and a picoCAD file may hold a collapsed
        face.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    left = [second[axis] - first[axis] for axis in range(_AXES)]
    right = [third[axis] - first[axis] for axis in range(_AXES)]
    cross = (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )
    length = math.sqrt(sum(value * value for value in cross))

    if length == 0.0:
        return (0.0, 1.0, 0.0)

    return tuple(value / length for value in cross)


def _mesh_arrays(objects):
    """
    Purpose: Flatten every object into one unwelded triangle soup.

    Entry:
        objects is the list of parsed object tables.

    Exit/Returns:
        Returns (positions, normals, uvs, counts): three flat lists of floats
        and a dict of object, face and triangle counts. Raises PicoCADError
        through the routines it calls.

    Module Globals:
        _FIELD_POSITION, _FIELD_ROTATION, _FIELD_VERTICES, _FIELD_FACES,
        _TRIANGLE_CORNERS read.

    Methodology:
        Fan-triangulate each face from its first corner, which is exact for
        the convex polygons picoCAD's own renderer is limited to, and give
        each triangle its own three vertices. Unwelded because UVs and flat
        normals are per-FACE: a shared vertex would have to carry one face's
        UV for all of them.

    Notes/References:
        No index buffer is written for the same reason -- see _document.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    positions = []
    normals = []
    uvs = []
    counts = {"objects": len(objects), "faces": 0, "triangles": 0}

    for entry in objects:
        origin = entry.fields[_FIELD_POSITION].items
        rotation = entry.fields[_FIELD_ROTATION].items
        vertices = [_placed(vertex.items, origin, rotation)
                    for vertex in entry.fields[_FIELD_VERTICES].items]

        for face in entry.fields[_FIELD_FACES].items:
            corners = _face_corners(face, vertices)
            counts["faces"] += 1

            for apex in range(1, len(corners) - 1):
                triangle = (corners[0], corners[apex], corners[apex + 1])
                normal = _normal_of(*[corner[0] for corner in triangle])
                counts["triangles"] += 1

                for corner in triangle:
                    positions.extend(corner[0])
                    normals.extend(normal)
                    uvs.extend(corner[1])

    return positions, normals, uvs, counts


# ─── Private routines: the texture ───────────────────────────────────────────

def _texture_png(rows):
    """
    Purpose: Render the hex sheet and its palette strip as PNG bytes.

    Entry:
        rows is 120 strings of 128 hex digits, already checked.

    Exit/Returns:
        Returns the encoded PNG: 128x128 RGB, the sheet on top and sixteen
        8x8 palette swatches filling the padding below it.

    Module Globals:
        _PALETTE, _PALETTE_SIZE, _SHEET_WIDTH, _SHEET_HEIGHT, _IMAGE_HEIGHT,
        _SWATCH_EDGE, _MODE_RGB, _PNG_FORMAT read.

    Methodology:
        Build the pixel list in one pass per row, then the strip, then hand
        the lot to Pillow. RGB and not RGBA deliberately: see what the module
        docstring says about the alpha colour.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    pixels = []

    for row in rows:
        pixels.extend(_PALETTE[int(digit, 16)] for digit in row)

    strip = []

    for column in range(_SHEET_WIDTH):
        index = column // _SWATCH_EDGE

        if index >= _PALETTE_SIZE:
            index = _PALETTE_SIZE - 1

        strip.append(_PALETTE[index])

    for _ in range(_IMAGE_HEIGHT - _SHEET_HEIGHT):
        pixels.extend(strip)

    image = Image.new(_MODE_RGB, (_SHEET_WIDTH, _IMAGE_HEIGHT))
    image.putdata(pixels)
    sink = BytesIO()
    image.save(sink, format=_PNG_FORMAT, optimize=True)

    return sink.getvalue()


# ─── Private routines: the glTF document ─────────────────────────────────────

def _accessor(view, count, kind, values=None):
    """
    Purpose: One accessor row, with the bounds the spec asks for.

    Entry:
        view is a bufferView index, count the number of elements, kind a glTF
        type name. values is the flat float list, needed only when bounds are
        wanted.

    Exit/Returns:
        Returns the accessor dictionary. min/max are included when values is
        given, which POSITION requires and the others do not.

    Module Globals:
        _COMPONENT_TYPE_FLOAT read.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    row = {
        "bufferView": view,
        "componentType": _COMPONENT_TYPE_FLOAT,
        "count": count,
        "type": kind,
    }

    if values is None:
        return row

    stride = len(values) // count
    row["min"] = [min(values[axis::stride]) for axis in range(stride)]
    row["max"] = [max(values[axis::stride]) for axis in range(stride)]

    return row


def _document(positions, normals, uvs):
    """
    Purpose: Build the whole glTF document and its binary payload.

    Entry:
        Three flat float lists of the same vertex count, positions and normals
        three-wide and uvs two-wide.

    Exit/Returns:
        Returns (document, payload). The document names scene.bin and
        textures/texture.png as external files, which is the source-directory
        shape pack_model.py reads.

    Module Globals:
        Most of the glTF vocabulary block, plus _GENERATOR and the names.

    Methodology:
        Three tightly packed bufferViews, one accessor each, one primitive.
        NO INDEX BUFFER: every corner is already unwelded, so an index array
        would be 0, 1, 2, ... and save nothing. The sampler is NEAREST with no
        mipmaps -- this is 8x8-cell pixel art, and a minified mip would blend
        the palette strip into the sheet above it.

    Notes/References:
        Nothing here is packed or embedded. pack_model.py does that, and doing
        it twice is how two files come to disagree about a texture ceiling.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    vertex_count = len(positions) // _AXES
    blocks = [positions, normals, uvs]
    payload = b""
    views = []

    for block in blocks:
        views.append({
            "buffer": 0,
            "byteOffset": len(payload),
            "byteLength": len(block) * 4,
            "target": _TARGET_ARRAY_BUFFER,
        })
        payload += struct.pack("<%df" % len(block), *block)

    accessors = [
        _accessor(0, vertex_count, _TYPE_VEC3, positions),
        _accessor(1, vertex_count, _TYPE_VEC3),
        _accessor(2, vertex_count, _TYPE_VEC2),
    ]
    document = {
        "asset": {"generator": _GENERATOR, "version": _GLTF_VERSION},
        "scene": 0,
        "scenes": [{"name": _MESH_NAME, "nodes": [0]}],
        "nodes": [{"mesh": 0, "name": _MESH_NAME}],
        "meshes": [{
            "name": _MESH_NAME,
            "primitives": [{
                "attributes": {
                    "POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
                "material": 0,
                "mode": _MODE_TRIANGLES,
            }],
        }],
        "materials": [{
            "name": _MATERIAL_NAME,
            "doubleSided": True,
            "pbrMetallicRoughness": {
                "baseColorTexture": {"index": 0},
                "metallicFactor": _METALLIC_NONE,
                "roughnessFactor": _ROUGHNESS_MATTE,
            },
        }],
        "textures": [{"sampler": 0, "source": 0}],
        "images": [{"name": _MESH_NAME, "mimeType": _MIME_PNG,
                    "uri": _TEXTURE_URI}],
        "samplers": [{
            "magFilter": _FILTER_NEAREST,
            "minFilter": _FILTER_NEAREST,
            "wrapS": _WRAP_CLAMP_TO_EDGE,
            "wrapT": _WRAP_CLAMP_TO_EDGE,
        }],
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(payload), "uri": _BUFFER_FILENAME}],
    }

    return document, payload


def _write_source(dest_dir, document, payload, png):
    """
    Purpose: Write one converted model as a source directory on disk.

    Entry:
        dest_dir - the directory to create. document, payload and png - what
        _document and _texture_png produced.

    Exit/Returns:
        Returns the total bytes written. The directory is created if absent
        and its scene.gltf, scene.bin and textures/ are overwritten.

    Module Globals:
        _GLTF_FILENAME, _BUFFER_FILENAME, _TEXTURES_DIRNAME,
        _TEXTURE_FILENAME read.

    Methodology:
        The layout is dictated entirely by pack_model.py: one scene.gltf at
        the root naming one external buffer, and images at the uris it writes.
        Nothing here is a choice this tool gets to make.

    Notes/References:
        Identical in shape to split_tileset._write_source, for the same reason
        -- assets/README.md describes this as what a download arrives in.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    os.makedirs(os.path.join(dest_dir, _TEXTURES_DIRNAME), exist_ok=True)
    written = 0

    with open(os.path.join(dest_dir, _GLTF_FILENAME), "w",
              encoding="utf-8") as handle:
        text = json.dumps(document, indent=2)
        handle.write(text)
        written += len(text)

    with open(os.path.join(dest_dir, _BUFFER_FILENAME), "wb") as handle:
        handle.write(payload)
        written += len(payload)

    texture_path = os.path.join(dest_dir, _TEXTURES_DIRNAME, _TEXTURE_FILENAME)

    with open(texture_path, "wb") as handle:
        handle.write(png)
        written += len(png)

    return written


# ─── Public routines ─────────────────────────────────────────────────────────

def read_model(picocad_path):
    """
    Purpose: Read one picoCAD save file into objects and a texture sheet.

    Entry:
        picocad_path names a picoCAD save file. It is opened read-only and
        never written to.

    Exit/Returns:
        Returns (name, objects, rows, alpha_colour): the model's own name, the
        parsed object tables, the texture rows and the palette index the
        header calls transparent. Raises PicoCADError for anything this cannot
        read.

    Module Globals:
        _HEADER_NAME_FIELD, _HEADER_ALPHA_FIELD read.

    Methodology:
        Split, parse, and hand back the pieces. Separate from convert() so a
        test can read a file without writing one.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    with open(picocad_path, encoding="utf-8") as handle:
        text = handle.read()

    header_fields, body, rows = _split_source(text)
    table, _ = _parse_table(body, 0)

    if not table.items:
        raise PicoCADError("the save file holds no objects")

    alpha_colour = int(header_fields[_HEADER_ALPHA_FIELD])

    return header_fields[_HEADER_NAME_FIELD], table.items, rows, alpha_colour


def convert(picocad_path, dest_dir):
    """
    Purpose: Convert one picoCAD save file into a model source directory.

    Entry:
        picocad_path names the save file. dest_dir is the directory to write.
        The build puts it under assets/.build/.

    Exit/Returns:
        Returns (dest_dir, report). report holds the model name, the object,
        face, triangle and vertex counts, the bytes written, the header's
        alpha colour and one warning line per rotated object. Raises
        PicoCADError for a file this cannot read.

    Module Globals:
        _FIELD_ROTATION, _FIELD_NAME, _AXES read.

    Methodology:
        Read, flatten, render the sheet, write. The rotation warning is
        collected rather than printed, so a caller that is not a command line
        still gets told -- see the note in _placed about why it exists.

    Notes/References:
        The save file is never written to. Re-running produces the same bytes.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    name, objects, rows, alpha_colour = read_model(picocad_path)
    positions, normals, uvs, counts = _mesh_arrays(objects)
    document, payload = _document(positions, normals, uvs)
    png = _texture_png(rows)
    written = _write_source(dest_dir, document, payload, png)
    warnings = []

    for index, entry in enumerate(objects):
        if any(entry.fields[_FIELD_ROTATION].items):
            warnings.append(
                "object %d (%s) carries a rotation; picoCAD's rotation order "
                "is unverified here -- check it against picoCAD's own view"
                % (index, entry.fields.get(_FIELD_NAME, "?")))

    report = dict(counts)
    report["name"] = name
    report["vertices"] = len(positions) // _AXES
    report["bytes"] = written
    report["alpha_colour"] = alpha_colour
    report["warnings"] = warnings

    return dest_dir, report
