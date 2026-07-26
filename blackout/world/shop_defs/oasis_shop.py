from world.shop_defs import ShopDef

ITEMS = {
    "oasis_shop": ShopDef(
        key="oasis_shop",
        name="Shopkeeper",
        desc="A tiny robot with a stall full of salvaged goods.",
        greeting='"Need supplies? I have the best scrap in the oasis."',
        farewell='"Stay safe out there."',
        upsell_factor=1.5,
        miser_factor=0.5,
        max_held_items=20,
        buy_list=["rusty_scrap_axe", "hammer", "rusty_metal_chunk"],
    ),
}
