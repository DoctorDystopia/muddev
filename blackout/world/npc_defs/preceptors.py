"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/09/2026
Description: The Preceptor NpcDef entries (DESIGN-0012).

             `preceptor_key` names the PreceptorDef in
             systems/gameplay/exterminator/preceptors.py, which gives the
             tasks and the buffs. Every Preceptor speaks from one dialogue
             module. world/npc_dialogues/preceptor.py holds the lines of each
             one.
"""

from systems.gameplay.exterminator.preceptors import (
    PRECEPTOR_ATTICUS_QUIN,
    PRECEPTOR_ATUM_MUSA,
)
from world.npc_database import NPC_TYPECLASS_PRECEPTOR, NpcDef


# The model of a Preceptor with no model record of its own.
_FALLBACK_ASSET_KEY = "talkative_npc"


NPCS = {
    # No model yet, so it keeps the fallback. Display text TBD.
    "atticus_quin": NpcDef(
        key="atticus_quin",
        name="Atticus Quin",
        typeclass=NPC_TYPECLASS_PRECEPTOR,
        desc=(
            "A preceptor in a long red coat, a red lens where one eye was. "
            "Wax seals hang from his sleeves on strips of parchment."
        ),
        asset_key=_FALLBACK_ASSET_KEY,
        dialogue="preceptor",
        preceptor_key=PRECEPTOR_ATTICUS_QUIN,
    ),

    # The model is a VoxEdit priest, assets/models/npcs/atum_musa.toml. All lore is TBD.
    "atum_musa": NpcDef(
        key="atum_musa",
        name="Atum Musa",
        typeclass=NPC_TYPECLASS_PRECEPTOR,
        desc=(
            "An old preceptor in a white linen kilt, a broad collar of gold and "
            "blue beads across the shoulders."
        ),
        dialogue="preceptor",
        preceptor_key=PRECEPTOR_ATUM_MUSA,
    ),
}
