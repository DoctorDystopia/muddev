"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/09/2026
Description: The NpcDef entries of the NPCs that give a quest and have no
             other role.

             A quest giver is a TalkativeNPC. Its dialogue module gives the
             quest, through the read and write API of QuestHandler.
"""

from world.npc_database import NPC_TYPECLASS_TALKATIVE, NpcDef


NPCS = {
    # The android that tends the oasis farm, and the giver of "Oasis in the
    # Wastes", the opening quest. Design is in the vault note of the quest.
    "lone_android": NpcDef(
        key="lone_android",
        name="Lone Android",
        typeclass=NPC_TYPECLASS_TALKATIVE,
        desc=(
            "A farm-hand android, alone. Its chassis is sand-scoured down to "
            "the primer and one knee joint whines when it moves. It is bent "
            "over a datapad, writing, and does not appear to have noticed you."
        ),
        dialogue="oasis_lone_android",
    ),
}
