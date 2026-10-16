"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/14/2026
Description: The decor kinds of the tile grid, one row for each kind.

             Decor is scenery and nothing more: a crate, a table, a lamp post
             (DESIGN-0013 section 6.5). `world/object_kinds.py` makes one
             object kind of the category `decor` from each row here, after
             its own rows. Thus, a decor key is an object kind key, and the
             rules of decor live there.

             THE ROWS ARE DATA. They live in `world/tables/decor_kinds.json`
             (Nick, 10/14/2026), and `world/table_file.py` reads them. The
             Tables tab of the terrain editor adds, edits, renames, and
             removes a row, and then runs the client export. The other
             object kinds stay Python rows, because each one names a spawner,
             an NpcDef, a target, or a climb.

             The `scenery` names what the client stands on each tile: a
             primitive of `SCENERY_PRIMITIVES`, or the key of a model record
             in `assets/models/`. `world/tests/test_tile_content.py` checks
             it.

             This module imports no Evennia. The client export reads it.
"""

from dataclasses import dataclass

from world import table_file


@dataclass(frozen=True)
class DecorKind:
    """
    One decor kind. The `key` is the kind that a chunk object stores. The
    `note` tells an author what the decor is, and no player sees it. The
    `scenery` is the primitive or the model that the client draws.
    """

    key: str
    note: str
    scenery: str


# The name of the table file, with no suffix.
TABLE_NAME: str = "decor_kinds"

_DECOR_ROWS: tuple = table_file.read_rows(TABLE_NAME, DecorKind)

# key -> DecorKind, in the order of the file.
DECOR_KINDS: dict = {row.key: row for row in _DECOR_ROWS}
