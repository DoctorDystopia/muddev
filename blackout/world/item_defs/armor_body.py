"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Blackout armor ItemDef entries — body armor
              test targets. Stats are OSRS bronze-tier translated to the
              0..127 scale. combat_stat_bonuses keys are per-damage-type
              (stab_attack_bonus, slash_attack_bonus, crush_attack_bonus,
               melee_strength_bonus) plus per-damage-type defense.
"""

import systems.combat.constants as combat_constants
from items.equipment.constants import WieldLocation
from world.item_database import ItemDef



ITEMS = {
    "rusty_scrap_chainbody": ItemDef(
        key="rusty_scrap_chainbody",
        name="rusty scrap chainbody",
        typeclass="typeclasses.items.ArmorItem",
        desc="Rusty scrap chainbody. Infection not included.",
        value=25,
        weight=3.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.BODY,
        tool_type="chainbody",
        tier=1,
        req_level=0,
        tags=[("rusty_scrap_chainbody", "armor")],
        # attack_speed=4,
        combat_stat_bonuses={
            # Attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,
            # Defense bonuses
            "stab_defense_bonus": 7,
            "slash_defense_bonus": 11,
            "crush_defense_bonus": 13,
            # Other bonuses
            "melee_strength_bonus": 0,
        },
        # combat_styles=_SHORTSWORD_COMBAT_STYLES,
        # default_combat_style="irimi",
    ),
}
