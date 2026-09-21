"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/13/2026
Description: Blackout armor ItemDef entries — head armor
"""



import systems.gameplay.combat.constants as combat_constants
from items.equipment.constants import WieldLocation
from world.item_database import ItemDef



ITEMS = {

    # ------------------------------------
    # --- RUSTY SCRAP MELEE ARMOR HEAD ---
    # ------------------------------------

    "rusty_scrap_great_helm": ItemDef(
        key="rusty_scrap_great_helm",
        name="rusty scrap great helm",
        typeclass="typeclasses.items.ArmorItem",
        desc="Rusty scrap great helm. Infection not included.",
        value=44,
        weight=2.721,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.HEAD,
        tool_type="helmet",
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_great_helm", "armor")],
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
            "stab_defense_bonus": 4,
            "slash_defense_bonus": 5,
            "crush_defense_bonus": 3,

            # Projectile defense bonuses
            "light_defense_bonus": 4,
            "standard_defense_bonus": 5,
            "heavy_defense_bonus": 3,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # ------------------------------
    # --- SCRAP MELEE ARMOR HEAD ---
    # ------------------------------

    "scrap_great_helm": ItemDef(
        key="scrap_great_helm",
        name="scrap great helm",
        typeclass="typeclasses.items.ArmorItem",
        desc="Scrap great helm. Infection not included.",
        value=154,
        weight=2.721,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.HEAD,
        tool_type="helmet",
        tier=1,
        req_level=10,
        tags=[("scrap_great_helm", "armor")],
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
            "stab_defense_bonus": 6,
            "slash_defense_bonus": 7,
            "crush_defense_bonus": 5,

            # Projectile defense bonuses
            "light_defense_bonus": 6,
            "standard_defense_bonus": 7,
            "heavy_defense_bonus": 5,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # -------------------------------
    # --- COPPER MELEE ARMOR HEAD ---
    # -------------------------------

    "copper_great_helm": ItemDef(
        key="copper_great_helm",
        name="copper great helm",
        typeclass="typeclasses.items.ArmorItem",
        desc="Copper great helm. It covers the face, which is a mercy.",
        value=550,
        weight=2.721,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.HEAD,
        tool_type="helmet",
        tier=2,
        req_level=20,
        tags=[("copper_great_helm", "armor")],
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
            "stab_defense_bonus": 9,
            "slash_defense_bonus": 10,
            "crush_defense_bonus": 7,

            # Projectile defense bonuses
            "light_defense_bonus": 9,
            "standard_defense_bonus": 10,
            "heavy_defense_bonus": 7,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),
}
