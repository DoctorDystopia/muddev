"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Base skill class defining the standard interface for all skills.
"""



class BaseSkill:
    """
    Purpose: Defines the standard interface and default behaviors for a playable skill.
    """
    key = "base"
    name = "Base Skill"
    category = "General"
    description = "Base skill description."


    def get_unlock_requirements(self, character: object) -> bool:
        """
        Purpose: Determines if the given character meets the requirements to unlock the skill.
        
        Entry:
            character is a valid Evennia Character object
        
        Exit/Returns:
            Returns True by default, allowing all characters access.
        
        Module Globals:
            None
            
        Methodology:
            Base implementation always returns True. Overridden in child classes.
            
        Notes/References:
            None
            
        Author: Nick Hobar
        Creation date: 06/02/2026
        """

        return True


    def execute(self, character: object, target: object) -> None:
        """
        Purpose: Executes the primary mechanic or action of the skill.
        
        Entry:
            character is a valid Evennia Character object
            target is a valid Evennia object (Character, Object, or Room)
        
        Exit/Returns:
            No conditions
        
        Module Globals:
            None
            
        Methodology:
            Base implementation does nothing. Overridden in child classes.
            
        Notes/References:
            None
            
        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        
        pass