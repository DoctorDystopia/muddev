"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Implementation of the Defense combat skill (defensive axis).
"""

from systems.progression.skills.skill_defs.base_skill import BaseSkill


class Defense(BaseSkill):
    """
    Purpose: Defines the Defense skill. Feeds combat_calc.effective_level
    on the defense axis.

    Passive skill: no standalone `execute` action and no unlock gate, so
    BaseSkill's defaults are inherited rather than restated. The combat
    handler reads the DEFENDER's defense level when computing
    defender_eff_def.

    Notes/References:
        The OSRS convention is that Defense XP is granted when a character
        TAKES damage rather than deals it. Blackout does not implement that
        yet: XP_PER_DAMAGE_TAKEN_DEFENSE is commented out in
        systems/combat/constants.py and CombatEntity.at_damage awards
        nothing, so today defense XP arrives only via the defensive stance's
        weapon_style_xp_skill on the attacker's own swing.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """

    key = "defense"
    name = "Defense"
    category = "Combat"
    description = "Proficiency at avoiding and absorbing melee hits."
