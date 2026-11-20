"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The NpcDef entries of the two NPCs of the Augmentation intro
             quest (DESIGN-0015, Phase 4): the recruiter at the Augmentation
             Clinic, and the contact at the Public Hospital.

             EVERY TEXT HERE IS A PLACEHOLDER, except the two names. Nick
             owns the lore and the names (10/30/2026), and he named the two
             NPCs on 11/19/2026. The keys and the names come from the quest
             module, so the quest and the defs cannot spell them
             differently.

             Each of the two speaks from a dialogue script (DESIGN-0017,
             11/11/2026): `godot/dialogue/aug_clinic_1.dialogue` and
             `aug_hospital_1.dialogue`. A script types each key as a
             literal, and the content check refuses a key that names
             nothing.
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
            "The chief doctor of the Augmentation Clinic. Seems important."
        ),
        dialogue_script="aug_clinic_1",
    ),
    quest.NPC_HOSPITAL_KEY: NpcDef(
        key=quest.NPC_HOSPITAL_KEY,
        name=quest.NPC_HOSPITAL_NAME,
        typeclass=NPC_TYPECLASS_TALKATIVE,
        asset_key=_FALLBACK_ASSET_KEY,
        desc=(
            "Head of the Al Wasta Regional Public Hospital. Looks tired."
        ),
        dialogue_script="aug_hospital_1",
    ),
}
