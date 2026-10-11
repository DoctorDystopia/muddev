"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: The creature types, one row for each type.

             A creature type is a general kind of hostile NPC, for example
             `mutant`. An Exterminator task names one creature type, not one
             exact NPC. Thus, a Mutant task counts the Mutant Raider, the
             Mutant Giant, the Big Mutant, and the Mutant Crab.

             One NPC can have several types. The Mutant Crab is a `mutant`
             and a `crab`, so it counts for a Mutant task and for a Crab
             task. `NpcDef.creature_types` lists the types of each NPC, and
             `creature_types_of` in `world/npc_database.py` reads them.

             An `npc_key` is not a creature type. `mutant_crab` names one
             NpcDef. `mutant` names a group of them.

             The vault note `03_Systems/Skills/Utility_Skills/
             Exterminator_Skill.md` owns the rules. DESIGN-0012, Phase 1.
             Every display name and every level here is TBD (Nick,
             10/06/2026).
"""

from dataclasses import dataclass



# ─── Creature type keys ────────────────────────────────────────────────────
# The one spelling of each type key. An NpcDef, a Preceptor, and a buff read
# the key from here, never from a string literal.
CREATURE_TYPE_MUTANT: str = "mutant"
CREATURE_TYPE_CRAB: str = "crab"
CREATURE_TYPE_EYE: str = "eye"
CREATURE_TYPE_GIANT: str = "giant"



@dataclass(frozen=True)
class CreatureType:
    """
    One creature type.

    `key` is the name that an NpcDef and a task store. `name` and `plural`
    are the display names. A task line uses `plural`, for example "Kill 40
    mutants". Each row holds its own plural, because English plurals are
    not regular. `required_level` is the Exterminator level that a player
    needs before a Preceptor gives a task of this type.
    """

    key: str
    name: str
    plural: str
    required_level: int



_CREATURE_TYPE_ROWS: tuple = (
    CreatureType(CREATURE_TYPE_MUTANT, "Mutant", "Mutants", 0),  # TBD name, TBD level
    CreatureType(CREATURE_TYPE_CRAB, "Crab", "Crabs", 0),        # TBD name, TBD level
    CreatureType(CREATURE_TYPE_EYE, "Eye", "Eyes", 5),           # TBD name, TBD level
    CreatureType(CREATURE_TYPE_GIANT, "Giant", "Giants", 10),    # TBD name, TBD level
)

# key -> CreatureType, in the order of _CREATURE_TYPE_ROWS.
CREATURE_TYPES: dict = {row.key: row for row in _CREATURE_TYPE_ROWS}
