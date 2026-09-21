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

from assets.pipeline import paths, sources


# ─── Public constant definitions ─────────────────────────────────────────────

class FetchError(RuntimeError):
    """A download or a copy that could not complete."""


# ─── Private constant definitions ────────────────────────────────────────────

_POLYHAVEN_API: str = "https://api.polyhaven.com"
_POLYHAVEN_PAGE: str = "https://polyhaven.com/a/%s"
_POLYHAVEN_TYPE_MODEL: int = 2
_POLYHAVEN_RESOLUTION: str = "1k"
_POLYHAVEN_FORMAT: str = "gltf"
_USER_AGENT: str = "Blackout-model-pipeline/1.0 (assets/pipeline/fetch.py)"
_TIMEOUT_SECONDS: int = 60
_ZIP_SUFFIX: str = ".zip"
_TODO: str = "TODO"

_SOURCE_TEMPLATE: str = '''title     = "{title}"
author    = "{author}"
url       = "{url}"
site      = "{site}"
license   = "{license}"
retrieved = {retrieved}
'''

_MODEL_TEMPLATE: str = '''source = "{source_id}"
file   = "{file}"
'''


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


def _write_source_record(directory: str, **fields) -> None:
    """
    Purpose: Write a source record, then seal its files.

    Entry:
        directory holds the download. fields fill _SOURCE_TEMPLATE.

    Exit/Returns:
        Returns None.

    Module Globals:
        paths.SOURCE_RECORD_NAME, _SOURCE_TEMPLATE read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    fields["retrieved"] = datetime.date.today().isoformat()
    text = _SOURCE_TEMPLATE.format(**fields)
    record = os.path.join(directory, paths.SOURCE_RECORD_NAME)

    with open(record, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    source_id = os.path.basename(directory)
    source = sources.load_source(source_id)
    sources.seal(source)


# ─── Public routines ─────────────────────────────────────────────────────────

def fetch_polyhaven(asset_id: str) -> str:
    """
    Purpose: Download one Poly Haven model as a new source.

    Entry:
        asset_id is a Poly Haven asset id, for example "wooden_crate_01".

    Exit/Returns:
        Returns the new source directory, polyhaven_<asset_id>. Raises
        FetchError when the id is not a model, has no 1k glTF, or a file
        fails its MD5.

    Module Globals:
        The _POLYHAVEN_* constants read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    info = json.loads(_download("%s/info/%s" % (_POLYHAVEN_API, asset_id)))

    if info.get("type") != _POLYHAVEN_TYPE_MODEL:
        raise FetchError("%s is not a Poly Haven model" % asset_id)

    listing = json.loads(_download("%s/files/%s" % (_POLYHAVEN_API, asset_id)))
    entry = listing[_POLYHAVEN_FORMAT][_POLYHAVEN_RESOLUTION][_POLYHAVEN_FORMAT]
    wanted = {os.path.basename(entry["url"]): entry}
    wanted.update(entry.get("include", {}))
    directory = _new_source_dir("polyhaven_" + asset_id)

    for relative, item in wanted.items():
        body = _download(item["url"])

        if hashlib.md5(body).hexdigest() != item["md5"]:
            raise FetchError("%s failed its MD5 check" % relative)

        target = os.path.join(directory, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)

        with open(target, "wb") as handle:
            handle.write(body)

    authors = ", ".join(sorted(info.get("authors", {}))) or _TODO
    _write_source_record(directory, title=info.get("name", asset_id),
                         author=authors, url=_POLYHAVEN_PAGE % asset_id,
                         site="polyhaven", license="CC0-1.0")

    return directory


def fetch_file(path: str, source_id: str) -> str:
    """
    Purpose: Copy a downloaded file or folder in as a new source.

    Entry:
        path names a file, a folder, or a .zip. source_id is a new id.

    Exit/Returns:
        Returns the new source directory. Its record has TODO fields, and a
        TODO license fails the license gate until someone fills it in.

    Module Globals:
        _ZIP_SUFFIX, _TODO read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    if not os.path.exists(path):
        raise FetchError("%s does not exist" % path)

    directory = _new_source_dir(source_id)

    if path.lower().endswith(_ZIP_SUFFIX):
        with zipfile.ZipFile(path) as archive:
            archive.extractall(directory)
    elif os.path.isdir(path):
        shutil.copytree(path, directory, dirs_exist_ok=True)
    else:
        shutil.copy2(path, directory)

    _write_source_record(directory, title=_TODO, author=_TODO, url=_TODO,
                         site=_TODO, license=_TODO)

    return directory


def write_model_record(family: str, asset_key: str, source_id: str,
                       filename: str) -> str:
    """
    Purpose: Write a new model record with no fixes.

    Entry:
        source_id names an existing source that holds filename.

    Exit/Returns:
        Returns the path of the new record. Raises FetchError when the record
        exists already, or the source or the file does not.

    Module Globals:
        paths.MODELS_DIR, paths.MODEL_RECORD_SUFFIX, _MODEL_TEMPLATE read.

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
    text = _MODEL_TEMPLATE.format(source_id=source_id, file=filename)

    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    return target
