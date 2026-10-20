"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Implementation of the Metalsmith production skill.
"""



from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill
from systems.interface.statefeed import constants as feed_const



class Metalsmith(BaseSkill):
    """
    Purpose: Manages the mechanics and unlock requirements for Metalsmith.

    Always unlocked, and production is driven through the crafting recipe
    system rather than a skill `execute`, so BaseSkill's defaults are
    inherited rather than restated.
    """
    key = skill_constants.SKILL_KEY_METALSMITH
    name = "Metalsmith"
    category = skill_constants.SKILL_CATEGORY_PRODUCTION
    description = "Skill in forging and shaping metal into finished tools and equipment."
    craft_moment = feed_const.MOMENT_METALSMITH_CRAFT
