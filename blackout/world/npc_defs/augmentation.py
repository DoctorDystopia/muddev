"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The NpcDef entries of the two NPCs of the Augmentation intro
             quest (DESIGN-0015, Phase 4): the recruiter at the Augmentation
             Clinic, and the contact at the Public Hospital.

             EVERY NAME AND EVERY TEXT HERE IS A PLACEHOLDER. Nick owns the
             lore and the names (10/30/2026). The keys and the names come
             from the quest module, so the quest, the defs, and the
             dialogues cannot spell them differently.
"""

from systems.gameplay.quests.content import quest_augmentation_intro as quest
from world.npc_database import NPC_TYPECLASS_TALKATIVE, NpcDef


# The model of an NPC with no model record of its own.
_FALLBACK_ASSET_KEY = "talkative_npc"


NPCS = {
    quest.NPC_CLINIC_KEY: NpcDef(
        key=quest.NPC_CLINIC_KEY,
        name=quest.NPC_CLINIC_NAME,
        typeclass=NPC_TYPECLASS_TALKATIVE,
        asset_key=_FALLBACK_ASSET_KEY,
        desc=(
            "Placeholder. The recruiter of the Augmentation Clinic, the one "
            "who gives the Augmentation intro quest."
        ),
        dialogue="aug_clinic_1",
    ),
    quest.NPC_HOSPITAL_KEY: NpcDef(
        key=quest.NPC_HOSPITAL_KEY,
        name=quest.NPC_HOSPITAL_NAME,
        typeclass=NPC_TYPECLASS_TALKATIVE,
        asset_key=_FALLBACK_ASSET_KEY,
        desc=(
            "Placeholder. The contact at the Al Wasta Regional Public "
            "Hospital, where the trail of the missing augments ends."
        ),
        dialogue="aug_hospital_1",
    ),
}
