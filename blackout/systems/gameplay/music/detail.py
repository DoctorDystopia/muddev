"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: What a track IS, for one character, in a structured form.

             One owner, two readers. The telnet `music` listing prints its
             rows from here, and statefeed/music.py sends them to the Music
             tab of the Godot client. Thus, the two cannot describe a track
             differently. It is the arrangement of
             systems/gameplay/combat/auras/detail.py, one system over.

             The area of the character comes from here too. It is a live
             read of the tile, so the snapshot and the hook that compares
             areas read one function.
"""

from systems.interface.statefeed import constants as feed_const
from world import music_tracks, tile_travel


# ─── Public routines ─────────────────────────────────────────────────────────

def area_of(character) -> str:
    """
    Purpose: Give the area key of the tile that the character stands on.

    Entry:
        character is any object with a location.

    Exit/Returns:
        Returns the area key, or "" off the tile world and off the loaded
        grid.

    Module Globals:
        None.

    Methodology:
        The read goes through the plane of the character, so a climb into
        another area counts. Limbo has no plane, and the read gives "".

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    plane = tile_travel.plane_view(character)
    tile = tile_travel.tile_of(character)

    if plane is None or tile is None:
        return ""

    area = plane.area_at(*tile)

    return str(area or "")


def track_rows(character) -> list:
    """
    Purpose: One row for each track of the table, with its state for the
             character.

    Entry:
        character is a Character with a `music` handler.

    Exit/Returns:
        Returns a list of dicts `{key, name, area, state, hint}`, in the
        order of the table. The state is MUSIC_STATE_LOCKED or
        MUSIC_STATE_UNLOCKED. A locked row carries its hint, and an
        unlocked row carries "" there, because the hint is the clue to the
        unlock.

    Module Globals:
        music_tracks.TRACKS read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    unlocked = set(character.music.unlocked_keys())
    rows = []

    for track in music_tracks.TRACKS.values():
        is_unlocked = track.key in unlocked

        if is_unlocked:
            state = feed_const.MUSIC_STATE_UNLOCKED
            hint = ""
        else:
            state = feed_const.MUSIC_STATE_LOCKED
            hint = str(track.hint)

        rows.append({
            feed_const.MUSIC_ROW_KEY: str(track.key),
            feed_const.MUSIC_ROW_NAME: str(track.name),
            feed_const.MUSIC_ROW_AREA: str(track.area),
            feed_const.MUSIC_ROW_STATE: state,
            feed_const.MUSIC_ROW_HINT: hint,
        })

    return rows


def unlocked_count(rows) -> int:
    """Count the unlocked rows of track_rows."""
    unlocked = [row for row in rows
                if row[feed_const.MUSIC_ROW_STATE] == feed_const.MUSIC_STATE_UNLOCKED]

    return len(unlocked)
