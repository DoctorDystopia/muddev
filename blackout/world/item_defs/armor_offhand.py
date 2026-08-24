"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Blackout armor ItemDef entries — offhand armor
              test targets. Stats are OSRS bronze-tier translated to the
              0..127 scale. combat_stat_bonuses keys are per-damage-type
              (stab_attack_bonus, slash_attack_bonus, crush_attack_bonus,
               melee_strength_bonus) plus per-damage-type defense.
"""



import systems.combat.constants as combat_constants
from items.equipment.constants import WieldLocation
from world.item_database import ItemDef



ITEMS = {
    "rusty_scrap_square_shield": ItemDef(
        key="rusty_scrap_square_shield",
        name="rusty scrap square shield",
        typeclass="typeclasses.items.ArmorItem",
        desc="Rusty scrap square shield. Infection not included.",
        value=48,
        weight=3.628,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.OFF_HAND,
        tool_type="square_shield",
        tier=1,
        req_level=0,
        tags=[("rusty_scrap_square_shield", "armor")],
        combat_stat_bonuses={
            # Attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,
            # Defense bonuses
            "stab_defense_bonus": 5,
            "slash_defense_bonus": 6,
            "crush_defense_bonus": 4,
            # Other bonuses
            "melee_strength_bonus": 0,
        },
    ),
}
