"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/05/2026
Description: The reach of each speech command, and the lines that it sends.

             Nick's rules, 10/05/2026:

             - `say` reaches every listener within SAY_RADIUS tiles, on the
               plane of the speaker. A player hears each person that the
               Godot client shows. This is the OSRS public chat rule.
             - `yell` reaches every listener in the area of the speaker, on
               every plane.
             - A wall does not stop speech. Only the reach counts.

             `hearing.py` applies the rules. `Character.at_say` sends the
             lines.
"""

from systems.interface.statefeed import constants as feed_const


# ─── Public constant definitions ─────────────────────────────────────────────

# The reach of each speech command: the `reach` argument of
# `Character.at_say`. A call with no reach is a say, because Evennia's `say`
# command gives none.
REACH_SAY: str = "say"
REACH_YELL: str = "yell"

# How far a say goes, in tiles. It IS the radius of the statefeed contents,
# so a player hears each person that the client draws. The metric is
# `targeting.within_metric`, the one of the statefeed and the auras.
SAY_RADIUS: int = feed_const.STATEFEED_ENTITY_RADIUS

# The lines of a say. Evennia writes the line to the speaker. The listeners
# get this one, on every tile of the say range.
SAY_HEARD: str = '{object} says, "{speech}"'

# The lines of a yell.
YELL_SELF: str = 'You yell, "|n{speech}|n"'
YELL_HEARD: str = '{object} yells, "{speech}"'
YELL_EMPTY: str = "Yell what?"
