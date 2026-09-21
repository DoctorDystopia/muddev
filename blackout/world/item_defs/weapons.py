"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Blackout weapon ItemDef entries — sword + spear
              test targets. Stats are OSRS bronze-tier translated to the
              0..127 scale. combat_stat_bonuses keys are per-damage-type
              (stab_attack_bonus, slash_attack_bonus, crush_attack_bonus,
               melee_strength_bonus) plus per-damage-type defense.
"""



import systems.gameplay.combat.constants as combat_constants
from items.equipment.constants import WieldLocation
from world.item_database import ItemDef



# ─── Common 4-combat-style melee map ──────────────────────────────────────────────
# Each weapon category defines four combat styles. Every style has:
#   attack_type               — damage type used for accuracy (stab / slash / crush)
#   weapon_style              — the manner of which a weapon is used in combat (accurate, aggressive, defensive, controlled)
#   weapon_style_xp_skill     — which skill(s) receives XP (fortitude / strike / brawn / defense) based on weapon style
#   weapon_style_level_boost  — ref to the invisible-level-boost dict from constants based on weapon style


# Dagger styles
_DAGGER_COMBAT_STYLES = {
    # Italian Renaissance Stiletto style: Emphasizes blindingly fast, precise jabs targeting unarmored vital spots (neck, eye slots, groin, inner thighs).
    "jab": {
        "attack_type": "stab",
        "weapon_style": "accurate",
        "weapon_style_xp_skill": combat_constants.ACCURATE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE,
    },
    "lunge": {
        "attack_type": "stab",
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE
    },
    "slash": {
        "attack_type": "slash",
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE
    },
    # Spanish Destreza style: close-quarters defensive posture utilizing limb locks and blade traps
    "bind": {
        "attack_type": "stab",
        "weapon_style": "defensive",
        "weapon_style_xp_skill": combat_constants.DEFENSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_DEFENSIVE
    }
}


# Stab sword styles
_SHORTSWORD_COMBAT_STYLES = {
    # Japanese Martial Arts style: Emphasizes precise thrusts and fluid footwork. "Close for you, far for your opponent"
    "irimi": {
        "attack_type": "stab",
        "weapon_style": "accurate",
        "weapon_style_xp_skill": combat_constants.ACCURATE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE,
    },
    "lunge": {
        "attack_type": "stab",
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE
    },
    "slash": {
        "attack_type": "slash",
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE
    },
    "guard": {
        "attack_type": "stab",
        "weapon_style": "defensive",
        "weapon_style_xp_skill": combat_constants.DEFENSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_DEFENSIVE
    }
}


# Scimitar styles
_SCIMITAR_COMBAT_STYLES = {
    "chop": {
        "attack_type": "sllash",
        "weapon_style": "accurate",
        "weapon_style_xp_skill": combat_constants.ACCURATE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE,
    },
    "slash": {
        "attack_type": "slash",
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE
    },
    "lunge": {
        "attack_type": "stab",
        "weapon_style": "controlled",
        "weapon_style_xp_skill": combat_constants.CONTROLLED_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_CONTROLLED
    },
    "guard": {
        "attack_type": "slash",
        "weapon_style": "defensive",
        "weapon_style_xp_skill": combat_constants.DEFENSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_DEFENSIVE
    }
}


# Spear styles
_SPEAR_COMBAT_STYLES = {
    "lunge": {
        "attack_type": "stab",
        "weapon_style": "controlled",
        "weapon_style_xp_skill": combat_constants.CONTROLLED_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_CONTROLLED
    },
    "swipe": {
        "attack_type": "slash",
        "weapon_style": "controlled",
        "weapon_style_xp_skill": combat_constants.CONTROLLED_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_CONTROLLED
    },
    "pummel": {
        "attack_type": "crush",
        "weapon_style": "controlled",
        "weapon_style_xp_skill": combat_constants.CONTROLLED_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_CONTROLLED
    },
    "guard": {
        "attack_type": "stab",
        "weapon_style": "defensive",
        "weapon_style_xp_skill": combat_constants.DEFENSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_DEFENSIVE
    }
}


# Battleaxe styles
_BATTLEAXE_COMBAT_STYLES = {
    # Viking/HEMA Overhead Cleave: A precise downward chop utilizing the top-heavy weight of the axe head to split defenses.
    "chop": {
        "attack_type": "slash",
        "weapon_style": "accurate",
        "weapon_style_xp_skill": combat_constants.ACCURATE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE,
    },
    "hack": {
        "attack_type": "slash",
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE
    },
    # Paulus Hector Mair Poll Strike: Blunt impact using the rear poll/butt of the axe head to deliver crushing force against armor.
    "smash": {
        "attack_type": "crush",
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE
    },
    # Norse Bearded-Axe Hooking/Parry: Defensive posture using the haft and axe beard (skegg) to trap weapons and catch incoming attacks.
    "block": {
        "attack_type": "slash",
        "weapon_style": "defensive",
        "weapon_style_xp_skill": combat_constants.DEFENSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_DEFENSIVE
    }
}



# Greatsword styles
_GREATSWORD_COMBAT_STYLES = {
    "chop": {
        "attack_type": "slash",
        "weapon_style": "accurate",
        "weapon_style_xp_skill": combat_constants.ACCURATE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE,
    },
    "slash": {
        "attack_type": "slash",
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE
    },
    "smash": {
        "attack_type": "crush",
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE
    },
    "block": {
        "attack_type": "slash",
        "weapon_style": "defensive",
        "weapon_style_xp_skill": combat_constants.DEFENSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_DEFENSIVE
    }
}



# ─── Common 4-combat-style projectile map ────────────────────────────────────
# A projectile style carries three keys no melee style does:
#   combat_axes        — which skills the shot resolves against. Guns for
#                        accuracy, Ballistics for damage. Melee styles name
#                        no table and read the melee one.
#   attack_speed_delta — ticks added to the weapon's speed. Only rapid.
#   range_bonus        — tiles added to the weapon's max_range. Only snipe.
#
# The attack_type is light / standard / heavy rather than stab / slash /
# crush. It selects the equipment bonus the same way: "light_attack_bonus",
# "standard_defense_bonus", and so on.

# Shortbow styles
_SHORTBOW_COMBAT_STYLES = {
    # Drawn slowly to the anchor point, aimed down the shaft.
    "accurate": {
        "attack_type": combat_constants.PROJECTILE_ATTACK_TYPE_STANDARD,
        "weapon_style": "accurate",
        "weapon_style_xp_skill": combat_constants.PROJECTILE_ACCURATE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.PROJECTILE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE,
        "combat_axes": combat_constants.PROJECTILE_COMBAT_AXES,
    },
    # A short draw and a fast release. It buys the tick with accuracy it
    # never gets back, which is why its level boost is empty.
    "rapid": {
        "attack_type": combat_constants.PROJECTILE_ATTACK_TYPE_LIGHT,
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.PROJECTILE_AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.PROJECTILE_WEAPON_STYLE_LEVEL_BOOST_RAPID,
        "combat_axes": combat_constants.PROJECTILE_COMBAT_AXES,
        "attack_speed_delta": -1,
    },
    # A full draw held for the heavy shaft, aimed at the gaps in plate.
    "penetrate": {
        "attack_type": combat_constants.PROJECTILE_ATTACK_TYPE_HEAVY,
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.PROJECTILE_AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.PROJECTILE_WEAPON_STYLE_LEVEL_BOOST_PENETRATE,
        "combat_axes": combat_constants.PROJECTILE_COMBAT_AXES,
    },
    # Braced and patient, from as far back as the bow will carry.
    #
    # THE ONLY STYLE THAT NAMES ITS OWN XP RATE. It trains Guns AND Defense,
    # so the 4.0 budget every style pays splits between them. Without the
    # rate it would take the melee defensive rate of 4.0 each and pay half
    # again as much XP as every other style in the game.
    "snipe": {
        "attack_type": combat_constants.PROJECTILE_ATTACK_TYPE_STANDARD,
        "weapon_style": "defensive",
        "weapon_style_xp_skill": combat_constants.PROJECTILE_DEFENSIVE_XP_SKILLS,
        "weapon_style_level_boost": combat_constants.PROJECTILE_WEAPON_STYLE_LEVEL_BOOST_SNIPE,
        "weapon_style_xp_rate": combat_constants.XP_PER_DAMAGE_PROJECTILE_DEFENSIVE_EACH,
        "combat_axes": combat_constants.PROJECTILE_COMBAT_AXES,
        "range_bonus": 2,
    },
}



ITEMS = {

    # ---------------------------------
    # --- RUSTY SCRAP MELEE WEAPONS ---
    # ---------------------------------

    "rusty_scrap_dagger": ItemDef(
        key="rusty_scrap_dagger",
        name="rusty scrap dagger",
        typeclass="typeclasses.items.WeaponItem",
        desc="Rusty scrap dagger. Infection not included.",
        value=10,
        weight=0.453,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="dagger",
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_dagger", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 4,
            "slash_attack_bonus": 2,
            "crush_attack_bonus": -4,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 3,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_DAGGER_COMBAT_STYLES,
        default_combat_style="jab",
    ),

    "rusty_scrap_shortsword": ItemDef(
        key="rusty_scrap_shortsword",
        name="rusty scrap shortsword",
        typeclass="typeclasses.items.WeaponItem",
        desc="Rusty scrap shortsword. Infection not included.",
        value=25,
        weight=3.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="shortsword",
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_shortsword", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 4,
            "slash_attack_bonus": 3,
            "crush_attack_bonus": -2,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 2,
            "crush_defense_bonus": 1,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 2,
            "heavy_defense_bonus": 1,

            # Other bonuses
            "melee_strength_bonus": 5,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_SHORTSWORD_COMBAT_STYLES,
        default_combat_style="irimi",
    ),

    "rusty_scrap_scimitar": ItemDef(
        key="rusty_scrap_scimitar",
        name="rusty scrap scimitar",
        typeclass="typeclasses.items.WeaponItem",
        desc="Rusty scrap scimitar. Infection not included.",
        value=32,
        weight=1.814,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="scimitar",
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_scimitar", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 1,
            "slash_attack_bonus": 7,
            "crush_attack_bonus": -2,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 1,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 1,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 6,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_SCIMITAR_COMBAT_STYLES,
        default_combat_style="chop",
    ),

    "rusty_scrap_spear": ItemDef(
        key="rusty_scrap_spear",
        name="rusty scrap spear",
        typeclass="typeclasses.items.WeaponItem",
        desc="Rusty scrap spear. Infection not included.",
        value=26,
        weight=2.267,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.TWO_HANDS,
        tool_type="spear",
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_spear", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 5,
            "slash_attack_bonus": 5,
            "crush_attack_bonus": 5,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 1,
            "slash_defense_bonus": 1,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 1,
            "standard_defense_bonus": 1,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 6,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_SPEAR_COMBAT_STYLES,
        default_combat_style="lunge",
    ),

    "rusty_scrap_battleaxe": ItemDef(
        key="rusty_scrap_battleaxe",
        name="rusty scrap battleaxe",
        typeclass="typeclasses.items.WeaponItem",
        desc="Rusty scrap battleaxe. Infection not included.",
        value=52,
        weight=2.721,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="battleaxe",
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_battleaxe", "weapon")],
        attack_speed=6,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": -2,
            "slash_attack_bonus": 6,
            "crush_attack_bonus": 3,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 9,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_BATTLEAXE_COMBAT_STYLES,
        default_combat_style="chop",
    ),

    "rusty_scrap_greatsword": ItemDef(
        key="rusty_scrap_greatsword",
        name="rusty scrap greatsword",
        typeclass="typeclasses.items.WeaponItem",
        desc="Rusty scrap greatsword. Infection not included.",
        value=80,
        weight=3.628,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.TWO_HANDS,
        tool_type="greatsword",
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_greatsword", "weapon")],
        attack_speed=7,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": -4,
            "slash_attack_bonus": 9,
            "crush_attack_bonus": 8,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 10,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_GREATSWORD_COMBAT_STYLES,
        default_combat_style="slash",
    ),



    # ---------------------------
    # --- SCRAP MELEE WEAPONS ---
    # ---------------------------

    "scrap_dagger": ItemDef(
        key="scrap_dagger",
        name="scrap dagger",
        typeclass="typeclasses.items.WeaponItem",
        desc="Scrap dagger. Infection not included.",
        value=35,
        weight=0.453,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="dagger",
        tier=1,
        req_level=10,
        tags=[("scrap_dagger", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 5,
            "slash_attack_bonus": 3,
            "crush_attack_bonus": -4,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 4,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_DAGGER_COMBAT_STYLES,
        default_combat_style="jab",
    ),

    "scrap_shortsword": ItemDef(
        key="scrap_shortsword",
        name="scrap shortsword",
        typeclass="typeclasses.items.WeaponItem",
        desc="Scrap shortsword. Infection not included.",
        value=91,
        weight=1.814,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="shortsword",
        tier=1,
        req_level=10,
        tags=[("scrap_shortsword", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 6,
            "slash_attack_bonus": 4,
            "crush_attack_bonus": -2,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 2,
            "crush_defense_bonus": 1,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 2,
            "heavy_defense_bonus": 1,

            # Other bonuses
            "melee_strength_bonus": 7,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_SHORTSWORD_COMBAT_STYLES,
        default_combat_style="irimi",
    ),

    "scrap_scimitar": ItemDef(
        key="scrap_scimitar",
        name="scrap scimitar",
        typeclass="typeclasses.items.WeaponItem",
        desc="Scrap scimitar. Infection not included.",
        value=67,
        weight=1.814,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="scimitar",
        tier=1,
        req_level=10,
        tags=[("scrap_scimitar", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 2,
            "slash_attack_bonus": 10,
            "crush_attack_bonus": -2,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 1,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 1,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 9,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_SCIMITAR_COMBAT_STYLES,
        default_combat_style="chop",
    ),

    "scrap_spear": ItemDef(
        key="scrap_spear",
        name="scrap spear",
        typeclass="typeclasses.items.WeaponItem",
        desc="Scrap spear. Infection not included.",
        value=91,
        weight=2.267,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.TWO_HANDS,
        tool_type="spear",
        tier=1,
        req_level=10,
        tags=[("scrap_spear", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 8,
            "slash_attack_bonus": 8,
            "crush_attack_bonus": 8,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 1,
            "slash_defense_bonus": 1,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 1,
            "standard_defense_bonus": 1,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 10,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_SPEAR_COMBAT_STYLES,
        default_combat_style="lunge",
    ),

    "scrap_battleaxe": ItemDef(
        key="scrap_battleaxe",
        name="scrap battleaxe",
        typeclass="typeclasses.items.WeaponItem",
        desc="Scrap battleaxe. Infection not included.",
        value=182,
        weight=2.721,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="battleaxe",
        tier=1,
        req_level=10,
        tags=[("scrap_battleaxe", "weapon")],
        attack_speed=6,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": -2,
            "slash_attack_bonus": 8,
            "crush_attack_bonus": 5,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 13,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_BATTLEAXE_COMBAT_STYLES,
        default_combat_style="chop",
    ),

    "scrap_greatsword": ItemDef(
        key="scrap_greatsword",
        name="scrap greatsword",
        typeclass="typeclasses.items.WeaponItem",
        desc="Scrap greatsword. Infection not included.",
        value=280,
        weight=3.628,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.TWO_HANDS,
        tool_type="greatsword",
        tier=1,
        req_level=10,
        tags=[("scrap_greatsword", "weapon")],
        attack_speed=7,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": -4,
            "slash_attack_bonus": 13,
            "crush_attack_bonus": 10,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 14,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_GREATSWORD_COMBAT_STYLES,
        default_combat_style="slash",
    ),



    # ----------------------------
    # --- COPPER MELEE WEAPONS ---
    # ----------------------------

    "copper_dagger": ItemDef(
        key="copper_dagger",
        name="copper dagger",
        typeclass="typeclasses.items.WeaponItem",
        desc="Copper dagger. Bright enough to see your own mistake in.",
        value=125,
        weight=0.453,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="dagger",
        tier=2,
        req_level=20,
        tags=[("copper_dagger", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 8,
            "slash_attack_bonus": 4,
            "crush_attack_bonus": -4,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 7,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_DAGGER_COMBAT_STYLES,
        default_combat_style="jab",
    ),

    "copper_shortsword": ItemDef(
        key="copper_shortsword",
        name="copper shortsword",
        typeclass="typeclasses.items.WeaponItem",
        desc="Copper shortsword. It holds an edge and it holds a shine.",
        value=325,
        weight=1.814,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="shortsword",
        tier=2,
        req_level=20,
        tags=[("copper_shortsword", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 11,
            "slash_attack_bonus": 8,
            "crush_attack_bonus": -2,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 2,
            "crush_defense_bonus": 1,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 2,
            "heavy_defense_bonus": 1,

            # Other bonuses
            "melee_strength_bonus": 12,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_SHORTSWORD_COMBAT_STYLES,
        default_combat_style="irimi",
    ),

    "copper_scimitar": ItemDef(
        key="copper_scimitar",
        name="copper scimitar",
        typeclass="typeclasses.items.WeaponItem",
        desc="Copper scimitar. The curve does most of the work.",
        value=400,
        weight=1.814,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="scimitar",
        tier=2,
        req_level=20,
        tags=[("copper_scimitar", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 3,
            "slash_attack_bonus": 15,
            "crush_attack_bonus": -2,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 1,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 1,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 14,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_SCIMITAR_COMBAT_STYLES,
        default_combat_style="chop",
    ),

    "copper_spear": ItemDef(
        key="copper_spear",
        name="copper spear",
        typeclass="typeclasses.items.WeaponItem",
        desc="Copper spear. Reach, and a point on the end of it.",
        value=325,
        weight=2.267,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.TWO_HANDS,
        tool_type="spear",
        tier=2,
        req_level=20,
        tags=[("copper_spear", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 12,
            "slash_attack_bonus": 12,
            "crush_attack_bonus": 12,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 1,
            "slash_defense_bonus": 1,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 1,
            "standard_defense_bonus": 1,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 12,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_SPEAR_COMBAT_STYLES,
        default_combat_style="lunge",
    ),

    "copper_battleaxe": ItemDef(
        key="copper_battleaxe",
        name="copper battleaxe",
        typeclass="typeclasses.items.WeaponItem",
        desc="Copper battleaxe. Heavy at the head, which is the idea.",
        value=650,
        weight=2.721,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="battleaxe",
        tier=2,
        req_level=20,
        tags=[("copper_battleaxe", "weapon")],
        attack_speed=6,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": -2,
            "slash_attack_bonus": 16,
            "crush_attack_bonus": 11,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 20,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_BATTLEAXE_COMBAT_STYLES,
        default_combat_style="chop",
    ),

    "copper_greatsword": ItemDef(
        key="copper_greatsword",
        name="copper greatsword",
        typeclass="typeclasses.items.WeaponItem",
        desc="Copper greatsword. Two hands, and no second opinion.",
        value=1000,
        weight=3.628,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.TWO_HANDS,
        tool_type="greatsword",
        tier=2,
        req_level=20,
        tags=[("copper_greatsword", "weapon")],
        attack_speed=7,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": -4,
            "slash_attack_bonus": 21,
            "crush_attack_bonus": 16,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 22,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_GREATSWORD_COMBAT_STYLES,
        default_combat_style="slash",
    ),



    # --------------------------------------
    # --- RUSTY SCRAP PROJECTILE WEAPONS ---
    # --------------------------------------

    # A bow carries NO projectile_strength_bonus. The ammunition does.
    # It is what makes an arrow an upgrade path of its own rather than
    # a consumable with no numbers on it.

    # max_range is the tiles it covers, and the snipe style adds two more.
    # accepted_ammo names the family it fires. An arrow declares the same
    # family through a tag, so one arrow fits every bow that says so.

    "rusty_scrap_shortbow": ItemDef(
        key="rusty_scrap_shortbow",
        name="rusty scrap shortbow",
        typeclass="typeclasses.items.WeaponItem",
        desc="A rusty scrap shortbow. The first kind of gun!",
        value=150,
        weight=3.628,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.TWO_HANDS,
        tool_type="bow",
        tier=0,
        req_level=0,
        tags=[("rusty_scrap_shortbow", "weapon")],
        attack_speed=3,
        max_range=7,
        accepted_ammo=combat_constants.AMMO_FAMILY_ARROW,
        combat_stat_bonuses={
            # Melee attack bonuses.
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": -4,

            # Projectile attack bonuses.
            "light_attack_bonus": 7,
            "standard_attack_bonus": 6,
            "heavy_attack_bonus": 4,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_SHORTBOW_COMBAT_STYLES,
        default_combat_style="accurate",
    ),



    # --------------------------------
    # --- SCRAP PROJECTILE WEAPONS ---
    # --------------------------------

    "scrap_shortbow": ItemDef(
        key="scrap_shortbow",
        name="scrap shortbow",
        typeclass="typeclasses.items.WeaponItem",
        desc="A scrap shortbow, strung with prime sinew. It draws clean.",
        value=340,
        weight=3.628,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.TWO_HANDS,
        tool_type="bow",
        tier=1,
        req_level=10,
        tags=[("scrap_shortbow", "weapon")],
        attack_speed=3,
        max_range=7,
        accepted_ammo=combat_constants.AMMO_FAMILY_ARROW,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": -4,

            # Projectile attack bonuses
            "light_attack_bonus": 11,
            "standard_attack_bonus": 9,
            "heavy_attack_bonus": 6,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_SHORTBOW_COMBAT_STYLES,
        default_combat_style="accurate",
    ),



    # ---------------------------------
    # --- COPPER PROJECTILE WEAPONS ---
    # ---------------------------------

    "copper_shortbow": ItemDef(
        key="copper_shortbow",
        name="copper shortbow",
        typeclass="typeclasses.items.WeaponItem",
        desc="A copper shortbow. It draws clean.",
        value=340,
        weight=3.628,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.TWO_HANDS,
        tool_type="bow",
        tier=2,
        req_level=20,
        tags=[("copper_shortbow", "weapon")],
        attack_speed=3,
        max_range=7,
        accepted_ammo=combat_constants.AMMO_FAMILY_ARROW,
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,

            # Projectile attack bonuses
            "light_attack_bonus": 20,
            "standard_attack_bonus": 19,
            "heavy_attack_bonus": 16,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 0,
        },
        combat_styles=_SHORTBOW_COMBAT_STYLES,
        default_combat_style="accurate",
    ),
}
