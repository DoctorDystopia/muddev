"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/25/2026
Description: Runs INSIDE Blender. Reads one MagicaVoxel .vox file, and writes
             it as one .glb.

             Never import this module in ordinary Python: `bpy` exists only
             inside Blender. assets/pipeline/blender.py starts Blender with
             this file as its script for a .vox file (FORMAT_SCRIPTS):

                 blender --background --factory-startup --python
                     blender_vox.py -- <input.vox> <output.glb>

             THE ADD-ON. Blender has no .vox importer of its own. The
             extension "MagicaVoxel VOX format" (blender_magicavoxel, by
             AstrorEnales, on extensions.blender.org) gives one. The flag
             --factory-startup turns every add-on off. Thus, this script
             turns that one on by its name, for this run only. Each machine
             that builds a .vox model needs the extension.

             THE PIN. The bytes of the model depend on the version of the
             add-on, and the lock file cannot see that version. Thus, this
             script refuses each version but _ADDON_VERSION. The text of this
             script feeds the input digest of each .vox model. A new pin thus
             makes each .vox model stale, and the next build makes it again.

             THE OPTIONS, fixed so that two machines give the same file:
               - Greedy watertight meshing. It joins the faces of one colour
                 on one plane, with no T-joint, so no crack shows. The
                 VoxEdit priest has 10,560 triangles as plain quads, and
                 3,194 with this meshing (10/25/2026).
               - The palette as one 256 x 1 texture.
               - 0.1 m for one voxel. The client puts each model in the
                 unit box.
               - Each model of the file is one node, in the place that the
                 scene graph of the file gives. A record can take one node.
               - No camera, and no material property (glass, glow, metal).

             THE AXES. The add-on keeps the axes of the file, and the glTF
             exporter turns Blender's Z-up into Y-up. The facing depends on
             the tool that made the file: the VoxEdit priest faces -Z. Give a
             model that faces the wrong way a `rotate` in its [fix].
"""

import os
import sys


# ─── Private constant definitions ────────────────────────────────────────────

# Everything after this on Blender's command line belongs to the script.
_ARGUMENT_SEPARATOR = "--"
_EXPECTED_ARGUMENTS = 2
_EXPORT_FORMAT = "GLB"

# The add-on: its module name, the prefix of an extension module, and the
# one version that this script accepts.
_ADDON_NAME = "blender_magicavoxel"
_EXTENSION_PREFIX = "bl_ext"
_ADDON_VERSION = (1, 6, 0)
_ADDON_PAGE = "https://github.com/AstrorEnales/blender_magicavoxel"

_IMPORT_OPTIONS = {
    "meshing_type": "GREEDY_WATERTIGHT",
    "material_mode": "MAT_AS_TEX",
    "voxel_size": 0.1,
    "import_cameras": False,
    "import_hierarchy": False,
    "import_material_props": False,
    "join_models": False,
}


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
    Creation date: 10/25/2026
    """
    if _ARGUMENT_SEPARATOR not in sys.argv:
        raise SystemExit("blender_vox: run me through assets/pipeline")

    start = sys.argv.index(_ARGUMENT_SEPARATOR) + 1
    mine = sys.argv[start:]

    if len(mine) != _EXPECTED_ARGUMENTS:
        raise SystemExit("blender_vox: want <input.vox> <output.glb>")

    return mine[0], mine[1]


def _enable_addon(bpy, addon_utils):
    """
    Purpose: Turn the .vox add-on on, for this run only.

    Entry:
        Running inside Blender, after a factory reset.

    Exit/Returns:
        Returns the module of the add-on. Raises SystemExit that says
        where to get it, when no repository holds it.

    Module Globals:
        _ADDON_NAME, _EXTENSION_PREFIX, _ADDON_PAGE read.

    Methodology:
        1. Try the add-on as an extension of each repository.
        2. Try it as a legacy add-on.
        3. Take the first name that turns on.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    repositories = bpy.context.preferences.extensions.repos
    names = ["%s.%s.%s" % (_EXTENSION_PREFIX, repository.module, _ADDON_NAME)
             for repository in repositories]
    names.append(_ADDON_NAME)

    # A repository without the add-on is no error here. The next one can
    # hold it.
    for name in names:
        module = addon_utils.enable(name, default_set=False,
                                    handle_error=lambda _problem: None)

        if module is not None:
            return module

    raise SystemExit("blender_vox: Blender has no add-on %s. In Blender, "
                     "install the extension 'MagicaVoxel VOX format' from "
                     "Get Extensions. Its page: %s" % (_ADDON_NAME,
                                                       _ADDON_PAGE))


def _check_version(addon_utils, module):
    """
    Purpose: Refuse each version of the add-on but the pinned one.

    Entry:
        module is the add-on, turned on.

    Exit/Returns:
        Returns None. Raises SystemExit that names both versions.

    Module Globals:
        _ADDON_VERSION read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    info = addon_utils.module_bl_info(module)
    found = tuple(info.get("version", ()))

    if found != _ADDON_VERSION:
        raise SystemExit("blender_vox: the build pins the add-on at %s, and "
                         "Blender has %s. Install that version, or change "
                         "_ADDON_VERSION in blender_vox.py. A new pin builds "
                         "each .vox model again." % (_ADDON_VERSION, found))


# ─── Public routines ─────────────────────────────────────────────────────────

def main():
    """
    Purpose: Convert one .vox file to .glb.

    Entry:
        Running inside Blender, with `-- <input.vox> <output.glb>`.

    Exit/Returns:
        Returns None. Writes the .glb and its directory.

    Module Globals:
        _IMPORT_OPTIONS, _EXPORT_FORMAT read.

    Methodology:
        1. Start from an empty factory scene. The factory scene has a cube.
        2. Turn the add-on on, and check its version.
        3. Import the file with the fixed options.
        4. Export it with the options of blender_ingest.py.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    import addon_utils
    import bpy

    input_path, output_path = _arguments()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    module = _enable_addon(bpy, addon_utils)
    _check_version(addon_utils, module)
    bpy.ops.import_scene.vox(filepath=input_path, **_IMPORT_OPTIONS)
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
