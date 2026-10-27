"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Put a new download into assets/sources/, with its source record,
             and write a new model record.

             POLY HAVEN has a public API. `fetch polyhaven <id>` downloads the
             1k glTF of a model, checks the MD5 that the API gives for each
             file, and fills in the whole source record: the author from the
             API, the license (always CC0). The API terms ask for a User-Agent
             that names the tool, and this module sends one.

             EVERY OTHER SITE (itch.io, Sketchfab, a Godot Asset Library pack)
             gives no license through an API, and on itch.io the license is
             different on each page. `fetch file` copies the download in
             (a .zip is unpacked) and writes a source record whose license
             is TODO. A TODO license fails the license gate, so the model
             cannot build until a person reads the page and fills it in.

             THE MODEL WIZARD (10/25/2026) asks a person for each field
             first. It gives them to fetch_file as SourceFields, and the
             record has no TODO. Before it writes a record, it shows the
             text from render_source_record and render_model_record. With
             read_polyhaven, it shows a Poly Haven model before the download.

             Every fetch ends with a seal, so the hashes describe the download
             exactly as it arrived.
"""

import datetime
import hashlib
import json
import os
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass, field

from assets.pipeline import paths, sources


# ─── Public constant definitions ─────────────────────────────────────────────

class FetchError(RuntimeError):
    """A download or a copy that could not complete."""


# The text of each field that a person must fill in.
TODO: str = "TODO"

# The site, the license and the source id prefix of a Poly Haven source.
POLYHAVEN_SITE: str = "polyhaven"
POLYHAVEN_LICENSE: str = "CC0-1.0"
POLYHAVEN_PREFIX: str = "polyhaven_"


@dataclass(frozen=True)
class SourceFields:
    """
    The fields of a source record that a person writes. The fetch adds
    `retrieved`, and the seal adds [files]. An empty notes or exception
    writes no line. local is True for a local source.
    """

    title: str
    author: str
    url: str
    site: str
    license: str
    notes: str = ""
    exception: str = ""
    local: bool = False


@dataclass(frozen=True)
class PolyHavenModel:
    """
    One Poly Haven model, as the API gives it, before the download.

    main_file is the glTF file that a model record names. files maps each
    path in the source to its API entry, with a `url` and an `md5`.
    """

    asset_id: str
    title: str
    author: str
    main_file: str
    files: dict = field(default_factory=dict)


# ─── Private constant definitions ────────────────────────────────────────────

_POLYHAVEN_API: str = "https://api.polyhaven.com"
_POLYHAVEN_PAGE: str = "https://polyhaven.com/a/%s"
_POLYHAVEN_TYPE_MODEL: int = 2
_POLYHAVEN_RESOLUTION: str = "1k"
_POLYHAVEN_FORMAT: str = "gltf"
_USER_AGENT: str = "Blackout-model-pipeline/1.0 (assets/pipeline/fetch.py)"
_TIMEOUT_SECONDS: int = 60
_ZIP_SUFFIX: str = ".zip"

_SOURCE_TEMPLATE: str = '''title     = "{title}"
author    = "{author}"
url       = "{url}"
site      = "{site}"
license   = "{license}"
retrieved = {retrieved}
'''
_NOTES_LINE: str = 'notes     = "%s"\n'
_EXCEPTION_LINE: str = 'exception = "%s"\n'
_LOCAL_LINE: str = "local     = true\n"

_MODEL_TEMPLATE: str = '''source = "{source_id}"
file   = "{file}"
'''
_ALIASES_LINE: str = "aliases = [%s]\n"
_VARIANT_LINE: str = 'variant_of = "%s"\n'
_NEAREST_FIX: str = '''
[fix]
# A palette: one texel for each colour. A mipmap mixes two colours.
filter = "nearest"
'''
_QUOTED: str = '"%s"'
_LIST_SEPARATOR: str = ", "


# ─── Private helper routines ─────────────────────────────────────────────────

def _download(url: str) -> bytes:
    """
    Purpose: Download one URL with the pipeline's User-Agent.

    Entry:
        url is an https URL.

    Exit/Returns:
        Returns the body. Raises FetchError on any network or HTTP failure.

    Module Globals:
        _USER_AGENT, _TIMEOUT_SECONDS read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as reply:
            body = reply.read()
    except OSError as problem:
        raise FetchError("could not download %s: %s" % (url, problem))

    return body


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
    Creation date: 10/25/2026
    """
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace('"', '\\"')

    return escaped


def _new_source_dir(source_id: str) -> str:
    """
    Purpose: Make the directory of a new source.

    Entry:
        source_id is a new directory name.

    Exit/Returns:
        Returns the new directory. Raises FetchError when it already exists,
        because a fetch never writes over a download.

    Module Globals:
        paths.SOURCES_DIR read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    directory = os.path.join(paths.SOURCES_DIR, source_id)

    if os.path.exists(directory):
        raise FetchError("%s already exists. Choose another source id"
                         % directory)

    os.makedirs(directory)

    return directory


def _write_source_record(directory: str, fields: SourceFields) -> None:
    """
    Purpose: Write a source record, then seal its files.

    Entry:
        directory holds the download.

    Exit/Returns:
        Returns None. For a local source, the seal writes its .gitignore.

    Module Globals:
        paths.SOURCE_RECORD_NAME read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    text = render_source_record(fields)
    record = os.path.join(directory, paths.SOURCE_RECORD_NAME)

    with open(record, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    source_id = os.path.basename(directory)
    source = sources.load_source(source_id)
    sources.seal(source)


def _polyhaven_files(asset_id: str) -> tuple:
    """
    Purpose: Name the files of the 1k glTF of one Poly Haven model.

    Entry:
        asset_id is a Poly Haven model.

    Exit/Returns:
        Returns (main file, {path: API entry}). Raises FetchError when the
        model has no 1k glTF.

    Module Globals:
        The _POLYHAVEN_* constants read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    body = _download("%s/files/%s" % (_POLYHAVEN_API, asset_id))
    listing = json.loads(body)

    try:
        formats = listing[_POLYHAVEN_FORMAT][_POLYHAVEN_RESOLUTION]
        entry = formats[_POLYHAVEN_FORMAT]
    except (KeyError, TypeError):
        raise FetchError("%s has no %s glTF on Poly Haven"
                         % (asset_id, _POLYHAVEN_RESOLUTION))

    main_file = os.path.basename(entry["url"])
    wanted = {main_file: entry}
    wanted.update(entry.get("include", {}))

    return main_file, wanted


# ─── Public routines ─────────────────────────────────────────────────────────

def render_source_record(fields: SourceFields) -> str:
    """
    Purpose: Give the text of a source record, with no [files] table.

    Entry:
        No conditions. A field can hold a quote or a backslash.

    Exit/Returns:
        Returns the text, with today as `retrieved`. The text escapes each
        field for TOML. An empty notes or exception gives no line.

    Module Globals:
        _SOURCE_TEMPLATE, _NOTES_LINE, _EXCEPTION_LINE, _LOCAL_LINE read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    today = datetime.date.today().isoformat()
    text = _SOURCE_TEMPLATE.format(
        title=_toml_text(fields.title), author=_toml_text(fields.author),
        url=_toml_text(fields.url), site=_toml_text(fields.site),
        license=_toml_text(fields.license), retrieved=today)

    if fields.notes:
        text += _NOTES_LINE % _toml_text(fields.notes)

    if fields.exception:
        text += _EXCEPTION_LINE % _toml_text(fields.exception)

    if fields.local:
        text += _LOCAL_LINE

    return text


def render_model_record(source_id: str, filename: str, aliases: tuple = (),
                        variant_of: str = "", nearest: bool = False) -> str:
    """
    Purpose: Give the text of a new model record.

    Entry:
        filename is a path in the source, with forward slashes. nearest is
        True for a palette texture.

    Exit/Returns:
        Returns the text. No aliases and no variant_of give no line. With
        nearest, the record has a [fix] with `filter = "nearest"`, and no
        other fix.

    Module Globals:
        _MODEL_TEMPLATE, _ALIASES_LINE, _VARIANT_LINE, _NEAREST_FIX,
        _QUOTED, _LIST_SEPARATOR read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    text = _MODEL_TEMPLATE.format(source_id=_toml_text(source_id),
                                  file=_toml_text(filename))

    if aliases:
        quoted = [_QUOTED % _toml_text(alias) for alias in aliases]
        text += _ALIASES_LINE % _LIST_SEPARATOR.join(quoted)

    if variant_of:
        text += _VARIANT_LINE % _toml_text(variant_of)

    if nearest:
        text += _NEAREST_FIX

    return text


def polyhaven_source_id(asset_id: str) -> str:
    """
    Purpose: Name the source of one Poly Haven model.

    Entry:
        asset_id is non-empty.

    Exit/Returns:
        Returns the source id.

    Module Globals:
        POLYHAVEN_PREFIX read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    return POLYHAVEN_PREFIX + asset_id


def read_polyhaven(asset_id: str) -> PolyHavenModel:
    """
    Purpose: Read what Poly Haven says about one model, with no download
    of its files.

    Entry:
        asset_id is a Poly Haven asset id, for example "wooden_crate_01".

    Exit/Returns:
        Returns the PolyHavenModel. Raises FetchError when the id is not a
        model, or has no 1k glTF.

    Module Globals:
        _POLYHAVEN_API, _POLYHAVEN_TYPE_MODEL read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    body = _download("%s/info/%s" % (_POLYHAVEN_API, asset_id))
    info = json.loads(body)

    if info.get("type") != _POLYHAVEN_TYPE_MODEL:
        raise FetchError("%s is not a Poly Haven model" % asset_id)

    main_file, wanted = _polyhaven_files(asset_id)
    authors = ", ".join(sorted(info.get("authors", {}))) or TODO

    return PolyHavenModel(asset_id=asset_id, title=info.get("name", asset_id),
                          author=authors, main_file=main_file, files=wanted)


def polyhaven_fields(model: PolyHavenModel) -> SourceFields:
    """
    Purpose: Give the source record of one Poly Haven model.

    Entry:
        model came from read_polyhaven.

    Exit/Returns:
        Returns the SourceFields. Poly Haven gives every field.

    Module Globals:
        _POLYHAVEN_PAGE, POLYHAVEN_SITE, POLYHAVEN_LICENSE read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    page = _POLYHAVEN_PAGE % model.asset_id

    return SourceFields(title=model.title, author=model.author, url=page,
                        site=POLYHAVEN_SITE, license=POLYHAVEN_LICENSE)


def fetch_polyhaven(asset_id: str, model: PolyHavenModel = None) -> str:
    """
    Purpose: Download one Poly Haven model as a new source.

    Entry:
        asset_id is a Poly Haven asset id. model came from read_polyhaven
        for that id, or is None.

    Exit/Returns:
        Returns the new source directory, polyhaven_<asset_id>. Raises
        FetchError when the id is not a model, has no 1k glTF, or a file
        fails its MD5.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    if model is None:
        model = read_polyhaven(asset_id)

    source_id = polyhaven_source_id(asset_id)
    directory = _new_source_dir(source_id)

    for relative, item in model.files.items():
        body = _download(item["url"])

        if hashlib.md5(body).hexdigest() != item["md5"]:
            raise FetchError("%s failed its MD5 check" % relative)

        target = os.path.join(directory, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)

        with open(target, "wb") as handle:
            handle.write(body)

    fields = polyhaven_fields(model)
    _write_source_record(directory, fields)

    return directory


def fetch_file(path: str, source_id: str, fields: SourceFields = None) -> str:
    """
    Purpose: Copy a downloaded file or folder in as a new source.

    Entry:
        path names a file, a folder, or a .zip. source_id is a new id.
        fields is the source record, or None.

    Exit/Returns:
        Returns the new source directory. With no fields, the record has
        TODO fields, and a TODO license fails the license gate until
        someone fills it in.

    Module Globals:
        _ZIP_SUFFIX, TODO read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    if not os.path.exists(path):
        raise FetchError("%s does not exist" % path)

    if fields is None:
        fields = SourceFields(title=TODO, author=TODO, url=TODO, site=TODO,
                              license=TODO)

    directory = _new_source_dir(source_id)

    if path.lower().endswith(_ZIP_SUFFIX):
        with zipfile.ZipFile(path) as archive:
            archive.extractall(directory)
    elif os.path.isdir(path):
        shutil.copytree(path, directory, dirs_exist_ok=True)
    else:
        shutil.copy2(path, directory)

    _write_source_record(directory, fields)

    return directory


def write_model_record(family: str, asset_key: str, source_id: str,
                       filename: str, aliases: tuple = (),
                       variant_of: str = "", nearest: bool = False) -> str:
    """
    Purpose: Write a new model record. Its only fix is the nearest filter
    of a palette, when nearest is True.

    Entry:
        source_id names an existing source that holds filename.

    Exit/Returns:
        Returns the path of the new record. Raises FetchError when the record
        exists already, or the source or the file does not.

    Module Globals:
        paths.MODELS_DIR, paths.MODEL_RECORD_SUFFIX read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    source = sources.load_source(source_id)
    target = os.path.join(paths.MODELS_DIR, family,
                          asset_key + paths.MODEL_RECORD_SUFFIX)

    if os.path.exists(target):
        raise FetchError("%s exists already" % target)

    if not os.path.isfile(os.path.join(source.directory, filename)):
        raise FetchError("%s has no file %s" % (source_id, filename))

    os.makedirs(os.path.dirname(target), exist_ok=True)
    text = render_model_record(source_id, filename, aliases, variant_of,
                               nearest)

    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    return target
