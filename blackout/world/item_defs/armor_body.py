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



    # ----------------------------------
    # --- MANGANESE MELEE ARMOR BODY ---
    # ----------------------------------

    # The OSRS Mithril chainbody, as the copper chainbody is the OSRS Steel
    # chainbody. As on every chainbody, the light projectile defense is the
    # stab defense, the heavy is the OSRS ranged defense (27), and the
    # standard is between the two. Every tier of chainbody weighs 3.0.
    "manganese_chainbody": ItemDef(
        key="manganese_chainbody",
        name="manganese chainbody",
        typeclass="typeclasses.items.ArmorItem",
        desc="Manganese chainbody.",
        value=1950,
        weight=3.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.BODY,
        tool_type="chainbody",
        tier=3,
        req_level=30,
        tags=[("manganese_chainbody", "armor")],
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
            "melee_stab_defense_bonus": 25,
            "melee_slash_defense_bonus": 35,
            "melee_crush_defense_bonus": 42,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 25,
            "projectile_standard_defense_bonus": 26,
            "projectile_heavy_defense_bonus": 27,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # ----------------------------------------
    # --- RUSTY SCRAP MELEE ARMOR PLATEBODY ---
    # ----------------------------------------

    # The platebodies are the OSRS platebodies on the chainbody rule.
    # Rusty scrap is Bronze, scrap is Iron, copper is Steel, and manganese
    # is Mithril. The light projectile defense is the stab defense, the
    # heavy is the OSRS ranged defense, and the standard is the middle of
    # the two, rounded down. The OSRS magic and ranged attack penalties are
    # dropped, as on the platelegs. Every tier weighs 10.0 (OSRS 9.979).
    "rusty_scrap_platebody": ItemDef(
        key="rusty_scrap_platebody",
        name="rusty scrap platebody",
        typeclass="typeclasses.items.ArmorItem",
        desc="Rusty scrap platebody.",
        value=160,
        weight=10.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.BODY,
        tool_type="platebody",
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_platebody", "armor")],
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
            "melee_stab_defense_bonus": 15,
            "melee_slash_defense_bonus": 14,
            "melee_crush_defense_bonus": 9,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 15,
            "projectile_standard_defense_bonus": 14,
            "projectile_heavy_defense_bonus": 14,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # ----------------------------------
    # --- SCRAP MELEE ARMOR PLATEBODY ---
    # ----------------------------------

    "scrap_platebody": ItemDef(
        key="scrap_platebody",
        name="scrap platebody",
        typeclass="typeclasses.items.ArmorItem",
        desc="Scrap platebody.",
        value=560,
        weight=10.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.BODY,
        tool_type="platebody",
        tier=1,
        req_level=10,
        tags=[("scrap_platebody", "armor")],
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
            "melee_stab_defense_bonus": 21,
            "melee_slash_defense_bonus": 20,
            "melee_crush_defense_bonus": 12,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 21,
            "projectile_standard_defense_bonus": 20,
            "projectile_heavy_defense_bonus": 20,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # -----------------------------------
    # --- COPPER MELEE ARMOR PLATEBODY ---
    # -----------------------------------

    "copper_platebody": ItemDef(
        key="copper_platebody",
        name="copper platebody",
        typeclass="typeclasses.items.ArmorItem",
        desc="Copper platebody.",
        value=2000,
        weight=10.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.BODY,
        tool_type="platebody",
        tier=2,
        req_level=20,
        tags=[("copper_platebody", "armor")],
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
            "melee_stab_defense_bonus": 32,
            "melee_slash_defense_bonus": 31,
            "melee_crush_defense_bonus": 24,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 32,
            "projectile_standard_defense_bonus": 31,
            "projectile_heavy_defense_bonus": 31,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),



    # --------------------------------------
    # --- MANGANESE MELEE ARMOR PLATEBODY ---
    # --------------------------------------

    "manganese_platebody": ItemDef(
        key="manganese_platebody",
        name="manganese platebody",
        typeclass="typeclasses.items.ArmorItem",
        desc="Manganese platebody.",
        value=5200,
        weight=10.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.BODY,
        tool_type="platebody",
        tier=3,
        req_level=30,
        tags=[("manganese_platebody", "armor")],
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
            "melee_stab_defense_bonus": 46,
            "melee_slash_defense_bonus": 44,
            "melee_crush_defense_bonus": 38,

            # Projectile defense bonuses
            "projectile_light_defense_bonus": 46,
            "projectile_standard_defense_bonus": 45,
            "projectile_heavy_defense_bonus": 44,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
    ),
}
