"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Weapon-type → skill-key map. Lets the EquipmentHandler dispatch
             tier-requirement checks by data lookup instead of hardcoded
             "if tool_type == 'axe'" branches. New weapon categories register
             here; non-weapon tool categories (gathering axes, mining picks)
             also live here because they share the same mechanic shape.
"""



# Maps the value of obj.db.tool_type to the skill key whose req_level is
# checked at wield time. Flat dict: O(1) lookup, no per-category branch
# block. Uses skills.meets_prerequisite (skill_key, req_level) per the
# existing handler.py pattern.

# EVERY tool_type the game emits must appear here. A value of None means
# "deliberately ungated" -- distinct from an absent key, which means "nobody
# registered this" and is treated as a misconfiguration. Making that
# distinction explicit is what stops a renamed category (the sword ->
# shortsword rename) from silently losing its level check: the renamed value
# is simply not in the map, so it fails closed and gets logged rather than
# being waved through as unrestricted.

WEAPON_SKILL_MAP: dict[str, str | None] = {
    # Gathering categories
    "axe":        "cutting",   # axes remain a Gathering tool (cuts trees)

    # Combat categories — gated via the Strike skill (melee accuracy).
    "shortsword": "strike",
    "spear":      "strike",
    "dagger":     "strike",
    "battleaxe":  "strike",

    # Gadgets are salvage anyone can point at anything. Their behaviour comes
    # from an action rules definition rather than from the wielder's accuracy,
    # so gating them on Strike would be gating the wrong skill.
    "gadget":     None,

    # Crafting tools carry no wield requirement. Declared explicitly so they
    # read as an intentional exemption rather than an oversight.
    "hammer":     None,

    "generic":    None,
    
    # Future categories land here — pickaxes map to "mining", etc.
}



ARMOR_SKILL_MAP: dict[str, str | None] = {
    # Armor categories, gated via the Defense skill. Every armor category the game emits must appear here. A value of None means "deliberately ungated"
    "chainbody": "defense",
    "boots": "defense",
    "square_shield": "defense",
}



def get_equippables_for_skill(skill_key: str) -> list:
    """
    Purpose: Get every equippable item that unlocks under a given skill.

    Entry:
        skill_key is a skill key string to match against the skill a
        registered tool_type resolves to.

    Exit/Returns:
        Returns a list of ItemDef, sorted by (req_level, name). An item
        whose tool_type is unregistered or explicitly ungated (mapped to
        None) is excluded.

    Module Globals:
        WEAPON_SKILL_MAP read.
        ARMOR_SKILL_MAP read.

    Methodology:
        Scans ITEM_DB for items carrying a tool_type, resolves each through
        WEAPON_SKILL_MAP then ARMOR_SKILL_MAP -- the same two maps
        EquipmentHandler.equip() checks at wield time -- and keeps the ones
        that resolve to skill_key. Deriving this from ITEM_DB and the
        existing maps keeps req_level and tool_type single-owned on ItemDef
        rather than duplicated into a third table.

    Notes/References:
        Mirrors systems.crafting.crafting_service.get_recipes_for_skill and
        systems.progression.skills.gatherables.get_gatherables_for_skill --
        the three functions together are what feed the skills menu's
        "Unlocks" listing.

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    from world.item_database import ITEM_DB

    matches = []
    for item_def in ITEM_DB.values():
        tool_type = item_def.tool_type
        if tool_type is None:
            continue

        required_skill = WEAPON_SKILL_MAP.get(tool_type)

        if required_skill is None:
            required_skill = ARMOR_SKILL_MAP.get(tool_type)

        if required_skill != skill_key:
            continue

        matches.append(item_def)

    matches.sort(key=lambda entry: (entry.req_level, entry.name))

    return matches