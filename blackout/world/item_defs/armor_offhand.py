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



import systems.gameplay.combat.constants as combat_constants
from items.equipment.constants import WieldLocation
from world.item_database import ItemDef



ITEMS = {

    # ---------------------------------------
    # --- RUSTY SCRAP MELEE ARMOR OFFHAND ---
    # ---------------------------------------

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
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_square_shield", "armor")],
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
            "crush_defense_bonus": 4,

            # Projectile defense bonuses
            "light_defense_bonus": 5,
            "standard_defense_bonus": 6,
            "heavy_defense_bonus": 4,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # ---------------------------------
    # --- SCRAP MELEE ARMOR OFFHAND ---
    # ---------------------------------

    "scrap_square_shield": ItemDef(
        key="scrap_square_shield",
        name="scrap square shield",
        typeclass="typeclasses.items.ArmorItem",
        desc="Scrap square shield. Infection not included.",
        value=168,
        weight=3.628,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.OFF_HAND,
        tool_type="square_shield",
        tier=1,
        req_level=10,
        tags=[("scrap_square_shield", "armor")],
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
            "slash_defense_bonus": 9,
            "crush_defense_bonus": 7,

            # Projectile defense bonuses
            "light_defense_bonus": 8,
            "standard_defense_bonus": 9,
            "heavy_defense_bonus": 7,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # ----------------------------------
    # --- COPPER MELEE ARMOR OFFHAND ---
    # ----------------------------------

    "copper_square_shield": ItemDef(
        key="copper_square_shield",
        name="copper square shield",
        typeclass="typeclasses.items.ArmorItem",
        desc="Copper square shield. Flat, bright, and between you and the rest of it.",
        value=600,
        weight=3.628,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.OFF_HAND,
        tool_type="square_shield",
        tier=2,
        req_level=20,
        tags=[("copper_square_shield", "armor")],
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
            "stab_defense_bonus": 12,
            "slash_defense_bonus": 13,
            "crush_defense_bonus": 11,

            # Projectile defense bonuses
            "light_defense_bonus": 12,
            "standard_defense_bonus": 13,
            "heavy_defense_bonus": 11,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),
}
