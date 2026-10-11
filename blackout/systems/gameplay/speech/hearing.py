"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/05/2026
Description: Find the listeners of one line of speech.

The reach
---------
`constants.py` holds Nick's rules. This module applies them. Each reach is a
row of _REACH_RULES: a function that gets the speaker and gives a test for
one listener. A new reach is one function and one row.

Off the tile world
------------------
A room off the tile world, for example Limbo, has no tile and no area. There,
each reach gives the room of the speaker only. That was the reach of every
say before 10/05/2026, because each tile is a separate room.

Why the connected sessions
--------------------------
A room broadcast sends to each object in the room, and most of them are
scenery. PERF-0002 measured 1,242 statefeed sends for two moves, nearly all
of them to rocks. A yell can reach a full area. Thus, the listeners come from
the connected sessions, and the cost follows the number of players.
"""

import evennia
from evennia.utils import logger

from systems.gameplay.combat.auras.targeting import tile_world_rooms
from world import tile_travel

from . import constants as const


# ─── Private helper routines ─────────────────────────────────────────────────

def _online_characters() -> list:
    """Return each character that a connected session puppets, one time."""
    sessions = evennia.SESSION_HANDLER.get_sessions()
    found = {}

    for session in sessions:
        puppet = session.get_puppet()

        if puppet is not None:
            found.setdefault(puppet.id, puppet)

    return list(found.values())


def _area_where(obj):
    """Return the area key of the tile of `obj`, or None off the tile world."""
    view = tile_travel.plane_view(obj)
    tile = tile_travel.tile_of(obj)

    if view is None or tile is None:
        return None

    return view.area_at(*tile)


def _say_rule(speaker):
    """Return a test: does a listener stand in the say range of `speaker`?"""
    rooms = tile_world_rooms(speaker.location, const.SAY_RADIUS)

    if rooms is None:
        rooms = [speaker.location]

    near = set(rooms)

    return lambda listener: listener.location in near


def _yell_rule(speaker):
    """Return a test: does a listener stand in the area of `speaker`?"""
    area = _area_where(speaker)

    if area is None:
        return lambda listener: listener.location == speaker.location

    return lambda listener: _area_where(listener) == area


# ─── Module globals ──────────────────────────────────────────────────────────

# reach -> the function that makes the test of a listener. After the
# helpers, because the rows name them.
_REACH_RULES: dict = {
    const.REACH_SAY: _say_rule,
    const.REACH_YELL: _yell_rule,
}


# ─── Public routines ─────────────────────────────────────────────────────────

def listeners(speaker, reach: str = const.REACH_SAY, online=None) -> list:
    """
    Purpose: List the listeners of one line that `speaker` speaks.

    Entry:
        speaker - the object that speaks.
        reach   - a key of _REACH_RULES. An unknown key gives [] and a log
                  line, so a typo never shows a traceback to a player.
        online  - the characters to test. None means each character that a
                  connected session puppets. A test gives its own list.

    Exit/Returns:
        A list of characters. The speaker is never in it. A speaker with no
        location gets [].

    Module Globals:
        _REACH_RULES read.

    Methodology:
        1. Get the rule of the reach, and make its test for the speaker.
        2. Keep each online character, except the speaker, that passes.

    Notes/References:
        The list includes the listeners in the room of the speaker.
        `Character.at_say` gives that room its line through Evennia, so it
        keeps only the other listeners.

    Author: Nick Hobar
    Creation date: 10/05/2026
    """
    rule = _REACH_RULES.get(reach)

    if getattr(speaker, "location", None) is None:
        return []

    if rule is None:
        logger.log_err(f"speech: unknown reach {reach!r} from {speaker.key}.")
        return []

    if online is None:
        online = _online_characters()

    hears = rule(speaker)
    found = [listener for listener in online
             if listener != speaker and hears(listener)]

    return found
