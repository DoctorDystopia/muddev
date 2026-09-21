"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Blackout armor ItemDef entries — capes, etc.
"""



import systems.gameplay.combat.constants as combat_constants
from items.equipment.constants import WieldLocation
from world.item_database import ItemDef



ITEMS = {

    # ------------------------------------
    # --- RUSTY SCRAP MELEE ARMOR BACK ---
    # ------------------------------------

    "rusty_scrap_hide_cape": ItemDef(
        key="rusty_scrap_hide_cape",
        name="rusty scrap hide cape",
        typeclass="typeclasses.items.ArmorItem",
        desc="Rusty scrap hide cape. Infection not included.",
        value=9,
        weight=0.453,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.BACK,
        tool_type="cape",
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_hide_cape", "armor")],
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
            "stab_defense_bonus": 1,
            "slash_defense_bonus": 1,
            "crush_defense_bonus": 1,

            # Projectile defense bonuses
            "light_defense_bonus": 1,
            "standard_defense_bonus": 1,
            "heavy_defense_bonus": 1,

            # Other bonuses
            "melee_strength_bonus": 1,
            "projectile_strength_bonus": 1,
        },
    ),



    # ------------------------------
    # --- SCRAP MELEE ARMOR BACK ---
    # ------------------------------

    "scrap_hide_cape": ItemDef(
        key="scrap_hide_cape",
        name="scrap hide cape",
        typeclass="typeclasses.items.ArmorItem",
        desc="Scrap hide cape. Vaguely fashionable.",
        value=29,
        weight=0.453,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.BACK,
        tool_type="cape",
        tier=1,
        req_level=10,
        tags=[("scrap_hide_cape", "armor")],
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
            "stab_defense_bonus": 2,
            "slash_defense_bonus": 2,
            "crush_defense_bonus": 2,

            # Projectile defense bonuses
            "light_defense_bonus": 2,
            "standard_defense_bonus": 2,
            "heavy_defense_bonus": 2,

            # Other bonuses
            "melee_strength_bonus": 2,
            "projectile_strength_bonus": 2,
        },
    ),



    # -------------------------------
    # --- COPPER MELEE ARMOR BACK ---
    # -------------------------------
    
    "copper_hide_cape": ItemDef(
        key="copper_hide_cape",
        name="copper hide cape",
        typeclass="typeclasses.items.ArmorItem",
        desc="Copper hide cape. Vaguely shiny.",
        value=89,
        weight=0.453,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.BACK,
        tool_type="cape",
        tier=2,
        req_level=20,
        tags=[("copper_hide_cape", "armor")],
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
            "stab_defense_bonus": 3,
            "slash_defense_bonus": 3,
            "crush_defense_bonus": 3,

            # Projectile defense bonuses
            "light_defense_bonus": 3,
            "standard_defense_bonus": 3,
            "heavy_defense_bonus": 3,

            # Other bonuses
            "melee_strength_bonus": 3,
            "projectile_strength_bonus": 3,
        },
    ),
}
