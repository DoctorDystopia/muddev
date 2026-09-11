"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/10/2026
Description: The Corpse typeclass -- an item that is also a gathering node.

             Everything about a corpse's CONTENT (what it yields, to which
             skill, at what level) lives in GATHERABLE_REGISTRY and in its
             ItemDef. This class is only the behaviour those two cannot
             express: it is used up by a successful harvest, it remembers
             which NPC it came from, and it tells a client that it affords
             both butchering and being carried off.
"""

from commands.gathering_cmds import gathering_verbs
from systems.interface.statefeed.constants import ASSET_KIND_CORPSE
from typeclasses.items import BaseItem


# Attribute holding the npc_key of the NPC this corpse was left by.
#
# Deliberately NOT `npc_key`. Two live readers key off that name and both
# would be wrong about a corpse:
#
#   systems/gameplay/spawning/respawn.py npc_present() -- a corpse answering
#   to "mutant_raider" reads as a live raider standing on the tile, so the
#   respawn sweep sees the slot as filled. It does not requeue; it DROPS the
#   entry. The raider would never come back, and dragging the corpse away
#   afterwards would not undo it, because there is nothing left to sweep.
#
#   systems/interface/statefeed/serializers.py _asset_identity() -- npc_key is
#   the first branch it checks, so the client would draw a walking raider
#   where the body is.
#
# Naming it differently is what makes both of those structurally impossible
# rather than a thing to remember. The corpse's own identity for the client
# comes from its asset key, and its yields from db.gatherable_key.
CORPSE_NPC_KEY_ATTR = "corpse_npc_key"



class Corpse(BaseItem):
    """
    Purpose: A body left where something died, workable by a gathering skill.

    Entry:
        Spawned through ITEM_DB, whose ItemDef supplies gatherable_key. The
        NPC that left it stamps CORPSE_NPC_KEY_ATTR afterwards.

    Exit/Returns:
        No conditions.

    Module variables:
        CORPSE_NPC_KEY_ATTR read by callers stamping provenance.

    Methodology:
        An ITEM, not scenery, because the design is that a player may butcher
        it where it fell or pocket it for later -- and being an item means
        `get`, `drop`, weight, the inventory handler and the 3D bag pane all
        already work on it. Being a gathering node at the same time costs one
        attribute, db.gatherable_key, which its ItemDef stamps.

        There is deliberately no decay timer. Blackout has no global despawn
        mechanic yet, and a corpse should not be the one object in the game
        that invents one for itself -- when items learn to rot, corpses rot
        with them. It is also NOT tied to the NPC's respawn window: the two
        were coupled in the original sketch of this feature, and coupling
        them would mean every future change to a respawn timer silently
        became a change to how long a body lasts. The only thing that ever
        made the coupling look necessary was the npc_key collision that
        CORPSE_NPC_KEY_ATTR above removes.

    Notes/References:
        world/item_defs/corpses.py holds the ItemDefs;
        systems/gameplay/progression/skills/gatherables.py holds the yields.

    Author: Nick Hobar
    Creation date: 09/10/2026
    """
    # Read by systems/interface/statefeed/serializers.py. A corpse is neither
    # an item nor a gatherable to a renderer -- it is both at once, and the
    # `actions` list is what says so.
    asset_kind = ASSET_KIND_CORPSE

    # Read by GatheringSkill.consume_node. One corpse is one harvest, by
    # design; declared here rather than branched on in the skill so that the
    # skill never has to ask what kind of thing it is working.
    consumed_by_harvest = True


    def extra_actions(self) -> list:
        """
        Purpose: Everything a player may do with a body.

        Entry:
            No conditions.

        Exit/Returns:
            Returns a list of {"command", "label"} dicts: one per gathering
            skill that can work this corpse, then `get`.

        Module variables:
            None.

        Methodology:
            The gathering verbs come first because they are why the corpse is
            interesting; `get` is last because carrying a body somewhere is
            the fallback, not the point. Both are offered rather than one
            chosen for the player -- which is the entire reason
            serialize_entity grew an action LIST.

            The verbs are read from the registry through the same helper the
            nodes use, so a corpse that gains a Brain Farming yield gains its
            button with no edit here.

            No level filtering. Two reasons: serialize_entity has no observer
            to filter against, and the skill already refuses with the level it
            wants, which tells the player something a missing button does not.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        actions = gathering_verbs(self)
        actions.append({"command": f"get {self.key}", "label": "get"})

        return actions


    @property
    def asset_key(self) -> str:
        """
        Purpose: Which corpse mesh a client should draw.

        Entry:
            No conditions.

        Exit/Returns:
            Returns the source NPC's key when one was stamped, else this
            corpse's own gatherable key, else "".

        Module variables:
            CORPSE_NPC_KEY_ATTR read.

        Methodology:
            The source NPC first, so a client that has art for a mutant
            raider can reuse it lying down. The gatherable key is the fallback
            rather than "" so a hand-built corpse still names something
            specific, and a client with neither falls through to the corpse
            FAMILY mesh -- which is the guarantee that adding a corpse never
            requires a client edit.

        Notes/References:
            serializers._asset_identity reads `asset_kind`/`asset_key` off the
            typeclass, so this property is consulted live.

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        source_key = self.attributes.get(CORPSE_NPC_KEY_ATTR, default=None)

        if source_key:
            return str(source_key)

        return str(self.attributes.get("gatherable_key", default="") or "")
