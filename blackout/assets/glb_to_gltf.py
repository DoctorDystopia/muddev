"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/12/2026
Description: Turns an untextured .glb download into the source directory shape
             pack_model.py already understands, with its material wired in.

             THE PROBLEM THIS FIXES. Kyle Fuji's Low Poly Food pack arrived
             through the Godot Asset Library, and a Godot pack is shaped for
             Godot: every model is a .glb carrying geometry and UVs and NO
             MATERIAL AT ALL. The look lives beside it, in a StandardMaterial3D
             .tres that a prefab applies with `material_override` -- so the .glb
             on its own is a correct mesh that renders untextured, and packing
             it as-is would serve exactly that. pack_model.py also reads only a
             scene.gltf with an external buffer, so it has nothing to point at
             in the first place.

             This is the step in front, and like the other three converters in
             this directory it is deliberately the only new thing: what it
             writes is an ordinary source directory (scene.gltf + scene.bin),
             and everything downstream is the pipeline that already exists.

             WHAT IT WRITES. A .glb is a glTF document and its buffer in one
             container, so splitting it is exact -- nothing is re-encoded. One
             material is then added and every primitive pointed at it:

                 baseColorTexture  the image `--texture` names
                 metallicFactor    0
                 roughnessFactor   the .tres's `roughness`, 0.7 for this pack
                 alphaMode         OPAQUE, spelled out

             The image is REFERENCED, not copied: its uri is written relative to
             the destination (`../Textures/T_protein_atlas_diffuse.png`), which
             pack_model.py resolves like any other. Several models share one
             atlas, and a copy per model would put the same half-megabyte in the
             repository once for each.

             WHY ALPHAMODE IS SPELLED OUT. The protein atlas is RGBA, and its
             alpha is not transparency: M_protein.tres reads ROUGHNESS out of it
             (`roughness_texture_channel = 3`), and sampled it runs 128 to 211 and
             never reaches 255. A material that took that channel as coverage
             would draw every egg and steak partly see-through. OPAQUE is the
             glTF default, but it is written anyway -- floating_eye is the
             standing proof of what an alpha channel misread as coverage looks
             like, and a default nobody wrote down is one an edit silently
             changes.

             WHAT IS DELIBERATELY NOT CARRIED. The normal map, the roughness
             texture and the junk atlas's metallic map. An item is drawn about
             seventy pixels across in an inventory cell and smaller on a tile,
             where none of the three resolves to anything; each would still cost
             a 512-square PNG in the served file. A constant roughness is what
             the .tres's scalar already is before its texture refines it.

             The download is never written to, exactly as pack_model.py never
             writes to one. Re-running produces the same bytes.

             --as-exported: A .GLB THAT ALREADY SAYS HOW IT LOOKS. A model
             built in Blender and exported as .glb carries its own materials,
             and pack_model.py still has nothing to point at. With
             --as-exported the container is split exactly and nothing is
             added: the materials ship as authored, alpha modes included,
             because replacing them is a decision rather than a conversion. The
             mode is a flag rather than implied by a missing --texture, so a
             forgotten --texture on an Asset Library mesh is refused instead
             of quietly producing an untextured source. It refuses a .glb with
             NO materials (that is what --texture is for) and one carrying
             images (pack_model.py resamples only an image beside scene.gltf,
             so an embedded one would ship at authoring size, past the family
             budget). Its sources are marked `--as-exported` in the generator
             string, which is how the manifest test tells the two apart.

             Pure file transformation. Importing this module touches no
             database and boots no Evennia -- but it sits outside the game
             package anyway, because it is a build tool and not game code.

             Usage:
                 ../evenv/Scripts/python.exe assets/glb_to_gltf.py
                     assets/items/food/kyle_fuji_food/Models/egg.glb
                     assets/items/food/kyle_fuji_food/egg
                     --texture assets/items/food/kyle_fuji_food/Textures/T_protein_atlas_diffuse.png
                 ../evenv/Scripts/python.exe assets/glb_to_gltf.py
                     assets/npcs/lone_android_clark/lone_android_clark.glb
                     assets/npcs/lone_android_clark --as-exported
"""

import json
import os
import struct
import sys


# ─── Private constant definitions ────────────────────────────────────────────

_GLTF_FILENAME = "scene.gltf"
_BUFFER_FILENAME = "scene.bin"

# The generator string written into what this produces, beside the exporter's
# own. A file that does not say where it came from is one nobody can
# regenerate.
_GENERATOR_SUFFIX = " + blackout glb_to_gltf.py"

# The option naming the split-only mode, and the mark it leaves in the
# generator string. One spelling for both, so a source says which mode wrote it
# in the words an operator would type to reproduce it.
_AS_EXPORTED_OPTION = "--as-exported"
_AS_EXPORTED_GENERATOR_SUFFIX = _GENERATOR_SUFFIX + " " + _AS_EXPORTED_OPTION

# glTF-Binary container, per the spec's Chapter 4. Little-endian throughout.
# The same constants pack_model.py writes with; this reads what it writes.
_GLB_MAGIC = 0x46546C67                 # "glTF"
_GLB_VERSION = 2
_GLB_HEADER_FORMAT = "<III"             # magic, version, total length
_CHUNK_HEADER_FORMAT = "<II"            # chunk length, chunk type
_CHUNK_TYPE_JSON = 0x4E4F534A           # "JSON"
_CHUNK_TYPE_BIN = 0x004E4942            # "BIN\0"

# The material this writes. Roughness is M_protein.tres's and M_junk_food.tres's
# own scalar; see the module docstring for what is deliberately left out.
_METALLIC_NONE = 0.0
_ROUGHNESS_DEFAULT = 0.7
_ALPHA_MODE_OPAQUE = "OPAQUE"
_MIME_PNG = "image/png"

# glTF sampler vocabulary. Spelled out rather than left as bare numbers,
# because a reader who has to look 9729 up is one who cannot check this file.
# LINEAR with mipmaps: this is painted atlas art, not pixel art, and it is
# minified a long way into an inventory cell.
_FILTER_LINEAR = 9729
_FILTER_LINEAR_MIPMAP_LINEAR = 9987
_WRAP_REPEAT = 10497

_ATTRIBUTE_UV = "TEXCOORD_0"
_URI_SEPARATOR = "/"

_TEXTURE_OPTION = "--texture"
_ROUGHNESS_OPTION = "--roughness"
_POSITIONAL_ARGUMENTS = 2


class GlbError(RuntimeError):
    """Raised when a .glb is not a shape this converter can read."""


# ─── Private routines: reading the container ─────────────────────────────────

def _read_chunk(data, offset):
    """
    Purpose: Read one chunk header and its payload out of a .glb.

    Entry:
        data is the whole file. offset points at a chunk header.

    Exit/Returns:
        Returns (chunk_type, payload, next_offset). Raises GlbError when the
        chunk claims more bytes than the file holds.

    Module Globals:
        _CHUNK_HEADER_FORMAT read.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    header_size = struct.calcsize(_CHUNK_HEADER_FORMAT)

    if offset + header_size > len(data):
        raise GlbError("truncated chunk header at byte %d" % offset)

    length, chunk_type = struct.unpack_from(_CHUNK_HEADER_FORMAT, data, offset)
    start = offset + header_size
    end = start + length

    if end > len(data):
        raise GlbError("chunk at byte %d claims %d bytes; the file ends first"
                       % (offset, length))

    return chunk_type, data[start:end], end


def _split_container(data):
    """
    Purpose: Cut a .glb into its decoded document and its binary buffer.

    Entry:
        data is the whole file's bytes.

    Exit/Returns:
        Returns (document, payload). payload is b"" for a .glb with no BIN
        chunk. Raises GlbError for a bad magic, an unsupported version, a first
        chunk that is not JSON, or JSON that does not decode.

    Module Globals:
        _GLB_HEADER_FORMAT, _GLB_MAGIC, _GLB_VERSION, _CHUNK_TYPE_JSON,
        _CHUNK_TYPE_BIN read.

    Methodology:
        The spec fixes the order: the JSON chunk first, then at most one BIN
        chunk. Anything after those is an extension chunk this has no use for,
        and the spec says a reader ignores it.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    header_size = struct.calcsize(_GLB_HEADER_FORMAT)

    if len(data) < header_size:
        raise GlbError("too short to be a .glb (%d bytes)" % len(data))

    magic, version, _total = struct.unpack_from(_GLB_HEADER_FORMAT, data, 0)

    if magic != _GLB_MAGIC:
        raise GlbError("not a .glb: bad magic 0x%08X" % magic)

    if version != _GLB_VERSION:
        raise GlbError("glTF-Binary version %d; only %d is read"
                       % (version, _GLB_VERSION))

    chunk_type, encoded, offset = _read_chunk(data, header_size)

    if chunk_type != _CHUNK_TYPE_JSON:
        raise GlbError("first chunk is not JSON")

    try:
        document = json.loads(encoded.decode("utf-8"))
    except ValueError as error:
        raise GlbError("JSON chunk does not decode: %s" % error)

    payload = b""

    if offset < len(data):
        chunk_type, payload, _ = _read_chunk(data, offset)

        if chunk_type != _CHUNK_TYPE_BIN:
            payload = b""

    return document, payload


def _check_buffer(document, payload):
    """
    Purpose: Refuse a buffer layout pack_model.py cannot read back.

    Entry:
        document and payload as _split_container returned them.

    Exit/Returns:
        Returns None. Raises GlbError for anything but one buffer, or a buffer
        declaring more bytes than the BIN chunk holds.

    Module Globals:
        None.

    Methodology:
        Shared by both modes: whatever the materials, the written source is
        one scene.gltf naming one scene.bin, which is the only shape
        pack_model.py reads.

    Author: Nick Hobar
    Creation date: 09/13/2026
    """
    buffers = document.get("buffers", [])
    count = len(buffers)

    if count != 1:
        raise GlbError("expected exactly 1 buffer, found %d" % count)

    declared = buffers[0].get("byteLength", 0)
    available = len(payload)

    if declared > available:
        raise GlbError("buffer declares %d bytes; the BIN chunk holds %d"
                       % (declared, available))


def _check_as_exported(document, payload):
    """
    Purpose: Refuse a .glb whose own materials cannot be kept as they are.

    Entry:
        document and payload as _split_container returned them.

    Exit/Returns:
        Returns None. Raises GlbError describing the first thing wrong.

    Module Globals:
        _TEXTURE_OPTION read.

    Methodology:
        The mirror of _check_document. No materials means the download does
        NOT say how it looks, and keeping that would serve a grey model with
        nothing reporting it -- the job --texture exists for. Images mean the
        look is carried in the buffer, where pack_model.py leaves it at its
        authoring size and the family's texture ceiling never applies.

    Author: Nick Hobar
    Creation date: 09/13/2026
    """
    materials = document.get("materials")
    images = document.get("images")

    if not materials:
        raise GlbError("the .glb carries no materials, so keeping it as "
                       "exported would serve it untextured; name a %s instead"
                       % _TEXTURE_OPTION)

    if images:
        raise GlbError("the .glb carries %d image(s) inside it; pack_model.py "
                       "resamples only an image beside scene.gltf, so these "
                       "would ship at authoring size" % len(images))

    _check_buffer(document, payload)


def _check_document(document, payload):
    """
    Purpose: Refuse a document this converter would get wrong.

    Entry:
        document and payload as _split_container returned them.

    Exit/Returns:
        Returns None. Raises GlbError describing the first thing wrong.

    Module Globals:
        _ATTRIBUTE_UV read.

    Methodology:
        Three refusals, each a different job this tool does not do. Existing
        materials or images mean the download already says how it looks, and
        replacing that is a decision rather than a conversion. More than one
        buffer is a repacking rule pack_model.py does not have either. A
        primitive with no UVs cannot be textured, and would render as the
        atlas's average colour with nothing reporting it.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    for key in ("materials", "images"):
        if document.get(key):
            raise GlbError("the .glb already carries %s; this converter adds a "
                           "material to an untextured download, and will not "
                           "replace one -- %s keeps it as authored"
                           % (key, _AS_EXPORTED_OPTION))

    _check_buffer(document, payload)

    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if _ATTRIBUTE_UV not in primitive.get("attributes", {}):
                raise GlbError("mesh %r has a primitive with no %s; nothing "
                               "can be textured" % (mesh.get("name"),
                                                    _ATTRIBUTE_UV))


# ─── Private routines: the material ──────────────────────────────────────────

def _texture_uri(texture_path, dest_dir):
    """
    Purpose: Name an image relative to the source directory that uses it.

    Entry:
        texture_path names an existing image. dest_dir is the directory the
        scene.gltf will be written into.

    Exit/Returns:
        Returns a forward-slashed relative uri, e.g.
        "../Textures/T_protein_atlas_diffuse.png". Raises GlbError when the
        image does not exist.

    Module Globals:
        _URI_SEPARATOR read.

    Methodology:
        A glTF uri is a URI, so its separator is "/" whatever the platform --
        os.path.relpath on Windows answers with backslashes.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    if not os.path.isfile(texture_path):
        raise GlbError("no image at %s" % texture_path)

    relative = os.path.relpath(os.path.abspath(texture_path),
                               os.path.abspath(dest_dir))

    return relative.replace(os.sep, _URI_SEPARATOR)


def _attach_material(document, uri, roughness):
    """
    Purpose: Give an untextured document one textured, opaque material.

    Entry:
        document has passed _check_document. uri names the base colour image
        relative to the source directory. 0 <= roughness <= 1.

    Exit/Returns:
        Returns the number of primitives now using the material. `document` is
        MUTATED: materials, textures, images and samplers are set, and every
        primitive's `material` points at index 0.

    Module Globals:
        _METALLIC_NONE, _ALPHA_MODE_OPAQUE, _MIME_PNG, the sampler vocabulary
        read.

    Methodology:
        One material for the whole model, because every model in the pack is
        one mesh on one atlas. The material is named for the image, so a
        packed file says which atlas it was drawn from.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    name = os.path.splitext(os.path.basename(uri))[0]
    document["materials"] = [{
        "name": name,
        "alphaMode": _ALPHA_MODE_OPAQUE,
        "pbrMetallicRoughness": {
            "baseColorTexture": {"index": 0},
            "metallicFactor": _METALLIC_NONE,
            "roughnessFactor": roughness,
        },
    }]
    document["textures"] = [{"sampler": 0, "source": 0}]
    document["images"] = [{"name": name, "mimeType": _MIME_PNG, "uri": uri}]
    document["samplers"] = [{
        "magFilter": _FILTER_LINEAR,
        "minFilter": _FILTER_LINEAR_MIPMAP_LINEAR,
        "wrapS": _WRAP_REPEAT,
        "wrapT": _WRAP_REPEAT,
    }]
    wired = 0

    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            primitive["material"] = 0
            wired += 1

    return wired


def _write_source(dest_dir, document, payload, generator_suffix):
    """
    Purpose: Write one converted model as a source directory on disk.

    Entry:
        dest_dir - the directory to create. document - checked, and given its
        material unless kept as exported. payload - the BIN chunk.
        generator_suffix - appended to the exporter's generator string, naming
        the mode that wrote the source.

    Exit/Returns:
        Returns the total bytes written. The directory is created if absent
        and its scene.gltf and scene.bin are overwritten.

    Module Globals:
        _GLTF_FILENAME, _BUFFER_FILENAME read.

    Methodology:
        The BIN chunk is padded to four bytes and the buffer's byteLength is
        not, so the payload is cut back to the declared length -- the written
        file then says exactly what the document says. The layout is
        pack_model.py's: one scene.gltf naming one external buffer.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    buffer = document["buffers"][0]
    declared = buffer["byteLength"]
    buffer["uri"] = _BUFFER_FILENAME
    asset = document.setdefault("asset", {})
    asset["generator"] = asset.get("generator", "") + generator_suffix
    os.makedirs(dest_dir, exist_ok=True)
    text = json.dumps(document, indent=2)

    with open(os.path.join(dest_dir, _GLTF_FILENAME), "w",
              encoding="utf-8") as handle:
        handle.write(text)

    with open(os.path.join(dest_dir, _BUFFER_FILENAME), "wb") as handle:
        handle.write(payload[:declared])

    return len(text) + declared


# ─── Public routines ─────────────────────────────────────────────────────────

def read_glb(glb_path):
    """
    Purpose: Read one .glb into its document and buffer, checked.

    Entry:
        glb_path names a .glb. It is opened read-only and never written to.

    Exit/Returns:
        Returns (document, payload). Raises GlbError for anything this cannot
        convert, OSError when the file cannot be read.

    Module Globals:
        None.

    Methodology:
        Separate from convert() so a test can read a file without writing one.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    with open(glb_path, "rb") as handle:
        data = handle.read()

    document, payload = _split_container(data)
    _check_document(document, payload)

    return document, payload


def convert(glb_path, dest_dir, texture_path, roughness=_ROUGHNESS_DEFAULT):
    """
    Purpose: Convert one untextured .glb into a textured model source directory.

    Entry:
        glb_path names the download. dest_dir is the directory to write, which
        has to be somewhere under assets/ for pack_model.py to name a family
        for it. texture_path names the base colour image. 0 <= roughness <= 1.

    Exit/Returns:
        Returns (dest_dir, report). report holds the mesh, primitive, and node
        counts, the image uri written and the bytes written. Raises GlbError
        for a file this cannot convert.

    Module Globals:
        None.

    Methodology:
        Read and check, resolve the image, attach the material, write.

    Notes/References:
        The download and the image are never written to. Re-running produces
        the same bytes.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    document, payload = read_glb(glb_path)
    uri = _texture_uri(texture_path, dest_dir)
    primitives = _attach_material(document, uri, roughness)
    written = _write_source(dest_dir, document, payload, _GENERATOR_SUFFIX)
    report = {
        "meshes": len(document.get("meshes", [])),
        "primitives": primitives,
        "nodes": len(document.get("nodes", [])),
        "uri": uri,
        "bytes": written,
    }

    return dest_dir, report


def split_as_exported(glb_path, dest_dir):
    """
    Purpose: Split one .glb that carries its own materials into a model source
             directory, adding and replacing nothing.

    Entry:
        glb_path names the export. dest_dir is the directory to write, under
        assets/ for pack_model.py to name a family for it.

    Exit/Returns:
        Returns (dest_dir, report). report holds the mesh, material and node
        counts and the bytes written. Raises GlbError for a file whose look
        cannot be kept as it is; nothing is written in that case.

    Module Globals:
        _AS_EXPORTED_GENERATOR_SUFFIX read.

    Methodology:
        Read, check, write. The document's materials -- alpha modes, double
        sidedness, extensions -- pass through untouched.

    Notes/References:
        The export is never written to. Re-running produces the same bytes.

    Author: Nick Hobar
    Creation date: 09/13/2026
    """
    with open(glb_path, "rb") as handle:
        data = handle.read()

    document, payload = _split_container(data)
    _check_as_exported(document, payload)
    written = _write_source(
        dest_dir, document, payload, _AS_EXPORTED_GENERATOR_SUFFIX)
    report = {
        "meshes": len(document.get("meshes", [])),
        "materials": len(document["materials"]),
        "nodes": len(document.get("nodes", [])),
        "bytes": written,
    }

    return dest_dir, report


# ─── Entry point ─────────────────────────────────────────────────────────────

_USAGE = """glb_to_gltf.py -- give an untextured .glb a material, as a source dir

  glb_to_gltf.py <model.glb> <destination> --texture IMAGE [--roughness R]
  glb_to_gltf.py <model.glb> <destination> --as-exported

Writes <destination>/scene.gltf and scene.bin -- an ordinary model source
directory, which assets/pack_model.py then packs into the served .glb like any
download. The destination has to be under assets/, because the first path
component below it is what names the served family.

--texture names the base colour image, as a path from here. It is referenced
from the scene.gltf, not copied. --roughness defaults to 0.7.

--as-exported keeps the materials a .glb already carries (a Blender export,
say) and adds nothing. It refuses a .glb with no materials or with images.

  ../evenv/Scripts/python.exe assets/glb_to_gltf.py
      assets/items/food/kyle_fuji_food/Models/egg.glb
      assets/items/food/kyle_fuji_food/egg
      --texture assets/items/food/kyle_fuji_food/Textures/T_protein_atlas_diffuse.png
"""


def _parse(arguments):
    """
    Purpose: Split the command line into positionals and options.

    Entry:
        arguments is sys.argv[1:].

    Exit/Returns:
        Returns (glb_path, dest_dir, texture_path, roughness, as_exported).
        texture_path is None exactly when as_exported is True. Raises GlbError
        for a missing positional, neither or both of --texture and
        --as-exported, an option with no value or a roughness that is not a
        number.

    Module Globals:
        _TEXTURE_OPTION, _ROUGHNESS_OPTION, _AS_EXPORTED_OPTION,
        _POSITIONAL_ARGUMENTS read.

    Methodology:
        Hand-parsed rather than argparse, matching pack_model.py and
        fbx_to_gltf.py.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    options = {_TEXTURE_OPTION: None, _ROUGHNESS_OPTION: None}
    positionals = []
    as_exported = False
    index = 0

    while index < len(arguments):
        argument = arguments[index]

        if argument == _AS_EXPORTED_OPTION:
            as_exported = True
            index += 1
            continue

        if argument in options:
            if index + 1 >= len(arguments):
                raise GlbError("%s needs a value" % argument)

            options[argument] = arguments[index + 1]
            index += 2
            continue

        positionals.append(argument)
        index += 1

    if len(positionals) != _POSITIONAL_ARGUMENTS:
        raise GlbError("expected a .glb and a destination")

    texture_path = options[_TEXTURE_OPTION]
    has_texture = texture_path is not None

    if has_texture == as_exported:
        raise GlbError("name exactly one of %s or %s"
                       % (_TEXTURE_OPTION, _AS_EXPORTED_OPTION))

    roughness = _parse_roughness(options[_ROUGHNESS_OPTION], as_exported)

    return positionals[0], positionals[1], texture_path, roughness, as_exported


def _parse_roughness(text, as_exported):
    """
    Purpose: Read the --roughness value, if one was given.

    Entry:
        text is the option's value or None. as_exported is the mode flag.

    Exit/Returns:
        Returns the roughness as a float, the default when text is None.
        Raises GlbError for a value that is not a number, or for any value
        given alongside --as-exported, which writes no material to apply it to.

    Module Globals:
        _ROUGHNESS_OPTION, _AS_EXPORTED_OPTION, _ROUGHNESS_DEFAULT read.

    Author: Nick Hobar
    Creation date: 09/13/2026
    """
    if text is None:
        return _ROUGHNESS_DEFAULT

    if as_exported:
        raise GlbError("%s sets the material this adds, and %s adds none"
                       % (_ROUGHNESS_OPTION, _AS_EXPORTED_OPTION))

    try:
        roughness = float(text)
    except ValueError:
        raise GlbError("%s must be a number" % _ROUGHNESS_OPTION)

    return roughness


def main(argv):
    """
    Purpose: Run the converter from the command line.

    Entry:
        argv - sys.argv.

    Exit/Returns:
        Returns a process exit status. Prints what was written on stdout.

    Module Globals:
        _USAGE read.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    if not argv[1:]:
        print(_USAGE)

        return 1

    try:
        glb_path, dest_dir, texture_path, roughness, as_exported = _parse(
            argv[1:])

        if as_exported:
            dest_dir, report = split_as_exported(glb_path, dest_dir)
            summary = ("  %(meshes)d mesh(es), %(materials)d material(s) kept "
                       "as exported, %(nodes)d node(s)" % report)
        else:
            dest_dir, report = convert(
                glb_path, dest_dir, texture_path, roughness)
            summary = ("  %(meshes)d mesh(es), %(primitives)d primitive(s), "
                       "%(nodes)d node(s); base colour %(uri)s" % report)
    except (GlbError, OSError) as problem:
        print("glb_to_gltf: %s" % problem)

        return 1

    print("%s -> %s" % (glb_path, dest_dir))
    print(summary)
    print("  %(bytes)d bytes written" % report)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
