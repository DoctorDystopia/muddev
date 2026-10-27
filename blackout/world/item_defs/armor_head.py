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
            "melee_stab_attack_bonus": 0,
            "melee_slash_attack_bonus": 0,
            "melee_crush_attack_bonus": 0,

            # Projectile attack bonuses
            "projectile_light_attack_bonus": 0,
            "projectile_standard_attack_bonus": 0,
            "projectile_heavy_attack_bonus": 0,

            # Melee defense bonuses
            "melee_stab_defense_bonus": 4,
            "melee_slash_defense_bonus": 5,
            "melee_crush_defense_bonus": 3,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 4,
            "projectile_standard_defense_bonus": 5,
            "projectile_heavy_defense_bonus": 3,

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
            "melee_stab_attack_bonus": 0,
            "melee_slash_attack_bonus": 0,
            "melee_crush_attack_bonus": 0,

            # Projectile attack bonuses
            "projectile_light_attack_bonus": 0,
            "projectile_standard_attack_bonus": 0,
            "projectile_heavy_attack_bonus": 0,

            # Melee defense bonuses
            "melee_stab_defense_bonus": 6,
            "melee_slash_defense_bonus": 7,
            "melee_crush_defense_bonus": 5,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 6,
            "projectile_standard_defense_bonus": 7,
            "projectile_heavy_defense_bonus": 5,

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
            "melee_stab_attack_bonus": 0,
            "melee_slash_attack_bonus": 0,
            "melee_crush_attack_bonus": 0,

            # Projectile attack bonuses
            "projectile_light_attack_bonus": 0,
            "projectile_standard_attack_bonus": 0,
            "projectile_heavy_attack_bonus": 0,

            # Melee defense bonuses
            "melee_stab_defense_bonus": 9,
            "melee_slash_defense_bonus": 10,
            "melee_crush_defense_bonus": 7,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 9,
            "projectile_standard_defense_bonus": 10,
            "projectile_heavy_defense_bonus": 7,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),
}
