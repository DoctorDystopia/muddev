"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: The vocabulary, bounds and message templates for player-written
             words. One owner for each, imported by everything else in the
             package and by the ItemDef that stamps the medium's tag.

             The tag category is the piece most worth reading twice. It is
             declared HERE and imported by world/item_defs/tools.py rather than
             typed there, for exactly the reason DEV_TOOL_TAG_CATEGORY is: the
             service finds a writer's medium by that category and the ItemDef
             stamps it, so a disagreement between the two spellings is a spray
             can that cannot be sprayed with nothing raised either way.
"""

# ─── The medium ──────────────────────────────────────────────────────────────

# The tag category an item declares to say it can write on the world.
#
# A CATEGORY and not a typeclass, so a second medium -- a paint stick, a
# welding torch, a datapad that prints stickers -- is one ItemDef entry and no
# edit anywhere in this package. CLAUDE.md blesses the multi-family tag
# explicitly: a spray can is a `crafting_tool` for the pane's mesh AND a
# graffiti medium for this check, and Evennia files each pair independently.
GRAFFITI_MEDIUM_CATEGORY: str = "graffiti_medium"

# Where a medium's remaining charges are stored, and how many it starts with.
#
# The default lives here rather than on the ItemDef, because it is a rule about
# the SYSTEM and not a property of one can: an item that declares the medium tag
# and nothing else works immediately, at the standard capacity. A can wanting
# its own number overrides this attribute at creation.
CHARGES_ATTR: str = "graffiti_charges"
DEFAULT_CHARGES: int = 12

# ─── Provenance and lifetime ─────────────────────────────────────────────────

# Who wrote it, and when. Both are stamped at write time and neither is ever
# rewritten: an edited scrawl is a new one, because a mutable author field is a
# way to pin someone else's words on a player.
#
# The id alone, with no copy of the name beside it. A name is derivable from the
# id whenever it is wanted and goes stale the moment a character is renamed, so
# a stored copy would be a second answer to "who wrote this" that can disagree
# with the first -- and the one a moderator would read.
AUTHOR_ID_ATTR: str = "graffiti_author_id"
WRITTEN_AT_ATTR: str = "graffiti_written_at"

# How long a scrawl lasts before the sweep takes it, in seconds.
#
# WALL CLOCK, not ticks. The tick counter is the right clock for anything
# measured against combat -- consumables use it -- and the wrong one here: a
# week of real time has to survive every restart, reload and quiet night in
# between, and a tick count does not obviously do that. A week is long enough
# that a player can show someone what they wrote and short enough that a bad
# week of a popular tile clears itself.
LIFETIME_SECONDS: int = 7 * 24 * 60 * 60

# How often the sweep runs. An hour, against a week-long lifetime: the point is
# that junk goes away, not that it goes away punctually, and a scrawl living an
# extra 59 minutes is nothing a player can see.
SWEEP_INTERVAL_SECONDS: int = 60 * 60

# The db_key of the singleton Script that runs the sweep. Read by decay.py
# through managers.get_singleton_script, which is what repairs the row if this
# package is ever moved -- see that routine for why a Script key is not enough
# on its own.
DECAY_SCRIPT_KEY: str = "graffiti_decay"

# ─── Refusals ────────────────────────────────────────────────────────────────

# The setting naming words a scrawl may not contain, and the default.
#
# EMPTY by default, and deliberately so: a blocklist is an editorial decision
# about a particular game's community and not something this module should make
# on a server operator's behalf. What belongs here is the SEAM -- one place the
# check happens, ahead of the writing -- so that turning it on is a settings
# edit rather than a patch.
#
# Matched case-insensitively as a substring, which over-blocks. That is the
# correct direction for the failure: a refused scrawl costs a player one charge
# they keep, and a permitted one costs a moderator a callout.
BLOCKLIST_SETTING: str = "BLACKOUT_GRAFFITI_BLOCKLIST"
BLOCKLIST_DEFAULT: tuple = ()

# ─── Messages ────────────────────────────────────────────────────────────────

MSG_WRITE_WHAT: str = "Write what? (write <text>)"
MSG_NO_MEDIUM: str = "You have nothing to write with."
MSG_EMPTY_MEDIUM: str = "{medium} is empty."
MSG_NOTHING_TO_WRITE: str = "That leaves nothing to read."
MSG_REFUSED: str = "You think better of writing that."
MSG_NOWHERE: str = "There is nothing here to write on."

# Names the charges left, because a can is a consumable and a player spending
# one is entitled to know how many they have. Says "charge" singular at one, for
# the same reason every other count in the game does.
MSG_WROTE: str = "You scrawl it across the wall. ({left} left in {medium}.)"
MSG_WROTE_LAST: str = "You scrawl it across the wall. {medium} sputters dry."

# What the room sees. The author is named on purpose: writing on a wall in
# front of other people is a public act, and a silent one would let a player
# deny it.
MSG_ROOM_WROTE: str = "{author} scrawls something across the wall."

# The key the created object carries. Not the text: a scrawl's words are a
# player's and change nothing about what the object IS, and a key that moved
# with them would be a player choosing what `destroy` and `look` match on.
GRAFFITI_KEY: str = "graffiti"
