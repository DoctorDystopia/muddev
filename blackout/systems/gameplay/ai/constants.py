"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: Named constants for the NPC behaviour system. One owner per fact,
             per CLAUDE.md -- a behaviour key is typed in an NpcDef, stamped
             onto a spawned object, and looked up in the registry, and those
             three spellings must be the same string.
"""



# ─── Behaviour keys ─────────────────────────────────────────────────────────
# The value stamped onto an NPC's db.ai_behavior and looked up in
# BEHAVIOR_REGISTRY. A "Metalsmith" vs "Metalsmithing" mismatch here would make
# an NPC silently inert rather than raise, which is why these are constants.

# Swing back at whatever last damaged us, for as long as it is still reachable.
AI_BEHAVIOR_AGGRESSIVE_MELEE = "aggressive_melee"

# The same, plus one step toward an attacker that is out of reach.
#
# A SECOND KEY, NOT A STEP ADDED TO THE FIRST. Every hostile in the game names
# aggressive_melee today, so folding the chase into it would have changed the
# behaviour of every NPC at once, with no way to keep one still. An NpcDef
# opts in by naming this key instead, which is a one-line content change per
# NPC and is reversible the same way.
AI_BEHAVIOR_CHASING_MELEE = "chasing_melee"


# ─── Chase tunables ─────────────────────────────────────────────────────────

# How far a chasing NPC follows before it gives up and goes home, measured
# from the tile it was standing on when the chase started.
#
# It is what stops a player pulling one raider across the whole map and
# parking it somewhere it does not belong. Ten tiles is past the reach of
# every weapon that exists, so a chase always gets at least one shot at
# closing the distance before the leash bites.
LEASH_DISTANCE_TILES = 10


# ─── Object attribute names ─────────────────────────────────────────────────

# db attribute naming which behaviour drives this entity. Absent or None means
# "no AI" -- which is the correct reading for a player Character, and is why the
# controller seam needs no isinstance check to tell a player from a monster.
AI_BEHAVIOR_ATTR = "ai_behavior"

# db attribute holding the ROOM a chase started from, and the tile a leashed
# NPC walks back to.
#
# On db rather than ndb, so a reload during a chase does not strand an NPC
# wherever it happened to be standing. It holds an object reference, not an
# import path -- see the CLAUDE.md rule, which is about paths and not about
# rows. The respawn queue persists room references for the same reason.
LEASH_ORIGIN_ATTR = "leash_origin"

# ndb attribute holding the id of the entity that last damaged this one.
# An id rather than the object: the attacker's row can be deleted between the
# hit and the next tick, and combat.py already resolves combatants by id for
# exactly that reason.
LAST_ATTACKER_ID_ATTR = "last_attacker_id"
