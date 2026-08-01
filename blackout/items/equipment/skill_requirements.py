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
#
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
    # Legacy alias: weapons.py renamed tool_type "sword" -> "shortsword", but
    # objects spawned before that rename still carry the old value. Kept so
    # those rows stay gated instead of failing closed and becoming unequippable.
    "sword":      "strike",
    # Crafting tools carry no wield requirement. Declared explicitly so they
    # read as an intentional exemption rather than an oversight.
    "hammer":     None,
    "generic":    None,
    # Future categories land here — pickaxes map to "mining", etc.
}
