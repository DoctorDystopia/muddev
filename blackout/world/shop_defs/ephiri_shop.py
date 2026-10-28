"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: ShopDef entry for Ephiri's Equipment Emporium shopkeeper's stock and pricing.
"""



from world.shop_defs import ShopDef, WareStock



ITEMS = {
    "ephiri_shop": ShopDef(
        key="ephiri_shop",
        name="Ephiri",
        desc="A rough looking human with a lot of sharp things on the wall.",
        greeting='"Need supplies? I have the best gear in Al Wasta."',
        farewell='"Stay safe out there."',
        upsell_factor=1.5,
        miser_factor=0.5,
        max_held_items=20,
        buy_list=["rusty_scrap_axe", "hammer", "rusty_metal_chunk", "spray_can", "rusty_scrap_dagger", "rusty_scrap_shortsword", "rusty_scrap_spear", "rusty_scrap_greatsword", "rusty_scrap_great_helm", "rusty_scrap_chainbody", "rusty_scrap_platelegs", "rusty_scrap_square_shield"],
        stock={
            "hammer": WareStock(max_stock=10, restock_seconds=60.0),
            "rusty_scrap_axe": WareStock(max_stock=10, restock_seconds=60.0),
            "rusty_scrap_dagger": WareStock(max_stock=10, restock_seconds=60.0),
            "rusty_scrap_shortsword": WareStock(max_stock=10, restock_seconds=60.0),
            "rusty_scrap_spear": WareStock(max_stock=10, restock_seconds=60.0),
            "rusty_scrap_greatsword": WareStock(max_stock=10, restock_seconds=60.0),
            "rusty_scrap_great_helm": WareStock(max_stock=10, restock_seconds=60.0),
            "rusty_scrap_chainbody": WareStock(max_stock=10, restock_seconds=60.0),
            "rusty_scrap_platelegs": WareStock(max_stock=10, restock_seconds=60.0),
            "rusty_scrap_square_shield": WareStock(max_stock=10, restock_seconds=60.0),
        },
    ),
}
