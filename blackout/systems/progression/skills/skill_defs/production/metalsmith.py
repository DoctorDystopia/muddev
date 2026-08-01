"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Implementation of the Metalsmith production skill.
"""



from systems.progression.skills.skill_defs.base_skill import BaseSkill



class Metalsmith(BaseSkill):
    """
    Purpose: Manages the mechanics and unlock requirements for Metalsmith.

    Always unlocked, and production is driven through the crafting recipe
    system rather than a skill `execute`, so BaseSkill's defaults are
    inherited rather than restated.
    """
    key = "metalsmith"
    name = "Metalsmith"
    category = "Production"
    description = "Skill in forging and shaping metal into finished tools and equipment."
