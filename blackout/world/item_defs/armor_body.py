"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Blackout armor ItemDef entries — body armor
              test targets. Stats are OSRS bronze-tier translated to the
              0..127 scale. combat_stat_bonuses keys are per-damage-type
              (melee_stab_attack_bonus, melee_slash_attack_bonus, melee_crush_attack_bonus,
               melee_strength_bonus) plus per-damage-type defense.
"""



import systems.gameplay.combat.constants as combat_constants
from items.equipment.constants import WieldLocation
from world.item_database import ItemDef



ITEMS = {

    # ------------------------------------
    # --- RUSTY SCRAP MELEE ARMOR BODY ---
    # ------------------------------------

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
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_chainbody", "armor")],
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
            "melee_stab_defense_bonus": 7,
            "melee_slash_defense_bonus": 11,
            "melee_crush_defense_bonus": 13,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 7,
            "projectile_standard_defense_bonus": 8,
            "projectile_heavy_defense_bonus": 9,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # ------------------------------
    # --- SCRAP MELEE ARMOR BODY ---
    # ------------------------------

    "scrap_chainbody": ItemDef(
        key="scrap_chainbody",
        name="scrap chainbody",
        typeclass="typeclasses.items.ArmorItem",
        desc="Scrap chainbody. Sturdy, enough",
        value=210,
        weight=3.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.BODY,
        tool_type="chainbody",
        tier=1,
        req_level=10,
        tags=[("scrap_chainbody", "armor")],
        # attack_speed=4,
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
            "melee_stab_defense_bonus": 10,
            "melee_slash_defense_bonus": 15,
            "melee_crush_defense_bonus": 19,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 10,
            "projectile_standard_defense_bonus": 11,
            "projectile_heavy_defense_bonus": 12,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # -------------------------------
    # --- COPPER MELEE ARMOR BODY ---
    # -------------------------------

    "copper_chainbody": ItemDef(
        key="copper_chainbody",
        name="copper chainbody",
        typeclass="typeclasses.items.ArmorItem",
        desc="Copper chainbody. A little shiny.",
        value=750,
        weight=3.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.BODY,
        tool_type="chainbody",
        tier=2,
        req_level=20,
        tags=[("copper_chainbody", "armor")],
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
            "melee_stab_defense_bonus": 17,
            "melee_slash_defense_bonus": 25,
            "melee_crush_defense_bonus": 30,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 17,
            "projectile_standard_defense_bonus": 18,
            "projectile_heavy_defense_bonus": 19,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),
}
