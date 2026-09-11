"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Converts an FBX download into the source directory shape
             pack_model.py already understands.

             THE PROBLEM THIS FIXES. Every download served so far arrived as
             scene.gltf + scene.bin + textures/, which is what pack_model.py
             reads. Not everything ships that way: itch.io asset packs are
             routinely .blend + .fbx + a loose texture, and the PSX skeleton
             this was written for is exactly that. There was no way to serve
             one short of opening Blender by hand, exporting, and leaving no
             record of which settings produced the file in the tree.

             It is the same kind of step split_tileset.py is, and for the same
             reason: it manufactures the shape the pipeline already takes,
             rather than teaching the pipeline a second shape. What it writes
             is an ordinary source directory, so every step downstream -- the
             manifest row, the pack, the credit -- is unchanged.

             WHY IT RE-EXECS ITSELF. The conversion has to happen inside
             Blender, whose Python is its own interpreter with `bpy` in it and
             nothing of this repo's virtualenv. So this file is run twice: once
             by the operator under evenv, where it finds Blender and shells
             out, and once by Blender, where `bpy` imports and the work
             happens. One file rather than two because the settings that
             produced a served model and the command that produced them are
             the same fact, and splitting them is how they drift.

             THE MATERIAL IS REBUILT, NOT EDITED, when `--texture` names one.
             An FBX that carries UVs and no texture reference is the normal
             case for a pack whose art is a palette PNG sitting beside the
             mesh -- the skeleton's material arrived as flat 0.8 grey with the
             128-square atlas unreferenced, and the .blend beside it wires that
             atlas through an EMISSION shader against a different colour
             variant. Neither is a material worth preserving, so the texture is
             wired into a fresh Principled BSDF: metallic 0, roughness 1, and
             NEAREST sampling, without which a 128-square pixel-art atlas is
             drawn blurred. Omit `--texture` and the material is exported
             exactly as it arrived.

             The download itself is never written to -- only the three
             generated paths (scene.gltf, scene.bin, textures/) are, in the
             directory named as the destination. Re-running overwrites those
             and nothing else.

             Pure file transformation. Importing this module touches no
             database, boots no Evennia, and starts no Blender: everything that
             does anything is behind the __main__ guard below.

             Usage:
                 ../evenv/Scripts/python.exe assets/fbx_to_gltf.py
                     assets/npcs/psx_low_poly_skeleton/skeleton.fbx
                     assets/npcs/psx_low_poly_skeleton
                     --texture base.png
"""

import glob
import os
import subprocess
import sys


# ─── Private constant definitions ────────────────────────────────────────────

_GLTF_FILENAME = "scene.gltf"
_TEXTURES_DIRNAME = "textures"

# Where Blender's exporter is told to put extracted images, relative to the
# .gltf. Matches what a Sketchfab download carries, which is what pack_model.py
# resamples out of.
_TEXTURE_DIR_OPTION = _TEXTURES_DIRNAME

# The environment variable that names blender.exe, for an install this cannot
# find. Checked before the search below, so an operator is never stuck.
_BLENDER_ENV_VAR = "BLENDER_EXE"

# Where Blender installs itself on the platforms this repo is developed on.
# Globbed rather than pinned to a version, because the version in the path
# changes with every upgrade and a pinned one turns a working tool into a
# support question. Newest match wins.
_BLENDER_SEARCH_GLOBS = (
    r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
    r"C:\Program Files (x86)\Blender Foundation\Blender *\blender.exe",
    "/usr/bin/blender",
    "/usr/local/bin/blender",
    "/Applications/Blender.app/Contents/MacOS/Blender",
)

# Blender's own flags. --factory-startup is the load-bearing one: it ignores
# whatever add-ons and unit settings the operator's Blender happens to carry,
# so two people converting the same download get the same bytes. The FBX and
# glTF add-ons are core extensions and survive it.
_BLENDER_FLAGS = ("--background", "--factory-startup", "--python")

# Everything after this on Blender's command line is the script's, not
# Blender's. Blender's own convention, not ours.
_ARGUMENT_SEPARATOR = "--"

# Pixel art sampled with anything smoother than this is pixel art nobody can
# see. Blender's name for NEAREST, which is what the glTF exporter writes into
# the sampler's magFilter.
_PIXEL_ART_INTERPOLATION = "Closest"

# A non-metal that scatters in every direction, which is what a painted or
# palette-mapped surface is. The one honest default for art that carries a
# base colour and nothing else.
_MATERIAL_METALLIC = 0.0
_MATERIAL_ROUGHNESS = 1.0

_BASE_COLOR_INPUT = "Base Color"
_METALLIC_INPUT = "Metallic"
_ROUGHNESS_INPUT = "Roughness"
_SURFACE_INPUT = "Surface"
_COLOR_OUTPUT = "Color"
_SHADER_OUTPUT = "BSDF"

_OUTPUT_NODE = "ShaderNodeOutputMaterial"
_PRINCIPLED_NODE = "ShaderNodeBsdfPrincipled"
_IMAGE_NODE = "ShaderNodeTexImage"

_TEXTURE_OPTION = "--texture"
_BLENDER_OPTION = "--blender"

# What the two halves agree to pass across Blender's command line: the source
# FBX, the scene.gltf to write, and the texture name ("" for none).
_BLENDER_ARGUMENT_COUNT = 3

# <fbx> and <destination>. Everything else is an option.
_POSITIONAL_COUNT = 2

# assets/fbx_to_gltf.py -> blackout/
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConvertError(RuntimeError):
    """Raised when a download is not a shape this converter can read."""


def find_blender(override=None):
    """
    Purpose: Name the blender.exe this conversion should run inside.

    Entry:
        override is an explicit path or None.

    Exit/Returns:
        Returns an absolute path to an executable. Raises ConvertError when
        nothing was found, naming the environment variable that fixes it.

    Module Globals:
        _BLENDER_ENV_VAR, _BLENDER_SEARCH_GLOBS read.

    Methodology:
        Three sources in falling order of deliberateness: the argument, the
        environment, then the search. The search is last because a machine
        with two Blenders installed should be told which one, not guessed at,
        and sorting the matches puts the newest version first so the guess is
        at least the defensible one.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    if override:
        return override

    from_environment = os.environ.get(_BLENDER_ENV_VAR, "")

    if from_environment:
        return from_environment

    for pattern in _BLENDER_SEARCH_GLOBS:
        matches = sorted(glob.glob(pattern), reverse=True)

        if matches:
            return matches[0]

    raise ConvertError(
        "no Blender found; set %s to blender.exe" % _BLENDER_ENV_VAR)


def convert(fbx_path, destination_dir, texture=None, blender=None):
    """
    Purpose: Run one FBX through Blender into a packable source directory.

    Entry:
        fbx_path names an existing .fbx. destination_dir is where the three
        generated paths are written; it is created when absent. texture names
        an image file RELATIVE TO THE FBX, or None to keep the material as it
        arrived. Both paths may be relative to the game dir.

    Exit/Returns:
        Returns the absolute path of the scene.gltf written. Raises
        ConvertError when the source is missing, no Blender was found, or
        Blender exited non-zero -- its output having already been printed,
        because a conversion failure is a Blender message and paraphrasing it
        helps nobody.

    Module Globals:
        _BLENDER_FLAGS, _ARGUMENT_SEPARATOR, _GLTF_FILENAME, _GAME_DIR read.

    Methodology:
        The child is handed THIS file, which is what makes the two halves one
        file. Blender is run with its output inherited rather than captured:
        the importer reports the FBX version and the exporter reports what it
        extracted, and both are worth seeing when a download turns out to be a
        shape nobody expected.

    Notes/References:
        assets/README.md, "Adding a model", for what happens after this.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    source = os.path.join(_GAME_DIR, fbx_path)
    exists = os.path.isfile(source)

    if not exists:
        raise ConvertError("no such FBX: %s" % source)

    destination = os.path.join(_GAME_DIR, destination_dir)
    os.makedirs(destination, exist_ok=True)
    written = os.path.join(destination, _GLTF_FILENAME)

    command = [find_blender(blender)]
    command.extend(_BLENDER_FLAGS)
    command.append(os.path.abspath(__file__))
    command.append(_ARGUMENT_SEPARATOR)
    command.extend([source, written, texture or ""])

    completed = subprocess.run(command)

    if completed.returncode != 0:
        raise ConvertError(
            "Blender exited %d converting %s" % (completed.returncode, source))

    return written


# ─── The Blender half ────────────────────────────────────────────────────────
#
# Everything below runs inside Blender's interpreter, where `bpy` exists and
# nothing of this repo's virtualenv does. Keep it importing nothing from here.


def _wire_base_colour(material, image_path, bpy):
    """
    Purpose: Replace one material with a Principled BSDF sampling an image.

    Entry:
        material is a Blender material. image_path names an existing image.
        bpy is the module, passed rather than imported so this routine stays
        readable from outside Blender.

    Exit/Returns:
        No return. Mutates the material's node tree in memory only; nothing is
        written back to the download.

    Module Globals:
        _PIXEL_ART_INTERPOLATION, _MATERIAL_METALLIC, _MATERIAL_ROUGHNESS and
        the node/socket name constants read.

    Methodology:
        Cleared and rebuilt rather than patched. A patch has to find the
        shader node an unknown exporter happened to write and guess which of
        its inputs is the base colour; the graph this needs is three nodes, so
        building it outright is both shorter and the same every time.

        NEAREST sampling is the point of the routine as much as the texture
        is. The glTF exporter turns Blender's `Closest` into the sampler's
        NEAREST magFilter, and a 128-square palette atlas filtered any other
        way arrives as mud.

    Notes/References:
        See the module docstring for why the skeleton's own material and the
        .blend's emission graph are both discarded rather than converted.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    tree = material.node_tree
    tree.nodes.clear()

    output = tree.nodes.new(_OUTPUT_NODE)
    shader = tree.nodes.new(_PRINCIPLED_NODE)
    texture = tree.nodes.new(_IMAGE_NODE)

    texture.image = bpy.data.images.load(image_path)
    texture.interpolation = _PIXEL_ART_INTERPOLATION

    shader.inputs[_METALLIC_INPUT].default_value = _MATERIAL_METALLIC
    shader.inputs[_ROUGHNESS_INPUT].default_value = _MATERIAL_ROUGHNESS

    tree.links.new(texture.outputs[_COLOR_OUTPUT],
                   shader.inputs[_BASE_COLOR_INPUT])
    tree.links.new(shader.outputs[_SHADER_OUTPUT],
                   output.inputs[_SURFACE_INPUT])


def _convert_inside_blender(source, written, texture):
    """
    Purpose: Import one FBX and write the glTF source directory beside it.

    Entry:
        Running inside Blender. source is an absolute .fbx path, written is
        the absolute scene.gltf to produce, texture is a filename relative to
        the FBX or "" to keep the material as imported.

    Exit/Returns:
        No return. Writes scene.gltf, scene.bin and textures/ at `written`.
        Raises ConvertError when `texture` names a file that is not there.

    Module Globals:
        _TEXTURE_DIR_OPTION read.

    Methodology:
        The scene is emptied first, so the file produced depends on the
        arguments and not on whatever Blender opened with.

        Imported objects are left alone otherwise -- the empties an FBX
        carries alongside its mesh cost two JSON rows and may be carrying the
        transform the mesh is parented under, and dropping them to tidy the
        output is how a model comes out somewhere other than where it was
        authored.

        Animations are not exported. Nothing in the client plays one, and the
        floating eye already ships five nobody has ever used.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=source)

    if texture:
        image_path = os.path.join(os.path.dirname(source), texture)
        exists = os.path.isfile(image_path)

        if not exists:
            raise ConvertError("no such texture: %s" % image_path)

        for material in bpy.data.materials:
            _wire_base_colour(material, image_path, bpy)

    os.makedirs(os.path.dirname(written), exist_ok=True)

    bpy.ops.export_scene.gltf(
        filepath=written,
        export_format="GLTF_SEPARATE",
        export_texture_dir=_TEXTURE_DIR_OPTION,
        export_apply=True,
        export_animations=False,
    )


def _blender_arguments():
    """
    Purpose: Read this script's own arguments off Blender's command line.

    Entry:
        Running inside Blender, which was given `-- source written texture`.

    Exit/Returns:
        Returns (source, written, texture). Raises ConvertError when the
        separator or the three values are not there, which means this file was
        run inside Blender by hand rather than through `convert`.

    Module Globals:
        _ARGUMENT_SEPARATOR read.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    present = _ARGUMENT_SEPARATOR in sys.argv

    if not present:
        raise ConvertError("run this through assets/fbx_to_gltf.py, not "
                           "directly inside Blender")

    arguments = sys.argv[sys.argv.index(_ARGUMENT_SEPARATOR) + 1:]
    count = len(arguments)

    if count != _BLENDER_ARGUMENT_COUNT:
        raise ConvertError("expected %d arguments after %s, got %d"
                           % (_BLENDER_ARGUMENT_COUNT, _ARGUMENT_SEPARATOR,
                              count))

    return arguments[0], arguments[1], arguments[2]


_USAGE = """fbx_to_gltf.py -- turn an FBX download into a packable source dir

  fbx_to_gltf.py <fbx> <destination> [--texture NAME] [--blender PATH]

Writes scene.gltf, scene.bin and textures/ into <destination>, which is then
an ordinary source directory: add a row to assets/model_manifest.json, pack it
with assets/pack_model.py, credit it in models/CREDITS.md.

--texture names an image BESIDE THE FBX to wire in as the base colour, for a
download whose mesh carries UVs but no material reference. Omit it to export
the material as it arrived.

Needs Blender. Set BLENDER_EXE if it is installed somewhere unusual."""


def _parse(arguments):
    """
    Purpose: Turn the operator's command line into convert()'s arguments.

    Entry:
        arguments is sys.argv[1:].

    Exit/Returns:
        Returns (fbx_path, destination_dir, texture, blender), the last two
        being None when not given. Raises ConvertError on a shape that is not
        two positionals and known options.

    Module Globals:
        _TEXTURE_OPTION, _BLENDER_OPTION read.

    Methodology:
        Hand-parsed rather than argparse, matching pack_model.py and
        split_tileset.py: three build tools with three argument conventions is
        worse than three short parsers.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    options = {_TEXTURE_OPTION: None, _BLENDER_OPTION: None}
    positional = []
    total = len(arguments)
    index = 0

    while index < total:
        token = arguments[index]
        value_index = index + 1

        if token in options:
            if value_index >= total:
                raise ConvertError("%s needs a value" % token)

            options[token] = arguments[value_index]
            index += 2
            continue

        positional.append(token)
        index += 1

    given = len(positional)

    if given != _POSITIONAL_COUNT:
        raise ConvertError("expected <fbx> and <destination>, got %d" % given)

    return (positional[0], positional[1],
            options[_TEXTURE_OPTION], options[_BLENDER_OPTION])


if __name__ == "__main__":
    # Which half is running is decided by whether `bpy` imports, not by a flag.
    # A flag is something the parent has to remember to pass and the child has
    # to be trusted to honour; this cannot be got wrong.
    try:
        import bpy                      # noqa: F401  -- presence is the test

        inside_blender = True
    except ImportError:
        inside_blender = False

    if inside_blender:
        try:
            _source, _written, _texture = _blender_arguments()
            _convert_inside_blender(_source, _written, _texture)
        except ConvertError as failure:
            print("convert failed: %s" % failure)
            sys.exit(1)

        sys.exit(0)

    if not sys.argv[1:]:
        print(_USAGE)
        sys.exit(1)

    try:
        _fbx, _destination, _texture, _blender = _parse(sys.argv[1:])
        _written = convert(_fbx, _destination, _texture, _blender)
    except (ConvertError, OSError) as failure:
        print("convert failed: %s" % failure)
        sys.exit(1)

    print("wrote %s" % _written)
    print("  now: add a row to assets/model_manifest.json and pack it")
