"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Find Blender and run blender_ingest.py in it.

             Only the build calls this, and only for a source file that is not
             glTF (an FBX, an OBJ, a .blend). A glTF download never starts
             Blender: the Node step reads it directly, with no round trip that
             could change its materials.

             Set BLENDER_EXE when Blender is installed in an unusual place.
"""

import glob
import os
import subprocess

from assets.pipeline import paths


# ─── Public constant definitions ─────────────────────────────────────────────

# The suffixes that glTF Transform reads directly. Every other suffix goes
# through Blender first.
GLTF_SUFFIXES: tuple = (".gltf", ".glb")


class BlenderError(RuntimeError):
    """Blender is not there, or the conversion failed."""


# ─── Private constant definitions ────────────────────────────────────────────

_BLENDER_ENV_VAR: str = "BLENDER_EXE"

# Where Blender installs itself. Globbed, not pinned to a version, because the
# version is in the path. The newest match wins.
_BLENDER_SEARCH_GLOBS: tuple = (
    r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
    r"C:\Program Files (x86)\Blender Foundation\Blender *\blender.exe",
    "/usr/bin/blender",
    "/usr/local/bin/blender",
    "/Applications/Blender.app/Contents/MacOS/Blender",
)
_BLENDER_FLAGS: tuple = ("--background", "--factory-startup", "--python")
_ARGUMENT_SEPARATOR: str = "--"
_TIMEOUT_SECONDS: int = 300


# ─── Public routines ─────────────────────────────────────────────────────────

def find_blender() -> str:
    """
    Purpose: Find the Blender executable.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the path of the executable. Raises BlenderError when neither
        BLENDER_EXE nor a standard install gives one.

    Module Globals:
        _BLENDER_ENV_VAR, _BLENDER_SEARCH_GLOBS read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    configured = os.environ.get(_BLENDER_ENV_VAR, "")

    if configured and os.path.isfile(configured):
        return configured

    found = []

    for pattern in _BLENDER_SEARCH_GLOBS:
        matches = glob.glob(pattern)
        found.extend(matches)

    if not found:
        raise BlenderError("Blender is not installed where I looked. Set %s"
                           % _BLENDER_ENV_VAR)

    newest = sorted(found)[-1]

    return newest


def to_glb(input_path: str, output_path: str) -> str:
    """
    Purpose: Convert one non-glTF file to .glb, in Blender.

    Entry:
        input_path names an existing file. output_path is where to write.

    Exit/Returns:
        Returns output_path. Raises BlenderError with Blender's last output
        lines when the conversion fails or writes nothing.

    Module Globals:
        paths.BLENDER_SCRIPT, _BLENDER_FLAGS, _ARGUMENT_SEPARATOR,
        _TIMEOUT_SECONDS read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    executable = find_blender()
    command = [executable, *_BLENDER_FLAGS, paths.BLENDER_SCRIPT,
               _ARGUMENT_SEPARATOR, input_path, output_path]
    finished = subprocess.run(command, capture_output=True, text=True,
                              timeout=_TIMEOUT_SECONDS, check=False)
    written = os.path.isfile(output_path)

    if finished.returncode != 0 or not written:
        tail = (finished.stdout + finished.stderr).strip().splitlines()[-8:]
        raise BlenderError("Blender could not convert %s:\n  %s"
                           % (input_path, "\n  ".join(tail)))

    return output_path
