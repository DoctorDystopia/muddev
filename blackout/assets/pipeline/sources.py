"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Source records. One download, one directory, one source.toml.

             A SOURCE is a download exactly as it arrived: a Sketchfab zip, an
             itch.io pack, a picoCAD save file. Nobody edits the art in it.
             One source can feed many models (the Kyle Fuji pack feeds five),
             so the license lives here and not on each model.

             The source record is the one owner of four facts:
               - who made the download, and where it came from
               - its license, as an SPDX id (see licenses.py)
               - an `exception`, when the license gate is waived, with why
               - a SHA-256 for every file in the directory

             THE HASHES. `pipeline seal <source_id>` writes them. `pipeline
             check` compares them. A changed hash means that someone edited a
             download, and an edit that nobody recorded is lost at the next
             re-download. The hashes also let the sources move out of git
             later (to Git LFS or R2) without trust in the copy.

             The [files] table is always LAST in the file, because seal
             replaces everything from its header to the end. Everything above
             it is written by a person and seal never changes it.

             A LOCAL SOURCE (Nick, 10/09/2026). `local = true` in the record
             says that the files of the download stay on the machine that
             holds them. git keeps the source record and ignores the files,
             through a .gitignore that seal writes into the directory. A
             bought pack is the reason: this repository is public, and a
             purchase gives no right to publish the download.

             On a machine with no copy of the files, the check skips the
             file hashes of a local source and prints a warning. The served
             .glb and the lock file are in git, so the check still compares
             them. Such a machine cannot BUILD a model of that source.
"""

import hashlib
import os
import tomllib
from dataclasses import dataclass, field

from assets.pipeline import licenses, paths


# ─── Public constant definitions ─────────────────────────────────────────────

# The fields a source record must set. `exception` and `notes` are optional.
REQUIRED_FIELDS: tuple = ("title", "author", "url", "site", "license",
                          "retrieved")


class SourceError(RuntimeError):
    """A source record that is missing, malformed, or fails the gate."""


@dataclass(frozen=True)
class Source:
    """
    One download and what is known about it.

    files maps a path relative to the source directory (forward slashes) to
    "sha256:<hex>". exception is empty unless the license gate is waived.
    local is True for a local source: git ignores its files.
    """

    source_id: str
    directory: str
    title: str
    author: str
    url: str
    site: str
    license: str
    retrieved: str
    notes: str = ""
    exception: str = ""
    local: bool = False
    files: dict = field(default_factory=dict)


# The file that keeps the files of a local source out of git. seal writes it.
LOCAL_GITIGNORE_NAME: str = ".gitignore"

# Its text. Every file is ignored, except this file and the source record.
LOCAL_GITIGNORE_TEXT: str = (
    "# A local source. Its files stay on this machine, and git keeps only\n"
    "# the source record. `python -m assets.pipeline seal` writes this file.\n"
    "*\n"
    "!.gitignore\n"
    "!source.toml\n"
)


# ─── Private constant definitions ────────────────────────────────────────────

_FILES_TABLE: str = "files"
_FILES_HEADER: str = "[files]"
_HASH_PREFIX: str = "sha256:"
_READ_CHUNK_BYTES: int = 1024 * 1024
_LOCAL_FIELD: str = "local"
_OPTIONAL_FIELDS: tuple = ("notes", "exception", _LOCAL_FIELD)
_KNOWN_FIELDS: frozenset = frozenset(
    REQUIRED_FIELDS + _OPTIONAL_FIELDS + (_FILES_TABLE,))

# Files that are not part of a download: the record itself, the .gitignore of
# a local source, and the caches that tools leave behind.
_IGNORED_NAMES: frozenset = frozenset(
    (paths.SOURCE_RECORD_NAME, LOCAL_GITIGNORE_NAME, "__pycache__",
     ".DS_Store", "Thumbs.db"))


# ─── Private helper routines ─────────────────────────────────────────────────

def _file_digest(path: str) -> str:
    """
    Purpose: Give the SHA-256 of one file, in the form a record stores.

    Entry:
        path names a readable file.

    Exit/Returns:
        Returns "sha256:<64 hex digits>".

    Module Globals:
        _HASH_PREFIX, _READ_CHUNK_BYTES read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        chunk = handle.read(_READ_CHUNK_BYTES)

        while chunk:
            digest.update(chunk)
            chunk = handle.read(_READ_CHUNK_BYTES)

    hex_digest = digest.hexdigest()

    return _HASH_PREFIX + hex_digest


def _record_path(source_id: str) -> str:
    """
    Purpose: Give the path of one source record.

    Entry:
        source_id is a directory name under SOURCES_DIR.

    Exit/Returns:
        Returns the path of its source.toml. The file does not need to exist.

    Module Globals:
        paths.SOURCES_DIR, paths.SOURCE_RECORD_NAME read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    return os.path.join(paths.SOURCES_DIR, source_id, paths.SOURCE_RECORD_NAME)


def _check_fields(source_id: str, document: dict) -> None:
    """
    Purpose: Refuse a source record with a missing or an unknown field.

    Entry:
        document is the parsed TOML of one source record.

    Exit/Returns:
        Returns None. Raises SourceError that names every bad field.

    Module Globals:
        REQUIRED_FIELDS, _KNOWN_FIELDS read.

    Methodology:
        An unknown field is refused, not ignored. "licence" for "license"
        would otherwise read as a record with no license at all.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    missing = [name for name in REQUIRED_FIELDS if not document.get(name)]
    unknown = sorted(set(document) - _KNOWN_FIELDS)
    local = document.get(_LOCAL_FIELD, False)

    if missing:
        raise SourceError("%s: source.toml has no %s"
                          % (source_id, ", ".join(missing)))

    if unknown:
        raise SourceError("%s: source.toml has unknown field(s) %s"
                          % (source_id, ", ".join(unknown)))

    if not isinstance(local, bool):
        raise SourceError("%s: source.toml `local` must be true or false"
                          % source_id)


# ─── Public routines ─────────────────────────────────────────────────────────

def list_source_ids() -> list:
    """
    Purpose: Name every source directory, with a record or without one.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the sorted directory names under SOURCES_DIR. Returns an empty
        list when SOURCES_DIR does not exist.

    Module Globals:
        paths.SOURCES_DIR read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    if not os.path.isdir(paths.SOURCES_DIR):
        return []

    names = os.listdir(paths.SOURCES_DIR)
    directories = [name for name in names
                   if os.path.isdir(os.path.join(paths.SOURCES_DIR, name))]

    return sorted(directories)


def load_source(source_id: str) -> Source:
    """
    Purpose: Read and check one source record.

    Entry:
        source_id is a directory name under SOURCES_DIR.

    Exit/Returns:
        Returns the Source. Raises SourceError when the record is missing,
        is not valid TOML, or has a missing or unknown field.

    Module Globals:
        paths.SOURCES_DIR read.

    Methodology:
        TOML dates arrive as datetime.date. The record keeps them as text,
        so the credits and the JSON output need no conversion.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    record = _record_path(source_id)

    try:
        with open(record, "rb") as handle:
            document = tomllib.load(handle)
    except FileNotFoundError:
        raise SourceError("%s: no %s" % (source_id, paths.SOURCE_RECORD_NAME))
    except tomllib.TOMLDecodeError as problem:
        raise SourceError("%s: source.toml is not valid TOML: %s"
                          % (source_id, problem))

    _check_fields(source_id, document)
    retrieved = str(document["retrieved"])
    directory = os.path.join(paths.SOURCES_DIR, source_id)
    files = dict(document.get(_FILES_TABLE, {}))

    return Source(
        source_id=source_id, directory=directory,
        title=document["title"], author=document["author"],
        url=document["url"], site=document["site"],
        license=document["license"], retrieved=retrieved,
        notes=document.get("notes", ""),
        exception=document.get("exception", ""),
        local=document.get(_LOCAL_FIELD, False), files=files)


def gate_problem(source: Source) -> str:
    """
    Purpose: Tell why one source may not be served, if it may not.

    Entry:
        source is a loaded Source.

    Exit/Returns:
        Returns "" when the license is allowed, or when an exception waives
        the gate. Returns one sentence that names the problem otherwise.

    Module Globals:
        None.

    Methodology:
        A `local_only` license needs a local source. No exception waives
        that rule, because the rule keeps a bought download out of a public
        repository.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    allowed = licenses.is_allowed(source.license)
    terms = licenses.terms_for(source.license)

    if allowed and terms.local_only and not source.local:
        return ("license '%s' gives no right to publish the download. Add "
                "`local = true` to the source record, then seal it"
                % source.license)

    if allowed or source.exception:
        return ""

    return ("license '%s' is not allowed. Use an allowed SPDX id, or add an "
            "`exception` with the reason" % source.license)


def files_absent(source: Source) -> bool:
    """
    Purpose: Tell whether this machine has no copy of a local source.

    Entry:
        source is a loaded Source.

    Exit/Returns:
        Returns True when source is local, its record names files, and none
        of them is on disk. Returns False for every other source.

    Module Globals:
        None.

    Methodology:
        All or nothing. A local source with only some of its files is a
        changed download, and hash_problems reports it as usual.

    Author: Nick Hobar
    Creation date: 10/09/2026
    """
    if not source.local or not source.files:
        return False

    on_disk = [name for name in source.files
               if os.path.isfile(os.path.join(source.directory, name))]

    return not on_disk


def gitignore_problem(source: Source) -> str:
    """
    Purpose: Tell why git can take the files of a local source, if it can.

    Entry:
        source is a loaded Source.

    Exit/Returns:
        Returns "" for a source that is not local, and for a local source
        whose .gitignore holds LOCAL_GITIGNORE_TEXT. Returns one sentence
        that names the problem otherwise.

    Module Globals:
        LOCAL_GITIGNORE_NAME, LOCAL_GITIGNORE_TEXT read.

    Methodology:
        Line endings are made uniform first, as for every text file here.

    Author: Nick Hobar
    Creation date: 10/09/2026
    """
    if not source.local:
        return ""

    path = os.path.join(source.directory, LOCAL_GITIGNORE_NAME)
    text = ""

    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", newline="") as handle:
            text = handle.read().replace("\r\n", "\n")

    if text == LOCAL_GITIGNORE_TEXT:
        return ""

    return ("a local source needs the %s that seal writes, or git takes its "
            "files" % LOCAL_GITIGNORE_NAME)


def current_files(source: Source) -> dict:
    """
    Purpose: Hash every file that is in one source directory now.

    Entry:
        source.directory exists.

    Exit/Returns:
        Returns {relative path with forward slashes: "sha256:<hex>"}, sorted
        by path. The source record and tool caches are left out.

    Module Globals:
        _IGNORED_NAMES read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    found = {}

    for folder, subfolders, filenames in os.walk(source.directory):
        subfolders[:] = [name for name in subfolders
                         if name not in _IGNORED_NAMES]

        for filename in filenames:
            if filename in _IGNORED_NAMES:
                continue

            full = os.path.join(folder, filename)
            relative = os.path.relpath(full, source.directory)
            key = relative.replace(os.sep, "/")
            found[key] = _file_digest(full)

    return dict(sorted(found.items()))


def seal(source: Source) -> int:
    """
    Purpose: Write the current hash of every file into one source record.

    Entry:
        source was loaded from its record, so the record exists.

    Exit/Returns:
        Returns the number of files sealed. The record is rewritten from its
        [files] header to the end. Every line above that header stays. For a
        local source, its .gitignore is written too. Raises SourceError for
        a local source with no files on this machine.

    Module Globals:
        _FILES_HEADER, LOCAL_GITIGNORE_NAME, LOCAL_GITIGNORE_TEXT read.

    Methodology:
        A seal with no files on disk writes an empty [files] table. For a
        local source on a second machine, that deletes the only record of
        the hashes. Thus, the seal refuses.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    absent = files_absent(source)

    if absent:
        raise SourceError("%s: the files of this local source are not on "
                          "this machine, so there is nothing to seal"
                          % source.source_id)

    if source.local:
        ignore_path = os.path.join(source.directory, LOCAL_GITIGNORE_NAME)

        with open(ignore_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(LOCAL_GITIGNORE_TEXT)

    record = _record_path(source.source_id)

    with open(record, "r", encoding="utf-8") as handle:
        text = handle.read()

    head, _separator, _old = text.partition(_FILES_HEADER)
    files = current_files(source)
    lines = ['"%s" = "%s"' % (name, digest) for name, digest in files.items()]
    body = "\n".join(lines)
    sealed = "%s%s\n%s\n" % (head.rstrip() + "\n\n", _FILES_HEADER, body)

    with open(record, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(sealed)

    return len(files)


def hash_problems(source: Source) -> list:
    """
    Purpose: Compare one source directory with the hashes in its record.

    Entry:
        source is a loaded Source.

    Exit/Returns:
        Returns one line for each added, removed, or changed file. Returns an
        empty list when the directory matches its record exactly.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    now = current_files(source)
    problems = []

    for name in sorted(set(now) | set(source.files)):
        recorded = source.files.get(name)
        present = now.get(name)

        if recorded is None:
            problems.append("%s is not in the record" % name)
        elif present is None:
            problems.append("%s is in the record but not on disk" % name)
        elif recorded != present:
            problems.append("%s changed since it was sealed" % name)

    return problems
