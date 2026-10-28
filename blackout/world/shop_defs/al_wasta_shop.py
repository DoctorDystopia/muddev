"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: ShopDef entry for the Al Wasta shopkeeper's stock and pricing.
"""



from world.shop_defs import ShopDef, WareStock



ITEMS = {
    "al_wasta_shop": ShopDef(
        key="al_wasta_shop",
        name="Shopkeeper",
        desc="A rough looking human with a building full of salvaged goods.",
        greeting='"Need supplies? I have the best scrap in the oasis."',
        farewell='"Stay safe out there."',
        upsell_factor=1.5,
        miser_factor=0.5,
        max_held_items=20,
        buy_list=["rusty_scrap_axe", "hammer", "rusty_metal_chunk", "spray_can", "mutant_raider_cured_chuck"],
        stock={
            "rusty_scrap_axe": WareStock(max_stock=10, restock_seconds=60.0),
            "hammer": WareStock(max_stock=10, restock_seconds=60.0),
            "rusty_metal_chunk": WareStock(max_stock=30, restock_seconds=10.0),
            "spray_can": WareStock(max_stock=5, restock_seconds=120.0),
            "mutant_raider_cured_chuck": WareStock(max_stock=30, restock_seconds=120.0),
        },
    ),
}
