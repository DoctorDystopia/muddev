"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Dynamic handler wrapper that attaches to Character typeclasses.
"""

from . import logic

class SkillHandler:
    """
    Handles progression state management on a specific character proxy.
    Saves automatically to the character's `db.skills` attribute dictionary.
    """

    def __init__(self, obj: object) -> None:
        """
        Purpose: Initializes the handler linked to a specific Evennia Typeclass instance.
        
        Entry:
            obj is a valid Evennia object
        
        Exit/Returns:
            No conditions
        
        Module Globals:
            None
            
        Methodology:
            Sets the internal object reference. Checks if the persistent 
            skills attribute exists. If not, initializes it as an empty dictionary.
            
        Notes/References:
            None
            
        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        self.obj = obj
        
        skills_attr = self.obj.db.skills
        has_skills = bool(skills_attr)
        
        if not has_skills:
            self.obj.db.skills = {}


    def get_level(self, skill_key: str) -> int:
        """ Passes execution to logic.get_level """
        result = logic.get_level(self.obj, skill_key)
        return result


    def get_total_xp(self, skill_key: str) -> int:
        """ Passes execution to logic.get_total_xp """
        result = logic.get_total_xp(self.obj, skill_key)
        return result


    def get_xp_level(self, skill_key: str) -> tuple[int, int, int]:
        """ Passes execution to logic.get_xp_level """
        result = logic.get_xp_level(self.obj, skill_key)
        return result


    def add_xp(self, skill_key: str, amount: int) -> None:
        """ Passes execution to logic.add_xp """
        logic.add_xp(self.obj, skill_key, amount)


    def meets_prerequisite(self, skill_key: str, required_level: int) -> bool:
        """ Passes execution to logic.meets_prerequisite """
        result = logic.meets_prerequisite(self.obj, skill_key, required_level)
        return result


    def check_synergy(self, skill_a: str, level_a: int, skill_b: str, level_b: int) -> bool:
        """ Passes execution to logic.check_synergy """
        result = logic.check_synergy(self.obj, skill_a, level_a, skill_b, level_b)
        return result