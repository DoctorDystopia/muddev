"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/13/2026
Description: Blackout armor ItemDef entries — legs armor
"""



import systems.gameplay.combat.constants as combat_constants
from items.equipment.constants import WieldLocation
from world.item_database import ItemDef



ITEMS = {
    # ─── Rusty scrap melee armor legs ───────────────────────────────────────────────
    "rusty_scrap_platelegs": ItemDef(
        key="rusty_scrap_platelegs",
        name="rusty scrap platelegs",
        typeclass="typeclasses.items.ArmorItem",
        desc="Rusty scrap platelegs. Infection not included.",
        value=80,
        weight=9.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.LEGS,
        tool_type="platelegs",
        tier=1,
        req_level=0,
        tags=[("rusty_scrap_platelegs", "armor")],
        # attack_speed=4,
        combat_stat_bonuses={
            # Attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,
            # Defense bonuses
            "stab_defense_bonus": 8,
            "slash_defense_bonus": 7,
            "crush_defense_bonus": 6,
            # Other bonuses
            "melee_strength_bonus": 0,
        },
    ),



    # ─── Scrap melee armor legs ───────────────────────────────────────────────
    "scrap_platelegs": ItemDef(
        key="scrap_platelegs",
        name="scrap platelegs",
        typeclass="typeclasses.items.ArmorItem",
        desc="Scrap platelegs. Infection not included.",
        value=280,
        weight=9.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.LEGS,
        tool_type="platelegs",
        tier=1,
        req_level=10,
        tags=[("scrap_platelegs", "armor")],
        # attack_speed=4,
        combat_stat_bonuses={
            # Attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,
            # Defense bonuses
            "stab_defense_bonus": 11,
            "slash_defense_bonus": 10,
            "crush_defense_bonus": 10,
            # Other bonuses
            "melee_strength_bonus": 0,
        },
    ),
}
