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
    Purpose: Defines the Guns skill. Blackout's ranged-accuracy axis —
    feeds combat_calc.effective_level on the guns skill axis.
    OSRS calls this "Ranged".

    Passive skill: no standalone `execute` action and no unlock gate, so
    BaseSkill's defaults are inherited rather than restated. The combat
    handler reads character.skills.get_level('guns') when computing
    attacker_eff_atk.

    Author: Nick Hobar
    Creation date: 09/14/2026
    """

    key = skill_constants.SKILL_KEY_GUNS
    name = "Guns"
    category = skill_constants.SKILL_CATEGORY_COMBAT
    description = "Proficiency with guns. Determines attack accuracy with guns."
