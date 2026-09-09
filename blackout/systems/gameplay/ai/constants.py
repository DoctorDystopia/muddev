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


# ─── Object attribute names ─────────────────────────────────────────────────

# db attribute naming which behaviour drives this entity. Absent or None means
# "no AI" -- which is the correct reading for a player Character, and is why the
# controller seam needs no isinstance check to tell a player from a monster.
AI_BEHAVIOR_ATTR = "ai_behavior"

# ndb attribute holding the id of the entity that last damaged this one.
# An id rather than the object: the attacker's row can be deleted between the
# hit and the next tick, and combat.py already resolves combatants by id for
# exactly that reason.
LAST_ATTACKER_ID_ATTR = "last_attacker_id"
