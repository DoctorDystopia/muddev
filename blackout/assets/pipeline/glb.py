"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Read what one served .glb holds, in pure Python.

             The check and the tests use this, so neither needs Node. It reads
             and never writes: the Node half of the build is the only writer
             of a .glb.

             It also owns GODOT_RUNTIME_EXTENSIONS: the glTF extensions that
             Godot's GLTFDocument reads at runtime. A served model that uses
             any other extension loads wrong or does not load at all, and
             Godot reports nothing useful. Draco, meshopt and quantization are
             the traps, because every other glTF tool supports them.
"""

import json
import struct
from dataclasses import dataclass
from io import BytesIO

from PIL import Image


# ─── Public constant definitions ─────────────────────────────────────────────

# From modules/gltf/ in the Godot source, read 09/18/2026. The first eight are
# the list in GLTFDocument::_get_supported_extensions. The last two come from
# the texture extensions in modules/gltf/extensions/.
GODOT_RUNTIME_EXTENSIONS: frozenset = frozenset((
    "GODOT_single_root",
    "KHR_animation_pointer",
    "KHR_lights_punctual",
    "KHR_materials_emissive_strength",
    "KHR_materials_pbrSpecularGlossiness",
    "KHR_materials_unlit",
    "KHR_node_visibility",
    "KHR_texture_transform",
    "EXT_texture_webp",
    "KHR_texture_basisu",
))


class GlbError(RuntimeError):
    """A file that is not a readable binary glTF."""


@dataclass(frozen=True)
class GlbSummary:
    """
    What one .glb holds. texture_edges holds the longest edge of each
    embedded image, in pixels.
    """

    size_bytes: int
    triangles: int
    extensions_used: tuple
    texture_edges: tuple
    alpha_modes: tuple
    generator: str


# ─── Private constant definitions ────────────────────────────────────────────

_GLB_MAGIC: int = 0x46546C67                 # "glTF"
_HEADER_FORMAT: str = "<III"                 # magic, version, total length
_CHUNK_HEADER_FORMAT: str = "<II"            # chunk length, chunk type
_CHUNK_TYPE_JSON: int = 0x4E4F534A           # "JSON"
_CHUNK_TYPE_BIN: int = 0x004E4942            # "BIN\0"
_MODE_TRIANGLES: int = 4
_VERTICES_PER_TRIANGLE: int = 3
_DEFAULT_ALPHA_MODE: str = "OPAQUE"


# ─── Private helper routines ─────────────────────────────────────────────────

def _chunks(payload: bytes) -> tuple:
    """
    Purpose: Split a GLB file into its JSON document and its binary chunk.

    Entry:
        payload is the whole file.

    Exit/Returns:
        Returns (document dict, bin bytes). bin is b"" when there is no
        binary chunk. Raises GlbError for a file that is not GLB.

    Module Globals:
        The _GLB_* and _CHUNK_* constants read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    header_size = struct.calcsize(_HEADER_FORMAT)
    chunk_header_size = struct.calcsize(_CHUNK_HEADER_FORMAT)
    magic, _version, _length = struct.unpack_from(_HEADER_FORMAT, payload)

    if magic != _GLB_MAGIC:
        raise GlbError("not a binary glTF file")

    offset = header_size
    document = None
    binary = b""

    while offset < len(payload):
        length, kind = struct.unpack_from(_CHUNK_HEADER_FORMAT, payload, offset)
        start = offset + chunk_header_size
        body = payload[start:start + length]

        if kind == _CHUNK_TYPE_JSON:
            document = json.loads(body.decode("utf-8"))
        elif kind == _CHUNK_TYPE_BIN:
            binary = body

        offset = start + length

    if document is None:
        raise GlbError("no JSON chunk")

    return document, binary


def _triangle_count(document: dict) -> int:
    """
    Purpose: Count the triangles of every triangle-list primitive.

    Entry:
        document is a decoded glTF.

    Exit/Returns:
        Returns the total. A primitive with indices counts indices, and one
        without counts POSITION vertices, three to a triangle.

    Module Globals:
        _MODE_TRIANGLES, _VERTICES_PER_TRIANGLE read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    accessors = document.get("accessors", [])
    total = 0

    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            mode = primitive.get("mode", _MODE_TRIANGLES)

            if mode != _MODE_TRIANGLES:
                continue

            index = primitive.get("indices",
                                  primitive["attributes"]["POSITION"])
            count = accessors[index]["count"]
            total += count // _VERTICES_PER_TRIANGLE

    return total


def _texture_edges(document: dict, binary: bytes) -> tuple:
    """
    Purpose: Measure the longest edge of every embedded image.

    Entry:
        document and binary come from _chunks.

    Exit/Returns:
        Returns one edge in pixels for each image that sits in a bufferView.
        An image that Pillow cannot open counts as 0.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    views = document.get("bufferViews", [])
    edges = []

    for image in document.get("images", []):
        if "bufferView" not in image:
            continue

        view = views[image["bufferView"]]
        start = view.get("byteOffset", 0)
        data = binary[start:start + view["byteLength"]]

        try:
            with Image.open(BytesIO(data)) as opened:
                longest = max(opened.size)
        except OSError:
            longest = 0

        edges.append(longest)

    return tuple(edges)


# ─── Public routines ─────────────────────────────────────────────────────────

def summarize(path: str) -> GlbSummary:
    """
    Purpose: Report what one served .glb holds.

    Entry:
        path names a readable .glb file.

    Exit/Returns:
        Returns a GlbSummary. Raises GlbError for a file that is not GLB.

    Module Globals:
        _DEFAULT_ALPHA_MODE read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    with open(path, "rb") as handle:
        payload = handle.read()

    document, binary = _chunks(payload)
    triangles = _triangle_count(document)
    edges = _texture_edges(document, binary)
    materials = document.get("materials", [])
    alpha_modes = tuple(material.get("alphaMode", _DEFAULT_ALPHA_MODE)
                        for material in materials)
    used = tuple(sorted(document.get("extensionsUsed", [])))
    generator = document.get("asset", {}).get("generator", "")

    return GlbSummary(
        size_bytes=len(payload), triangles=triangles, extensions_used=used,
        texture_edges=edges, alpha_modes=alpha_modes, generator=generator)
