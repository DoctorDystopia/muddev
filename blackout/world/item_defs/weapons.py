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

import systems.combat.constants as combat_constants
from items.equipment.constants import WieldLocation
from world.item_database import ItemDef


# ─── Common 4-combat-style melee map ──────────────────────────────────────────────
# Each weapon category defines four combat styles. Every style has:
#   attack_type               — damage type used for accuracy (stab / slash / crush)
#   weapon_style              — the manner of which a weapon is used in combat (accurate, aggressive, defensive, controlled)
#   weapon_style_xp_skill     — which skill(s) receives XP (fortitude / strike / brawn / defense) based on weapon style
#   weapon_style_level_boost  — ref to the invisible-level-boost dict from constants based on weapon style

# Stab sword styles
_SHORTSWORD_COMBAT_STYLES = {
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



ITEMS = {
    "rusty_scrap_shortsword": ItemDef(
        key="rusty_scrap_shortsword",
        name="Rusty Scrap Shortsword",
        typeclass="typeclasses.items.WeaponItem",
        desc="Rusty scrap shortsword. Infection not included.",
        value=25,
        weight=3.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="shortsword",
        tier=1,
        req_level=0,
        tags=[("rusty_scrap_shortsword", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Attack bonuses
            "stab_attack_bonus": 4,
            "slash_attack_bonus": 3,
            "crush_attack_bonus": -2,
            # Defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 2,
            "crush_defense_bonus": 1,
            # Other bonuses
            "melee_strength_bonus": 5,
        },
        combat_styles=_SHORTSWORD_COMBAT_STYLES,
        default_combat_style="irimi",
    ),
    "rusty_scrap_spear": ItemDef(
        key="rusty_scrap_spear",
        name="Rusty Scrap Spear",
        typeclass="typeclasses.items.WeaponItem",
        desc="Rusty scrap spear. Infection not included.",
        value=25,
        weight=3.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="spear",
        tier=1,
        req_level=0,
        tags=[("rusty_scrap_spear", "weapon")],
        attack_speed=4,
        combat_stat_bonuses={
            # Attack bonuses
            "stab_attack_bonus": 5,
            "slash_attack_bonus": 5,
            "crush_attack_bonus": 5,
            # Defense bonuses
            "stab_defense_bonus": 1,
            "slash_defense_bonus": 1,
            "crush_defense_bonus": 0,
            # Other bonuses
            "melee_strength_bonus": 6,
        },
        combat_styles=_SPEAR_COMBAT_STYLES,
        default_combat_style="lunge",
    ),
}
