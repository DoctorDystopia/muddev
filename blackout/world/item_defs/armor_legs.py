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

    # ------------------------------------
    # --- RUSTY SCRAP MELEE ARMOR LEGS ---
    # ------------------------------------

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
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_platelegs", "armor")],
        # attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 8,
            "slash_defense_bonus": 7,
            "crush_defense_bonus": 6,

            # Projectile defense bonuses
            "light_defense_bonus": 8,
            "standard_defense_bonus": 7,
            "heavy_defense_bonus": 6,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # ------------------------------
    # --- SCRAP MELEE ARMOR LEGS ---
    # ------------------------------

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
            # Melee attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 11,
            "slash_defense_bonus": 10,
            "crush_defense_bonus": 10,

            # Projectile defense bonuses
            "light_defense_bonus": 11,
            "standard_defense_bonus": 10,
            "heavy_defense_bonus": 10,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # -------------------------------
    # --- COPPER MELEE ARMOR LEGS ---
    # -------------------------------

    "copper_platelegs": ItemDef(
        key="copper_platelegs",
        name="copper platelegs",
        typeclass="typeclasses.items.ArmorItem",
        desc="Copper platelegs. They ring when you walk, and you learn to like it.",
        value=1000,
        weight=9.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.LEGS,
        tool_type="platelegs",
        tier=2,
        req_level=20,
        tags=[("copper_platelegs", "armor")],
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 17,
            "slash_defense_bonus": 16,
            "crush_defense_bonus": 15,

            # Projectile defense bonuses
            "light_defense_bonus": 17,
            "standard_defense_bonus": 16,
            "heavy_defense_bonus": 15,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),
}
