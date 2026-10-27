"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Blackout armor ItemDef entries — feet armor
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
    # --- RUSTY SCRAP MELEE ARMOR FEET ---
    # ------------------------------------

    "rusty_scrap_boots": ItemDef(
        key="rusty_scrap_boots",
        name="rusty scrap boots",
        typeclass="typeclasses.items.ArmorItem",
        desc="Rusty scrap boots. Infection not included.",
        value=24,
        weight=1.36,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.FEET,
        tool_type="boots",
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_boots", "armor")],
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
            "melee_stab_defense_bonus": 1,
            "melee_slash_defense_bonus": 2,
            "melee_crush_defense_bonus": 3,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 1,
            "projectile_standard_defense_bonus": 2,
            "projectile_heavy_defense_bonus": 3,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # ------------------------------
    # --- SCRAP MELEE ARMOR FEET ---
    # ------------------------------

    "scrap_boots": ItemDef(
        key="scrap_boots",
        name="scrap boots",
        typeclass="typeclasses.items.ArmorItem",
        desc="Scrap boots. Infection not included.",
        value=84,
        weight=1.36,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.FEET,
        tool_type="boots",
        tier=1,
        req_level=10,
        tags=[("scrap_boots", "armor")],
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
            "melee_stab_defense_bonus": 2,
            "melee_slash_defense_bonus": 3,
            "melee_crush_defense_bonus": 4,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 2,
            "projectile_standard_defense_bonus": 3,
            "projectile_heavy_defense_bonus": 4,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # -------------------------------
    # --- COPPER MELEE ARMOR FEET ---
    # -------------------------------

    "copper_boots": ItemDef(
        key="copper_boots",
        name="copper boots",
        typeclass="typeclasses.items.ArmorItem",
        desc="Copper boots. Solid over the toe, where it counts.",
        value=300,
        weight=1.36,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.FEET,
        tool_type="boots",
        tier=2,
        req_level=20,
        tags=[("copper_boots", "armor")],
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
            "melee_stab_defense_bonus": 5,
            "melee_slash_defense_bonus": 6,
            "melee_crush_defense_bonus": 7,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 5,
            "projectile_standard_defense_bonus": 6,
            "projectile_heavy_defense_bonus": 7,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),
}
