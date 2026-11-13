"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: Turn the music of a character into the plain values that
             CharMusicPayload carries.

             IT COMPOSES NOTHING. The rows come from
             systems/gameplay/music/detail.py, and the telnet `music`
             listing reads the same rows. Thus, the Music tab that a
             graphical client draws and the listing that a telnet player
             reads describe the same tracks by construction. The area comes
             from the same module, so the snapshot and the area hook read
             one function.

             Imported LAZILY by events.emit_music. The detail module reads
             the tile world, and typeclasses/mixins.py imports events.py
             at startup.
"""

from systems.gameplay.music import detail

from .payloads import CharMusicPayload


# ─── Public interface ────────────────────────────────────────────────────────

def build_payload(observer) -> CharMusicPayload:
    """
    Purpose: Build the music of the observer as one snapshot.

    Entry:
        observer - the puppeted Character.

    Exit/Returns:
        Returns a CharMusicPayload.

    Module Globals:
        None.

    Methodology:
        A straight copy of detail.area_of and detail.track_rows into the
        dataclass.

    Notes/References:
        Sent on CHANNEL_CHAR_MUSIC. Every value must survive json.dumps,
        see systems/interface/statefeed/payloads.py.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    payload = CharMusicPayload(
        area=detail.area_of(observer),
        rows=detail.track_rows(observer),
    )

    return payload
