"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/21/2026
Description: The items that an item spawn may name, and the item list file
             of the terrain editor.

             An item spawn names an ItemDef key in the `spawn` of its chunk
             object (Nick, 10/21/2026). The terrain editor lists the items in
             its Item field, draws the model of the item on the tile, and
             checks each spawn. GDScript cannot import ITEM_DB. Thus, this
             module renders the facts as one JSON file beside the plugin, as
             figure_catalog.py does for the figure workbench.

             WHICH ITEMS. Every ItemDef except a dev tool. A dev tool carries
             a tag of DEV_TOOL_TAG_CATEGORY, and no player may find one on
             the ground. `stacking()` is the one owner of the list. The
             content check of the world reads it
             (world/tests/test_tile_content.py), and the editor reads the
             file.

             The game client never reads the file. The web export leaves out
             the whole plugin directory.

             PURE, as clientexport.py is. render() returns a string and
             writes nothing. scripts/export_client_constants.py writes the
             file, and test_spawn_items.py compares the file in git with a
             new render. A stale file thus fails the suite.

             THE FILE:

                 format  1
                 items   [{key, name, family, stackable}, ...], sorted by key

             `family` is the family that the client resolves the item to
             (`figure_catalog.family_of`). The editor draws the model of the
             item from its key and its family, as the client draws an item
             on the ground.
"""

import json
import os

from systems.devtools.constants import DEV_TOOL_TAG_CATEGORY
from world.item_database import ITEM_DB

from .figure_catalog import family_of


# ─── Private constant definitions ────────────────────────────────────────────

# The format number of the item list file. A reader refuses a newer one.
_FORMAT: int = 1

# One tab for each level, as the item catalog of the figure workbench has.
_INDENT: str = "\t"

# The game dir (blackout/), three levels up from this file.
_GAME_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

# The repo root. The Godot client is a sibling of the game dir.
_REPO_ROOT: str = os.path.dirname(_GAME_DIR)

# Where the list goes: beside the plugin that reads it.
_OUTPUT_PATH: str = os.path.join(
    _REPO_ROOT, "godot", "addons", "blackout_terrain", "spawn_items.json")


# ─── Private helper routines ─────────────────────────────────────────────────

def _spawnable(item_def) -> bool:
    """Return True if an item spawn may name this item: not a dev tool."""
    categories = {category for _key, category in item_def.tags}

    return DEV_TOOL_TAG_CATEGORY not in categories


# ─── Public routines ─────────────────────────────────────────────────────────

def item_rows() -> list:
    """
    Purpose: Give one row for each item that an item spawn may name.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a list of {key, name, family, stackable} dicts, sorted by
        key.

    Module Globals:
        ITEM_DB read.

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    rows = []

    for key in sorted(ITEM_DB):
        item_def = ITEM_DB[key]

        if not _spawnable(item_def):
            continue

        rows.append({
            "key": key,
            "name": item_def.name,
            "family": family_of(item_def),
            "stackable": bool(item_def.stackable),
        })

    return rows


def stacking() -> dict:
    """
    Purpose: Give each item that an item spawn may name, and if it stacks.

    Entry:
        No conditions.

    Exit/Returns:
        Returns {item key: True if the item stacks}. `tile_checks.check_world`
        takes this table as its `items`.

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    return {row["key"]: row["stackable"] for row in item_rows()}


def text_of(rows: list) -> str:
    """
    Purpose: Write rows of items as the text of an item list file.

    Entry:
        rows - a list of {key, name, family, stackable} dicts.

    Exit/Returns:
        Returns JSON text with sorted keys and a newline at the end. Writes
        nothing.

    Module Globals:
        _FORMAT and _INDENT read.

    Methodology:
        One fact on each line and sorted keys, so a git diff shows one line
        for each changed fact. The same content gives the same bytes.

    Notes/References:
        The fixture of the content check writes its short item list with
        this (`world/tests/check_fixture_builder.py`). Thus, the editor
        reads both files with one reader.

    Author: Nick Hobar
    Creation date: 10/21/2026
    """
    content = {"format": _FORMAT, "items": rows}
    text = json.dumps(content, indent=_INDENT, sort_keys=True,
                      ensure_ascii=False)

    return text + "\n"


def render() -> str:
    """Return the text of the item list file of the game. Writes nothing."""
    return text_of(item_rows())


def output_path() -> str:
    """Return the absolute path of the item list file."""
    return _OUTPUT_PATH
