"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Blackout jewellery ItemDef entries — neck and finger items whose
             effect comes from a rules definition, not from combat stats.

Jewellery is the reason action rules are collected from EVERY equipment slot
rather than from the wielded weapon alone: an amulet changes how an action
resolves without being the thing performing it.
"""

from items.equipment.constants import WieldLocation
from world.item_database import ItemDef


ITEMS = {
    "glass_cannon_amulet": ItemDef(
        key="glass_cannon_amulet",
        name="Glass Cannon amulet",
        typeclass="typeclasses.items.EquippableItem",
        desc=(
            "A blown-glass pendant, gray cloudy fog hides something powerful. It "
            "rewards muscle you have not balanced with the sense to survive."
        ),
        value=120,
        weight=0.2,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.NECK,
        tier=1,
        req_level=0,
        tags=[("glass_cannon_amulet", "jewellery")],
        combat_rules=["glass_cannon_amulet"],
    ),
}
