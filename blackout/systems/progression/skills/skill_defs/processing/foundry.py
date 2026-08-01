"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Implementation of the Foundry processing skill.
"""



from systems.progression.skills.skill_defs.base_skill import BaseSkill



class Foundry(BaseSkill):
    """
    Purpose: Manages the mechanics and unlock requirements for Foundry.

    Always unlocked, and processing is driven through the crafting recipe
    system rather than a skill `execute`, so BaseSkill's defaults are
    inherited rather than restated.
    """
    key = "foundry"
    name = "Foundry"
    category = "Processing"
    description = "Skill in smelting and processing raw gathered materials into usable crafting components."
