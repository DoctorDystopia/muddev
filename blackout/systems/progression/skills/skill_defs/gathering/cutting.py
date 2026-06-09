"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Implementation of the Cutting gathering skill.
"""



from systems.progression.skills.skill_defs.base_skill import BaseSkill



class Cutting(BaseSkill):
    """
    Purpose: Manages the mechanics and unlock requirements for Cutting.
    """
    key = "cutting"
    name = "Cutting"
    category = "Gathering"
    description = "Proficiency with harvesting materials from trees and plants."


    def get_unlock_requirements(self, character: object) -> bool:
        """
        Purpose: Checks if the character has the necessary reward to unlock Cutting.
        
        Entry:
            character is a valid Evennia Character object
        
        Exit/Returns:
            Returns True if the character possesses the unlock reward, False otherwise.
        
        Module Globals:
            None
            
        Methodology:
            Retrieves the 'has_cutting_reward' attribute from the character's 
            database. Evaluates the boolean state of the retrieved value.
            
        Notes/References:
            None
            
        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        has_reward_attr = character.db.has_cutting_reward
        has_unlocked = bool(has_reward_attr)
        
        return has_unlocked


    def execute(self, character: object, target: object) -> None:
        """
        Purpose: Executes the cutting harvesting action on a valid target.
        
        Entry:
            character is a valid Evennia Character object
            target is a valid Evennia object
        
        Exit/Returns:
            No conditions
        
        Module Globals:
            None
            
        Methodology:
            Checks if the target is a valid cutting node object. If valid, 
            sends a message to the character indicating the cutting action has begun.
            
        Notes/References:
            None
            
        Author: Nick Hobar
        Creation date: 06/05/2026
        """
        
        target_is_valid = hasattr(target, 'is_cutting_node') and target.is_cutting_node()
        begin_cutting_msg = "You begin cutting the {}.".format(target.key)
        
        if target_is_valid:
            print(f"\n[DEBUG]: Target {target} is a valid cutting node.")
            print(f"[DEBUG]: {begin_cutting_msg}")
            character.msg(begin_cutting_msg)