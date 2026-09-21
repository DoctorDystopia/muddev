"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/10/2026
Description: ItemDef entries for the corpses hostile NPCs leave behind.

             A corpse is an ITEM and not a piece of scenery, because the
             design is that a player may butcher it where it fell or pocket it
             and deal with it later. Being an item means the inventory
             handler, `get`, `drop`, weight and the 3D pane all work on it
             already.

             It is a gathering NODE at the same time, by carrying a
             gatherable_key -- so the same registry that says a rusty pole
             yields a metal chunk to Cutting says a raider corpse yields a
             chuck to Butchery, and the same skill code reads both.

             What it must NOT carry is db.npc_key. Two separate things read
             that attribute and both would be wrong about a corpse:
             npc_present() would see a live mutant raider standing on the tile
             and cancel the real one's respawn permanently, and the statefeed
             would classify the corpse as an NPC and draw a walking raider.
             Provenance lives in db.corpse_npc_key instead -- a different
             name, so neither reader can find it by accident.
"""



from systems.interface.statefeed.constants import ITEM_FAMILY_CORPSE
from world.item_database import ItemDef



ITEMS = {
    "mutant_raider_corpse": ItemDef(
        key="mutant_raider_corpse",
        name="Mutant Raider corpse",
        typeclass="typeclasses.corpses.Corpse",
        desc="What is left of a mutant raider. Stinky...",
        value=2,
        weight=30.0,
        tradeable=True,
        stackable=False,
        gatherable_key="mutant_raider_corpse",
        tags=[("mutant_raider_corpse", ITEM_FAMILY_CORPSE)],
    ),

    # Twice the raider's weight and value, by the same rule every giant entry
    # in materials.py and food.py follows. A player who wants to butcher this
    # one somewhere else carries 60 units to get it there.
    "mutant_giant_corpse": ItemDef(
        key="mutant_giant_corpse",
        name="Mutant Giant corpse",
        typeclass="typeclasses.corpses.Corpse",
        desc="What is left of a mutant giant. It takes up most of the tile.",
        value=4,
        weight=60.0,
        tradeable=True,
        stackable=False,
        gatherable_key="mutant_giant_corpse",
        tags=[("mutant_giant_corpse", ITEM_FAMILY_CORPSE)],
    ),
}
