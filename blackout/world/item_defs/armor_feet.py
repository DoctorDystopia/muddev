"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Blackout armor ItemDef entries — feet armor
              test targets. Stats are OSRS bronze-tier translated to the
              0..127 scale. combat_stat_bonuses keys are per-damage-type
              (stab_attack_bonus, slash_attack_bonus, crush_attack_bonus,
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
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 1,
            "slash_defense_bonus": 2,
            "crush_defense_bonus": 3,

            # Projectile defense bonuses
            "light_defense_bonus": 1,
            "standard_defense_bonus": 2,
            "heavy_defense_bonus": 3,

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
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 2,
            "slash_defense_bonus": 3,
            "crush_defense_bonus": 4,

            # Projectile defense bonuses
            "light_defense_bonus": 2,
            "standard_defense_bonus": 3,
            "heavy_defense_bonus": 4,

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
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 5,
            "slash_defense_bonus": 6,
            "crush_defense_bonus": 7,

            # Projectile defense bonuses
            "light_defense_bonus": 5,
            "standard_defense_bonus": 6,
            "heavy_defense_bonus": 7,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),
}
