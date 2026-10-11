"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/09/2026
Description: The spawner of every NPC, one registry entry for each NpcDef.

             The spawner key of an NPC is its npc key. The object kind of the
             NPC in world/object_kinds.py names that key in its `spawner`.
             Thus, a new NpcDef is placeable with no spawner code: the one
             loop below registers it.

             Until 10/09/2026, each NPC had its own spawner function: five
             for the hostiles in npc_combat.py, the same except for the key,
             and four for the talking NPCs in npcs.py.

             THE MIGRATION OF THE OLD ROWS. A talking NPC that an old spawner
             made has no db.npc_key, and three of them carry a typeclass path
             that no longer exists. `_adopt_legacy` finds such an NPC on its
             tile, swaps it to the typeclass of its role, and stamps its key.
             It rides the tile sync that the operator already runs, as
             ShopkeepNPC.ensure_cleanup_script does. Remove it when no live
             database holds an old row.
"""

from evennia.utils import logger

from systems.gameplay.spawning.respawn import npc_standing
from typeclasses.spawners import register_spawner
from world.npc_database import NPC_DB, NPC_KEY_ATTR


# The typeclass path of each NPC that an old spawner made -> its npc key. The
# rows keep the path after the class is gone: `typeclass_path` is a database
# field, and Evennia loads such a row as a DefaultObject.
LEGACY_NPC_TYPECLASSES: dict = {
    "typeclasses.npcs.LoneAndroidNPC": "lone_android",
    "typeclasses.npcs.AtticusQuinNPC": "atticus_quin",
    "typeclasses.npcs.AtumMusaNPC": "atum_musa",
    "typeclasses.npcs.ShopkeepNPC": "shopkeeper_oasis",
}



def _adopt_legacy(npc_key: str, room):
    """
    Purpose: Give an old NPC on this tile the identity of its def.

    Entry:
        npc_key is a key of NPC_DB. room is a tile room.

    Exit/Returns:
        Returns the adopted NPC, or None if no old NPC of this key stands in
        the room.

    Module Globals:
        LEGACY_NPC_TYPECLASSES, NPC_DB, NPC_KEY_ATTR read.

    Methodology:
        An old NPC is an object with no npc_key whose typeclass path maps to
        this key. If its path differs from the typeclass of the def, swap the
        typeclass. clean_cmdsets and the start hooks rebuild the cmdsets of
        the role, so no copy of an old cmdset stays.

    Notes/References:
        The module docstring gives the reason.

    Author: Nick Hobar
    Creation date: 10/09/2026
    """
    npc_def = NPC_DB[npc_key]
    wanted = npc_def.resolved_typeclass()

    for obj in room.contents:
        if obj.attributes.has(NPC_KEY_ATTR):
            continue

        if LEGACY_NPC_TYPECLASSES.get(obj.typeclass_path) != npc_key:
            continue

        if obj.typeclass_path != wanted:
            obj.swap_typeclass(wanted, clean_cmdsets=True, run_start_hooks="all")

        obj.attributes.add(NPC_KEY_ATTR, npc_key)
        logger.log_info(f"npc_spawners: adopted {obj.dbref} as {npc_key!r}.")

        return obj

    return None



def spawn_npc(npc_key: str, room):
    """
    Purpose: Stand up the NPC of one NpcDef on its tile.

    Entry:
        npc_key is a key of NPC_DB. room is a tile room.

    Exit/Returns:
        Returns the NPC on the tile: the one already standing, or a new one.
        The tile sync gives it its facing.

    Module Globals:
        NPC_DB read.

    Methodology:
        1. An NPC with this npc_key already stands here: keep it.
        2. Else an old NPC of this key stands here: adopt it.
        3. Else create one from the def.
        Then call refresh_from_def, so the name and the role upkeep follow
        the def on each tile sync.

        The presence guard keys on db.npc_key, not on is_typeclass: every
        hostile shares one typeclass, and so do all shopkeeps. The respawn
        manager uses the same guard, which closes the race of a sync during
        the dead window of a hostile.

    Notes/References:
        The tile sync calls each spawner on each refresh, so it must be
        idempotent.

    Author: Nick Hobar
    Creation date: 10/09/2026
    """
    standing = npc_standing(npc_key, room)

    if standing is None:
        standing = _adopt_legacy(npc_key, room)

    if standing is None:
        standing = NPC_DB[npc_key].create(location=room)

    standing.refresh_from_def()

    return standing



def _spawner_for(npc_key: str):
    """Give the spawner callable of one npc key, for SPAWNER_REGISTRY."""
    def _spawn(room):
        return spawn_npc(npc_key, room)

    _spawn.__name__ = f"spawn_{npc_key}"

    return _spawn



for _npc_key in NPC_DB:
    register_spawner(_npc_key)(_spawner_for(_npc_key))
