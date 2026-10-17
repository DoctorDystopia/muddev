"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/16/2026
Description: The two lists of names that the server reads from the figure
             files: the body types and the named colors.

             The figure workbench writes the rigs and the palette into
             blackout/assets/figure/. A body type is the key of a rig, so the
             file name of a rig is the body type. A named color is a key of
             the `colors` table of the palette. This module reads each list on
             each call. The callers are a moderator action and a test, so no
             cache is necessary, and a save in the workbench reaches the next
             call.
"""

import json
import os

from assets.pipeline import paths


# ─── Private constant definitions ────────────────────────────────────────────

# The table of the palette file that holds the named colors.
_COLORS_KEY: str = "colors"


# ─── Public routines ─────────────────────────────────────────────────────────

def body_types() -> list:
    """
    Purpose: Give each body type that has a rig.

    Entry:
        None.

    Exit/Returns:
        Returns a sorted list of body type keys. An empty list when the rig
        directory is not there.

    Module Globals:
        paths.FIGURE_RIGS_DIR and paths.FIGURE_FILE_SUFFIX read.

    Methodology:
        The rig file name is the body type: figure/rigs/<body_type>.json.

    Author: Nick Hobar
    Creation date: 10/16/2026
    """
    suffix = paths.FIGURE_FILE_SUFFIX

    if not os.path.isdir(paths.FIGURE_RIGS_DIR):
        return []

    names = os.listdir(paths.FIGURE_RIGS_DIR)
    found = sorted(name[:-len(suffix)] for name in names if name.endswith(suffix))

    return found


def named_colors() -> list:
    """
    Purpose: Give each named color of the palette.

    Entry:
        None.

    Exit/Returns:
        Returns a sorted list of named colors. An empty list when the palette
        file is not there or does not read.

    Module Globals:
        paths.FIGURE_PALETTE_PATH and _COLORS_KEY read.

    Methodology:
        A palette that does not read gives no color. The figure workbench
        and test_figure_files.py report such a file. Here, the effect is only
        that a moderator cannot set a color until the file reads again.

    Author: Nick Hobar
    Creation date: 10/16/2026
    """
    try:
        with open(paths.FIGURE_PALETTE_PATH, encoding="utf-8") as handle:
            palette = json.load(handle)
    except (OSError, ValueError):
        return []

    colors = palette.get(_COLORS_KEY, {}) if isinstance(palette, dict) else {}
    found = sorted(colors) if isinstance(colors, dict) else []

    return found
