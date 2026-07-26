from world.item_database import ItemDef
from items.equipment.constants import WieldLocation

ITEMS = {
    "rusty_scrap_sword": ItemDef(
        key="rusty_scrap_sword",
        name="Rusty Scrap Sword",
        typeclass="typeclasses.items.WeaponItem",
        desc="Rusty scrap sword. Infection not included.",
        value=20,
        weight=3.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="sword",
        tier=1,
        req_level=0,
        tags=[("rusty_scrap_sword", "weapon")],
    ),
    "rusty_scrap_spear": ItemDef(
        key="rusty_scrap_spear",
        name="Rusty Scrap Spear",
        typeclass="typeclasses.items.WeaponItem",
        desc="Rusty scrap spear. Infection not included.",
        value=20,
        weight=3.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="spear",
        tier=1,
        req_level=0,
        tags=[("rusty_scrap_spear", "weapon")],
    ),
}