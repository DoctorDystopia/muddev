"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: ItemDef entries for raw and processed crafting materials.
"""

from world.item_database import ItemDef

ITEMS = {
    "rusty_metal_chunk": ItemDef(
        key="rusty_metal_chunk",
        name="rusty metal chunk",
        desc="A chunk of metal corroded by rust and age.",
        value=1,
        weight=2.0,
        tradeable=True,
        stackable=False,
        tags=[("rusty_metal_chunk", "crafting_material")],
    ),
    "rusty_metal_dust": ItemDef(
        key="rusty_metal_dust",
        name="rusty metal dust",
        desc="A fine, reddish-brown dust ground from rusty metal.",
        value=2,
        weight=0.2,
        tradeable=True,
        stackable=True,
        tags=[("rusty_metal_dust", "crafting_material")],
    ),
    "rusty_scrap_metal": ItemDef(
        key="rusty_scrap_metal",
        name="rusty scrap metal",
        desc="A rough piece of scrap metal, smelted down from a rusty chunk.",
        value=5,
        weight=1.0,
        tradeable=True,
        stackable=False,
        tags=[("rusty_scrap_metal", "crafting_material")],
    ),
}
