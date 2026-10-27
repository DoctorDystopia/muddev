"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/25/2026
Description: The model wizard. `python -m assets.pipeline add` asks one
             question at a time, and adds one model to the pipeline. It does
             steps 1 to 4 of "Add a model" in assets/README.md, with no TODO
             to fill in later.

             THREE ORIGINS:
               1. A file, a folder or a .zip on this machine. Enter at the
                  path question opens a file dialog.
               2. A Poly Haven model. The API gives each field of the source
                  record.
               3. A source that is in sources/ already. One pack can feed
                  many models.

             THE QUESTIONS, in this order:
               1. The origin.
               2. For a new source: the license, the credit, the source id.
               3. The model file in the source.
               4. The family and the asset key. The wizard first shows each
                  asset key that the game names and no model draws yet. A
                  number picks one.
               5. The aliases, and the base of a model variant.

             AN ASSET KEY THAT THE GAME DOES NOT NAME GETS A WARNING
             (10/25/2026). The client then draws the model nowhere, and
             nothing says so. The bench of 10/25/2026 went in as
             gunsmith_bench, which is its object kind. The game draws it as
             gunbench. The key list file (paths.KEY_LIST_PATH) gives each key
             that the server names. The server writes it, because this
             process has no Django. The client names some keys too, for
             example a family shape. Thus, the warning asks, and a yes keeps
             the key.

             THE WIZARD WRITES NOTHING BEFORE THE CONFIRM. It shows the
             text of each record, and it writes only after a yes. Ctrl+C at
             any question before that leaves the disk as it was.

             THE WIZARD DECIDES NO RULE. The license gate, the key pattern,
             the record text, the seal and the family budgets belong to the
             modules that own them. The wizard reads them, so a question
             cannot accept what the build refuses.

             The build question comes last. __main__ runs the build, as it
             does for figure-model.

             The questions themselves (questions.py) are shared with the
             sound wizard, assets/audio/wizard.py.

             Reads and writes files only. It touches no database.
"""

import json
import os
import re
import zipfile
from dataclasses import dataclass
from typing import Callable

from assets.pipeline import (blender, budgets, build, fetch, figure, licenses,
                             paths, questions, records, sources)
from assets.pipeline.questions import INDENT, Console


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass(frozen=True)
class WizardResult:
    """
    What the wizard wrote. build is True when the person asked for a build
    now and this machine can build.
    """

    asset_key: str
    record_path: str
    build: bool


class KeyListError(Exception):
    """The key list file is not there, or it does not read."""


# ─── Private constant definitions ────────────────────────────────────────────

@dataclass
class _Plan:
    """
    The answers so far.

    origin: the row of _ORIGINS.
    upload: the path of a file origin.
    polyhaven: the model of a Poly Haven origin.
    fields: the record of a new source, or None.
    source_note: what the write does to the source.
    name_hint: the name of the download, for the defaults.
    """

    origin: int = 0
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


# The newest format of the key list file that the wizard reads, and the
# fields of one row. systems/interface/statefeed/key_list.py writes them.
_KEY_LIST_FORMAT: int = 1
_KEY_LIST_FIELDS: tuple = ("key", "owner", "kind", "name")

# One row of the offered asset keys: the key and its kind, each in a column
# as wide as its longest text, then the name, then the worn look note.
_OFFER_LABEL: str = "%-*s  %-*s  %s%s"
_OFFER_HINT: str = "Type the key of one of them."

# An item with a worn look draws on the figure with no served model. A
# served model takes the place of that look in the hand.
_WORN_LOOK_NOTE: str = "  (it has a worn look)"

# Enough of a .txt file to read the picoCAD header.
_HEAD_CHARS: int = 16

# A free default source id gets the first free number in this range.
_FIRST_COPY: int = 2
_LAST_COPY: int = 99

_ZIP_SUFFIX: str = ".zip"
_MODEL_SUFFIXES: tuple = (blender.GLTF_SUFFIXES + blender.BLENDER_SUFFIXES
                          + (build.PICOCAD_SUFFIX,))

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

_BUILD_COMMAND: str = "../evenv/Scripts/python.exe -m assets.pipeline build %s"
_DIALOG_TITLE: str = "Choose a 3D model, a folder of one, or a .zip"
_DIALOG_MODELS: str = "3D models and .zip files"

_STOPPED: str = "  Stopped. Nothing was written."

# The columns of a row of _ORIGINS.
_ROW_LABEL: int = 0
_ROW_ASKER: int = 1
_ROW_WRITER: int = 2


# ─── Private helper routines: names and paths ────────────────────────────────

def _shown(path: str) -> str:
    """Give a path relative to assets/, with forward slashes, if it can."""
    try:
        relative = os.path.relpath(path, paths.ASSETS_DIR)
    except ValueError:
        return path

    return relative.replace(os.sep, "/")


def _site_for(url: str) -> str:
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
        _MODEL_SUFFIXES, build.PICOCAD_SUFFIX, build.PICOCAD_HEADER
        read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    suffix = os.path.splitext(name)[1].lower()
    junk = _is_junk(name)

    if junk or suffix not in _MODEL_SUFFIXES:
        return False

    if suffix != build.PICOCAD_SUFFIX:
        return True

    head = read_head()

    return head.startswith(build.PICOCAD_HEADER)


def _is_palette(name: str) -> bool:
    """Tell whether the texture of a model file is always a palette."""
    suffix = os.path.splitext(name)[1].lower()

    return suffix in blender.PALETTE_SUFFIXES


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


def _folder_model_files(folder: str) -> tuple:
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


def _upload_model_files(path: str) -> tuple:
    """
    Purpose: Name each model file that a copy of one upload would hold.

    Entry:
        path exists.

    Exit/Returns:
        Returns the paths that a model record can name after fetch_file
        copies path in, sorted.

    Module Globals:
        _ZIP_SUFFIX read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    if path.lower().endswith(_ZIP_SUFFIX):
        return _zip_model_files(path)

    if os.path.isdir(path):
        return _folder_model_files(path)

    name = os.path.basename(path)
    is_model = _is_model_file(name, lambda: _head_of_file(path))

    return (name,) if is_model else ()


def _pick_model_file() -> str:
    """Open the file dialog on the model files and the .zip files."""
    suffixes = _MODEL_SUFFIXES + (_ZIP_SUFFIX,)
    chosen = questions.open_file_dialog(_DIALOG_TITLE, _DIALOG_MODELS,
                                        suffixes)

    return chosen


# ─── Private helper routines: a new source from a file ───────────────────────

def _ask_upload(console: Console) -> tuple:
    """
    Purpose: Ask for the path of an upload until it holds a model file.

    Entry:
        No conditions.

    Exit/Returns:
        Returns (path, its model files). Enter at the question opens the
        file dialog.

    Module Globals:
        questions.PROMPT, INDENT, _MODEL_SUFFIXES read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    readable = " ".join(_MODEL_SUFFIXES)
    console.say("")
    console.say("Type the path of the file, the folder or the .zip. You can "
                "drag it here. Press Enter to open a file dialog.")

    while True:
        typed = console.ask(questions.PROMPT)
        path = questions.clean_path(typed)

        if not path:
            path = console.pick_file()

        if not path:
            console.say(INDENT + "No file was chosen. Type a path.")
            continue

        if not os.path.exists(path):
            console.say(INDENT + "%s does not exist." % path)
            continue

        found = _upload_model_files(path)

        if found:
            return path, found

        console.say(INDENT + "%s holds no model file that the build reads: "
                    "%s, or a .zip of them." % (path, readable))


def _license_note(terms: licenses.LicenseTerms) -> str:
    """Give what one allowed license asks of a model, after its name."""
    note = ""

    if terms.attribution:
        note += ". The credits box must name the author"

    if terms.local_only:
        note += ". Git keeps none of its files (a local source)"

    return note


def _ask_license(console: Console) -> tuple:
    """Ask for the license of a new source: (SPDX id, exception)."""
    spdx, exception = questions.ask_license(
        console, "Which license does the download page give? On itch.io, "
        "each page has its own.", "Why can Blackout serve it? The check "
        "shows this reason on each run.", _license_note)

    return spdx, exception


def _ask_credits(console: Console, spdx: str, exception: str,
                 name_hint: str) -> fetch.SourceFields:
    """
    Purpose: Ask for the credit fields of a new source record.

    Entry:
        spdx and exception came from _ask_license.

    Exit/Returns:
        Returns the SourceFields. A local_only license gives a local source.

    Module Globals:
        figure.DEFAULT_AUTHOR, figure.OWNED_URL read.

    Notes:
        Art made for Blackout takes the author and the URL of figure-model
        as the defaults.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    owned = spdx == licenses.OWNED_LICENSE
    terms = licenses.terms_for(spdx)
    author_default = figure.DEFAULT_AUTHOR if owned else ""
    url_default = figure.OWNED_URL if owned else ""
    title_default = questions.as_title(name_hint)
    title = questions.ask_text(console, "The title of the model.",
                               title_default, questions.required)
    author = questions.ask_text(console, "Who made it? The credits box shows "
                                "this name.", author_default,
                                questions.required)
    url = questions.ask_text(console, "The URL of the download page.",
                             url_default, questions.required)
    site_default = _site_for(url)
    site = questions.ask_text(console, "The site of the download.",
                              site_default, questions.required)
    notes = questions.ask_text(console, "Notes for the next person, for "
                               "example the name of the .zip. Press Enter "
                               "for none.")

    return fetch.SourceFields(title=title, author=author, url=url, site=site,
                              license=spdx, notes=notes, exception=exception,
                              local=terms.local_only)


def _source_exists(source_id: str) -> bool:
    """Tell whether sources/ has an entry with this name."""
    directory = os.path.join(paths.SOURCES_DIR, source_id)

    return os.path.exists(directory)


def _new_source_problem(value: str) -> str:
    """Refuse a source id that is no key, or that sources/ has already."""
    fits = records.is_key(value)
    exists = fits and _source_exists(value)

    if not fits:
        return "A source id uses only a-z, 0-9 and _, with a letter first."

    if exists:
        return "sources/%s exists already. Type another one." % value

    return ""


def _free_source_id(wanted: str) -> str:
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
        problem = _new_source_problem(candidate)

        if wanted and not problem:
            return candidate

    return ""


def _ask_source_id(console: Console, site: str, name_hint: str) -> str:
    """
    Purpose: Ask for the source id of a new source.

    Entry:
        site is the site of the source record.

    Exit/Returns:
        Returns a free source id. The default is the first word of the
        site and the name of the download: itch_rusty_sword.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    prefix = site.split(".")[0]
    wanted = questions.as_key("%s_%s" % (prefix, name_hint))
    default = _free_source_id(wanted)

    return questions.ask_text(console, "The source id: the name of its "
                              "directory in sources/.", default,
                              _new_source_problem)


def _ask_file_origin(console: Console, _all_records: list) -> _Plan:
    """
    Purpose: Ask the questions of a new source from a file, a folder or a
    .zip.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the plan, with the source and its model files.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    upload, found = _ask_upload(console)
    name_hint = questions.name_of(upload)
    spdx, exception = _ask_license(console)
    fields = _ask_credits(console, spdx, exception, name_hint)
    source_id = _ask_source_id(console, fields.site, name_hint)
    note = "a copy of %s" % upload

    if fields.local:
        note += ". Git keeps only its source record"

    return _Plan(upload=upload, fields=fields, source_id=source_id,
                 source_note=note, name_hint=name_hint, model_files=found)


# ─── Private helper routines: the other origins ──────────────────────────────

def _ask_polyhaven_origin(console: Console, _all_records: list) -> _Plan:
    """
    Purpose: Ask for a Poly Haven model, and read what the API gives.

    Entry:
        No conditions. The API needs the network.

    Exit/Returns:
        Returns the plan. Returns None when the source exists already,
        because the person can choose that source as an origin.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    while True:
        typed = questions.ask_text(console, "The Poly Haven id of the model: "
                                   "the end of its page URL, for example "
                                   "wooden_crate_01.",
                                   check=questions.required)
        asset_id = typed.rstrip("/").split("/")[-1]
        source_id = fetch.polyhaven_source_id(asset_id)
        fits = records.is_key(source_id)
        exists = _source_exists(source_id)

        if not fits:
            console.say(INDENT + "A Poly Haven id uses only a-z, 0-9 and _.")
            continue

        if exists:
            console.say(INDENT + "sources/%s exists already. Choose it as a "
                        "source that is in sources/." % source_id)
            return None

        try:
            model = fetch.read_polyhaven(asset_id)
        except fetch.FetchError as problem:
            console.say(INDENT + str(problem))
            continue

        console.say(INDENT + "Found %s, by %s." % (model.title, model.author))
        fields = fetch.polyhaven_fields(model)
        note = "a download of %d files from Poly Haven" % len(model.files)

        return _Plan(polyhaven=model, fields=fields, source_id=source_id,
                     source_note=note, name_hint=asset_id,
                     model_files=(model.main_file,))


def _source_label(source_id: str, counts: dict) -> str:
    """Give the row of one source: its license, and the records it feeds."""
    try:
        source = sources.load_source(source_id)
    except sources.SourceError:
        return "%s  (its source.toml does not load)" % source_id

    used = counts.get(source_id, 0)

    return "%s  (%s, model records: %d)" % (source_id, source.license, used)


def _source_problem(source: sources.Source) -> str:
    """Tell why no model of one source can be chosen here, or give ""."""
    absent = sources.files_absent(source)
    found = () if absent else _folder_model_files(source.directory)

    if absent:
        return "The files of this local source are not on this machine."

    if not found:
        return "%s holds no model file that the build reads." % (
            source.source_id)

    return ""


def _source_usable(console: Console, source_id: str) -> bool:
    """
    Purpose: Tell whether the person can take a model from one source.

    Entry:
        source_id is a directory in sources/.

    Exit/Returns:
        Returns False for a source that does not load or has no model
        file. A source that fails the license gate needs a yes.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    try:
        source = sources.load_source(source_id)
    except sources.SourceError as problem:
        console.say(INDENT + str(problem))
        return False

    problem = _source_problem(source)
    refusal = sources.gate_problem(source)

    if problem:
        console.say(INDENT + problem)
        return False

    if not refusal:
        return True

    console.say(INDENT + "The build refuses this source until you correct "
                "its source.toml: " + refusal)
    use_it = questions.ask_yes(console, "Use it anyway?", False)

    return use_it


def _ask_source_origin(console: Console, all_records: list) -> _Plan:
    """
    Purpose: Ask the person to choose a source that is in sources/ already.

    Entry:
        all_records holds every loaded model record.

    Exit/Returns:
        Returns the plan. Returns None when sources/ is empty.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    source_ids = sources.list_source_ids()
    counts = {}

    for record in all_records:
        counts[record.source_id] = counts.get(record.source_id, 0) + 1

    if not source_ids:
        console.say(INDENT + "sources/ holds no source. Choose another "
                    "origin.")
        return None

    labels = [_source_label(source_id, counts) for source_id in source_ids]
    usable = False

    while not usable:
        chosen = questions.ask_choice(console, "Which source holds the "
                                      "model?", labels)
        source_id = source_ids[chosen]
        usable = _source_usable(console, source_id)

    directory = os.path.join(paths.SOURCES_DIR, source_id)
    found = _folder_model_files(directory)

    return _Plan(source_id=source_id, model_files=found)


# ─── Private helper routines: the key list ───────────────────────────────────

def _checked_rows(content, shown: str) -> list:
    """
    Purpose: Give the rows of a parsed key list file.

    Entry:
        content is the parsed JSON. shown names the file in a problem.

    Exit/Returns:
        Returns the rows. Raises KeyListError for a file with no format
        number or no rows, a newer format, or a row with a missing field.

    Module Globals:
        _KEY_LIST_FORMAT, _KEY_LIST_FIELDS read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    whole = isinstance(content, dict)
    version = content.get("format") if whole else None
    rows = content.get("keys") if whole else None
    shaped = isinstance(version, int) and isinstance(rows, list)

    if not shaped:
        raise KeyListError("%s has no format number or no rows." % shown)

    if version > _KEY_LIST_FORMAT:
        raise KeyListError("%s has format %d. The wizard reads format %d."
                           % (shown, version, _KEY_LIST_FORMAT))

    for row in rows:
        complete = isinstance(row, dict) and all(
            isinstance(row.get(field), str) for field in _KEY_LIST_FIELDS)

        if not complete:
            raise KeyListError("%s has a row with a missing field: %r."
                               % (shown, row))

    return rows


def _load_key_list(console: Console):
    """
    Purpose: Read the key list for the asset key questions.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the rows. Returns None when the file does not read. Then
        the wizard offers no key, and it warns about no key.

    Module Globals:
        paths.KEY_LIST_PATH read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    try:
        rows = read_key_list(paths.KEY_LIST_PATH)
    except KeyListError as problem:
        console.say("")
        console.say("%s The wizard cannot check the asset key." % problem)
        return None

    return rows


def _named_rows(key_list: list) -> dict:
    """Map each asset key of the key list to its first row."""
    named = {}

    for row in key_list:
        named.setdefault(row["key"], row)

    return named


def _worn_look_keys() -> set:
    """Name each asset key that has a worn look in figure/looks/."""
    folder = paths.FIGURE_LOOKS_DIR
    suffix = paths.FIGURE_FILE_SUFFIX
    present = os.path.isdir(folder)
    names = os.listdir(folder) if present else []

    return {name[:-len(suffix)] for name in names if name.endswith(suffix)}


def _offered_keys(key_list: list, owners: dict, family_keys: set,
                  looks: set) -> list:
    """
    Purpose: Give the rows of each asset key that the game names and no
    model record has.

    Entry:
        owners maps each key that a record has to that record. family_keys
        holds each key of the records of the chosen family. looks holds
        each key with a worn look.

    Exit/Returns:
        Returns one row for each key. A kind that the chosen family draws
        already comes first. A key with no worn look comes before a key
        with one. Then the rows go by kind, then by key.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    named = _named_rows(key_list)
    drawn = {named[key]["kind"] for key in family_keys if key in named}
    free = [row for key, row in named.items() if key not in owners]

    return sorted(free, key=lambda row: (row["kind"] not in drawn,
                                         row["key"] in looks,
                                         row["kind"], row["key"]))


def _show_offer(console: Console, offered: list, looks: set) -> None:
    """Show the offered asset keys, with a number on each."""
    key_width = max(len(row["key"]) for row in offered)
    kind_width = max(len(row["kind"]) for row in offered)
    labels = [_OFFER_LABEL % (key_width, row["key"], kind_width, row["kind"],
                              row["name"],
                              _WORN_LOOK_NOTE if row["key"] in looks else "")
              for row in offered]
    console.say("")
    console.say("The game names these asset keys, and no model record draws "
                "them yet:")
    questions.show_rows(console, labels, list(range(len(labels))), _OFFER_HINT)


def _unnamed_hint(key: str, key_list: list) -> str:
    """
    Purpose: Tell what the game draws for a key that it does not name.

    Entry:
        key_list does not name key as an asset key.

    Exit/Returns:
        Returns one sentence. When key is the owner of other asset keys,
        for example an object kind, the sentence names those keys.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    drawn_as = sorted({row["key"] for row in key_list
                       if row["owner"] == key and row["key"] != key})

    if drawn_as:
        return "In the game, %s draws with the asset key %s." % (
            key, ", ".join(drawn_as))

    return ("The client draws the model only if the client names the key, "
            "for example as a family shape.")


def _keep_key(console: Console, key: str, key_list) -> bool:
    """
    Purpose: Ask about an asset key that the game does not name.

    Entry:
        key_list is the rows, or None when the key list does not read.

    Exit/Returns:
        Returns True for a key that the key list names, and for any key
        when there is no key list. For another key, it gives a warning and
        returns the answer to "Keep it?". Enter gives no.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    if key_list is None:
        return True

    named = {row["key"] for row in key_list}

    if key in named:
        return True

    hint = _unnamed_hint(key, key_list)
    console.say(INDENT + "The game names no entity with the asset key %s. "
                "%s" % (key, hint))
    keep = questions.ask_yes(console, "Keep %s?" % key, False)

    return keep


# ─── Private helper routines: the model record ───────────────────────────────

def _ask_model_file(console: Console, plan: _Plan) -> str:
    """
    Purpose: Ask which file of the source is the model.

    Entry:
        plan.model_files is not empty.

    Exit/Returns:
        Returns the file. With one model file, no question comes.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    files = list(plan.model_files)

    if len(files) == 1:
        console.say("")
        console.say("The model file is %s." % files[0])
        return files[0]

    chosen = questions.ask_choice(console, "Which file is the model? The "
                                  "source holds %d model files." % len(files),
                                  files)

    return files[chosen]


def _families() -> list:
    """Name each family: each one with a budget, and each in models/."""
    found = set(budgets.FAMILY_BUDGETS)
    present = os.path.isdir(paths.MODELS_DIR)
    names = os.listdir(paths.MODELS_DIR) if present else []

    for name in names:
        folder = os.path.join(paths.MODELS_DIR, name)

        if os.path.isdir(folder):
            found.add(name)

    return sorted(found)


def _family_label(family: str) -> str:
    """Give the row of one family: its budget, with no reason."""
    described = budgets.describe_budget(family)

    return described.split(_BUDGET_REASON)[0]


def _new_family_problem(value: str) -> str:
    """Refuse a family that is no key."""
    fits = records.is_key(value)

    return "" if fits else ("A family uses only a-z, 0-9 and _, with a "
                            "letter first.")


def _ask_family(console: Console) -> str:
    """
    Purpose: Ask for the family of the model record.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a family. A new family gets the budget of an unlisted
        family.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    families = _families()
    labels = [_family_label(family) for family in families]
    labels.append("A new family. It gets the budget of an unlisted family")
    chosen = questions.ask_choice(console, "Which family is it? The family "
                                  "sets the budget of the served file.",
                                  labels)

    if chosen < len(families):
        return families[chosen]

    return questions.ask_text(console, "The name of the new family.",
                              check=_new_family_problem)


def _key_problem(value: str, owners: dict) -> str:
    """Refuse an asset key that is no key, or that a record has already."""
    fits = records.is_key(value)
    owner = owners.get(value, "")

    if not fits:
        return "An asset key uses only a-z, 0-9 and _, with a letter first."

    if owner:
        return "%s has the key %s already." % (_shown(owner), value)

    return ""


def _default_key(plan: _Plan, owners: dict) -> str:
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
    taken = _key_problem(wanted, owners)

    return "" if taken else wanted


def _typed_key_problem(value: str, offered: list, owners: dict) -> str:
    """Accept a number of the offered list, or a free asset key."""
    picked = questions.picked_row(value, offered)

    if picked:
        return ""

    return _key_problem(value, owners)


def _ask_asset_key(console: Console, plan: _Plan, all_records: list,
                   key_list) -> str:
    """
    Purpose: Ask for the asset key of the new model record.

    Entry:
        all_records holds every loaded model record. key_list is the rows
        of the key list, or None.

    Exit/Returns:
        Returns a free asset key. A key that the game does not name needs a
        yes.

    Module Globals:
        None.

    Methodology:
        1. Show each asset key that the game names and no record has.
        2. Ask for a number of that list, or a key.
        3. Warn about a key that the game does not name, and ask again
           after a no.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    owners = {key: record.record_path for record in all_records
              for key in record.keys}
    family_keys = {key for record in all_records
                   if record.family == plan.family for key in record.keys}
    looks = _worn_look_keys()
    rows = [] if key_list is None else _offered_keys(key_list, owners,
                                                     family_keys, looks)
    offered = [row["key"] for row in rows]
    default = _default_key(plan, owners)
    question = "The asset key: the name of the model in the game and in the "
    question += "client."

    if offered:
        _show_offer(console, rows, looks)
        question += " Type a number from the list, or a key."

    while True:
        typed = questions.ask_text(console, question, default,
                                   lambda value: _typed_key_problem(
                                       value, offered, owners))
        key = questions.picked_row(typed, offered) or typed
        kept = _keep_key(console, key, key_list)

        if kept:
            return key


def _split_aliases(text: str) -> tuple:
    """Give each alias of a typed list, in order."""
    parts = [part.strip() for part in text.split(_ALIAS_SEPARATOR)]

    return tuple(part for part in parts if part)


def _aliases_problem(text: str, asset_key: str, owners: dict) -> str:
    """Refuse an alias that is no free key, the asset key, or a repeat."""
    aliases = _split_aliases(text)

    if len(set(aliases)) != len(aliases):
        return "The list holds one alias two times."

    for alias in aliases:
        problem = _key_problem(alias, owners)

        if alias == asset_key:
            return "%s is the asset key itself." % alias

        if problem:
            return problem

    return ""


def _ask_aliases(console: Console, asset_key: str, owners: dict,
                 key_list) -> tuple:
    """
    Purpose: Ask for more asset keys that draw the same model.

    Entry:
        owners maps each asset key and alias on disk to its record.
        key_list is the rows of the key list, or None.

    Exit/Returns:
        Returns the aliases. Enter gives none. An alias that the game does
        not name needs a yes, as the asset key does.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    while True:
        text = questions.ask_text(console, "More asset keys that draw the "
                                  "same model, with a comma between two. "
                                  "Press Enter for none.",
                                  check=lambda value: _aliases_problem(
                                      value, asset_key, owners))
        aliases = _split_aliases(text)
        kept = all(_keep_key(console, alias, key_list) for alias in aliases)

        if kept:
            return aliases


def _variant_problem(value: str, asset_key: str, bases: dict) -> str:
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


def _ask_variant(console: Console, asset_key: str, all_records: list) -> str:
    """Ask for the base of a model variant. Enter gives no base."""
    bases = {record.asset_key: record for record in all_records}
    variant_of = questions.ask_text(console, "Is it a second look of another "
                                    "model (a model variant)? Type the asset "
                                    "key of that model. Press Enter for no.",
                                    check=lambda value: _variant_problem(
                                        value, asset_key, bases))

    return variant_of


# ─── Private helper routines: the confirm and the write ──────────────────────

def _show_plan(console: Console, plan: _Plan) -> None:
    """
    Purpose: Show each file that the wizard is about to write, with its
    text.

    Entry:
        Every question of the plan has its answer.

    Exit/Returns:
        Returns None.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    source_dir = os.path.join(paths.SOURCES_DIR, plan.source_id)
    source_record = os.path.join(source_dir, paths.SOURCE_RECORD_NAME)
    record_path = os.path.join(paths.MODELS_DIR, plan.family,
                               plan.asset_key + paths.MODEL_RECORD_SUFFIX)
    nearest = _is_palette(plan.model_file)
    model_text = fetch.render_model_record(plan.source_id, plan.model_file,
                                           plan.aliases, plan.variant_of,
                                           nearest)
    console.say("")
    console.say("The plan:")

    if plan.fields is None:
        console.say(INDENT + "%s/ stays as it is" % _shown(source_dir))
    else:
        source_text = fetch.render_source_record(plan.fields)
        console.say(INDENT + "%s/  %s" % (_shown(source_dir),
                                           plan.source_note))
        console.say(INDENT + _shown(source_record))
        questions.show_text(console, source_text)
        questions.show_text(console, "[files]  (the seal writes the hash of "
                            "each file)")

    console.say(INDENT + _shown(record_path))
    questions.show_text(console, model_text)


def _write_upload(plan: _Plan) -> str:
    """Copy the upload in as a new source, and give its directory."""
    directory = fetch.fetch_file(plan.upload, plan.source_id, plan.fields)

    return directory


def _write_polyhaven(plan: _Plan) -> str:
    """Download the Poly Haven model as a new source, and give its
    directory."""
    directory = fetch.fetch_polyhaven(plan.polyhaven.asset_id, plan.polyhaven)

    return directory


def _write_nothing(_plan: _Plan) -> str:
    """Keep a source that is in sources/ already as it is."""
    return ""


def _ask_build(console: Console, plan: _Plan) -> bool:
    """
    Purpose: Ask whether to build the new model now.

    Entry:
        The model record is on disk.

    Exit/Returns:
        Returns True for a build. Returns False with no question when this
        machine cannot build the model.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    problem = build.tools_problem(plan.model_file)

    if problem:
        console.say("")
        console.say("This machine cannot build the model now: %s." % problem)
        return False

    wanted = questions.ask_yes(console, "Build %s now?" % plan.asset_key, True)

    return wanted


# The origins of a model: the label, the questions, and the write of the
# source. A fourth origin is one more row.
_ORIGINS: tuple = (
    ("A file, a folder or a .zip on this machine", _ask_file_origin,
     _write_upload),
    ("A Poly Haven model (CC0). The wizard downloads it",
     _ask_polyhaven_origin, _write_polyhaven),
    ("A source that is in sources/ already", _ask_source_origin,
     _write_nothing),
)


def _ask_origin(console: Console, all_records: list) -> _Plan:
    """
    Purpose: Ask where the model comes from, and ask the questions of that
    origin.

    Entry:
        all_records holds every loaded model record.

    Exit/Returns:
        Returns the plan. An origin that cannot go on asks this question
        again.

    Module Globals:
        _ORIGINS, _ROW_LABEL, _ROW_ASKER read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    labels = [row[_ROW_LABEL] for row in _ORIGINS]
    plan = None

    while plan is None:
        origin = questions.ask_choice(console, "Where does the model come "
                                      "from?", labels)
        asker = _ORIGINS[origin][_ROW_ASKER]
        plan = asker(console, all_records)

    plan.origin = origin

    return plan


def _ask_plan(console: Console):
    """
    Purpose: Ask every question, show the plan, and ask for the confirm.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the plan, or None for a no at the confirm. Raises
        records.RecordError when a model record on disk does not load.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    all_records = records.load_all()
    owners = {key: record.record_path for record in all_records
              for key in record.keys}
    console.say("Add a model. Press Ctrl+C at a question to stop. The wizard "
                "writes nothing before you confirm.")
    plan = _ask_origin(console, all_records)
    plan.model_file = _ask_model_file(console, plan)
    plan.family = _ask_family(console)
    key_list = _load_key_list(console)
    plan.asset_key = _ask_asset_key(console, plan, all_records, key_list)
    plan.aliases = _ask_aliases(console, plan.asset_key, owners, key_list)
    plan.variant_of = _ask_variant(console, plan.asset_key, all_records)
    _show_plan(console, plan)
    confirmed = questions.ask_yes(console, "Write these files?", True)

    return plan if confirmed else None


def _write(console: Console, plan: _Plan) -> str:
    """
    Purpose: Write the source of the plan and its model record.

    Entry:
        The person confirmed the plan.

    Exit/Returns:
        Returns the path of the model record. Raises fetch.FetchError or
        sources.SourceError when a write fails.

    Module Globals:
        _ORIGINS, _ROW_WRITER read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    writer = _ORIGINS[plan.origin][_ROW_WRITER]
    directory = writer(plan)
    console.say("")

    if directory:
        console.say(INDENT + "wrote %s" % _shown(directory))

    nearest = _is_palette(plan.model_file)
    record_path = fetch.write_model_record(
        plan.family, plan.asset_key, plan.source_id, plan.model_file,
        plan.aliases, plan.variant_of, nearest)
    console.say(INDENT + "wrote %s" % _shown(record_path))

    return record_path


# ─── Public routines ─────────────────────────────────────────────────────────

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
    shown = _shown(path)

    if not os.path.isfile(path):
        raise KeyListError("%s is not there." % shown)

    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = json.load(handle)
    except (OSError, ValueError) as problem:
        raise KeyListError("%s does not read: %s." % (shown, problem))

    return _checked_rows(content, shown)


def run(console: Console = None):
    """
    Purpose: Ask the questions of the model wizard, and write what the
    answers give.

    Entry:
        console is None for the terminal, or a scripted Console.

    Exit/Returns:
        Returns the WizardResult. Returns None when the person stops or
        says no at the confirm, and then nothing was written. Raises
        records.RecordError, fetch.FetchError or sources.SourceError.

    Module Globals:
        _STOPPED read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    if console is None:
        console = Console(ask=input, say=print, pick_file=_pick_model_file)

    try:
        plan = _ask_plan(console)
    except (KeyboardInterrupt, EOFError):
        plan = None

    if plan is None:
        console.say("")
        console.say(_STOPPED)
        return None

    record_path = _write(console, plan)

    try:
        wanted = _ask_build(console, plan)
    except (KeyboardInterrupt, EOFError):
        wanted = False

    return WizardResult(asset_key=plan.asset_key, record_path=record_path,
                        build=wanted)


def next_steps(result: WizardResult, built: bool) -> list:
    """
    Purpose: Give the steps that come after the wizard, as lines to show.

    Entry:
        built is True when the build of the model passed.

    Exit/Returns:
        Returns the lines, numbered. A model that is not built gets the
        build command first.

    Module Globals:
        _BUILD_COMMAND, INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    record = _shown(result.record_path)
    steps = []

    if not built:
        steps.append("Build it from blackout/: "
                     + _BUILD_COMMAND % result.asset_key)

    steps.append("Run `evennia reload`, and look at the model in the "
                 "client.")
    steps.append("If it faces the wrong way or looks wrong, add a [fix] to "
                 "%s, and build again." % record)
    steps.append("Commit the source, the record, build.lock.json and the "
                 "served tree in one commit.")
    lines = ["", "Next:"]
    lines.extend("%s%d. %s" % (INDENT, number, step)
                 for number, step in enumerate(steps, start=1))

    return lines
