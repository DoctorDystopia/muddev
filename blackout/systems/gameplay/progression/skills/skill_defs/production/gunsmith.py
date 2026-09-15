"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/14/2026
Description: Implementation of the Gunsmith production skill.
"""



from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill



class Gunsmith(BaseSkill):
    """
    Purpose: Manages the mechanics and unlock requirements for Gunsmith.

    Always unlocked, and production is driven through the crafting recipe
    system rather than a skill `execute`, so BaseSkill's defaults are
    inherited rather than restated.
    """
    
    key = skill_constants.SKILL_KEY_GUNSMITH
    name = "Gunsmith"
    category = skill_constants.SKILL_CATEGORY_PRODUCTION
    description = "Skill in using crafting components to produce finished guns."
