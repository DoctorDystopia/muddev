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

# The speed cap: the most tiles that a walker moves in one tick (Nick,
# 11/14/2026: 3). A lit augment adds its tile bonus to the walk or the run,
# up to this cap. Nitro at the top power level takes a run to the cap. The
# Godot client reads it too. Its step animation must slide a move of this
# length, and not snap it.
MAX_TILES_PER_TICK: int = 3

# ─── Attribute names ─────────────────────────────────────────────────────────

# The run toggle, on the character. Persistent, so run stays on through a
# logout, as in OSRS. No resource drains yet (Nick, 09/29/2026).
RUN_ATTR: str = "run_enabled"

# The walk in progress, on `ndb`. `walk.set_walk` is its one writer.
WALK_NDB_ATTR: str = "tile_walk"

# The tile carry, on `ndb`, as a Fraction. A walker keeps this part of a tile
# from one tick to the next. A whole tile of carry adds one tile to the
# stride of that tick. The carry stays on the character, not on the walk. A
# held key makes a new walk two times a tick.
TILE_CARRY_NDB_ATTR: str = "tile_carry"

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
# A walk with a follow-up that ends short of its goal says this, in the
# place of the follow-up. Placeholder words (Nick, 11/16/2026).
MSG_CANNOT_REACH: str = "You cannot reach that."
MSG_RUN_ON: str = "You will now run."
MSG_RUN_OFF: str = "You will now walk."
MSG_RUN_USAGE: str = "Usage: run, run on, or run off."
