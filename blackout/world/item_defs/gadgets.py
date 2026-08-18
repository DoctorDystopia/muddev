"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Blackout gadget ItemDef entries — wieldable items whose combat
             behaviour comes from a rules definition rather than from stats.

A gadget's `combat_rules` list names entries in
systems/combat/rules/RULES_REGISTRY. Those definitions own the action; the
combat_stat_bonuses here exist only so the item resolves through the same
profile path as a sword, not because the numbers do much.
"""

import systems.combat.constants as combat_constants
from items.equipment.constants import WieldLocation
from world.item_database import ItemDef


# ─── Private constant definitions ────────────────────────────────────────────

# Gadgets have no meaningful stance choice: the rules definition replaces or
# rewrites the damage roll, so the four-style table a sword carries would be
# four names for the same outcome. One style keeps the profile path happy.
_GADGET_COMBAT_STYLES = {
    "discharge": {
        "attack_type": combat_constants.ATTACK_TYPE_CRUSH,
        "weapon_style": "accurate",
        "weapon_style_xp_skill": combat_constants.ACCURATE_XP_SKILLS,
        "weapon_style_level_boost": (
            combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE
        ),
    },
}

_TOY_SWORD_COMBAT_STYLES = {
    "bonk": {
        "attack_type": combat_constants.ATTACK_TYPE_CRUSH,
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": (
            combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE
        ),
    },
}

_BIT_BLADE_COMBAT_STYLES = {
    "rend": {
        "attack_type": combat_constants.ATTACK_TYPE_SLASH,
        "weapon_style": "accurate",
        "weapon_style_xp_skill": combat_constants.ACCURATE_XP_SKILLS,
        "weapon_style_level_boost": (
            combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE
        ),
    },
}

# A gadget carries no stat bonuses of its own.
_NO_COMBAT_BONUSES = {
    "stab_attack_bonus": 0,
    "slash_attack_bonus": 0,
    "crush_attack_bonus": 0,
    "stab_defense_bonus": 0,
    "slash_defense_bonus": 0,
    "crush_defense_bonus": 0,
    "melee_strength_bonus": 0,
}


ITEMS = {
    "malfunctioning_gizmo": ItemDef(
        key="malfunctioning_gizmo",
        name="malfunctioning gizmo",
        typeclass="typeclasses.items.WeaponItem",
        desc=("A club-sized tangle of salvage that hums when held. Four times in five it discharges at whatever you happen to be hitting at the time."),
        value=40,
        weight=1.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="gadget",
        tier=1,
        req_level=0,
        tags=[("malfunctioning_gizmo", "weapon")],
        attack_speed=4,
        combat_stat_bonuses=dict(_NO_COMBAT_BONUSES),
        combat_styles=_GADGET_COMBAT_STYLES,
        default_combat_style="discharge",
        combat_rules=["malfunctioning_gizmo"],
    ),
    "toy_sword": ItemDef(
        key="toy_sword",
        name="Toy Sword",
        typeclass="typeclasses.items.WeaponItem",
        desc=("Moulded plastic, scuffed at the tip. A replica of Aerang’s legendary sword, beloved by D&D&D fans."),
        value=5,
        weight=0.5,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="gadget",
        tier=1,
        req_level=0,
        tags=[("toy_sword", "weapon")],
        attack_speed=4,
        combat_stat_bonuses=dict(_NO_COMBAT_BONUSES),
        combat_styles=_TOY_SWORD_COMBAT_STYLES,
        default_combat_style="bonk",
        combat_rules=["toy_sword"],
    ),
    "bit_blade": ItemDef(
        key="bit_blade",
        name="bit-blade",
        typeclass="typeclasses.items.WeaponItem",
        desc=("The edge hums and flickers"),
        value=512,
        weight=0.5,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="gadget",
        tier=1,
        req_level=31,
        tags=[("bit_blade", "weapon")],
        attack_speed=4,
        combat_stat_bonuses=dict(_NO_COMBAT_BONUSES),
        combat_styles=_BIT_BLADE_COMBAT_STYLES,
        default_combat_style="rend",
        combat_rules=["bit_blade"],
    ),
    "broken_bit_blade": ItemDef(
        key="broken_bit_blade",
        name="broken bit-blade",
        typeclass="typeclasses.items.WeaponItem",
        desc=("The edge is dim"),
        value=1,
        weight=0.5,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="gadget",
        tier=1,
        req_level=0,
        tags=[("broken_bit_blade", "bit_blade", "weapon")],
        attack_speed=4,
        combat_stat_bonuses=dict(_NO_COMBAT_BONUSES),
        combat_styles=_BIT_BLADE_COMBAT_STYLES,
        default_combat_style="rend",
        combat_rules=["broken_bit_blade"],
    ),
    "mk2_bit_blade": ItemDef(
        key="mk2_bit_blade",
        name="MK.II bit-blade",
        typeclass="typeclasses.items.WeaponItem",
        desc=("The edge burns into your retinas, you look away"),
        value=524_288,
        weight=0.5,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="gadget",
        tier=1,
        req_level=63,
        tags=[("mk2_bit_blade", "bit_blade", "weapon")],
        attack_speed=4,
        combat_stat_bonuses=dict(_NO_COMBAT_BONUSES),
        combat_styles=_BIT_BLADE_COMBAT_STYLES,
        default_combat_style="rend",
        combat_rules=["mk2_bit_blade"],
    ),
    "legendary_bit_blade": ItemDef(
        key="legendary_bit_blade",
        name="0x7F",
        typeclass="typeclasses.items.WeaponItem",
        desc=("The edge warps the space around it"),
        value=1_073_741_824,
        weight=0.5,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="gadget",
        tier=1,
        req_level=127,
        tags=[("legendary_bit_blade", "bit_blade", "weapon")],
        attack_speed=4,
        combat_stat_bonuses=dict(_NO_COMBAT_BONUSES),
        combat_styles=_BIT_BLADE_COMBAT_STYLES,
        default_combat_style="rend",
        combat_rules=["legendary_bit_blade"],
    ),
}
