"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/25/2026
Description: The key list: each asset key that the server names, and the
             key list file of the model wizard.

             The model wizard (`python -m assets.pipeline add`) offers each
             asset key that the server names and no model record draws yet.
             It also warns about a typed asset key that the server does not
             name. The pipeline runs with no Django, so it cannot import
             ITEM_DB, NPC_DB or OBJECT_KINDS. Thus, this module renders the
             facts as one JSON file, as spawn_items.py does for the terrain
             editor.

             WHICH KEYS. The keys that `serializers._classify` sends for an
             entity, and the scenery keys of the object kinds:
               - the key of each ItemDef. The feed names an item by its key.
               - the model of each NPC def (`resolved_asset_key`).
               - the preview key of each object kind.
                 test_object_kind_preview.py holds it equal to the key that
                 the feed sends for the entity of the kind.
               - the scenery of each object kind. A primitive does not go in,
                 because the client draws a primitive with no model.
             ASSET_KEY_GENERIC does not go in. A model for it draws on each
             item that nothing else classifies (statefeed/constants.py).

             The client names some keys too, for example the family shapes
             in family_shapes.gd. The list does not hold them, because the
             server does not own them. For this reason the wizard warns and
             asks. It does not refuse.

             PURE, as spawn_items.py is. render() returns a string and writes
             nothing. scripts/export_client_constants.py writes the file, and
             test_key_list.py compares the file in git with a new render. A
             stale file thus fails the suite.

             THE FILE:

                 format  1
                 keys    [{key, owner, kind, name}, ...], sorted by key, then
                         by owner

             `owner` is the key of the ItemDef, the NPC def or the object
             kind that names the asset key. One asset key can have several
             owners. `kind` is a word for a person, not a protocol value: the
             family of the entity, or the category of the object kind for a
             scenery key. `name` is the name that a player reads.
"""

import json

from assets.pipeline import paths as model_paths
from systems.core.tilegrid import constants as tile_const
from world.item_database import ITEM_DB
from world.npc_database import NPC_DB
from world.object_kinds import OBJECT_KINDS

from . import constants as const
from .figure_catalog import family_of


# ─── Private constant definitions ────────────────────────────────────────────

# The format number of the key list file. A reader refuses a newer one.
_FORMAT: int = 1

# One tab for each level, as the item list of the terrain editor has.
_INDENT: str = "\t"

# The asset keys that never go in the list. See the module docstring.
_NEVER_LISTED: frozenset = frozenset(
    (const.ASSET_KEY_GENERIC,) + tile_const.SCENERY_PRIMITIVES)


# ─── Private helper routines ─────────────────────────────────────────────────

def _row(key: str, owner: str, kind: str, name: str) -> dict:
    """Return one row of the key list."""
    return {"key": key, "owner": owner, "kind": kind, "name": name}


def _item_rows() -> list:
    """Return one row for each ItemDef. Its own key names it."""
    return [_row(key, key, family_of(item_def), item_def.name)
            for key, item_def in ITEM_DB.items()]


def _npc_rows() -> list:
    """Return one row for each NPC def: the key of its model."""
    return [_row(npc_def.resolved_asset_key(), key, const.ASSET_KIND_NPC,
                 npc_def.name)
            for key, npc_def in NPC_DB.items()]


def _preview_rows() -> list:
    """Return one row for each object kind that stands up an entity."""
    rows = []

    for key, kind in OBJECT_KINDS.items():
        if not kind.preview:
            continue

        asset_key, family = kind.preview
        rows.append(_row(asset_key, key, family, kind.name or key))

    return rows


def _scenery_rows() -> list:
    """Return one row for each object kind with scenery."""
    return [_row(kind.scenery, key, kind.category, kind.name or key)
            for key, kind in OBJECT_KINDS.items() if kind.scenery]


# The owners that name an asset key, in order. When two rows give one
# (key, owner) pair, the first row stays: an NPC def gives a better name than
# the object kind of the same NPC. A fifth owner is one more builder here.
_ROW_BUILDERS: tuple = (_item_rows, _npc_rows, _preview_rows, _scenery_rows)


# ─── Public routines ─────────────────────────────────────────────────────────

def key_rows() -> list:
    """
    Purpose: Give one row for each pair of an asset key and its owner.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a list of {key, owner, kind, name} dicts, sorted by key,
        then by owner. No key of _NEVER_LISTED is in it.

    Module Globals:
        _ROW_BUILDERS and _NEVER_LISTED read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    found = {}

    for builder in _ROW_BUILDERS:
        for row in builder():
            pair = (row["key"], row["owner"])
            listed = row["key"] and row["key"] not in _NEVER_LISTED

            if listed and pair not in found:
                found[pair] = row

    return [found[pair] for pair in sorted(found)]


def text_of(rows: list) -> str:
    """
    Purpose: Write rows of the key list as the text of a key list file.

    Entry:
        rows - a list of {key, owner, kind, name} dicts.

    Exit/Returns:
        Returns JSON text with sorted keys and a newline at the end. Writes
        nothing.

    Module Globals:
        _FORMAT and _INDENT read.

    Methodology:
        One fact on each line and sorted keys, so a git diff shows one line
        for each changed fact. The same content gives the same bytes.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    content = {"format": _FORMAT, "keys": rows}
    text = json.dumps(content, indent=_INDENT, sort_keys=True,
                      ensure_ascii=False)

    return text + "\n"


def render() -> str:
    """Return the text of the key list file of the game. Writes nothing."""
    return text_of(key_rows())


def output_path() -> str:
    """Return the absolute path of the key list file."""
    return model_paths.KEY_LIST_PATH
