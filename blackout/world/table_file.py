"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/14/2026
Description: The reader of the table files. A table file is one JSON file
             that holds the rows of one table of the tile grid: the areas,
             the floor types, the wall styles, and the decor kinds.

Why a file and not a tuple
--------------------------
The Tables tab of the terrain editor adds, edits, renames, and removes a row
(Nick, 10/14/2026). The editor writes data, never Python. Thus, the rows
moved from the tuples of `world/areas.py`, `world/floor_types.py`,
`world/wall_styles.py`, and `world/object_kinds.py` into the files of
`TABLE_DIRECTORY`. Each module keeps its public names (`AREAS`,
`DEFAULT_AREA`, ...), so no reader of a table changed.

The format
----------
    {"format": 1, "rows": [{"key": "oasis", "note": "...", ...}, ...]}

- The order of the rows is the order of the table. The first row is the
  default of its table, for example the area of a new chunk.
- A row holds each field of the row class of its table. A field with a
  default may stay out of the row.
- A row holds no other field. Thus, a typo fails at start, and no field
  sits in the file that nothing reads.
- Each key is a legal chunk file name, and no two rows share a key.

A bad file raises TableFileError at import. Thus, a server with a bad row
does not start, and the test suite fails loudly.

This module imports no Evennia. The client export reads every table.
"""

import dataclasses
import json
import os
import re

from systems.core.tilegrid import constants as tile_const


# ─── Public constant definitions ─────────────────────────────────────────────

# The keys of a table file.
FORMAT_KEY: str = "format"
ROWS_KEY: str = "rows"

# The field of a row that names it.
KEY_FIELD: str = "key"

# The game directory, one level above this file.
_GAME_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The directory of the table files, as an OS path.
TABLE_DIRECTORY_PATH: str = os.path.join(
    _GAME_DIR, *tile_const.TABLE_DIRECTORY.split("/"))


# ─── Private constant definitions ────────────────────────────────────────────

_KEY_RE = re.compile(tile_const.CHUNK_NAME_PATTERN)

# The JSON type of each type that a row field may have. The annotation can
# be the type itself or its name, as `from __future__ import annotations`
# gives it.
_FIELD_TYPES: dict = {str: str, bool: bool, "str": str, "bool": bool}


# ─── Public classes ──────────────────────────────────────────────────────────

class TableFileError(ValueError):
    """A table file that does not read, or a row that breaks a rule."""


# ─── Public routines ─────────────────────────────────────────────────────────

def table_path(table: str, directory: str = TABLE_DIRECTORY_PATH) -> str:
    """Return the path of the file of `table` in `directory`."""
    return os.path.join(directory, table + tile_const.TABLE_FILE_SUFFIX)


def field_names(row_class) -> tuple:
    """Return the field names of a row class, in the order of the class."""
    return tuple(field.name for field in dataclasses.fields(row_class))


def read_rows(table: str, row_class,
              directory: str = TABLE_DIRECTORY_PATH) -> tuple:
    """
    Purpose: Read the rows of one table file.

    Entry:
        table     - the name of the table, the file name with no suffix.
        row_class - a frozen dataclass whose fields the rows hold.
        directory - the table directory. A test gives its own.

    Exit/Returns:
        A tuple of row_class, in the order of the file.
        Raises TableFileError for a file that is not there, that does not
        parse, or that breaks a rule of the module docstring.

    Module Globals:
        None.

    Methodology:
        Parse the JSON text, then give it to rows_from_data.

    Notes/References:
        The GDScript twin of the reader is TileTables in
        godot/world/terrain/tile_tables.gd.

    Author: Nick Hobar
    Creation date: 10/14/2026
    """
    path = table_path(table, directory)

    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        raise TableFileError(f"{path}: {error}") from error

    return rows_from_data(data, row_class, path)


def rows_from_data(data, row_class, source: str) -> tuple:
    """
    Purpose: Check the content of a table file, and make its rows.

    Entry:
        data      - the parsed JSON of the file.
        row_class - a frozen dataclass whose fields the rows hold.
        source    - the name of the file, for the error text.

    Exit/Returns:
        A tuple of row_class, in the order of the rows.
        Raises TableFileError, with the source and the row index.

    Module Globals:
        FORMAT_KEY, ROWS_KEY, KEY_FIELD read.

    Methodology:
        Check the format and the rows list, then each row, then the keys.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/14/2026
    """
    if not isinstance(data, dict) or set(data) != {FORMAT_KEY, ROWS_KEY}:
        raise TableFileError(
            f"{source}: the file must hold exactly {FORMAT_KEY!r} and {ROWS_KEY!r}")

    if data[FORMAT_KEY] != tile_const.TABLE_FORMAT_VERSION:
        raise TableFileError(f"{source}: format {data[FORMAT_KEY]!r} is not "
                             f"{tile_const.TABLE_FORMAT_VERSION}")

    rows = data[ROWS_KEY]

    if not isinstance(rows, list) or not rows:
        raise TableFileError(f"{source}: {ROWS_KEY!r} must be a list with a row")

    made = tuple(_row(item, row_class, f"{source}, row {index}")
                 for index, item in enumerate(rows))
    keys = [row.key for row in made]
    doubled = sorted({key for key in keys if keys.count(key) > 1})

    if doubled:
        raise TableFileError(f"{source}: two rows have the key {doubled[0]!r}")

    return made


# ─── Private helper routines ─────────────────────────────────────────────────

def _row(item, row_class, where: str):
    """
    Purpose: Check one row, and make it.

    Entry:
        item      - one element of the rows list.
        row_class - the frozen dataclass of the table.
        where     - the file and the row index, for the error text.

    Exit/Returns:
        One row_class. Raises TableFileError for a bad row.

    Module Globals:
        KEY_FIELD, _KEY_RE, _FIELD_TYPES read.

    Methodology:
        A field with no default must be there. No other field may be there.
        Each value must have the type of its field. The key must match the
        chunk name pattern.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/14/2026
    """
    if not isinstance(item, dict):
        raise TableFileError(f"{where}: a row must be an object")

    fields = {field.name: field for field in dataclasses.fields(row_class)}
    unknown = sorted(set(item) - set(fields))

    if unknown:
        raise TableFileError(f"{where}: no field {unknown[0]!r} in a row")

    for name, field in fields.items():
        _check_field(item, name, field, where)

    key_ok = _KEY_RE.search(item[KEY_FIELD]) is not None

    if not key_ok:
        raise TableFileError(f"{where}: {item[KEY_FIELD]!r} is not a legal key")

    return row_class(**item)


def _check_field(item: dict, name: str, field, where: str) -> None:
    """
    Purpose: Check one field of one row.

    Entry:
        item  - the row, a dict.
        name  - the field name.
        field - the dataclasses.Field of the name.
        where - the file and the row index, for the error text.

    Exit/Returns:
        None. Raises TableFileError for a missing field with no default, or
        for a value of another type.

    Module Globals:
        _FIELD_TYPES read.

    Methodology:
        A missing field is legal only with a default. `bool` is a subclass
        of `int` in Python, but a row field is never an int, so isinstance
        is a whole test here.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/14/2026
    """
    has_default = field.default is not dataclasses.MISSING

    if name not in item:
        if not has_default:
            raise TableFileError(f"{where}: the field {name!r} is missing")
        return

    wanted = _FIELD_TYPES.get(field.type)

    if wanted is None:
        raise TableFileError(f"{where}: the field {name!r} has no JSON type")

    if not isinstance(item[name], wanted):
        raise TableFileError(
            f"{where}: the field {name!r} must be a {wanted.__name__}")
