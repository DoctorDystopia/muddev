from world.item_database import ItemDef

ITEMS = {
    "rusty_metal_chunk": ItemDef(
        key="rusty_metal_chunk",
        name="Rusty Metal Chunk",
        desc="A chunk of metal corroded by rust and age.",
        value=1,
        weight=2.0,
        tradeable=True,
        stackable=False,
        tags=[("rusty_metal_chunk", "crafting_material")],
    ),
    "rusty_metal_dust": ItemDef(
        key="rusty_metal_dust",
        name="Rusty Metal Dust",
        desc="A fine, reddish-brown dust ground from rusty metal.",
        value=2,
        weight=0.2,
        tradeable=True,
        stackable=True,
        tags=[("rusty_metal_dust", "crafting_material")],
    ),
    "rusty_scrap_metal": ItemDef(
        key="rusty_scrap_metal",
        name="Rusty Scrap Metal",
        desc="A rough piece of scrap metal, smelted down from a rusty chunk.",
        value=5,
        weight=1.0,
        tradeable=True,
        stackable=False,
        tags=[("rusty_scrap_metal", "crafting_material")],
    ),
}
