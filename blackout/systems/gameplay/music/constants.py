"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: The vocabulary of the music unlocks: the attribute names and
             the one line that a player reads.

             The wire vocabulary (the channel, the states of a row, the
             keys of a row) is NOT here. It lives in
             systems/interface/statefeed/constants.py with the other
             channel facts, because the client export reads that module.
             The ability rail has the same split.

             This module imports the colors only. The handler and the
             detail module import it, and both of them must stay free of
             the statefeed at import time.
"""

from systems.interface.ui.colors import HIGHLIGHT_COLOR, RESET_COLOR


# ─── Public constant definitions ─────────────────────────────────────────────

# The Attribute of a character that holds the keys of its unlocked tracks,
# as a list in the order of the unlocks. `MusicHandler` is its one writer.
UNLOCKED_TRACKS_ATTR: str = "unlocked_tracks"

# The ndb attribute that holds the area a session last saw its character
# in. `Character._follow_area` compares the area of the tile to it, and
# only a change reaches the handler. An ndb, because the fact is "the
# area that THIS session last saw". A login reads it again.
MUSIC_AREA_ATTR: str = "music_area"

# The line of a new track. Player-facing text, so the voice stays. The
# text is a placeholder for Nick. One line for each track, as the quest
# system sends its lines.
MSG_TRACK_UNLOCKED: str = (
    f"{HIGHLIGHT_COLOR}[MUSIC] You have unlocked a new music track: "
    f"{{name}}.{RESET_COLOR}"
)
