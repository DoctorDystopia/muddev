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
    """
    key = "foundry"
    name = "Foundry"
    category = "Processing"
    description = "Skill in smelting and processing raw gathered materials into usable crafting components."


    def get_unlock_requirements(self, character: object) -> bool:
        """
        Purpose: Foundry is always unlocked for all players.
        """
        return True


    def execute(self, character: object, target: object) -> None:
        """
        Purpose: Stub — processing is handled through the crafting recipe system.
        """
        pass
