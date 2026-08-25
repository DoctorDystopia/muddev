"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: ItemDef entries for gathering and crafting tools.
"""

import systems.combat.constants as combat_constants
from systems.crafting.constants import TOOL_TAG_CATEGORY
from systems.statefeed.constants import ITEM_FAMILY_WEAPON
from world.item_database import ItemDef
from items.equipment.constants import WieldLocation



# ─── Private constant definitions ────────────────────────────────────────────

# A felling axe swung at something that swings back. Three motions, not the
# battleaxe's four: a wood axe has no poll heavy enough for the battleaxe's
# "smash", so the crush style it would carry is left off rather than given a
# number. Declared here rather than imported from item_defs/weapons.py
# because every item_defs module owns its own style tables -- gadgets.py does
# the same -- and an axe is a weaker weapon than a battleaxe in stats, not a
# copy of one.
_AXE_COMBAT_STYLES = {
    # Chop: the woodcutting stroke, aimed rather than thrown.
    "chop": {
        "attack_type": combat_constants.ATTACK_TYPE_SLASH,
        "weapon_style": "accurate",
        "weapon_style_xp_skill": combat_constants.ACCURATE_XP_SKILLS,
        "weapon_style_level_boost": (
            combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE
        ),
    },
    # Hack: the same stroke with the shoulders behind it and nothing held back.
    "hack": {
        "attack_type": combat_constants.ATTACK_TYPE_SLASH,
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": (
            combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE
        ),
    },
    # Smash: the same stroke with the shoulders behind it and nothing held back.
    "smash": {
        "attack_type": combat_constants.ATTACK_TYPE_CRUSH,
        "weapon_style": "aggressive",
        "weapon_style_xp_skill": combat_constants.AGGRESSIVE_XP_SKILLS,
        "weapon_style_level_boost": (
            combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE
        ),
    },
    # Block: the haft held crosswise to catch what is coming in.
    "block": {
        "attack_type": combat_constants.ATTACK_TYPE_SLASH,
        "weapon_style": "defensive",
        "weapon_style_xp_skill": combat_constants.DEFENSIVE_XP_SKILLS,
        "weapon_style_level_boost": (
            combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_DEFENSIVE
        ),
    },
}



ITEMS = {
    # An item may declare AS MANY families as it belongs to; the tag list is a
    # list, and Evennia files each (key, category) pair independently. The axe
    # is a crafting_tool because a recipe looks for one under that category,
    # and a weapon because the 3D client picks a mesh by family. Neither reader
    # cares that the other tag is there.
    #
    # What makes it swing is NOT the weapon tag -- nothing in combat reads a
    # tag. `combat_styles` plus `attack_speed` on the equipped object are the
    # whole of it (systems/combat/combat.py: _combat_style_source reads the
    # wielded object's db fields and never asks what typeclass or tag it
    # carries). An axe with the tag and no styles would render as a weapon and
    # still hit for unarmed damage.
    #
    # Stats are a weaker, faster rusty_scrap_battleaxe: same slash-first
    # profile, less strength behind it, one tick quicker. It stays gated on
    # `cutting` rather than `strike`, because WEAPON_SKILL_MAP keys on
    # tool_type and the tool_type of an axe is what a tree checks too.
    "rusty_scrap_axe": ItemDef(
        key="rusty_scrap_axe",
        name="rusty scrap axe",
        typeclass="typeclasses.items.ToolItem",
        desc="A crude axe hammered together from scrap metal.",
        value=10,
        weight=3.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="axe",
        tier=1,
        req_level=0,
        tags=[
            ("rusty_scrap_axe", TOOL_TAG_CATEGORY),
            ("rusty_scrap_axe", ITEM_FAMILY_WEAPON),
        ],
        attack_speed=5,
        combat_stat_bonuses={
            # Attack bonuses
            "stab_attack_bonus": -2,
            "slash_attack_bonus": 4,
            "crush_attack_bonus": 2,
            # Defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 1,
            "crush_defense_bonus": 0,
            # Other bonuses
            "melee_strength_bonus": 5,
        },
        combat_styles=_AXE_COMBAT_STYLES,
        default_combat_style="chop",
    ),
    "hammer": ItemDef(
        key="hammer",
        name="hammer",
        typeclass="typeclasses.crafting_tools.Hammer",
        desc="A heavy hammer used for hitting things.",
        value=15,
        weight=4.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="hammer",
        tier=1,
        req_level=0,
        tags=[("hammer", TOOL_TAG_CATEGORY)],
    ),
}
