"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Where every part of the model pipeline lives on disk. The one
             owner of those paths.

             Each path is absolute and comes from this file's own location,
             so a command gives the same answer from any working directory.
"""

import os


# ─── Public constant definitions ─────────────────────────────────────────────

# assets/pipeline/paths.py -> assets/
ASSETS_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# assets/ -> blackout/
GAME_DIR: str = os.path.dirname(ASSETS_DIR)

# One directory for each download, exactly as it arrived.
SOURCES_DIR: str = os.path.join(ASSETS_DIR, "sources")

# One model record for each served model: models/<family>/<asset_key>.toml.
MODELS_DIR: str = os.path.join(ASSETS_DIR, "models")

# Scratch space for the build. Gitignored. Safe to delete at any time.
BUILD_DIR: str = os.path.join(ASSETS_DIR, ".build")

# The Node half of the build, and the packages it needs.
NODE_SCRIPT: str = os.path.join(ASSETS_DIR, "pipeline", "build_model.mjs")
NODE_MODULES_DIR: str = os.path.join(ASSETS_DIR, "node_modules")

# The script that runs INSIDE Blender. It never runs in this Python.
BLENDER_SCRIPT: str = os.path.join(ASSETS_DIR, "pipeline", "blender_ingest.py")

# The served tree. Evennia serves it in development, and publish.sh copies it
# to R2 for the public site.
SERVED_DIR: str = os.path.join(
    GAME_DIR, "web", "static", "webclient", "models")
CLIENT_MANIFEST_PATH: str = os.path.join(SERVED_DIR, "manifest.json")
CREDITS_MARKDOWN_PATH: str = os.path.join(SERVED_DIR, "CREDITS.md")
CREDITS_JSON_PATH: str = os.path.join(SERVED_DIR, "credits.json")

# The file name of a source record, inside each source directory.
SOURCE_RECORD_NAME: str = "source.toml"

# The suffix of a model record, and of a served model.
MODEL_RECORD_SUFFIX: str = ".toml"
SERVED_SUFFIX: str = ".glb"


# ─── Public routines ─────────────────────────────────────────────────────────

def served_relative(family: str, asset_key: str) -> str:
    """
    Purpose: Name one served model, relative to the served tree.

    Entry:
        family and asset_key are non-empty.

    Exit/Returns:
        Returns "family/asset_key.glb", with a forward slash on every
        platform. The client manifest stores this form.

    Module Globals:
        SERVED_SUFFIX read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    return "%s/%s%s" % (family, asset_key, SERVED_SUFFIX)


def served_path(family: str, asset_key: str) -> str:
    """
    Purpose: Give the absolute path of one served model.

    Entry:
        family and asset_key are non-empty.

    Exit/Returns:
        Returns the path under SERVED_DIR. The file does not need to exist.

    Module Globals:
        SERVED_DIR, SERVED_SUFFIX read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    filename = asset_key + SERVED_SUFFIX

    return os.path.join(SERVED_DIR, family, filename)
