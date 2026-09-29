"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/29/2026
Description: The tunables, the attribute names, and the player text of
             the walk. The speed of a walk and of a run is here.

             `walk.py` reads them. This module imports nothing, so the
             statefeed can read the run attribute name with no import of the
             walk.
"""

# ─── Speed ───────────────────────────────────────────────────────────────────

# Tiles for each tick. A walk and a run use the same tick. The OSRS rule:
# one tile a tick to walk, two tiles a tick to run. A run takes its two
# tiles in ONE move, so it skips the middle tile (the OSRS tile skip).
WALK_TILES_PER_TICK: int = 1
RUN_TILES_PER_TICK: int = 2

# ─── Attribute names ─────────────────────────────────────────────────────────

# The run toggle, on the character. Persistent, so run stays on through a
# logout, as in OSRS. No resource drains yet (Nick, 09/29/2026).
RUN_ATTR: str = "run_enabled"

# The walk in progress, on `ndb`. `walk.set_walk` is its one writer.
WALK_NDB_ATTR: str = "tile_walk"

# The last refused step, on `ndb`, as (tile, direction). A held key sends its
# direction two times a tick. The player reads the refusal one time, not
# each time the client sends the key again.
REFUSAL_NDB_ATTR: str = "tile_walk_refusal"

# ─── The run command ─────────────────────────────────────────────────────────

RUN_WORDS_ON: frozenset = frozenset({"on", "1", "yes"})
RUN_WORDS_OFF: frozenset = frozenset({"off", "0", "no"})

# ─── Player text ─────────────────────────────────────────────────────────────

MSG_NO_WAY: str = "You cannot go that way."
MSG_BLOCKED: str = "Something blocks the way."
MSG_WALL: str = "A wall blocks the way."
MSG_CORNER: str = "You cannot cut that corner."
MSG_TOO_STEEP: str = "It is too steep to climb."
MSG_WALK_BROKEN: str = "Your walk stops."
MSG_ARRIVED: str = "Target reached."
MSG_RUN_ON: str = "You will now run."
MSG_RUN_OFF: str = "You will now walk."
MSG_RUN_USAGE: str = "Usage: run, run on, or run off."
