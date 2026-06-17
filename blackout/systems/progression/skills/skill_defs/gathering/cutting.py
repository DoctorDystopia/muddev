"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Implementation of the Cutting gathering skill.
"""



import time

from systems.progression.skills.skill_defs.base_skill import BaseSkill
from evennia import create_object



_MIN_HARVEST_COOLDOWN = 3.0



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


    def _get_loot_info(self, target: object) -> tuple[str | None, int]:
        """
        Purpose: Determines what loot to generate from a cutting target.
        
        Entry:
            target is a valid Evennia object with db attributes
        
        Exit/Returns:
            Tuple of (item_name, xp_reward). item_name is None if invalid.
        
        Module Globals:
            None
            
        Methodology:
            Retrieves xp_reward from the target's database. If no xp_reward 
            exists defaults to 0. Returns a hardcoded item name string and 
            the calculated xp reward as a tuple.
            
        Notes/References:
            None
            
        Author: Nick Hobar
        Creation date: 06/09/2026
        """
        xp_reward = target.db.xp_reward or 0
        
        return "Rusty Metal Chunk", xp_reward


    def _has_tool(self, character: object) -> bool:
        """
        Purpose: Checks if the character has an axe in inventory.
        
        Entry:
            character is a valid Evennia Character object
        
        Exit/Returns:
            Returns True if any inventory item's key matches 'axe' (case-insensitive).
        
        Module Globals:
            None
            
        Methodology:
            Iterates over character.contents checking if any item.key is 'axe'.
            
        Notes/References:
            None
            
        Author: Nick Hobar
        Creation date: 06/09/2026
        """
        has_axe = any(item.key.lower() == "axe" for item in character.contents)
        
        return has_axe


    def _execute_gathering(self, character: object, target: object, item_name: str, xp_reward: int, current_time: float) -> None:
        """
        Purpose: Performs the gathering action after all validations have passed.
        
        Entry:
            character is a valid Evennia Character object
            target is a valid Evennia object with a .key attribute
            item_name is a non-empty string for the created item
            xp_reward is a non-negative integer
            current_time is a float representing the current system time
        
        Exit/Returns:
            No conditions
        
        Module Globals:
            None
            
        Methodology:
            Creates the loot item using create_object. Sets the character's 
            last_harvest_time cooldown via ndb using the explicitly passed time. 
            Adds XP via the character.skills interface. Sends a success message 
            combining all results.
            
        Notes/References:
            Requires target.db.xp_reward to be populated
            
        Author: Nick Hobar
        Creation date: 06/09/2026
        """
        create_object(
            "typeclasses.objects.Object",
            key=item_name,
            location=character,
            home=character
        )
        
        character.ndb.last_harvest_time = current_time
        
        character.skills.add_xp(self.key, xp_reward)
        
        success_msg = f"You successfully cut the {target.key} and receive a {item_name} for {xp_reward} XP."
        character.msg(success_msg)


    def execute(self, character: object, target: object) -> None:
        """
        Purpose: Executes the entire cutting harvesting action, including all validations.
        
        Entry:
            character is a valid Evennia Character object
            target is a valid Evennia object
        
        Exit/Returns:
            No conditions (early returns on validation failures)
        
        Module Globals:
            _MIN_HARVEST_COOLDOWN read
            
        Methodology:
            Validates the target is a node first. Accumulates any missing tool, 
            unlock, or level requirements and returns them in a single formatted 
            message if any fail. Evaluates the harvest cooldown. On pass of all 
            checks, invokes _execute_gathering to process loot, xp, and cooldown.
            
        Notes/References:
            None
            
        Author: Nick Hobar
        Creation date: 06/09/2026
        """
        # 1. Target Type Validation (Fail fast if it's not a node)
        target_is_valid = hasattr(target, 'is_cutting_node') and target.is_cutting_node()
        
        if not target_is_valid:
            # Use Evennia's native inheritance check instead of hasattr
            if target.is_typeclass("typeclasses.characters.Character", exact=False):
                if target.key == character.key:
                    character.msg("You cannot cut yourself for materials.")
                    return
                character.msg(f"You cannot cut {target.key} for materials. They're a person! Unless..")
                return
            character.msg(f"The {target.key} is not something you can cut for materials.")
            return

        # 2. Accumulate all missing requirements
        missing_reqs = []
        
        has_axe = self._has_tool(character)
        if not has_axe:
            missing_reqs.append("any kind of axe")
            
        if not self.get_unlock_requirements(character):
            missing_reqs.append("the 'Cutting Reward' unlock")
            
        req_level = target.db.required_level or 1
        if not character.skills.meets_prerequisite(self.key, req_level):
            missing_reqs.append(f"Cutting level {req_level}")

        if missing_reqs:
            reqs_string = ", ".join(missing_reqs)
            character.msg(f"To cut the {target.key}, you require: {reqs_string}.")
            return

        # 3. Check Cooldowns
        current_time = time.time()
        last_harvest = character.ndb.last_harvest_time
        
        if last_harvest is not None:
            time_diff = current_time - last_harvest
            if time_diff < _MIN_HARVEST_COOLDOWN:
                character.msg("You are already busy gathering.")
                return
        
        # 4. Proceed with Gathering
        item_name, xp_reward = self._get_loot_info(target)
        self._execute_gathering(character, target, item_name, xp_reward, current_time)


    # def execute(self, character: object, target: object) -> None:
    #     """
    #     Purpose: Executes the entire cutting harvesting action, including all validations.
        
    #     Entry:
    #         character is a valid Evennia Character object
    #         target is a valid Evennia object
        
    #     Exit/Returns:
    #         No conditions (early returns on each validation failure)
        
    #     Module Globals:
    #         None
            
    #     Methodology:
    #         Sequentially validates the target, cooldowns, unlocks, level 
    #         prerequisite, and tool availability. On pass of all checks, 
    #         invokes _execute_gathering to process loot, xp, and cooldown.
            
    #     Notes/References:
    #         None
            
    #     Author: Nick Hobar
    #     Creation date: 06/09/2026
    #     """
    #     self._current_time = time.time()
        
    #     # target_is_valid = hasattr(target, 'is_cutting_node') and target.is_cutting_node()
    #     # if not target_is_valid:
    #     #     character.msg("You cannot cut that.")
    #     #     return
    #     target_is_valid = hasattr(target, 'is_cutting_node') and target.is_cutting_node()
        
    #     if not target_is_valid:
    #         character.msg(f"The {target.key} is not something you can cut for materials.")
    #         return

    #     last_harvest = character.ndb.last_harvest_time
    #     if last_harvest is not None:
    #         time_diff = self._current_time - last_harvest
    #         if time_diff < _MIN_HARVEST_COOLDOWN:
    #             character.msg("You are already busy gathering.")
    #             return
        
    #     if not self.get_unlock_requirements(character):
    #         character.msg("You do not know how to cut this material.")
    #         return
        
    #     req_level = target.db.required_level or 1
    #     if not character.skills.meets_prerequisite(self.key, req_level):
    #         character.msg(f"You need a Cutting level of {req_level} to cut this.")
    #         return
        
    #     has_axe = self._has_tool(character)
    #     if not has_axe:
    #         character.msg("You need an axe to cut this.")
    #         return
        
    #     item_name, xp_reward = self._get_loot_info(target)
    #     self._execute_gathering(character, target, item_name, xp_reward)


    # def execute(self, character: object, target: object) -> None:
    #     """
    #     Purpose: Executes the cutting harvesting action on a valid target.
        
    #     Entry:
    #         character is a valid Evennia Character object
    #         target is a valid Evennia object
        
    #     Exit/Returns:
    #         No conditions
        
    #     Module Globals:
    #         None
            
    #     Methodology:
    #         Checks if the target is a valid cutting node object. If valid, 
    #         sends a message to the character indicating the cutting action has begun.
            
    #     Notes/References:
    #         None
            
    #     Author: Nick Hobar
    #     Creation date: 06/05/2026
    #     """
        
    #     target_is_valid = hasattr(target, 'is_cutting_node') and target.is_cutting_node()
    #     begin_cutting_msg = "You begin cutting the {}.".format(target.key)
        
    #     if target_is_valid:
    #         print(f"\n[DEBUG]: Target {target} is a valid cutting node.")
    #         print(f"[DEBUG]: {begin_cutting_msg}")
    #         character.msg(begin_cutting_msg)