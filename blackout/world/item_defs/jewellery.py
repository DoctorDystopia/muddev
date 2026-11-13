"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Blackout jewellery ItemDef entries — neck and finger items.
             An item gets its effect from a rules definition, from a flat
             stat block, or from the two.

Jewellery is the reason action rules are collected from EVERY equipment slot
rather than from the wielded weapon alone: an amulet changes how an action
resolves without being the thing performing it.

A flat bonus needs no rules definition. The Necklace of Brawn declares
combat_stat_bonuses, and the equipment handler adds it like an armour piece.
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
        value=1120,
        weight=0.2,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.NECK,
        tier=0,
        req_level=0,
        tags=[("glass_cannon_amulet", "jewellery")],
        combat_rules=["glass_cannon_amulet"],
    ),

    "necklace_of_brawn": ItemDef(
        key="necklace_of_brawn",
        name="Necklace of Brawn",
        typeclass="typeclasses.items.EquippableItem",
        desc=(
            "A sturdy necklace adorned with a dense, black pendant. It "
            "enhances the wearer's physical strength."
        ),
        value=320,
        weight=0.2,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.NECK,
        tier=0,
        req_level=0,
        tags=[("necklace_of_brawn", "jewellery")],
        combat_stat_bonuses={
            # Melee attack bonuses
            "melee_stab_attack_bonus": 0,
            "melee_slash_attack_bonus": 0,
            "melee_crush_attack_bonus": 0,

            # Projectile attack bonuses
            "projectile_light_attack_bonus": 0,
            "projectile_standard_attack_bonus": 0,
            "projectile_heavy_attack_bonus": 0,

            # Melee defense bonuses
            "melee_stab_defense_bonus": 0,
            "melee_slash_defense_bonus": 0,
            "melee_crush_defense_bonus": 0,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 0,
            "projectile_standard_defense_bonus": 0,
            "projectile_heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 10,
            "projectile_strength_bonus": 0,
        },
    ),
}
