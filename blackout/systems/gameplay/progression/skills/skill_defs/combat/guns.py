"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/14/2026
Description: Implementation of the guns combat skill (accuracy axis).
"""



from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill



class Guns(BaseSkill):
    """
    Purpose: Defines the Guns skill. Blackout's projectile-ACCURACY axis —
    feeds combat_calc.effective_level on the guns skill axis.

    ACCURACY ONLY. OSRS puts projectile accuracy and projectile damage on one
    "Projectile" skill. Blackout splits them, the same way it splits melee into
    Strike and Brawn: Guns decides whether a shot lands, and Ballistics
    decides how hard it lands. A shot that reads this skill for damage is a
    bug.

    Guns also gates which projectile weapon a character may wield, through
    WEAPON_SKILL_MAP in items/equipment/skill_requirements.py.

    Passive skill: no standalone `execute` action and no unlock gate, so
    BaseSkill's defaults are inherited rather than restated. The projectile
    action rules read character.skills.get_level('guns') when they compute
    the effective attack level.

    Author: Nick Hobar
    Creation date: 09/14/2026
    """

    key = skill_constants.SKILL_KEY_GUNS
    name = "Guns"
    category = skill_constants.SKILL_CATEGORY_COMBAT
    description = "Proficiency with guns. Determines how often a shot lands."
