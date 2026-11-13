"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: The music tracks, one row for each track (DESIGN-0016).

             A track is one piece of music that the client plays. Each
             track belongs to one area, and each track has one unlock rule.
             The server owns this list. The client owns the play: which
             track plays, in which mode, at which volume.

             THE ROWS ARE DATA. They live in `world/tables/music_tracks.json`,
             and `world/table_file.py` reads them, as it reads the areas.
             The sound wizard (`python -m assets.audio add`) writes a row
             when it adds a track. A hand edit of the file is legal too.
             The order of the rows is the order of the list that a player
             sees.

             THE KEY NAMES THE FILE. The served file of a track is
             `web/static/webclient/music/<key>.ogg`, and no row names a
             file. The server sends keys. The client builds the URL.

             THE UNLOCK VOCABULARY has two rows today. `area` unlocks the
             track when the player first enters its area, and `unlock_key`
             stays empty. `quest` unlocks it when the player completes the
             quest that `unlock_key` names. A later rule is one more
             constant here and one more branch in the music handler.

             A bad row stops the server at start: an area that the area
             table does not have, an unlock that is not in the vocabulary,
             a quest unlock with no quest key, or an area unlock with one.
             `world/tests/test_music_tracks.py` checks the quest keys, which
             this module cannot read at import without an import ring.
"""

from dataclasses import dataclass

from world import areas, table_file


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass(frozen=True)
class Track:
    """
    One track. The `key` names the served file. The `name` is the title
    that the player sees. The `area` is a key of the area table. The
    `unlock` is a row of UNLOCKS, and `unlock_key` is the quest of a quest
    unlock. The `hint` is the line of a locked row, and Nick writes it. The
    `note` tells an author what the track is, and no player sees it.
    """

    key: str
    name: str
    area: str
    unlock: str
    unlock_key: str
    hint: str
    note: str


# The name of the table file, with no suffix.
TABLE_NAME: str = "music_tracks"

# The unlock vocabulary.
UNLOCK_AREA: str = "area"
UNLOCK_QUEST: str = "quest"
UNLOCKS: tuple = (UNLOCK_AREA, UNLOCK_QUEST)

# The served tree of the tracks, from the game directory, with forward
# slashes, and the suffix of a served file. The client fetches
# `<origin>/static/webclient/music/<key>.ogg`.
SERVED_DIRECTORY: str = "web/static/webclient/music"
SERVED_SUFFIX: str = ".ogg"

# The source record of the master of a track is `assets/sources/music_<key>/`.
SOURCE_PREFIX: str = "music_"


# ─── Public routines ─────────────────────────────────────────────────────────

def row_problem(track: Track, area_keys) -> str:
    """
    Purpose: Tell what is wrong with one track row, if anything.

    Entry:
        area_keys holds each key of the area table.

    Exit/Returns:
        Returns "" for a good row, or one sentence that names the problem.

    Module Globals:
        UNLOCKS, UNLOCK_AREA, UNLOCK_QUEST read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    known_area = track.area in area_keys
    known_unlock = track.unlock in UNLOCKS
    quest_with_key = track.unlock != UNLOCK_QUEST or track.unlock_key
    area_with_no_key = track.unlock != UNLOCK_AREA or not track.unlock_key

    if not track.name:
        return "the track %s has no name" % track.key

    if not known_area:
        return "the track %s names the area %r, which the area table does " \
               "not have" % (track.key, track.area)

    if not known_unlock:
        return "the track %s has the unlock %r. The unlocks are %s" % (
            track.key, track.unlock, ", ".join(UNLOCKS))

    if not quest_with_key:
        return "the track %s unlocks on a quest, but names no quest key" \
               % track.key

    if not area_with_no_key:
        return "the track %s unlocks on its area, so its unlock key must " \
               "stay empty" % track.key

    return ""


def check_rows(rows, area_keys) -> None:
    """
    Purpose: Refuse a table with a bad row.

    Entry:
        rows holds Track rows. area_keys holds each key of the area table.

    Exit/Returns:
        Returns None. Raises table_file.TableFileError for the first bad
        row.

    Module Globals:
        TABLE_NAME read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    for track in rows:
        problem = row_problem(track, area_keys)

        if problem:
            raise table_file.TableFileError("%s: %s" % (TABLE_NAME, problem))


def served_relative(key: str) -> str:
    """Give the served file of a track, from the game directory."""
    return "%s/%s%s" % (SERVED_DIRECTORY, key, SERVED_SUFFIX)


def source_id_for(key: str) -> str:
    """Give the source id of the master of a track."""
    return SOURCE_PREFIX + key


def tracks_of_area(area: str) -> tuple:
    """Give each track of one area, in the order of the table."""
    return tuple(track for track in TRACKS.values() if track.area == area)


# ─── The rows ────────────────────────────────────────────────────────────────

# A world with no track yet is legal, so the table may hold no row.
_TRACK_ROWS: tuple = table_file.read_rows(TABLE_NAME, Track, allow_empty=True)

check_rows(_TRACK_ROWS, areas.AREAS)

# key -> Track, in the order of the file.
TRACKS: dict = {row.key: row for row in _TRACK_ROWS}
