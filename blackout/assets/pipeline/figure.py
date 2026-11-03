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

             The command then builds that model. The `export` origin of
             the model plan (plans.py) calls import_model too. The gear
             editor imports through it, with `add-write` (11/02/2026), so
             the author uses no terminal.

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


def _taken_key_problem(family: str, model_key: str, source_id: str) -> str:
    """
    Purpose: Tell whether another model record has a model key, or reads
    the source that the import writes.

    Entry:
        family and source_id are those that the import writes.

    Exit/Returns:
        Returns the problem that names the record, or "".

    Module Globals:
        None.

    Methodology:
        A key is one file in the manifest. An item key can be an alias of
        another model, as rusty_scrap_arrow is. The author must take the key
        out of that record first, because the import must not change art
        that it did not bring. Only the record of an earlier import of the
        same key, in the same family, passes.

        The source has the same rule (11/02/2026). An import empties its
        source. blood_sword.toml reads blackout_bloody_sword2, so an import
        of bloody_sword2 deleted the file of the blood sword.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    for record in records.load_all():
        own = (record.source_id == source_id and record.family == family
               and record.asset_key == model_key)

        if model_key in record.keys and not own:
            return ("the asset key '%s' has a model already: %s. Remove the "
                    "key from that record first, or delete the record"
                    % (model_key, record.record_path))

        if record.source_id == source_id and not own:
            return ("%s feeds the model record %s. An import of '%s' would "
                    "replace its file. Type another key"
                    % (source_id, record.record_path, model_key))

    return ""


def _owned_problem(source_id: str) -> str:
    """
    Purpose: Tell whether an import may write into one source.

    Entry:
        source_id is SOURCE_PREFIX and a model key.

    Exit/Returns:
        Returns "" for a source that is not there, and for a source of art
        of Blackout. Returns the problem for any other source.

    Module Globals:
        paths.SOURCES_DIR, paths.SOURCE_RECORD_NAME read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    record = os.path.join(paths.SOURCES_DIR, source_id,
                          paths.SOURCE_RECORD_NAME)

    if not os.path.isfile(record):
        return ""

    source = sources.load_source(source_id)

    if source.license == licenses.OWNED_LICENSE:
        return ""

    return ("%s is not art of Blackout (license '%s'), so an import does not "
            "write over it" % (source_id, source.license))


def _source_record_text(title: str, author: str) -> str:
    """Give the text of the source record of a new import."""
    today = datetime.date.today().isoformat()

    return _SOURCE_TEMPLATE.format(
        title=_toml_text(title), author=_toml_text(author), url=OWNED_URL,
        site=OWNED_SITE, license=licenses.OWNED_LICENSE, retrieved=today)


def _prepare_source(source_id: str, title: str, author: str) -> str:
    """
    Purpose: Make the source directory of an import, with its record.

    Entry:
        source_id is SOURCE_PREFIX and a model key. _owned_problem accepts
        it.

    Exit/Returns:
        Returns the directory. A new directory gets a source record with the
        owned license. A directory that exists keeps its record, and each
        other file of it goes.

    Module Globals:
        paths.SOURCES_DIR, paths.SOURCE_RECORD_NAME read.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    directory = os.path.join(paths.SOURCES_DIR, source_id)
    record = os.path.join(directory, paths.SOURCE_RECORD_NAME)

    if os.path.isfile(record):
        source = sources.load_source(source_id)

        for name in sources.current_files(source):
            os.remove(os.path.join(directory, name))

        return directory

    os.makedirs(directory, exist_ok=True)
    text = _source_record_text(title, author)

    with open(record, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    return directory


def _record_path(family: str, model_key: str) -> str:
    """Give the path of the model record of an import."""
    return os.path.join(paths.MODELS_DIR, family,
                        model_key + paths.MODEL_RECORD_SUFFIX)


def _record_text(target: str, source_id: str, filename: str) -> str:
    """
    Purpose: Give the text of the model record of an import.

    Entry:
        target is the path of the record.

    Exit/Returns:
        Returns the text. A record that exists keeps each line but its
        `file` line, so a [fix] of the author stays.

    Module Globals:
        _MODEL_TEMPLATE, _FILE_LINE_PATTERN, _FILE_LINE read.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    if not os.path.isfile(target):
        return _MODEL_TEMPLATE.format(source_id=source_id, file=filename)

    with open(target, "r", encoding="utf-8") as handle:
        old_text = handle.read()

    file_line = _FILE_LINE % filename

    return re.sub(_FILE_LINE_PATTERN, lambda _match: file_line, old_text)


def _write_record(family: str, model_key: str, source_id: str,
                  filename: str) -> str:
    """
    Purpose: Write the model record of an import, or point it at a new file.

    Entry:
        The source source_id holds filename.

    Exit/Returns:
        Returns the path of the record.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    target = _record_path(family, model_key)
    text = _record_text(target, source_id, filename)
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


def import_filename(model_key: str, path: str) -> str:
    """Give the name that an import gives its copy: the key and the suffix."""
    suffix = os.path.splitext(path)[1].lower()

    return model_key + suffix


def import_problem(family: str, model_key: str, path: str) -> str:
    """
    Purpose: Tell why an import of one model file cannot go on.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the problem, or "". The problems are a bad key or family, a
        missing file, a key that another model has, and a source that is
        not art of Blackout.

    Module Globals:
        None.

    Notes:
        import_model raises each of these as a FigureError. The model form
        (form.py) asks this routine before it writes, so it shows the same
        problem with no write.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    key_fits = records.is_key(model_key)
    family_fits = records.is_key(family)

    if not key_fits or not family_fits:
        return ("a model key and a family use only a-z, 0-9 and _, with a "
                "letter first")

    if not os.path.isfile(path):
        return "%s is not a file" % path

    source_id = source_id_for(model_key)
    problem = _taken_key_problem(family, model_key, source_id)

    return problem or _owned_problem(source_id)


def import_preview(family: str, model_key: str, path: str,
                   author: str = DEFAULT_AUTHOR) -> list:
    """
    Purpose: Give each file that an import writes or keeps, with no write.

    Entry:
        import_problem accepts the import.

    Exit/Returns:
        Returns (path, note, text) tuples: the source directory, the source
        record, and the model record. The text is "" for a record that
        stays as it is.

    Module Globals:
        paths.SOURCES_DIR, paths.SOURCE_RECORD_NAME read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    source_id = source_id_for(model_key)
    directory = os.path.join(paths.SOURCES_DIR, source_id)
    record = os.path.join(directory, paths.SOURCE_RECORD_NAME)
    filename = import_filename(model_key, path)
    target = _record_path(family, model_key)
    again = os.path.isfile(record)
    copy_note = "a copy of %s as %s" % (path, filename)
    source_text = "" if again else _source_record_text(
        import_title(model_key), author)
    kept = os.path.isfile(target)
    record_note = "keeps each line but its file line" if kept else ""

    if again:
        copy_note += ". Each file of the earlier import goes"

    return [(directory, copy_note, ""),
            (record, "stays as it is" if again else "", source_text),
            (target, record_note, _record_text(target, source_id, filename))]


def import_title(model_key: str) -> str:
    """Give the title of the source of an import: "Body 1 head"."""
    return model_key.replace("_", " ").capitalize()


def import_model(family: str, model_key: str, path: str,
                 author: str = DEFAULT_AUTHOR) -> str:
    """
    Purpose: Bring one model file in as a source and a model record.

    Entry:
        path names one model file. family is the directory of the record.

    Exit/Returns:
        Returns the path of the model record. The model is not built yet.
        Raises FigureError with the problem of import_problem.

    Module Globals:
        None.

    Methodology:
        1. Refuse what import_problem refuses.
        2. Make the source, or empty the source of an earlier import.
        3. Copy the file in as <model_key><suffix>, and seal the source.
        4. Write the model record, or change its `file` line.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    problem = import_problem(family, model_key, path)

    if problem:
        raise FigureError(problem)

    source_id = source_id_for(model_key)
    directory = _prepare_source(source_id, import_title(model_key), author)
    filename = import_filename(model_key, path)
    shutil.copyfile(path, os.path.join(directory, filename))
    source = sources.load_source(source_id)
    sources.seal(source)
    record_path = _write_record(family, model_key, source_id, filename)

    return record_path
