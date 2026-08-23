"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: ItemDef entries for raw and processed crafting materials.
"""



from world.item_database import ItemDef



ITEMS = {
    # Rusty metal items
    "rusty_metal_chunk": ItemDef(
        key="rusty_metal_chunk",
        name="rusty metal chunk",
        desc="A chunk of metal corroded by rust and age.",
        value=4,
        weight=2.0,
        tradeable=True,
        stackable=False,
        tags=[("rusty_metal_chunk", "crafting_material")],
    ),
    "rusty_metal_dust": ItemDef(
        key="rusty_metal_dust",
        name="rusty metal dust",
        desc="A fine, reddish-brown dust ground from rusty metal.",
        value=8,
        weight=0.2,
        tradeable=True,
        stackable=True,
        tags=[("rusty_metal_dust", "crafting_material")],
    ),
    "rusty_scrap_metal": ItemDef(
        key="rusty_scrap_metal",
        name="rusty scrap metal",
        desc="A rough piece of scrap metal, smelted down from a rusty chunk.",
        value=10,
        weight=1.0,
        tradeable=True,
        stackable=False,
        tags=[("rusty_scrap_metal", "crafting_material")],
    ),

    # Metal items
    "metal_chunk": ItemDef(
        key="metal_chunk",
        name="metal chunk",
        desc="A chunk of metal. Weirdly fresh.",
        value=17,
        weight=2.267,
        tradeable=True,
        stackable=False,
        tags=[("metal_chunk", "crafting_material")],
    ),
    "metal_dust": ItemDef(
        key="metal_dust",
        name="metal dust",
        desc="A fine, grey dust ground from metal.",
        value=19,
        weight=0.2,
        tradeable=True,
        stackable=True,
        tags=[("metal_dust", "crafting_material")],
    ),
    "scrap_metal": ItemDef(
        key="scrap_metal",
        name="scrap metal",
        desc="A rough piece of scrap metal, smelted down from a metal chunk.",
        value=28,
        weight=1.814,
        tradeable=True,
        stackable=False,
        tags=[("scrap_metal", "crafting_material")],
    ),
}
