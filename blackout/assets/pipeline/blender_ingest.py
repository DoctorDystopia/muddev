"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Runs INSIDE Blender. Reads one download in any format that
             Blender can import, and writes it as one .glb.

             Never import this module in ordinary Python: `bpy` exists only
             inside Blender. assets/pipeline/blender.py starts Blender with
             this file as its script:

                 blender --background --factory-startup --python
                     blender_ingest.py -- <input> <output.glb>

             This step does ONE thing: it changes the format. Every correction
             (a texture, a rotation, a filter) happens after it, in the Node
             step, the same way for a glTF download and for an FBX download.
             Thus, one model record means the same thing whatever format its
             source arrived in.

             --factory-startup is important. It ignores the add-ons and unit
             settings of the operator's own Blender, so two machines give the
             same file.
"""

import os
import sys


# ─── Private constant definitions ────────────────────────────────────────────

# Everything after this on Blender's command line belongs to the script.
_ARGUMENT_SEPARATOR = "--"
_EXPECTED_ARGUMENTS = 2
_EXPORT_FORMAT = "GLB"

# Blender's importer for each file suffix. A suffix not here is refused.
_IMPORTERS = {
    ".fbx": ("import_scene", "fbx"),
    ".obj": ("wm", "obj_import"),
    ".dae": ("wm", "collada_import"),
    ".stl": ("wm", "stl_import"),
    ".ply": ("wm", "ply_import"),
    ".usd": ("wm", "usd_import"),
    ".usdc": ("wm", "usd_import"),
    ".usdz": ("wm", "usd_import"),
    ".gltf": ("import_scene", "gltf"),
    ".glb": ("import_scene", "gltf"),
}
_BLEND_SUFFIX = ".blend"


# ─── Private helper routines ─────────────────────────────────────────────────

def _arguments():
    """
    Purpose: Read this script's own arguments off Blender's command line.

    Entry:
        Blender was given `-- <input> <output>`.

    Exit/Returns:
        Returns (input_path, output_path). Raises SystemExit with a message
        when the separator or the two values are not there.

    Module Globals:
        _ARGUMENT_SEPARATOR, _EXPECTED_ARGUMENTS read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    if _ARGUMENT_SEPARATOR not in sys.argv:
        raise SystemExit("blender_ingest: run me through assets/pipeline")

    start = sys.argv.index(_ARGUMENT_SEPARATOR) + 1
    mine = sys.argv[start:]

    if len(mine) != _EXPECTED_ARGUMENTS:
        raise SystemExit("blender_ingest: want <input> <output.glb>")

    return mine[0], mine[1]


def _import(bpy, input_path):
    """
    Purpose: Load one file into an empty Blender scene.

    Entry:
        input_path names an existing file. Its suffix is in _IMPORTERS or is
        .blend.

    Exit/Returns:
        Returns None. The scene holds the file's objects. Raises SystemExit
        for a suffix that Blender cannot import here.

    Module Globals:
        _IMPORTERS, _BLEND_SUFFIX read.

    Methodology:
        1. Open a .blend as the scene itself.
        2. For any other suffix, start from an empty factory scene and call
           its importer.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    suffix = os.path.splitext(input_path)[1].lower()

    if suffix == _BLEND_SUFFIX:
        bpy.ops.wm.open_mainfile(filepath=input_path)
        return

    if suffix not in _IMPORTERS:
        raise SystemExit("blender_ingest: no importer for %s" % suffix)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    group, name = _IMPORTERS[suffix]
    operator = getattr(getattr(bpy.ops, group), name)
    operator(filepath=input_path)


def main():
    """
    Purpose: Convert one file to .glb.

    Entry:
        Running inside Blender, with `-- <input> <output.glb>`.

    Exit/Returns:
        Returns None. Writes the .glb and its directory.

    Module Globals:
        _EXPORT_FORMAT read.

    Methodology:
        export_apply applies modifiers, so the served mesh is the one that
        the author saw. Cameras and lights are not exported: a model is a
        mesh, not a scene.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    import bpy

    input_path, output_path = _arguments()
    _import(bpy, input_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format=_EXPORT_FORMAT,
        export_apply=True,
        export_cameras=False,
        export_lights=False,
    )


if __name__ == "__main__":
    main()
