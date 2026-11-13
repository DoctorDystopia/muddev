"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: The music unlocks of one character.

             `db.unlocked_tracks` has ONE writer, this class. The three
             public writers carry `_publishes`, so the `char_music`
             channel follows each unlock with no call beside the write.
             QuestHandler has the same split, one system over.

             A key that the track table no longer holds stays in the
             Attribute and shows nowhere. A row that comes back into the
             table shows again. Nothing migrates.

             The handler sends the unlock line itself, as QuestHandler
             sends its lines. The handler is the one place that knows that
             an unlock is new.
"""

import functools as _functools

from systems.interface.statefeed import constants as feed_const
from world import music_tracks

from . import constants


# ─── Private constant definitions ────────────────────────────────────────────

# The routing tag of the unlock line. The SERVER says what a line IS. The
# client decides which tab shows it.
_MSG_PROGRESSION: dict = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_PROGRESSION,
}


# ─── Private helper routines ─────────────────────────────────────────────────

def _publishes(method):
    """
    Purpose: Mark the music of a character stale after a method that can
             change it.

    Entry:
        method - an unbound MusicHandler method that writes the unlocks.

    Exit/Returns:
        Returns the wrapped method, which returns what the original does.

    Module Globals:
        None.

    Methodology:
        A mark, not a send. `refresh_music` records the observer, and the
        buffer builds the snapshot one time after the last change. Thus,
        an area with three tracks sends one snapshot, not three.

        The import is inside the wrapper. The statefeed events reach the
        payload builders, and typeclasses/characters.py imports this
        module at startup.

    Notes/References:
        QuestHandler._publishes is the model.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    @_functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        result = method(self, *args, **kwargs)

        from systems.interface.statefeed import events as _feed

        _feed.refresh_music(self.obj)

        return result

    return wrapper


class MusicHandler:
    """
    Purpose: Which tracks one character holds, and the three ways a track
             unlocks.

    Entry:
        obj is the Character that this handler belongs to.

    Exit/Returns:
        No conditions.

    Module Globals:
        constants.UNLOCKED_TRACKS_ATTR read.

    Methodology:
        The reads give keys in the order of the track table, never the
        order of the unlocks. Thus, the two readers of detail.py draw one
        list.

    Notes/References:
        `Character.music` builds one through _handler_property.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """

    def __init__(self, obj):
        self.obj = obj

    # ─── Reads ───────────────────────────────────────────────────────────────

    def _held(self) -> list:
        """The stored keys, or an empty list on a character with none."""
        held = self.obj.attributes.get(constants.UNLOCKED_TRACKS_ATTR)

        if held is None:
            return []

        return list(held)

    def is_unlocked(self, key: str) -> bool:
        """Return True when the character holds the track."""
        return key in self._held()

    def unlocked_keys(self) -> tuple:
        """Each unlocked key that the table holds, in the order of the table."""
        held = set(self._held())

        return tuple(key for key in music_tracks.TRACKS if key in held)

    # ─── Writes ──────────────────────────────────────────────────────────────

    def _unlock_rows(self, tracks) -> list:
        """Unlock each track that the character does not hold. Tell each."""
        held = self._held()
        new_keys = []

        for track in tracks:
            if track.key in held:
                continue

            held.append(track.key)
            new_keys.append(track.key)
            self.obj.msg(
                (constants.MSG_TRACK_UNLOCKED.format(name=track.name),
                 _MSG_PROGRESSION))

        if new_keys:
            self.obj.attributes.add(constants.UNLOCKED_TRACKS_ATTR, held)

        return new_keys

    @_publishes
    def unlock(self, key: str) -> bool:
        """
        Purpose: Unlock one track by its key.

        Entry:
            key is a key of the track table.

        Exit/Returns:
            Returns True when the unlock is new. False for a held track, or
            for a key that the table does not have.

        Module Globals:
            music_tracks.TRACKS read.

        Author: Nick Hobar
        Creation date: 11/08/2026
        """
        track = music_tracks.TRACKS.get(key)

        if track is None:
            return False

        new_keys = self._unlock_rows((track,))

        return bool(new_keys)

    @_publishes
    def enter_area(self, area) -> list:
        """
        Purpose: Unlock each area track of an area the character entered.

        Entry:
            area is a key of the area table, or None off the tile world.

        Exit/Returns:
            Returns the keys that this call unlocked, in table order.

        Module Globals:
            music_tracks.UNLOCK_AREA read.

        Methodology:
            The mark of `_publishes` lands with or without a new key. The
            `area` field of the snapshot moved, and the pane follows it.

        Author: Nick Hobar
        Creation date: 11/08/2026
        """
        if not area:
            return []

        tracks = [track for track in music_tracks.tracks_of_area(area)
                  if track.unlock == music_tracks.UNLOCK_AREA]

        return self._unlock_rows(tracks)

    @_publishes
    def on_quest_complete(self, quest_key: str) -> list:
        """
        Purpose: Unlock each quest track of a quest the character completed.

        Entry:
            quest_key is the key of the completed quest.

        Exit/Returns:
            Returns the keys that this call unlocked, in table order.

        Module Globals:
            music_tracks.UNLOCK_QUEST read.

        Author: Nick Hobar
        Creation date: 11/08/2026
        """
        tracks = [track for track in music_tracks.TRACKS.values()
                  if track.unlock == music_tracks.UNLOCK_QUEST
                  and track.unlock_key == quest_key]

        return self._unlock_rows(tracks)
