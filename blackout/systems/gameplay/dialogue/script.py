"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The compiled script (DESIGN-0017): the shape that the server
             reads, the reader of one compiled script file, and the digest
             that ties a compiled script to its dialogue script.

             This module imports no game system. The runner, the content
             check, and the tests all read a script through it.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field

from systems.gameplay.dialogue import constants as dialogue_const


# ─── Public classes ──────────────────────────────────────────────────────────

class DialogueScriptError(Exception):
    """A compiled script that the server cannot read or cannot run."""


@dataclass(frozen=True)
class CompiledScript:
    """
    Purpose: Hold one compiled script as the script export wrote it.

    Entry:
        key is the file name without its suffix. An NpcDef names it.
        compiler_version is the COMPILER_VERSION of the addon that made it.
        source_sha256 is the digest of the dialogue script. See
        source_digest.
        cues maps each cue name to the id of its line.
        lines maps each line id to the line, a dict in the addon's format.

    Exit/Returns:
        Not applicable. A dataclass.

    Module Globals:
        None.

    Methodology:
        The lines stay in the addon's format. The runner reads them through
        the field names in constants.py. A second shape here is a second
        format to keep equal to the addon.

    Notes/References:
        godot/addons/dialogue_manager/compiler/compiled_line.gd writes each
        line.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """

    key: str
    compiler_version: int = dialogue_const.SUPPORTED_COMPILER_VERSION
    source_sha256: str = ""
    cues: dict = field(default_factory=dict)
    lines: dict = field(default_factory=dict)


    def line(self, line_id: str) -> dict:
        """The line with this id. Raises DialogueScriptError if none has it."""
        found = self.lines.get(line_id)

        if found is None:
            raise DialogueScriptError(
                f"the script '{self.key}' has no line with the id '{line_id}'")

        return found


    def cue_line(self, cue: str) -> str | None:
        """The id of the line of a cue, or None if the script has no such cue."""
        return self.cues.get(cue)


# ─── Public routines ─────────────────────────────────────────────────────────

def source_digest(text: str) -> str:
    """
    Purpose: Give the digest of the text of one dialogue script.

    Entry:
        text is the content of a `.dialogue` file.

    Exit/Returns:
        Returns the SHA-256 of the text, as lowercase hex.

    Module Globals:
        None.

    Methodology:
        1. Change each CRLF to LF. git stores LF, and a tool on this machine
           can write CRLF.
        2. Encode the text as UTF-8 and hash it.

    Notes/References:
        `DialogueScriptExport.digest_of` in the Godot project is the twin.
        The two must give the same digest for the same file.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    normalized = text.replace("\r\n", "\n")
    encoded = normalized.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()

    return digest


def read_source(path: str) -> str:
    """The text of one dialogue script file, with the line ends as they are."""
    with open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()

    return text


def load_script(path: str) -> CompiledScript:
    """
    Purpose: Read one compiled script file.

    Entry:
        path names a file that the script export wrote.

    Exit/Returns:
        Returns the CompiledScript. Its key is the file name with no suffix.
        Raises DialogueScriptError for a file that is missing, is not JSON,
        or has a format that this package does not read.

    Module Globals:
        None.

    Methodology:
        1. Read the file as JSON.
        2. Refuse a format number that is not COMPILED_FORMAT.
        3. Copy the fields into a CompiledScript.

    Notes/References:
        The content check (checks.py) refuses a wrong compiler version. This
        reader only refuses a file that it cannot take apart.

    Author: Nick Hobar
    Creation date: 11/11/2026
    """
    key = os.path.splitext(os.path.basename(path))[0]

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as error:
        raise DialogueScriptError(
            f"cannot read the compiled script '{path}': {error}") from error

    file_format = payload.get(dialogue_const.KEY_FORMAT)

    if file_format != dialogue_const.COMPILED_FORMAT:
        raise DialogueScriptError(
            f"the compiled script '{key}' has the format {file_format!r}, and "
            f"this server reads the format {dialogue_const.COMPILED_FORMAT}")

    script = CompiledScript(
        key=key,
        compiler_version=payload.get(dialogue_const.KEY_COMPILER_VERSION, 0),
        source_sha256=payload.get(dialogue_const.KEY_SOURCE_SHA256, ""),
        cues=payload.get(dialogue_const.KEY_CUES, {}),
        lines=payload.get(dialogue_const.KEY_LINES, {}),
    )

    return script
