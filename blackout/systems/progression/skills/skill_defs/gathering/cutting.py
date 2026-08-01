"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Implementation of the Cutting gathering skill.
"""



from systems.progression.skills.skill_defs.base_skill import BaseSkill
from world.item_database import ITEM_DB



_MIN_HARVEST_COOLDOWN = 3.0



class Cutting(BaseSkill):
    """
    Purpose: Manages the mechanics and unlock requirements for Cutting.
    """
    key = "cutting"
    name = "Cutting"
    category = "Gathering"
    description = "Proficiency with harvesting materials from trees and plants."
    cooldown_seconds = _MIN_HARVEST_COOLDOWN


    def get_unlock_requirements(self, character: object) -> bool:
        """
        Purpose: Cutting is always unlocked for all players.
        """
        return True


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
        Purpose: Checks if the character has an axe in inventory or equipped.
        """
        def _is_axe(item):
            return getattr(item.db, "tool_type", None) == "axe"

        has_axe = any(_is_axe(item) for item in character.contents)
        if not has_axe:
            has_axe = any(_is_axe(item) for item in character.equipment.all())

        return has_axe


    def _execute_gathering(self, character: object, target: object, item_name: str, xp_reward: int) -> None:
        """
        Purpose: Performs the gathering action after all validations have passed.

        Entry:
            character is a valid Evennia Character object
            target is a valid Evennia object with a .key attribute
            item_name is a non-empty string for the created item
            xp_reward is a non-negative integer

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Creates the loot item from the ITEM_DB. Arms this skill's
            cooldown through the shared BaseSkill helper. Adds XP via the
            character.skills interface. Sends a success message combining all
            results.

        Notes/References:
            Requires target.db.xp_reward to be populated

        Author: Nick Hobar
        Creation date: 06/09/2026
        """
        ITEM_DB["rusty_metal_chunk"].create(
            location=character,
            home=character,
        )

        self.arm_cooldown(character)

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
            None

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
            
        req_level = target.db.required_level if target.db.required_level is not None else 1
        if not character.skills.meets_prerequisite(self.key, req_level):
            missing_reqs.append(f"Cutting level {req_level}")

        if missing_reqs:
            reqs_string = ", ".join(missing_reqs)
            character.msg(f"To cut the {target.key}, you require: {reqs_string}.")
            return

        # 3. Check Cooldowns
        if not self.is_off_cooldown(character):
            character.msg("You are already busy gathering.")
            return

        # 4. Proceed with Gathering
        item_name, xp_reward = self._get_loot_info(target)
        self._execute_gathering(character, target, item_name, xp_reward)

