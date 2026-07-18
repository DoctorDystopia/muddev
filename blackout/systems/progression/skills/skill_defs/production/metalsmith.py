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
    """
    key = "metalsmith"
    name = "Metalsmith"
    category = "Production"
    description = "Skill in forging and shaping metal into finished tools and equipment."


    def get_unlock_requirements(self, character: object) -> bool:
        """
        Purpose: Metalsmith is always unlocked for all players.
        """
        return True


    def execute(self, character: object, target: object) -> None:
        """
        Purpose: Stub — production is handled through the crafting recipe system.
        """
        pass
