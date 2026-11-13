"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/26/2026
Description: Where every part of the sound wizard lives on disk. The one
             owner of those paths.

             Each path is absolute and comes from this file's own location,
             so a command gives the same answer from any working directory.
             The one exception is the folder of the sound packs, which is
             outside the repo.
"""

import os

from assets.pipeline import paths as pipeline_paths
from world import music_tracks, table_file


# ─── Public constant definitions ─────────────────────────────────────────────

# assets/audio/paths.py -> assets/audio/ -> assets/ -> blackout/ -> the repo.
AUDIO_PACKAGE_DIR: str = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR: str = os.path.dirname(AUDIO_PACKAGE_DIR)
GAME_DIR: str = os.path.dirname(ASSETS_DIR)
REPO_DIR: str = os.path.dirname(GAME_DIR)

# The Godot project. The import of a new sound clip runs on it.
GODOT_PROJECT_DIR: str = os.path.join(REPO_DIR, "godot")

# Every sound clip that the client plays, in one folder for each sound kind.
AUDIO_DIR: str = os.path.join(GODOT_PROJECT_DIR, "audio")

# The cue table: each cue with its sound kind and its sound clip, and the
# cue of each moment. SoundCues reads it, and the sound wizard writes it.
CUE_TABLE_PATH: str = os.path.join(AUDIO_DIR, "cues.json")

# The credits of the sound clips: one section for each sound pack.
CREDITS_PATH: str = os.path.join(AUDIO_DIR, "CREDITS.md")

# The generated constants of the client. The sound wizard reads the moment
# names from this file, because this process has no Django and cannot read
# statefeed/constants.py.
CLIENT_CONSTANTS_PATH: str = os.path.join(GODOT_PROJECT_DIR, "autoload",
                                          "blackout_constants.gd")

# The folder of the sound packs on this machine. A sound pack never enters
# the repo (godot/audio/CREDITS.md). Set BLACKOUT_SOUND_PACKS when the packs
# are in a different place. The file dialog opens here.
PACKS_ENV_VAR: str = "BLACKOUT_SOUND_PACKS"
PACKS_DIR: str = (os.environ.get(PACKS_ENV_VAR)
                  or os.path.join(os.path.expanduser("~"), "Games",
                                  "Projects", "Godot", "Assets"))

# The file beside each sound clip that tells Godot how to import it.
IMPORT_SUFFIX: str = ".import"

# The served tree of the tracks (DESIGN-0016). Evennia serves it in
# development, and publish.sh copies it to R2, as it does the models. The
# client fetches each track from it. world/music_tracks.py owns the
# relative path, so the server and the wizard name one directory.
SERVED_MUSIC_DIR: str = os.path.join(GAME_DIR,
                                     *music_tracks.SERVED_DIRECTORY.split("/"))

# The music track table: one row for each track. The server reads it at
# start, and the sound wizard writes it.
TRACK_TABLE_PATH: str = table_file.table_path(music_tracks.TABLE_NAME)



# ─── Public routines ─────────────────────────────────────────────────────────

def clip_path(clip: str) -> str:
    """
    Purpose: Give the absolute path of one sound clip of the cue table.

    Entry:
        clip is relative to godot/audio/, with forward slashes, for example
        "sfx/guns_shot.wav".

    Exit/Returns:
        Returns the path under AUDIO_DIR. The file does not need to exist.

    Module Globals:
        AUDIO_DIR read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    parts = clip.split("/")

    return os.path.join(AUDIO_DIR, *parts)


def track_path(key: str) -> str:
    """Give the absolute path of the served file of one track."""
    return os.path.join(SERVED_MUSIC_DIR, key + music_tracks.SERVED_SUFFIX)


def source_dir(key: str) -> str:
    """
    Purpose: Give the absolute path of the source directory of one track.

    Entry:
        key is a track key.

    Exit/Returns:
        Returns the directory under the sources of the model pipeline:
        the master of a track is a source record, as a download is. A
        test that patches pipeline paths.SOURCES_DIR moves it too, because
        the read happens at the call.

    Module Globals:
        pipeline_paths.SOURCES_DIR read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    return os.path.join(pipeline_paths.SOURCES_DIR,
                        music_tracks.source_id_for(key))
