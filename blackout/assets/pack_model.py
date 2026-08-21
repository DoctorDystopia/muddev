"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/17/2026
Description: Turns a downloaded glTF model directory into the single .glb file
             the webclient serves, downscaling its textures on the way.

             Model downloads arrive as scene.gltf + scene.bin + a textures/
             directory, at resolutions meant for a hero asset filling a screen
             -- 2048 square for a sword drawn two centimetres wide in an
             inventory cell. Serving that shape directly would mean four HTTP
             requests per item and a megabyte of texture nobody can see. This
             packs the lot into one self-contained .glb with the images
             resampled to something honest for the size they render at, and
             any material our vendored GLTFLoader cannot read rewritten into
             one it can.

             The served file lands in web/static/webclient/models/<family>/,
             where <family> is the directory the download sits in under
             assets/ -- items, npcs, world_objects. The source layout is the
             only place that division is decided.

             The source directory is never written to. Re-running is safe and
             produces the same bytes.

             Pure file transformation. Importing this module touches no
             database and boots no Evennia -- but it sits outside the game
             package anyway, because it is a build tool and not game code.

             Usage:
                 ../evenv/Scripts/python.exe assets/pack_model.py
                     assets/items/weapons/rusty_sword rusty_scrap_shortsword
                     [max_texture_edge]
"""

import json
import os
import struct
import sys
from io import BytesIO

from PIL import Image

# Longest edge, in pixels, any packed texture keeps. An inventory cell is about
# 70px and a world-pane item is smaller, so 512 is already generous; it is
# headroom for models inspected close up, not a size anything resolves today.
MAX_TEXTURE_EDGE = 512

# glTF-Binary container, per the spec's Chapter 4. Little-endian throughout.
_GLB_MAGIC = 0x46546C67                 # "glTF"
_GLB_VERSION = 2
_GLB_HEADER_FORMAT = "<III"             # magic, version, total length
_CHUNK_HEADER_FORMAT = "<II"            # chunk length, chunk type
_CHUNK_TYPE_JSON = 0x4E4F534A           # "JSON"
_CHUNK_TYPE_BIN = 0x004E4942            # "BIN\0"
_CHUNK_ALIGNMENT = 4
_JSON_PAD_BYTE = b"\x20"                # spec: pad the JSON chunk with spaces
_BIN_PAD_BYTE = b"\x00"                 # spec: pad the binary chunk with zeros

_MIME_PNG = "image/png"
_PNG_FORMAT = "PNG"

# Pillow silently forces NEAREST resampling for these two modes -- an indexed
# image cannot be interpolated in its own colour space, so there is nothing to
# average. Converting to true colour first is what keeps the LANCZOS promise in
# _resample_texture honest for a texture that arrived paletted, which the
# teleporter's beam did.
_INDEXED_MODES = ("P", "1")
_MODE_RGB = "RGB"
_MODE_RGBA = "RGBA"
_TRANSPARENCY_KEY = "transparency"

# The material extension Sketchfab still exports and our vendored GLTFLoader
# (three.js r147) no longer reads. See _convert_spec_gloss_material.
_SPEC_GLOSS_EXTENSION = "KHR_materials_pbrSpecularGlossiness"
_SPEC_GLOSS_TEXTURE = "specularGlossinessTexture"
_EXTENSION_LISTS = ("extensionsUsed", "extensionsRequired")
_EXTENSIONS_KEY = "extensions"

# Reflectance of an ordinary non-metal, from the glTF 2.0 spec's material
# model. A specular factor at or below it is a dielectric, which is the one
# case the spec-gloss conversion can be exact for.
_DIELECTRIC_SPECULAR = 0.04
_WHITE_SPECULAR = (1.0, 1.0, 1.0)
_FULL_GLOSS = 1.0
_METALLIC_NONE = 0.0

_GLTF_FILENAME = "scene.gltf"
_MODELS_RELATIVE_PATH = os.path.join("web", "static", "webclient", "models")
_MODEL_EXTENSION = ".glb"

# Where downloads live. The first path component BELOW it names the family --
# items, npcs, world_objects -- and the served tree mirrors that, so the
# source layout is the only place the division is decided.
_ASSETS_DIRNAME = "assets"

_BYTES_PER_KB = 1024
_EXPECTED_ARGUMENTS = 3
_MAX_EDGE_ARGUMENT = 3                  # argv slot of the optional edge

# assets/pack_model.py -> blackout/
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PackError(RuntimeError):
    """Raised when a source directory is not a shape this packer can read."""


def _read_source_gltf(source_dir):
    """
    Purpose: Read and decode the scene.gltf at the root of a source directory.

    Entry:
        source_dir names an existing directory holding scene.gltf.

    Exit/Returns:
        Returns the decoded glTF document as a dict. Raises PackError when the
        file is missing or is not valid JSON.

    Module Globals:
        _GLTF_FILENAME read.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    path = os.path.join(source_dir, _GLTF_FILENAME)
    exists = os.path.isfile(path)

    if not exists:
        raise PackError("no %s in %s" % (_GLTF_FILENAME, source_dir))

    with open(path, "r", encoding="utf-8") as handle:
        try:
            document = json.load(handle)
        except ValueError as error:
            raise PackError("%s is not valid JSON: %s" % (path, error))

    return document


def _read_source_buffer(source_dir, document):
    """
    Purpose: Read the single external .bin buffer a source glTF references.

    Entry:
        document is a decoded glTF holding exactly one buffer, whose `uri`
        names a file relative to source_dir.

    Exit/Returns:
        Returns the buffer's bytes. Raises PackError for any other buffer
        shape -- several buffers, or one already embedded -- because those
        need repacking rules this tool does not have.

    Module Globals:
        None.

    Notes/References:
        Every exporter this has met so far emits exactly one.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    buffers = document.get("buffers", [])
    count = len(buffers)

    if count != 1:
        raise PackError("expected exactly 1 buffer, found %d" % count)

    uri = buffers[0].get("uri", "")

    if not uri:
        raise PackError("buffer 0 has no uri; the source is already packed")

    path = os.path.join(source_dir, uri)

    with open(path, "rb") as handle:
        payload = handle.read()

    return payload


def _served_family(source_dir):
    """
    Purpose: Name the served subdirectory one source directory belongs in.

    Entry:
        source_dir names a directory under assets/, at any depth below the
        family directory -- assets/items/weapons/rusty_sword is a family of
        "items".

    Exit/Returns:
        Returns the family name. Raises PackError when the source is not under
        assets/ at all, because then nothing names the family and a guess would
        put the file somewhere no registration expects it.

    Module Globals:
        _GAME_DIR, _ASSETS_DIRNAME read.

    Methodology:
        The served tree mirrors the source tree rather than restating it in an
        argument, so a download dropped in assets/npcs/ can only ever be packed
        into models/npcs/. One owner for the division, and no way to type it
        inconsistently.

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    absolute = os.path.abspath(source_dir)
    root = os.path.join(_GAME_DIR, _ASSETS_DIRNAME)
    prefix = root + os.sep
    inside = absolute.startswith(prefix)

    if not inside:
        raise PackError("%s is not under %s, so nothing names its family; "
                        "model downloads live there" % (source_dir, root))

    relative = absolute[len(prefix):]
    parts = relative.split(os.sep)

    return parts[0]


def _to_true_color(image):
    """
    Purpose: Convert an indexed image to true colour so it can be resampled.

    Entry:
        image is an open Pillow image in any mode.

    Exit/Returns:
        Returns the image unchanged when it is already true colour, and a
        converted copy otherwise. Transparency survives the conversion.

    Module Globals:
        _INDEXED_MODES, _MODE_RGB, _MODE_RGBA, _TRANSPARENCY_KEY read.

    Methodology:
        Pillow forces NEAREST for "P" and "1" images no matter what filter is
        asked for -- there is nothing to average between two palette indices --
        so a paletted texture shrunk 4x arrives visibly aliased while the
        caller believes it asked for LANCZOS. Converting first is the whole
        fix. A palette carrying a transparency index becomes RGBA rather than
        RGB, because dropping it would turn the teleporter's blended beam into
        a solid box.

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    indexed = image.mode in _INDEXED_MODES

    if not indexed:
        return image

    transparent = _TRANSPARENCY_KEY in image.info
    target = _MODE_RGB

    if transparent:
        target = _MODE_RGBA

    converted = image.convert(target)

    return converted


def _convert_spec_gloss_material(material) -> bool:
    """
    Purpose: Rewrite one specular-glossiness material as core metallic-
             roughness, in place.

    Entry:
        material is one entry of a glTF document's `materials` array.

    Exit/Returns:
        Returns True when the material carried KHR_materials_pbrSpecular-
        Glossiness and was rewritten, False when it carried no such extension.
        Raises PackError for a spec-gloss material this cannot convert exactly.

    Module Globals:
        _SPEC_GLOSS_EXTENSION, _SPEC_GLOSS_TEXTURE, _EXTENSIONS_KEY,
        _DIELECTRIC_SPECULAR, _WHITE_SPECULAR, _FULL_GLOSS, _METALLIC_NONE
        read.

    Methodology:
        Only the DIELECTRIC case is converted, and it is the only one that
        converts exactly. A black specular factor means the surface reflects
        like a non-metal, so metallic is 0, the diffuse colour IS the base
        colour, and roughness is 1 - glossiness. A metallic material would need
        the Khronos solver, and a specularGlossinessTexture would need the
        texture itself resampled channel by channel; both raise rather than
        approximate, because a silently wrong colour is worse than a build that
        stops and names the material.

    Notes/References:
        The extension was deprecated by Khronos and dropped from three.js's
        GLTFLoader; the r147 build vendored here has no reader for it, so a
        material left in this form loads as flat untextured white. That is not
        a fallback the resolver can see -- the model loads "successfully" --
        so the fix belongs here, at the one point the download is translated.

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    extensions = material.get(_EXTENSIONS_KEY, {})
    entry = extensions.get(_SPEC_GLOSS_EXTENSION)

    if entry is None:
        return False

    name = material.get("name", "")
    specular = entry.get("specularFactor", _WHITE_SPECULAR)
    strongest = max(specular)
    has_texture = _SPEC_GLOSS_TEXTURE in entry

    if strongest > _DIELECTRIC_SPECULAR:
        raise PackError("material '%s' is metallic (specular %s); converting "
                        "it needs the Khronos solver this does not have"
                        % (name, specular))

    if has_texture:
        raise PackError("material '%s' carries a %s; converting it needs the "
                        "texture resampled, not just the factors"
                        % (name, _SPEC_GLOSS_TEXTURE))

    glossiness = entry.get("glossinessFactor", _FULL_GLOSS)
    roughness = _FULL_GLOSS - glossiness
    pbr = {"metallicFactor": _METALLIC_NONE, "roughnessFactor": roughness}
    diffuse_factor = entry.get("diffuseFactor")
    diffuse_texture = entry.get("diffuseTexture")

    if diffuse_factor:
        pbr["baseColorFactor"] = diffuse_factor

    if diffuse_texture:
        pbr["baseColorTexture"] = diffuse_texture

    material["pbrMetallicRoughness"] = pbr
    extensions.pop(_SPEC_GLOSS_EXTENSION)

    if not extensions:
        material.pop(_EXTENSIONS_KEY)

    return True


def _convert_spec_gloss(document) -> int:
    """
    Purpose: Rewrite every specular-glossiness material in a glTF document.

    Entry:
        document is a decoded glTF.

    Exit/Returns:
        Returns how many materials were converted. `document` is MUTATED: each
        converted material gains a pbrMetallicRoughness block and loses the
        extension, and the extension is struck from extensionsUsed and
        extensionsRequired.

    Module Globals:
        _SPEC_GLOSS_EXTENSION, _EXTENSION_LISTS read.

    Methodology:
        The extension lists are cleaned only after a conversion actually
        happened, so a document naming the extension while using it in a form
        this cannot convert still fails in _convert_spec_gloss_material rather
        than being quietly declared clean.

    Author: Nick Hobar
    Creation date: 08/20/2026
    """
    materials = document.get("materials", [])
    converted = 0

    for material in materials:
        changed = _convert_spec_gloss_material(material)

        if changed:
            converted += 1

    if not converted:
        return 0

    for key in _EXTENSION_LISTS:
        names = document.get(key)

        if not names:
            continue

        remaining = [name for name in names if name != _SPEC_GLOSS_EXTENSION]
        document[key] = remaining

    return converted


def _resample_texture(path, max_edge):
    """
    Purpose: Load one texture and re-encode it as PNG, shrunk if oversized.

    Entry:
        path names an image file Pillow can open. max_edge >= 1.

    Exit/Returns:
        Returns (png_bytes, original_size, packed_size), the sizes being
        (width, height). An image already within max_edge is re-encoded rather
        than passed through, so output is uniformly optimized PNG.

    Module Globals:
        _PNG_FORMAT read.

    Methodology:
        Scales the longest edge to max_edge and the other by the same ratio, so
        aspect is preserved. LANCZOS because these are diffuse and normal maps
        being minified, where a cheaper filter aliases visibly -- which is why
        an indexed image is converted to true colour first, since Pillow would
        otherwise substitute NEAREST for it without saying so.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    opened = Image.open(path)
    source = _to_true_color(opened)
    original_size = source.size
    longest = max(original_size)
    packed = source

    if longest > max_edge:
        ratio = float(max_edge) / float(longest)
        width = max(1, int(round(original_size[0] * ratio)))
        height = max(1, int(round(original_size[1] * ratio)))
        packed = source.resize((width, height), Image.LANCZOS)

    sink = BytesIO()
    packed.save(sink, format=_PNG_FORMAT, optimize=True)
    encoded = sink.getvalue()

    return encoded, original_size, packed.size


def _pad_to_alignment(payload, pad_byte):
    """
    Purpose: Grow a chunk to the next 4-byte boundary the GLB spec requires.

    Entry:
        payload is bytes. pad_byte is a single byte.

    Exit/Returns:
        Returns payload plus 0..3 padding bytes.

    Module Globals:
        _CHUNK_ALIGNMENT read.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    remainder = len(payload) % _CHUNK_ALIGNMENT

    if remainder == 0:
        return payload

    shortfall = _CHUNK_ALIGNMENT - remainder
    padding = pad_byte * shortfall

    return payload + padding


def _embed_images(document, source_dir, buffer_bytes, max_edge):
    """
    Purpose: Move every external image into the binary buffer, downscaled.

    Entry:
        document is a decoded glTF whose images carry `uri`s relative to
        source_dir. buffer_bytes is the buffer the images are appended to.

    Exit/Returns:
        Returns (packed_buffer, report). `document` is MUTATED: each image
        loses its uri and gains a bufferView index and a mimeType, one
        bufferView is appended per image, and the buffer entry is rewritten
        with no uri. `report` holds one
        (uri, original_size, packed_size, packed_bytes) row per image, for the
        caller to print. Images already embedded are left alone.

    Module Globals:
        _MIME_PNG, _BIN_PAD_BYTE read.

    Methodology:
        Existing bufferViews keep their offsets because the original buffer
        stays at the front; images are appended past its end, each padded so
        the next starts on a 4-byte boundary.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    images = document.get("images", [])
    views = document.setdefault("bufferViews", [])
    packed_buffer = buffer_bytes
    report = []

    for image in images:
        uri = image.get("uri", "")

        if not uri:
            continue

        path = os.path.join(source_dir, uri)
        png, original_size, packed_size = _resample_texture(path, max_edge)
        offset = len(packed_buffer)
        views.append(
            {"buffer": 0, "byteOffset": offset, "byteLength": len(png)})
        image.pop("uri")
        image["bufferView"] = len(views) - 1
        image["mimeType"] = _MIME_PNG
        packed_buffer = _pad_to_alignment(packed_buffer + png, _BIN_PAD_BYTE)
        report.append((uri, original_size, packed_size, len(png)))

    document["buffers"] = [{"byteLength": len(packed_buffer)}]

    return packed_buffer, report


def _build_container(document, buffer_bytes):
    """
    Purpose: Wrap a glTF document and its buffer in the GLB container.

    Entry:
        document is a decoded glTF with no external references left.

    Exit/Returns:
        Returns the complete .glb file as bytes.

    Module Globals:
        Every _GLB_* and _CHUNK_* constant read.

    Methodology:
        A 12-byte header, then a JSON chunk, then a BIN chunk. Each chunk is an
        8-byte header (length, type) followed by its padded payload, and the
        file header's total length counts everything including itself.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    encoded = json.dumps(document, separators=(",", ":")).encode("utf-8")
    json_chunk = _pad_to_alignment(encoded, _JSON_PAD_BYTE)
    bin_chunk = _pad_to_alignment(buffer_bytes, _BIN_PAD_BYTE)
    chunk_header_size = struct.calcsize(_CHUNK_HEADER_FORMAT)
    header_size = struct.calcsize(_GLB_HEADER_FORMAT)
    total = (header_size
             + chunk_header_size + len(json_chunk)
             + chunk_header_size + len(bin_chunk))
    parts = [
        struct.pack(_GLB_HEADER_FORMAT, _GLB_MAGIC, _GLB_VERSION, total),
        struct.pack(_CHUNK_HEADER_FORMAT, len(json_chunk), _CHUNK_TYPE_JSON),
        json_chunk,
        struct.pack(_CHUNK_HEADER_FORMAT, len(bin_chunk), _CHUNK_TYPE_BIN),
        bin_chunk,
    ]
    container = b"".join(parts)

    return container


def model_output_path(asset_key, family):
    """
    Purpose: Name the served .glb file for one asset key.

    Entry:
        asset_key is the statefeed asset key, e.g. "rusty_scrap_shortsword".
        family is the served subdirectory, as _served_family reports it.

    Exit/Returns:
        Returns the absolute path the packed model belongs at. The file is
        named for the ASSET KEY rather than for the download it came from,
        because the asset key is what blackout_models.js registers.

    Module Globals:
        _GAME_DIR, _MODELS_RELATIVE_PATH, _MODEL_EXTENSION read.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    directory = os.path.join(_GAME_DIR, _MODELS_RELATIVE_PATH, family)
    filename = asset_key + _MODEL_EXTENSION
    path = os.path.join(directory, filename)

    return path


def pack(source_dir, asset_key, max_edge=MAX_TEXTURE_EDGE):
    """
    Purpose: Pack one source model directory into the served .glb.

    Entry:
        source_dir holds scene.gltf and everything it references, and lives
        under assets/<family>/. asset_key names the thing the model is for.
        max_edge >= 1.

    Exit/Returns:
        Returns (output_path, report, converted): the texture rows _embed_images
        built and how many materials were rewritten out of spec-gloss. Writes
        the .glb, creating its directory if needed. Raises PackError when the
        source is not a shape this can read. The source directory is not
        modified.

    Module Globals:
        None written.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    family = _served_family(source_dir)
    document = _read_source_gltf(source_dir)
    converted = _convert_spec_gloss(document)
    buffer_bytes = _read_source_buffer(source_dir, document)
    packed_buffer, report = _embed_images(
        document, source_dir, buffer_bytes, max_edge)
    container = _build_container(document, packed_buffer)
    output_path = model_output_path(asset_key, family)
    directory = os.path.dirname(output_path)
    os.makedirs(directory, exist_ok=True)

    with open(output_path, "wb") as handle:
        handle.write(container)

    return output_path, report, converted


def _describe(output_path, report, converted):
    """
    Purpose: Print what the pack did, in a form worth pasting into a commit.

    Entry:
        report is the list _embed_images returned. converted is the material
        count _convert_spec_gloss returned.

    Exit/Returns:
        Returns None. Writes to stdout.

    Module Globals:
        _BYTES_PER_KB, _SPEC_GLOSS_EXTENSION read.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    if converted:
        print("  rewrote %d material(s) out of %s"
              % (converted, _SPEC_GLOSS_EXTENSION))

    for uri, original_size, packed_size, packed_bytes in report:
        print("  %-40s %dx%d -> %dx%d  %d KB"
              % (uri, original_size[0], original_size[1],
                 packed_size[0], packed_size[1], packed_bytes // _BYTES_PER_KB))

    size = os.path.getsize(output_path)
    print("  wrote %s (%d KB)" % (output_path, size // _BYTES_PER_KB))


if __name__ == "__main__":
    given = len(sys.argv)
    accepted = (_EXPECTED_ARGUMENTS, _EXPECTED_ARGUMENTS + 1)

    if given not in accepted:
        print(__doc__)
        sys.exit(1)

    edge = MAX_TEXTURE_EDGE

    try:
        if given > _EXPECTED_ARGUMENTS:
            edge = int(sys.argv[_MAX_EDGE_ARGUMENT])

        written, summary, rewritten = pack(sys.argv[1], sys.argv[2], edge)
    except (PackError, OSError, ValueError) as failure:
        print("pack failed: %s" % failure)
        sys.exit(1)

    _describe(written, summary, rewritten)
