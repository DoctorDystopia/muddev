"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/09/2026
Description: The shopkeep NpcDef entries.

             One entry for each shopkeep, and one object kind of the same key
             in world/object_kinds.py, so the terrain editor can place it.
             OSRS does the same: each shopkeep is its own NPC. `shop_key`
             names the ShopDef in world/shop_defs that gives the wares.
"""



from world.npc_database import NPC_TYPECLASS_SHOPKEEP, NpcDef



NPCS = {
    # The stall at the oasis. Until 10/09/2026, three places gave three
    # different descriptions. The tile sync wrote this one last, so this is
    # the text that players saw.
    "shopkeeper_oasis": NpcDef(
        key="shopkeeper_oasis",
        name="Shopkeeper",
        typeclass=NPC_TYPECLASS_SHOPKEEP,
        desc="A tiny robot with a stall full of salvaged goods.",
        asset_key="shopkeeper",
        dialogue="shopkeep",
        shop_key="oasis_shop",
    ),
    "shopkeeper_al_wasta": NpcDef(
        key="shopkeeper_al_wasta",
        name="Shopkeeper",
        typeclass=NPC_TYPECLASS_SHOPKEEP,
        desc="A rough looking human with a building full of salvaged goods.",
        asset_key="shopkeeper_al_wasta",
        dialogue="shopkeep",
        shop_key="al_wasta_shop",
    ),
    "shopkeeper_ephiri": NpcDef(
        key="shopkeeper_ephiri",
        name="Ephiri",
        typeclass=NPC_TYPECLASS_SHOPKEEP,
        desc="A rough looking human with a lot of sharp things on the wall.",
        asset_key="shopkeeper_ephiri",
        dialogue="shopkeep",
        shop_key="ephiri_shop",
    ),
}
