"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: The music unlocks of a character (DESIGN-0016).

             The server owns the list. `world/music_tracks.py` holds the
             tracks, and `handler.py` holds which of them one character
             has unlocked. The client owns the play: which track plays, in
             which mode, at which volume.

             The package takes the quest split. `constants.py` holds the
             vocabulary and the templates. `handler.py` writes
             `db.unlocked_tracks`, and nothing else does. `detail.py` reads
             the handler into rows, and two readers share those rows: the
             `music` command and the `char_music` channel.
"""
