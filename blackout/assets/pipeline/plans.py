"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/02/2026
Description: The plan of one new model: the answers of `add`, the check of
             each answer, and the write. Two askers fill a plan. The
             terminal wizard (wizard.py) asks one question at a time. The
             model form of the Godot editor (form.py) sends all the answers
             at one time. Both use the routines here. Thus, the two refuse
             the same answers and write the same files.

             The routines came out of wizard.py on 11/02/2026, when Nick
             asked for the model form.

             FOUR ORIGINS. Each origin is a row of ORIGIN_LABELS, of
             _PREVIEWS and of _WRITERS:
               file       a file, a folder or a .zip on this machine
               polyhaven  a Poly Haven model. The write downloads it
               source     a source that is in sources/ already
               export     a new export of art made here. An import of the
                          same key again puts the new file in the place of
                          the old file. figure.py owns its rules. The gear
                          editor imports through it. The terminal wizard
                          does not ask it, because `figure-model` does the
                          same in one line.

             THE PLAN DECIDES NO RULE. The license gate, the key pattern,
             the record text, the seal and the family budgets belong to the
             modules that own them. The plan reads them, so an answer cannot
             pass what the build refuses.

             THE KEY LIST. paths.KEY_LIST_PATH names each asset key that the
             server names. The server writes it, because this process has no
             Django. A key that it does not name gets a warning, not a
             refusal, because the client names some keys itself, for example
             a family shape.

             Reads and writes files only. It touches no database.
"""

import json
import os
import re
import zipfile
from dataclasses import dataclass
from typing import Callable

from assets.pipeline import (blender, budgets, build, fetch, figure,
                             licenses, paths, questions, records, sources)


# ─── Public constant definitions ─────────────────────────────────────────────

ORIGIN_FILE: str = "file"
ORIGIN_POLYHAVEN: str = "polyhaven"
ORIGIN_SOURCE: str = "source"
ORIGIN_EXPORT: str = "export"

# The label of each origin, in the order that a list shows them.
ORIGIN_LABELS: dict = {
    ORIGIN_FILE: "A file, a folder or a .zip on this machine",
    ORIGIN_POLYHAVEN: "A Poly Haven model (CC0). The write downloads it",
    ORIGIN_SOURCE: "A source that is in sources/ already",
    ORIGIN_EXPORT: ("A new export of art made here. An import of the same "
                    "key again replaces the file"),
}

ZIP_SUFFIX: str = ".zip"
MODEL_SUFFIXES: tuple = (blender.GLTF_SUFFIXES + blender.BLENDER_SUFFIXES
                         + (build.PICOCAD_SUFFIX,))

# The newest format of the key list file that the plan reads, and the
# fields of one row. systems/interface/statefeed/key_list.py writes them.
KEY_LIST_FORMAT: int = 1
KEY_LIST_FIELDS: tuple = ("key", "owner", "kind", "name")


@dataclass
class Plan:
    """
    The answers so far.

    origin: a key of ORIGIN_LABELS.
    upload: the path of a file origin or of an export.
    polyhaven: the model of a Poly Haven origin.
    fields: the record of a new source, or None.
    source_note: what the write does to the source.
    name_hint: the name of the download, for the defaults.
    """

    origin: str = ""
    upload: str = ""
    polyhaven: fetch.PolyHavenModel = None
    fields: fetch.SourceFields = None
    source_id: str = ""
    source_note: str = ""
    name_hint: str = ""
    model_files: tuple = ()
    model_file: str = ""
    family: str = ""
    asset_key: str = ""
    aliases: tuple = ()
    variant_of: str = ""


@dataclass(frozen=True)
class PlannedFile:
    """
    One file or directory that a write makes or keeps. path is relative to
    assets/ when it can be. text is the content of a record, or "".
    """

    path: str
    note: str = ""
    text: str = ""


class KeyListError(Exception):
    """A key list file that is not there, is not JSON, or has a bad row."""


# ─── Private constant definitions ────────────────────────────────────────────

# Enough of a .txt file to read the picoCAD header.
_HEAD_CHARS: int = 16

# A free default source id gets the first free number in this range.
_FIRST_COPY: int = 2
_LAST_COPY: int = 99

# What macOS adds to a .zip: a folder of copies, and "._" resource files.
_JUNK_PREFIXES: tuple = ("__MACOSX", "._")

_ALIAS_SEPARATOR: str = ","
_BUDGET_REASON: str = " -- "

# The site that a source record names for a host, as the sources in git
# name it. Any other host is the site itself.
_HOST_PREFIX: str = "www."
_SITE_HOSTS: dict = {
    "itch.io": "itch.io",
    "sketchfab.com": "sketchfab",
    "polyhaven.com": fetch.POLYHAVEN_SITE,
    "github.com": "github",
    "godotengine.org": "godot-asset-library",
    "quaternius.com": "quaternius",
    "playblackout.io": figure.OWNED_SITE,
}
_URL_SCHEME: str = r"^[a-z]+://"

_SEAL_NOTE: str = "[files]  (the seal writes the hash of each file)"
_KEPT_NOTE: str = "stays as it is"


# ─── Public routines: names and paths ────────────────────────────────────────

def shown(path: str) -> str:
    """Give a path relative to assets/, with forward slashes, if it can."""
    try:
        relative = os.path.relpath(path, paths.ASSETS_DIR)
    except ValueError:
        return path

    return relative.replace(os.sep, "/")


def site_for(url: str) -> str:
    """
    Purpose: Give the site of a source record for one URL.

    Entry:
        url is any text.

    Exit/Returns:
        Returns the site of the host in _SITE_HOSTS, or the host itself.
        A subdomain counts: "eclair.itch.io" gives "itch.io".

    Module Globals:
        _URL_SCHEME, _HOST_PREFIX, _SITE_HOSTS read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    bare = re.sub(_URL_SCHEME, "", url.strip().lower())
    host = bare.split("/")[0]

    if host.startswith(_HOST_PREFIX):
        host = host[len(_HOST_PREFIX):]

    for known, site in _SITE_HOSTS.items():
        if host == known or host.endswith("." + known):
            return site

    return host


# ─── Private helper routines: model files ────────────────────────────────────

def _is_junk(name: str) -> bool:
    """Tell whether a path in a download is a file that macOS added."""
    parts = name.replace("\\", "/").split("/")

    return any(part.startswith(_JUNK_PREFIXES) for part in parts)


def _is_model_file(name: str, read_head: Callable) -> bool:
    """
    Purpose: Tell whether one file of a download is a model that the build
    reads.

    Entry:
        read_head returns the start of the file as text. Only a .txt file
        calls it.

    Exit/Returns:
        Returns True for a model suffix, and for a .txt file that is a
        picoCAD save file.

    Module Globals:
        MODEL_SUFFIXES, build.PICOCAD_SUFFIX, build.PICOCAD_HEADER read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    suffix = os.path.splitext(name)[1].lower()
    junk = _is_junk(name)

    if junk or suffix not in MODEL_SUFFIXES:
        return False

    if suffix != build.PICOCAD_SUFFIX:
        return True

    head = read_head()

    return head.startswith(build.PICOCAD_HEADER)


def _head_of_file(path: str) -> str:
    """Give the start of one file as text, or "" when it does not read."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(_HEAD_CHARS)
    except OSError:
        return ""

    return head.decode("utf-8", errors="replace")


def _zip_head(archive: zipfile.ZipFile, member: str) -> str:
    """Give the start of one file inside an open .zip as text."""
    with archive.open(member) as handle:
        head = handle.read(_HEAD_CHARS)

    return head.decode("utf-8", errors="replace")


def _zip_model_files(path: str) -> tuple:
    """
    Purpose: Name each model file inside one .zip.

    Entry:
        path names a file.

    Exit/Returns:
        Returns the sorted paths inside the .zip, with forward slashes.
        Returns () when the file is not a .zip that opens.

    Module Globals:
        None.

    Notes:
        A folder entry ends in "/" and has no suffix, so it is no model.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    found = []

    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                is_model = _is_model_file(
                    name, lambda member=name: _zip_head(archive, member))

                if is_model:
                    found.append(name)
    except (zipfile.BadZipFile, OSError):
        return ()

    return tuple(sorted(found))


# ─── Public routines: model files ────────────────────────────────────────────

def is_palette(name: str) -> bool:
    """Tell whether the texture of a model file is always a palette."""
    suffix = os.path.splitext(name)[1].lower()

    return suffix in blender.PALETTE_SUFFIXES


def folder_model_files(folder: str) -> tuple:
    """
    Purpose: Name each model file inside one folder and its subfolders.

    Entry:
        folder names a directory.

    Exit/Returns:
        Returns the sorted paths relative to folder, with forward slashes.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    found = []

    for parent, _subfolders, filenames in os.walk(folder):
        for filename in filenames:
            full = os.path.join(parent, filename)
            relative = os.path.relpath(full, folder).replace(os.sep, "/")
            is_model = _is_model_file(relative,
                                      lambda path=full: _head_of_file(path))

            if is_model:
                found.append(relative)

    return tuple(sorted(found))


def upload_model_files(path: str) -> tuple:
    """
    Purpose: Name each model file that a copy of one upload would hold.

    Entry:
        path exists.

    Exit/Returns:
        Returns the paths that a model record can name after fetch_file
        copies path in, sorted.

    Module Globals:
        ZIP_SUFFIX read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    if path.lower().endswith(ZIP_SUFFIX):
        return _zip_model_files(path)

    if os.path.isdir(path):
        return folder_model_files(path)

    name = os.path.basename(path)
    is_model = _is_model_file(name, lambda: _head_of_file(path))

    return (name,) if is_model else ()


# ─── Public routines: a new source ───────────────────────────────────────────

def license_note(terms: licenses.LicenseTerms) -> str:
    """Give what one allowed license asks of a model, after its name."""
    note = ""

    if terms.attribution:
        note += ". The credits box must name the author"

    if terms.local_only:
        note += ". Git keeps none of its files (a local source)"

    return note


def credit_defaults(spdx: str, name_hint: str) -> dict:
    """
    Purpose: Give the default credit fields of a new source.

    Entry:
        spdx is the license of the source. name_hint is the name of the
        download.

    Exit/Returns:
        Returns {"title", "author", "url"}. Art made for Blackout takes the
        author and the URL of figure-model. Another license gives no
        author and no URL.

    Module Globals:
        figure.DEFAULT_AUTHOR, figure.OWNED_URL read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    owned = spdx == licenses.OWNED_LICENSE

    return {"title": questions.as_title(name_hint),
            "author": figure.DEFAULT_AUTHOR if owned else "",
            "url": figure.OWNED_URL if owned else ""}


def source_exists(source_id: str) -> bool:
    """Tell whether sources/ has an entry with this name."""
    directory = os.path.join(paths.SOURCES_DIR, source_id)

    return os.path.exists(directory)


def new_source_problem(value: str) -> str:
    """Refuse a source id that is no key, or that sources/ has already."""
    fits = records.is_key(value)
    exists = fits and source_exists(value)

    if not fits:
        return "A source id uses only a-z, 0-9 and _, with a letter first."

    if exists:
        return "sources/%s exists already. Type another one." % value

    return ""


def free_source_id(wanted: str) -> str:
    """
    Purpose: Give a source id that sources/ does not have yet.

    Entry:
        wanted is a key, or "".

    Exit/Returns:
        Returns wanted when it is free, or wanted with the first free
        number. Returns "" when wanted is "" or each number is taken.

    Module Globals:
        _FIRST_COPY, _LAST_COPY read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    candidates = [wanted] + ["%s_%d" % (wanted, number) for number
                             in range(_FIRST_COPY, _LAST_COPY + 1)]

    for candidate in candidates:
        problem = new_source_problem(candidate)

        if wanted and not problem:
            return candidate

    return ""


def default_source_id(site: str, name_hint: str) -> str:
    """
    Purpose: Give the default source id of a new source.

    Entry:
        site is the site of the source record.

    Exit/Returns:
        Returns a free source id: the first word of the site and the name
        of the download, for example itch_rusty_sword. Returns "" when no
        free id comes from them.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    prefix = site.split(".")[0]
    wanted = questions.as_key("%s_%s" % (prefix, name_hint))

    return free_source_id(wanted)


def upload_note(upload: str, fields: fetch.SourceFields) -> str:
    """Tell what the write does to the source of an upload."""
    note = "a copy of %s" % upload

    if fields.local:
        note += ". Git keeps only its source record"

    return note


def polyhaven_note(model: fetch.PolyHavenModel) -> str:
    """Tell what the write does to the source of a Poly Haven model."""
    if not model.files:
        return "a download from Poly Haven"

    return "a download of %d files from Poly Haven" % len(model.files)


# ─── Public routines: a source that is in sources/ already ───────────────────

def record_counts(all_records: list) -> dict:
    """Map each source id to the number of model records that it feeds."""
    counts = {}

    for record in all_records:
        counts[record.source_id] = counts.get(record.source_id, 0) + 1

    return counts


def source_label(source_id: str, counts: dict) -> str:
    """Give the row of one source: its license, and the records it feeds."""
    try:
        source = sources.load_source(source_id)
    except sources.SourceError:
        return "%s  (its source.toml does not load)" % source_id

    used = counts.get(source_id, 0)

    return "%s  (%s, model records: %d)" % (source_id, source.license, used)


def source_problem(source: sources.Source) -> str:
    """Tell why no model of one source can be chosen, or give ""."""
    absent = sources.files_absent(source)
    found = () if absent else folder_model_files(source.directory)

    if absent:
        return "The files of this local source are not on this machine."

    if not found:
        return "%s holds no model file that the build reads." % (
            source.source_id)

    return ""


# ─── Public routines: the family, the key, the aliases, the base ─────────────

def families() -> list:
    """Name each family: each one with a budget, and each in models/."""
    found = set(budgets.FAMILY_BUDGETS)
    present = os.path.isdir(paths.MODELS_DIR)
    names = os.listdir(paths.MODELS_DIR) if present else []

    for name in names:
        folder = os.path.join(paths.MODELS_DIR, name)

        if os.path.isdir(folder):
            found.add(name)

    return sorted(found)


def family_label(family: str) -> str:
    """Give the row of one family: its budget, with no reason."""
    described = budgets.describe_budget(family)

    return described.split(_BUDGET_REASON)[0]


def new_family_problem(value: str) -> str:
    """Refuse a family that is no key."""
    fits = records.is_key(value)

    return "" if fits else ("A family uses only a-z, 0-9 and _, with a "
                            "letter first.")


def owners_of(all_records: list) -> dict:
    """Map each asset key and alias on disk to the path of its record."""
    return {key: record.record_path for record in all_records
            for key in record.keys}


def key_problem(value: str, owners: dict) -> str:
    """Refuse an asset key that is no key, or that a record has already."""
    fits = records.is_key(value)
    owner = owners.get(value, "")

    if not fits:
        return "An asset key uses only a-z, 0-9 and _, with a letter first."

    if owner:
        return "%s has the key %s already." % (shown(owner), value)

    return ""


def default_key(plan: Plan, owners: dict) -> str:
    """
    Purpose: Give the default asset key of the new model record.

    Entry:
        owners maps each asset key and alias on disk to its record.

    Exit/Returns:
        Returns the name of the download for a source with one model, or
        the name of the model file. Returns "" when a record has that key.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    one_model = len(plan.model_files) == 1
    stem = questions.name_of(plan.model_file)
    name = plan.name_hint if one_model and plan.name_hint else stem
    wanted = questions.as_key(name)
    taken = key_problem(wanted, owners)

    return "" if taken else wanted


def split_aliases(text: str) -> tuple:
    """Give each alias of a typed list, in order."""
    parts = [part.strip() for part in text.split(_ALIAS_SEPARATOR)]

    return tuple(part for part in parts if part)


def aliases_problem(aliases: tuple, asset_key: str, owners: dict) -> str:
    """Refuse an alias that is no free key, the asset key, or a repeat."""
    if len(set(aliases)) != len(aliases):
        return "The list holds one alias two times."

    for alias in aliases:
        problem = key_problem(alias, owners)

        if alias == asset_key:
            return "%s is the asset key itself." % alias

        if problem:
            return problem

    return ""


def variant_problem(value: str, asset_key: str, bases: dict) -> str:
    """Refuse a base that is the model, no record of its own, or a variant."""
    base = bases.get(value)

    if not value:
        return ""

    if value == asset_key:
        return "A model cannot be a variant of itself."

    if base is None:
        return ("No model record has %s as its own key. An alias is no base."
                % value)

    if base.variant_of:
        return ("%s is a variant itself. Type the key of its base, %s."
                % (value, base.variant_of))

    return ""


# ─── Private helper routines: the key list ───────────────────────────────────

def _checked_rows(content, shown_path: str) -> list:
    """
    Purpose: Give the rows of a parsed key list file.

    Entry:
        content is the parsed JSON. shown_path names the file in a problem.

    Exit/Returns:
        Returns the rows. Raises KeyListError for a file with no format
        number or no rows, a newer format, or a row with a missing field.

    Module Globals:
        KEY_LIST_FORMAT, KEY_LIST_FIELDS read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    whole = isinstance(content, dict)
    version = content.get("format") if whole else None
    rows = content.get("keys") if whole else None
    shaped = isinstance(version, int) and isinstance(rows, list)

    if not shaped:
        raise KeyListError("%s has no format number or no rows."
                           % shown_path)

    if version > KEY_LIST_FORMAT:
        raise KeyListError("%s has format %d. The plan reads format %d."
                           % (shown_path, version, KEY_LIST_FORMAT))

    for row in rows:
        complete = isinstance(row, dict) and all(
            isinstance(row.get(field), str) for field in KEY_LIST_FIELDS)

        if not complete:
            raise KeyListError("%s has a row with a missing field: %r."
                               % (shown_path, row))

    return rows


# ─── Public routines: the key list ───────────────────────────────────────────

def read_key_list(path: str) -> list:
    """
    Purpose: Read a key list file: each asset key that the server names.

    Entry:
        path names the file, for example paths.KEY_LIST_PATH.

    Exit/Returns:
        Returns the rows, {key, owner, kind, name} dicts. Raises
        KeyListError when the file is not there, is not JSON, has a newer
        format, or has a row with a missing field.

    Module Globals:
        None.

    Notes:
        systems/interface/statefeed/key_list.py writes the file. Its test
        reads the file in git back through this routine.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    shown_path = shown(path)

    if not os.path.isfile(path):
        raise KeyListError("%s is not there." % shown_path)

    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = json.load(handle)
    except (OSError, ValueError) as problem:
        raise KeyListError("%s does not read: %s." % (shown_path, problem))

    return _checked_rows(content, shown_path)


def named_rows(key_list: list) -> dict:
    """Map each asset key of the key list to its first row."""
    named = {}

    for row in key_list:
        named.setdefault(row["key"], row)

    return named


def worn_look_keys() -> set:
    """Name each asset key that has a worn look in figure/looks/."""
    folder = paths.FIGURE_LOOKS_DIR
    suffix = paths.FIGURE_FILE_SUFFIX
    present = os.path.isdir(folder)
    names = os.listdir(folder) if present else []

    return {name[:-len(suffix)] for name in names if name.endswith(suffix)}


def offered_keys(key_list: list, all_records: list, family: str,
                 looks: set) -> list:
    """
    Purpose: Give the rows of each asset key that the game names and no
    model record has.

    Entry:
        all_records holds every loaded model record. family is the chosen
        family, or "". looks holds each key with a worn look.

    Exit/Returns:
        Returns one row for each key. A kind that the chosen family draws
        already comes first. A key with no worn look comes before a key
        with one. Then the rows go by kind, then by key.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    owners = owners_of(all_records)
    family_keys = {key for record in all_records
                   if record.family == family for key in record.keys}
    named = named_rows(key_list)
    drawn = {named[key]["kind"] for key in family_keys if key in named}
    free = [row for key, row in named.items() if key not in owners]

    return sorted(free, key=lambda row: (row["kind"] not in drawn,
                                         row["key"] in looks,
                                         row["kind"], row["key"]))


def is_named(key: str, key_list) -> bool:
    """Tell whether the key list names a key. No key list names each key."""
    if key_list is None:
        return True

    return any(row["key"] == key for row in key_list)


def unnamed_hint(key: str, key_list: list) -> str:
    """
    Purpose: Tell what the game draws for a key that it does not name.

    Entry:
        key_list does not name key as an asset key.

    Exit/Returns:
        Returns the warning. When key is the owner of other asset keys,
        for example an object kind, the warning names those keys.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    drawn_as = sorted({row["key"] for row in key_list
                       if row["owner"] == key and row["key"] != key})
    warning = "The game names no entity with the asset key %s. " % key

    if drawn_as:
        return warning + "In the game, %s draws with the asset key %s." % (
            key, ", ".join(drawn_as))

    return warning + ("The client draws the model only if the client names "
                      "the key, for example as a family shape.")


# ─── Private helper routines: the preview and the write ──────────────────────

def record_path_of(plan: Plan) -> str:
    """Give the path of the model record that the plan writes."""
    return os.path.join(paths.MODELS_DIR, plan.family,
                        plan.asset_key + paths.MODEL_RECORD_SUFFIX)


def _model_record(plan: Plan) -> PlannedFile:
    """Give the model record of a plan that is no export."""
    nearest = is_palette(plan.model_file)
    text = fetch.render_model_record(plan.source_id, plan.model_file,
                                     plan.aliases, plan.variant_of, nearest)

    return PlannedFile(shown(record_path_of(plan)), "", text)


def _preview_new_source(plan: Plan) -> list:
    """Give the files of a plan with a new source: an upload or a download."""
    directory = os.path.join(paths.SOURCES_DIR, plan.source_id)
    record = os.path.join(directory, paths.SOURCE_RECORD_NAME)
    text = fetch.render_source_record(plan.fields) + _SEAL_NOTE + "\n"

    return [PlannedFile(shown(directory) + "/", plan.source_note),
            PlannedFile(shown(record), "", text), _model_record(plan)]


def _preview_kept_source(plan: Plan) -> list:
    """Give the files of a plan with a source that is in sources/."""
    directory = os.path.join(paths.SOURCES_DIR, plan.source_id)

    return [PlannedFile(shown(directory) + "/", _KEPT_NOTE),
            _model_record(plan)]


def _preview_export(plan: Plan) -> list:
    """Give the files of an export, as figure.py writes them."""
    rows = figure.import_preview(plan.family, plan.asset_key, plan.upload,
                                 plan.fields.author)
    planned = [PlannedFile(shown(path), note, text)
               for path, note, text in rows]
    directory = planned[0]

    # The first row is the source directory. A directory ends in "/", as
    # the other origins show it.
    planned[0] = PlannedFile(directory.path + "/", directory.note)

    return planned


def _write_record(plan: Plan) -> str:
    """Write the model record of a plan that is no export."""
    nearest = is_palette(plan.model_file)

    return fetch.write_model_record(
        plan.family, plan.asset_key, plan.source_id, plan.model_file,
        plan.aliases, plan.variant_of, nearest)


def _write_upload(plan: Plan) -> list:
    """Copy the upload in as a new source, then write the model record."""
    directory = fetch.fetch_file(plan.upload, plan.source_id, plan.fields)

    return [directory, _write_record(plan)]


def _write_polyhaven(plan: Plan) -> list:
    """
    Download the Poly Haven model as a new source, then write the model
    record. A plan with no file list reads the API again.
    """
    model = plan.polyhaven if plan.polyhaven.files else None
    directory = fetch.fetch_polyhaven(plan.polyhaven.asset_id, model)

    return [directory, _write_record(plan)]


def _write_source(plan: Plan) -> list:
    """Keep a source that is in sources/ already, and write the record."""
    return [_write_record(plan)]


def _write_export(plan: Plan) -> list:
    """Bring an export in through figure.py: the source and the record."""
    record = figure.import_model(plan.family, plan.asset_key, plan.upload,
                                 plan.fields.author)
    directory = os.path.join(paths.SOURCES_DIR, plan.source_id)

    return [directory, record]


# The preview and the write of each origin. A fifth origin is one more row
# in each table, and one more row in ORIGIN_LABELS.
_PREVIEWS: dict = {
    ORIGIN_FILE: _preview_new_source,
    ORIGIN_POLYHAVEN: _preview_new_source,
    ORIGIN_SOURCE: _preview_kept_source,
    ORIGIN_EXPORT: _preview_export,
}

_WRITERS: dict = {
    ORIGIN_FILE: _write_upload,
    ORIGIN_POLYHAVEN: _write_polyhaven,
    ORIGIN_SOURCE: _write_source,
    ORIGIN_EXPORT: _write_export,
}


# ─── Public routines: the preview and the write ──────────────────────────────

def export_plan(upload: str, author: str, family: str,
                asset_key: str) -> Plan:
    """
    Purpose: Make the plan of an export of art made here.

    Entry:
        No conditions. figure.import_problem tells whether it can go on.

    Exit/Returns:
        Returns the plan. Its source is SOURCE_PREFIX and the key, and its
        model file is the key and the suffix of the upload.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    filename = figure.import_filename(asset_key, upload)
    fields = fetch.SourceFields(
        title=figure.import_title(asset_key), author=author,
        url=figure.OWNED_URL, site=figure.OWNED_SITE,
        license=licenses.OWNED_LICENSE)

    return Plan(origin=ORIGIN_EXPORT, upload=upload, fields=fields,
                source_id=figure.source_id_for(asset_key),
                name_hint=questions.name_of(upload), model_files=(filename,),
                model_file=filename, family=family, asset_key=asset_key)


def preview(plan: Plan) -> list:
    """
    Purpose: Give each file that the write of a plan makes or keeps.

    Entry:
        Every answer of the plan passed its check.

    Exit/Returns:
        Returns the PlannedFile rows, in the order of the write. Writes
        nothing.

    Module Globals:
        _PREVIEWS read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    previewer = _PREVIEWS[plan.origin]

    return previewer(plan)


def write(plan: Plan) -> list:
    """
    Purpose: Write the source of a plan and its model record.

    Entry:
        Every answer of the plan passed its check, and the person
        confirmed it.

    Exit/Returns:
        Returns the paths written, the model record last. Raises
        fetch.FetchError, sources.SourceError or figure.FigureError when a
        write fails.

    Module Globals:
        _WRITERS read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    writer = _WRITERS[plan.origin]

    return writer(plan)
