"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/12/2026
Description: The figure files in the model pipeline (DESIGN-0014, Phase W4).

             THE FIGURE SET. The figure workbench of the Godot project writes
             one file for each rig and for each worn look, into
             assets/figure/. It writes one palette file there also (Phase
             W5). The build puts the content of each one into ONE served
             file, figure.json, beside the served models. A new worn look
             then reaches a player with no client export, and the client
             makes one fetch for all of them.

             figure.json is a generated file, as the manifest is. The check
             fails when the file in git differs from a new render. The text
             has no indent, because a client downloads it.

             A FIGURE MODEL. `figure-model` brings one model file into the
             pipeline, for art that Nick made for Blackout. It does the steps
             of "Add a model" in assets/README.md with no TODO to fill in:

               1. It copies the file into sources/blackout_<model_key>/.
               2. It writes the source record, with the owned license, and
                  seals it.
               3. It writes the model record, with `color_roles = true`.

             The command then builds that model. The figure workbench runs
             the command from its import button, so the author uses no
             terminal.

             ONE FILE FOR EACH SOURCE. A second import of one model key puts
             the new file in the place of the old file. The source of an
             import is art of Blackout, and a new export is a new download.

             Reads and writes files only. It touches no database.
"""

import datetime
import json
import os
import re
import shutil

from assets.pipeline import licenses, paths, records, sources


# ─── Public constant definitions ─────────────────────────────────────────────

# The format number of figure.json. The Godot reader is FigureSet.
FIGURE_SET_FORMAT: int = 1

# The family of a figure model that is no item: a body, a kit part.
FIGURE_FAMILY: str = "figure"

# The author of a figure model when the command names none.
DEFAULT_AUTHOR: str = "Nick Hobar"

# The source id of a figure model is this prefix and the model key.
SOURCE_PREFIX: str = "blackout_"

# The site and the URL of a source of art made for Blackout. The model
# wizard gives them as the defaults for such a source.
OWNED_SITE: str = "blackout"
OWNED_URL: str = "https://playblackout.io"


class FigureError(RuntimeError):
    """A figure file that does not read, or an import that cannot go on."""


# ─── Private constant definitions ────────────────────────────────────────────

_KEY_FIELD: str = "key"
_JSON_SEPARATORS: tuple = (",", ":")

_SOURCE_TEMPLATE: str = '''title     = "{title}"
author    = "{author}"
url       = "{url}"
site      = "{site}"
license   = "{license}"
retrieved = {retrieved}
notes     = "Art made for Blackout. `python -m assets.pipeline figure-model` wrote this record."
'''

_MODEL_TEMPLATE: str = '''source = "{source_id}"
file   = "{file}"

[output]
# The name of each material is a color role of a worn look. The build keeps
# each name.
color_roles = true
'''

# The `file` line of a model record, for an import with another suffix.
_FILE_LINE_PATTERN: str = r'(?m)^file\s*=\s*"[^"]*"\s*$'
_FILE_LINE: str = 'file   = "%s"'


# ─── Private helper routines ─────────────────────────────────────────────────

def _read_figure_files(folder: str) -> dict:
    """
    Purpose: Read each figure file of one directory.

    Entry:
        folder is a path. It does not need to exist.

    Exit/Returns:
        Returns {file stem: parsed content}, sorted by stem. Raises
        FigureError for a file that is not one JSON object, or whose key is
        not its file name.

    Module Globals:
        paths.FIGURE_FILE_SUFFIX, _KEY_FIELD read.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    found = {}

    if not os.path.isdir(folder):
        return found

    suffix = paths.FIGURE_FILE_SUFFIX
    names = sorted(name for name in os.listdir(folder)
                   if name.endswith(suffix))

    for name in names:
        stem = name[:-len(suffix)]
        where = "%s/%s" % (os.path.basename(folder), name)
        path = os.path.join(folder, name)

        try:
            with open(path, "r", encoding="utf-8") as handle:
                content = json.load(handle)
        except ValueError as problem:
            raise FigureError("%s is not valid JSON: %s" % (where, problem))

        if not isinstance(content, dict) or content.get(_KEY_FIELD) != stem:
            raise FigureError("%s: the key must be the file name" % where)

        found[stem] = content

    return found


def _read_palette() -> dict:
    """
    Purpose: Read the palette file of the figure workbench.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the parsed content. With no palette file, returns an empty
        dict: the client then takes each named color from its own start
        table. Raises FigureError for a file that is not one JSON object.

    Module Globals:
        paths.FIGURE_PALETTE_PATH read.

    Author: Nick Hobar
    Creation date: 10/13/2026
    """
    path = paths.FIGURE_PALETTE_PATH
    where = "figure/%s" % os.path.basename(path)

    if not os.path.isfile(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = json.load(handle)
    except ValueError as problem:
        raise FigureError("%s is not valid JSON: %s" % (where, problem))

    if not isinstance(content, dict):
        raise FigureError("%s must hold one JSON object" % where)

    return content


def _toml_text(value: str) -> str:
    """
    Purpose: Make a text safe inside a TOML basic string.

    Entry:
        value is any text.

    Exit/Returns:
        Returns value with each backslash and each quote escaped.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace('"', '\\"')

    return escaped


def _refuse_taken_key(family: str, model_key: str, source_id: str) -> None:
    """
    Purpose: Refuse a model key that another model record has.

    Entry:
        family and source_id are those that the import writes.

    Exit/Returns:
        Returns None. Raises FigureError that names the record.

    Module Globals:
        None.

    Methodology:
        A key is one file in the manifest. An item key can be an alias of
        another model, as rusty_scrap_arrow is. The author must take the key
        out of that record first, because the import must not change art
        that it did not bring. Only the record of an earlier import of the
        same key, in the same family, passes.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    for record in records.load_all():
        if model_key not in record.keys:
            continue

        own = (record.source_id == source_id and record.family == family
               and record.asset_key == model_key)

        if not own:
            raise FigureError(
                "the asset key '%s' has a model already: %s. Remove the key "
                "from that record first, or delete the record"
                % (model_key, record.record_path))


def _prepare_source(source_id: str, title: str, author: str) -> str:
    """
    Purpose: Make the source directory of an import, with its record.

    Entry:
        source_id is SOURCE_PREFIX and a model key.

    Exit/Returns:
        Returns the directory. A new directory gets a source record with the
        owned license. A directory that exists keeps its record, and each
        other file of it goes. Raises FigureError for a source that is not
        art of Blackout.

    Module Globals:
        paths.SOURCES_DIR, paths.SOURCE_RECORD_NAME, _SOURCE_TEMPLATE,
        OWNED_SITE, OWNED_URL read.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    directory = os.path.join(paths.SOURCES_DIR, source_id)
    record = os.path.join(directory, paths.SOURCE_RECORD_NAME)

    if os.path.isfile(record):
        source = sources.load_source(source_id)

        if source.license != licenses.OWNED_LICENSE:
            raise FigureError("%s is not art of Blackout (license '%s'), so "
                              "an import does not write over it"
                              % (source_id, source.license))

        for name in sources.current_files(source):
            os.remove(os.path.join(directory, name))

        return directory

    os.makedirs(directory, exist_ok=True)
    today = datetime.date.today().isoformat()
    text = _SOURCE_TEMPLATE.format(
        title=_toml_text(title), author=_toml_text(author), url=OWNED_URL,
        site=OWNED_SITE, license=licenses.OWNED_LICENSE, retrieved=today)

    with open(record, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    return directory


def _write_record(family: str, model_key: str, source_id: str,
                  filename: str) -> str:
    """
    Purpose: Write the model record of an import, or point it at a new file.

    Entry:
        The source source_id holds filename.

    Exit/Returns:
        Returns the path of the record. A record that exists keeps each line
        but its `file` line, so a [fix] of the author stays.

    Module Globals:
        paths.MODELS_DIR, paths.MODEL_RECORD_SUFFIX, _MODEL_TEMPLATE,
        _FILE_LINE_PATTERN, _FILE_LINE read.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    target = os.path.join(paths.MODELS_DIR, family,
                          model_key + paths.MODEL_RECORD_SUFFIX)
    text = _MODEL_TEMPLATE.format(source_id=source_id, file=filename)

    if os.path.isfile(target):
        with open(target, "r", encoding="utf-8") as handle:
            old_text = handle.read()

        file_line = _FILE_LINE % filename
        text = re.sub(_FILE_LINE_PATTERN, lambda _match: file_line, old_text)

    os.makedirs(os.path.dirname(target), exist_ok=True)

    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    return target


# ─── Public routines ─────────────────────────────────────────────────────────

def render_figure_set() -> str:
    """
    Purpose: Render figure.json from the figure files on disk.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the whole file: one JSON object with `format`, `rigs`,
        `looks` and `palette`, sorted keys, no indent, and one final
        newline. Raises FigureError for a figure file that does not read.

    Module Globals:
        FIGURE_SET_FORMAT, paths.FIGURE_RIGS_DIR, paths.FIGURE_LOOKS_DIR,
        _JSON_SEPARATORS read.

    Methodology:
        The content of each file goes in as it is. FigureRig, FigureLook
        and FigurePalette of the Godot project check its form, in the
        workbench and in the client, and test_figure_files.py checks each
        server name.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    rigs = _read_figure_files(paths.FIGURE_RIGS_DIR)
    looks = _read_figure_files(paths.FIGURE_LOOKS_DIR)
    palette = _read_palette()
    document = {"format": FIGURE_SET_FORMAT, "rigs": rigs, "looks": looks,
                "palette": palette}
    text = json.dumps(document, sort_keys=True, separators=_JSON_SEPARATORS)

    return text + "\n"


def write_figure_set() -> str:
    """
    Purpose: Write figure.json.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the path written. The file is UTF-8 with LF line endings.
        Raises FigureError for a figure file that does not read.

    Module Globals:
        paths.FIGURE_SET_PATH read.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    text = render_figure_set()
    os.makedirs(os.path.dirname(paths.FIGURE_SET_PATH), exist_ok=True)

    with open(paths.FIGURE_SET_PATH, "w", encoding="utf-8",
              newline="\n") as handle:
        handle.write(text)

    return paths.FIGURE_SET_PATH


def source_id_for(model_key: str) -> str:
    """
    Purpose: Name the source of the figure model of one model key.

    Entry:
        model_key is non-empty.

    Exit/Returns:
        Returns the source id.

    Module Globals:
        SOURCE_PREFIX read.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    return SOURCE_PREFIX + model_key


def import_model(family: str, model_key: str, path: str,
                 author: str = DEFAULT_AUTHOR) -> str:
    """
    Purpose: Bring one model file in as a source and a model record.

    Entry:
        path names one model file. family is the directory of the record.

    Exit/Returns:
        Returns the path of the model record. The model is not built yet.
        Raises FigureError for a bad key, a missing file, a key that another
        model has, or a source that is not art of Blackout.

    Module Globals:
        None.

    Methodology:
        1. Refuse a key that another model record has.
        2. Make the source, or empty the source of an earlier import.
        3. Copy the file in as <model_key><suffix>, and seal the source.
        4. Write the model record, or change its `file` line.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    key_fits = records.is_key(model_key)
    family_fits = records.is_key(family)

    if not key_fits or not family_fits:
        raise FigureError("a model key and a family use only a-z, 0-9 and _, "
                          "with a letter first")

    if not os.path.isfile(path):
        raise FigureError("%s is not a file" % path)

    source_id = source_id_for(model_key)
    _refuse_taken_key(family, model_key, source_id)
    title = model_key.replace("_", " ").capitalize()
    directory = _prepare_source(source_id, title, author)
    suffix = os.path.splitext(path)[1].lower()
    filename = model_key + suffix
    shutil.copyfile(path, os.path.join(directory, filename))
    source = sources.load_source(source_id)
    sources.seal(source)
    record_path = _write_record(family, model_key, source_id, filename)

    return record_path
