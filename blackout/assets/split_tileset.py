"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Splits one node out of a multi-node glTF tileset into the source
             directory shape pack_model.py already understands.

             THE PROBLEM THIS FIXES. Every model this repo serves arrived as
             its own download -- one scene.gltf holding one thing. A tileset
             does not: Tileset_desert is thirty-four tiles in a single file
             sharing one palette image, and there is no download boundary
             between them. pack_model.py packs a DIRECTORY, so without a step
             in front of it the only ways to serve a tile were to serve all
             thirty-four as one model (whose bounding box is the whole set, so
             normalisation puts a single tile somewhere under a millimetre
             across) or to hand-edit JSON per tile.

             This is that step, and it is deliberately the only new thing:
             what it writes is an ordinary source directory --
             scene.gltf + scene.bin + textures/ -- so everything downstream is
             the pipeline that already exists. The tileset is a source of
             downloads rather than a special case.

             WHAT IS KEPT WHOLE, AND WHY. Nodes, meshes, accessors and
             bufferViews are pruned to the one tile; the buffer is rebuilt
             tight around what survives. Materials, textures, samplers and
             images are copied WHOLE, which keeps every index in the surviving
             primitives valid with no remapping at all. That is right for a
             palette-atlas tileset -- one image, two materials, shared by all
             thirty-four tiles -- and it costs a few unused JSON rows per file.
             A tileset with a texture per tile would want them pruned too, and
             this is the routine to teach it in.

             The source file is never written to, exactly as pack_model.py
             never writes to a download. Re-running produces the same bytes.

             Pure file transformation. Importing this module touches no
             database and boots no Evennia.

             Usage:
                 ../evenv/Scripts/python.exe assets/split_tileset.py
                     assets/tiles/desert/Tileset.gltf assets/tiles/desert
                     center_h center_b
"""

import base64
import json
import os
import sys


# ─── Private constant definitions ────────────────────────────────────────────

_GLTF_FILENAME = "scene.gltf"
_BUFFER_FILENAME = "scene.bin"
_TEXTURES_DIRNAME = "textures"

# The generator string written into what this produces. A file that does not
# say where it came from is one nobody can regenerate.
_GENERATOR = "blackout split_tileset.py"
_GLTF_VERSION = "2.0"

# bufferView offsets are padded to this. The spec requires an accessor's offset
# to be a multiple of its component size (4 at most), so 4 satisfies every
# accessor this can meet.
_VIEW_ALIGNMENT = 4
_PAD_BYTE = b"\x00"

# glTF componentType -> bytes per component.
_COMPONENT_SIZES = {
    5120: 1,                            # BYTE
    5121: 1,                            # UNSIGNED_BYTE
    5122: 2,                            # SHORT
    5123: 2,                            # UNSIGNED_SHORT
    5125: 4,                            # UNSIGNED_INT
    5126: 4,                            # FLOAT
}

# glTF accessor type -> component count.
_TYPE_COMPONENTS = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}

# mimeType -> the extension an extracted image is written with.
_IMAGE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
}
_DEFAULT_IMAGE_EXTENSION = ".png"

# The prefix a data: URI carries, and the marker its payload starts after.
_DATA_URI_PREFIX = "data:"
_DATA_URI_SEPARATOR = ","

# Tables copied whole rather than pruned. See the module docstring.
_SHARED_TABLES = ("materials", "textures", "samplers")

# Node transform keys carried through to the extracted node.
_TRANSFORM_KEYS = ("translation", "rotation", "scale", "matrix")

_MINIMUM_ARGUMENTS = 4


class SplitError(RuntimeError):
    """A tileset this tool cannot split, said once and clearly."""


# ─── Private helper routines ─────────────────────────────────────────────────

def _load_document(path):
    """
    Purpose: Read and decode a tileset glTF.

    Entry:
        path - the .gltf file to read.

    Exit/Returns:
        Returns the decoded document as a dict. Raises SplitError when the file
        is missing or is not valid JSON.

    Module Globals:
        None.

    Methodology:
        A plain read. The tileset is the ONE file this tool trusts, so failing
        loudly here is better than any recovery.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    if not os.path.isfile(path):
        raise SplitError("no tileset at %s" % path)

    with open(path, "r", encoding="utf-8") as handle:
        try:
            document = json.load(handle)
        except ValueError as error:
            raise SplitError("%s is not valid JSON: %s" % (path, error))

    return document


def _buffer_bytes(document, source_dir):
    """
    Purpose: Get the single binary buffer a tileset's accessors read from.

    Entry:
        document - a decoded glTF holding exactly one buffer. source_dir names
        the directory the tileset sits in, for a buffer stored beside it.

    Exit/Returns:
        Returns the buffer's bytes. Raises SplitError for any other buffer
        shape, because several buffers would need an index this tool does not
        keep.

    Module Globals:
        _DATA_URI_PREFIX, _DATA_URI_SEPARATOR read.

    Methodology:
        Three shapes are legal and all three appear in the wild: a base64
        data: URI (what Blender's glTF exporter writes for a single-file
        export, and what Tileset_desert is), a filename beside the document,
        and no uri at all -- which only happens inside a .glb and cannot be
        read from a .gltf.

    Notes/References:
        pack_model._read_source_buffer handles the middle case only; this one
        exists because a tileset is usually shipped as one file.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    buffers = document.get("buffers", [])
    count = len(buffers)

    if count != 1:
        raise SplitError("expected exactly 1 buffer, found %d" % count)

    uri = buffers[0].get("uri", "")

    if not uri:
        raise SplitError("buffer 0 has no uri; a .glb has to be unpacked first")

    if uri.startswith(_DATA_URI_PREFIX):
        payload = uri.split(_DATA_URI_SEPARATOR, 1)[1]

        return base64.b64decode(payload)

    with open(os.path.join(source_dir, uri), "rb") as handle:
        return handle.read()


def _find_node(document, node_name):
    """
    Purpose: Locate one named node in a tileset.

    Entry:
        document - a decoded glTF. node_name - the node's `name`, as the
        tileset spells it.

    Exit/Returns:
        Returns the node dict. Raises SplitError naming what IS there when the
        node is absent, because a typo in a tile name is the likely mistake and
        a list of the alternatives is the answer to it.

    Module Globals:
        None.

    Methodology:
        A scan. Thirty-four nodes is not worth an index.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    for node in document.get("nodes", []):
        if node.get("name") == node_name:
            return node

    available = sorted(
        node.get("name", "") for node in document.get("nodes", []))

    raise SplitError("no node named '%s'. The tileset holds: %s"
                     % (node_name, ", ".join(available)))


def _accessor_span(document, accessor):
    """
    Purpose: Report where one accessor's bytes actually live in the buffer.

    Entry:
        document - a decoded glTF. accessor - one entry from its accessors.

    Exit/Returns:
        Returns (start, length) into the buffer. Raises SplitError for an
        interleaved accessor, which this tool cannot repack without also
        repacking every accessor sharing the stride.

    Module Globals:
        _COMPONENT_SIZES, _TYPE_COMPONENTS read.

    Methodology:
        With no byteStride the data is tightly packed, so the length is simply
        count * components * component size -- which is what lets each surviving
        accessor be copied into a bufferView of its own.

    Notes/References:
        Refusing rather than approximating is the same call pack_model makes on
        a specular-glossiness material it cannot convert exactly.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    view = document["bufferViews"][accessor["bufferView"]]

    if view.get("byteStride"):
        raise SplitError("accessor uses an interleaved bufferView; "
                         "this tool copies one accessor per view")

    components = _TYPE_COMPONENTS[accessor["type"]]
    size = _COMPONENT_SIZES[accessor["componentType"]]
    length = accessor["count"] * components * size
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)

    return start, length


def _pad(payload):
    """
    Purpose: Grow a buffer to the next alignment boundary.

    Entry:
        payload - the bytes so far.

    Exit/Returns:
        Returns payload plus 0..3 zero bytes.

    Module Globals:
        _VIEW_ALIGNMENT, _PAD_BYTE read.

    Methodology:
        Applied between bufferViews so the next accessor starts on a boundary
        every component size divides.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    remainder = len(payload) % _VIEW_ALIGNMENT

    if remainder == 0:
        return payload

    return payload + _PAD_BYTE * (_VIEW_ALIGNMENT - remainder)


def _copy_accessors(document, raw, mesh):
    """
    Purpose: Rebuild one mesh's accessors and their bytes, tight.

    Entry:
        document - the decoded tileset. raw - its buffer bytes. mesh - the mesh
        whose primitives are being kept. MUTATES the primitives of `mesh`,
        which must already be a copy.

    Exit/Returns:
        Returns (accessors, views, payload) -- the new accessor and bufferView
        tables and the buffer they index into. Every attribute and indices
        reference in `mesh` is rewritten to the new numbering.

    Module Globals:
        None written.

    Methodology:
        One accessor keeps one bufferView. That is how the source is already
        laid out, it is what _accessor_span refuses to depart from, and it makes
        the rewrite a straight append: no offset arithmetic survives from the
        original file, so a mistake here cannot silently read a neighbour's
        vertices.

    Notes/References:
        Accessor min/max are carried through unchanged; they describe the same
        numbers in the same order.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    state = {"accessors": [], "views": [], "payload": b"", "seen": {}}

    for primitive in mesh["primitives"]:
        attributes = primitive["attributes"]

        for name in sorted(attributes):
            attributes[name] = _keep_accessor(
                document, raw, state, attributes[name])

        if "indices" in primitive:
            primitive["indices"] = _keep_accessor(
                document, raw, state, primitive["indices"])

    return state["accessors"], state["views"], state["payload"]


def _keep_accessor(document, raw, state, index):
    """
    Purpose: Copy one accessor and its bytes into the rebuild, once.

    Entry:
        document - the decoded tileset. raw - its buffer bytes. state - the
        rebuild in progress, holding `accessors`, `views`, `payload` and the
        `seen` map of old index -> new index. MUTATED. index - the accessor
        number in the source document.

    Exit/Returns:
        Returns the accessor's number in the rebuilt table. An accessor asked
        for twice is copied once, which is what makes a primitive sharing
        POSITION with its own indices cost one copy.

    Module Globals:
        None written.

    Methodology:
        Append the accessor's exact byte span, give it a bufferView of its own
        at the current end of the payload, and pad after it. The accessor's
        own byteOffset is dropped because the copy starts at the view.

    Notes/References:
        Split out of _copy_accessors to keep both routines inside the length
        cap style.md sets, and because "copy one accessor" is the whole of the
        rule that has to be right.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    if index in state["seen"]:
        return state["seen"][index]

    source = document["accessors"][index]
    start, length = _accessor_span(document, source)
    moved = dict(source)

    moved["bufferView"] = len(state["views"])
    moved.pop("byteOffset", None)

    view = {"buffer": 0, "byteOffset": len(state["payload"]),
            "byteLength": length}
    target = document["bufferViews"][source["bufferView"]].get("target")

    if target is not None:
        view["target"] = target

    state["views"].append(view)
    state["payload"] = _pad(state["payload"] + raw[start:start + length])
    state["accessors"].append(moved)
    state["seen"][index] = len(state["accessors"]) - 1

    return state["seen"][index]


def _extract_images(document, raw, source_dir):
    """
    Purpose: Pull every image out of a tileset into files beside the split.

    Entry:
        document - the decoded tileset. raw - its buffer bytes. source_dir -
        where the tileset itself sits, for an image stored as a plain filename.

    Exit/Returns:
        Returns (images, files) -- the rebuilt images table, each entry now
        carrying a `uri` under textures/, and a list of (relative path, bytes)
        for the caller to write.

    Module Globals:
        _TEXTURES_DIRNAME, _IMAGE_EXTENSIONS, _DEFAULT_IMAGE_EXTENSION read.

    Methodology:
        EXTERNAL on purpose, and this is the one place the output is not simply
        a subset of the input. pack_model.py resamples an image it finds at a
        `uri` and leaves an already-embedded one alone -- so a tile written with
        its palette still inside the buffer would be served at the tileset's
        full authoring resolution, silently, whatever budget its family sets.

    Notes/References:
        assets/asset_budgets.py is the budget that would have been bypassed.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    images = []
    files = []

    for number, image in enumerate(document.get("images", [])):
        payload = _image_bytes(image, raw, document, source_dir)
        stem = image.get("name") or "image_%d" % number
        extension = _IMAGE_EXTENSIONS.get(
            image.get("mimeType", ""), _DEFAULT_IMAGE_EXTENSION)
        relative = "%s/%s%s" % (_TEXTURES_DIRNAME, stem, extension)

        files.append((relative, payload))
        images.append({"name": stem, "uri": relative})

    return images, files


def _image_bytes(image, raw, document, source_dir):
    """
    Purpose: Get one image's bytes, however the tileset chose to store them.

    Entry:
        image - one entry from the images table. raw - the buffer bytes.
        document - the decoded tileset, for a bufferView lookup. source_dir -
        where a plain filename would be relative to.

    Exit/Returns:
        Returns the encoded image bytes. Raises SplitError when the entry names
        no storage at all.

    Module Globals:
        _DATA_URI_PREFIX, _DATA_URI_SEPARATOR read.

    Methodology:
        Three shapes, the same three a buffer has: inside the binary buffer, a
        base64 data: URI, or a file beside the tileset.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    if "bufferView" in image:
        view = document["bufferViews"][image["bufferView"]]
        start = view.get("byteOffset", 0)

        return raw[start:start + view["byteLength"]]

    uri = image.get("uri", "")

    if not uri:
        raise SplitError("an image names neither a bufferView nor a uri")

    if uri.startswith(_DATA_URI_PREFIX):
        return base64.b64decode(uri.split(_DATA_URI_SEPARATOR, 1)[1])

    with open(os.path.join(source_dir, uri), "rb") as handle:
        return handle.read()


def _split_document(document, raw, node_name, source_dir):
    """
    Purpose: Build the one-tile glTF, its buffer and its image files.

    Entry:
        document - the decoded tileset. raw - its buffer bytes. node_name - the
        tile to keep. source_dir - where the tileset sits.

    Exit/Returns:
        Returns (document, buffer_bytes, image_files). Nothing passed in is
        mutated; the mesh and its primitives are deep-copied before rewriting.

    Module Globals:
        _GENERATOR, _GLTF_VERSION, _BUFFER_FILENAME, _SHARED_TABLES,
        _TRANSFORM_KEYS read.

    Methodology:
        Keep the node, its mesh and what that mesh reads. Copy the material,
        texture and sampler tables whole so every index inside the surviving
        primitives stays valid without a remap -- see the module docstring on
        why that is the right trade for a palette atlas.

    Notes/References:
        The node's own transform is carried across. Tileset_desert's nodes
        carry none, but a tileset whose tiles are placed by node transform
        would arrive at the wrong size without this.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    node = _find_node(document, node_name)

    if "mesh" not in node:
        raise SplitError("node '%s' carries no mesh" % node_name)

    mesh = json.loads(json.dumps(document["meshes"][node["mesh"]]))
    accessors, views, payload = _copy_accessors(document, raw, mesh)
    images, files = _extract_images(document, raw, source_dir)
    kept = {
        "asset": {"version": _GLTF_VERSION, "generator": _GENERATOR},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": node_name}],
        "meshes": [mesh],
        "accessors": accessors,
        "bufferViews": views,
        "images": images,
        "buffers": [{"uri": _BUFFER_FILENAME, "byteLength": len(payload)}],
    }

    for key in _TRANSFORM_KEYS:
        if key in node:
            kept["nodes"][0][key] = node[key]

    for table in _SHARED_TABLES:
        if table in document:
            kept[table] = document[table]

    return kept, payload, files


def _write_source(dest_dir, document, payload, files):
    """
    Purpose: Write one extracted tile as a source directory on disk.

    Entry:
        dest_dir - the directory to create. document, payload, files - what
        _split_document produced.

    Exit/Returns:
        Returns the total bytes written. The directory is created if absent and
        its scene.gltf, scene.bin and textures/ are overwritten.

    Module Globals:
        _GLTF_FILENAME, _BUFFER_FILENAME, _TEXTURES_DIRNAME read.

    Methodology:
        The layout is dictated entirely by pack_model.py: one scene.gltf at the
        root naming one external buffer, and images at the uris it writes.
        Nothing here is a choice this tool gets to make.

    Notes/References:
        assets/README.md describes this shape as what a download arrives in.

    Author: Nick Hobar
    Creation date: 08/28/2026
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

    for relative, image_bytes in files:
        path = os.path.join(dest_dir, *relative.split("/"))

        with open(path, "wb") as handle:
            handle.write(image_bytes)
            written += len(image_bytes)

    return written


# ─── Public routines ─────────────────────────────────────────────────────────

def split(tileset_path, dest_root, node_name):
    """
    Purpose: Extract one tile from a tileset into its own source directory.

    Entry:
        tileset_path - the multi-node .gltf. dest_root - the directory the
        per-tile directories are created under, which has to be somewhere under
        assets/ for pack_model.py to name a family for it. node_name - the
        tile's node name, which also names the directory.

    Exit/Returns:
        Returns (dest_dir, bytes_written). Raises SplitError for a tileset shape
        this cannot handle or a node name that is not in it.

    Module Globals:
        None written.

    Methodology:
        Read once, split, write. The tileset is re-read per tile rather than
        cached, because splitting four tiles out of a 380 KB document is not
        worth a cache and a stale one would be a very confusing bug.

    Notes/References:
        Nothing here writes to the tileset. See the module docstring.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    source_dir = os.path.dirname(os.path.abspath(tileset_path))
    document = _load_document(tileset_path)
    raw = _buffer_bytes(document, source_dir)
    kept, payload, files = _split_document(
        document, raw, node_name, source_dir)
    dest_dir = os.path.join(dest_root, node_name)
    written = _write_source(dest_dir, kept, payload, files)

    return dest_dir, written


# ─── Entry point ─────────────────────────────────────────────────────────────

_USAGE = """split_tileset.py -- split one glTF tileset into per-tile sources

  split_tileset.py <tileset.gltf> <dest_root> <node> [<node> ...]

Writes <dest_root>/<node>/ as an ordinary model source directory -- scene.gltf,
scene.bin, textures/ -- which assets/pack_model.py then packs into the served
.glb like any download. dest_root has to be under assets/, because the first
path component below it is what names the served family.

  ../evenv/Scripts/python.exe assets/split_tileset.py
      assets/tiles/desert/Tileset.gltf assets/tiles/desert center_h center_b
"""


def main(argv):
    """
    Purpose: Run the splitter from the command line.

    Entry:
        argv - sys.argv. Wants the tileset, the destination root and at least
        one node name.

    Exit/Returns:
        Returns a process exit status. Prints one line per tile written.

    Module Globals:
        _USAGE, _MINIMUM_ARGUMENTS read.

    Methodology:
        Every tile is attempted even if one fails, and the status reflects
        whether any did -- splitting four tiles and being told about only the
        first mistake is two more runs than it needs to be.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    if len(argv) < _MINIMUM_ARGUMENTS:
        print(_USAGE)

        return 1

    tileset_path, dest_root = argv[1], argv[2]
    failed = False

    for node_name in argv[3:]:
        try:
            dest_dir, written = split(tileset_path, dest_root, node_name)
        except SplitError as error:
            print("%s: %s" % (node_name, error))
            failed = True
            continue

        print("%-22s -> %s (%d bytes)" % (node_name, dest_dir, written))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
