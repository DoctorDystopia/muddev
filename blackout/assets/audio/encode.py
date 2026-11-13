"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: The encode of a track: a FLAC master in, an OGG Vorbis file
             out, through ffmpeg. The one place that names ffmpeg.

             ffmpeg is the third tool of the asset pipeline, beside Node
             (glTF Transform) and Blender. Nothing in Python encodes Vorbis.
             The wizard finds ffmpeg before it asks a question, and it
             refuses with one line when this machine has none. Set
             FFMPEG_BIN when ffmpeg is in an unusual place.

             Why OGG: Godot plays OGG and MP3, and no FLAC. An MP3 carries
             encoder padding, so a loop of an MP3 clicks at the seam, and
             Single mode loops. Vorbis loops clean (DESIGN-0016, Nick,
             11/08/2026).

             Runs ffmpeg, and writes nothing else.
"""

import os
import shutil
import subprocess

from assets.audio import kinds


# ─── Private constant definitions ────────────────────────────────────────────

_FFMPEG_ENV_VAR: str = "FFMPEG_BIN"
_FFMPEG_COMMAND: str = "ffmpeg"

# No video, the Vorbis encoder, the quality, and a yes to an overwrite.
_ENCODE_FLAGS: tuple = ("-hide_banner", "-loglevel", "error", "-y")
_INPUT_FLAG: str = "-i"
_AUDIO_FLAGS: tuple = ("-vn", "-c:a", "libvorbis", "-q:a")
_TIMEOUT_SECONDS: int = 600
_TAIL_LINES: int = 8


# ─── Public routines ─────────────────────────────────────────────────────────

def find_ffmpeg() -> str:
    """
    Purpose: Find the ffmpeg executable.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the path of the executable, or "" when neither FFMPEG_BIN
        nor the PATH gives one.

    Module Globals:
        _FFMPEG_ENV_VAR, _FFMPEG_COMMAND read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    configured = os.environ.get(_FFMPEG_ENV_VAR, "")

    if configured and os.path.isfile(configured):
        return configured

    on_path = shutil.which(_FFMPEG_COMMAND)

    return on_path or ""


def encode_command(executable: str, master: str, output: str) -> list:
    """Give the command line of the encode of one master."""
    return [executable, *_ENCODE_FLAGS, _INPUT_FLAG, master, *_AUDIO_FLAGS,
            str(kinds.MUSIC_QUALITY), output]


def run_encode(executable: str, master: str, output: str) -> str:
    """
    Purpose: Encode one master to its served file.

    Entry:
        executable came from find_ffmpeg. The folder of output exists.

    Exit/Returns:
        Returns "" when ffmpeg ends with no error and the output is there.
        Returns the last lines of its output otherwise.

    Module Globals:
        _TIMEOUT_SECONDS, _TAIL_LINES read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    command = encode_command(executable, master, output)

    try:
        finished = subprocess.run(command, capture_output=True, text=True,
                                  timeout=_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as problem:
        return str(problem)

    if finished.returncode == 0 and os.path.isfile(output):
        return ""

    text = (finished.stdout or "") + (finished.stderr or "")
    tail = text.strip().splitlines()[-_TAIL_LINES:]

    return "ffmpeg ended with code %d:\n  %s" % (finished.returncode,
                                                 "\n  ".join(tail))
