"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Base skill class defining the standard interface for all skills.
"""



# Public constant definitions

# Prefix for the per-skill cooldown names stored on character.cooldowns.
# Namespaced so a skill cooldown can never collide with a cooldown some other
# system (combat, consumables) registers on the same handler.
COOLDOWN_KEY_PREFIX = "skill_"

# A skill with this cooldown imposes none.
NO_COOLDOWN = 0.0



class BaseSkill:
    """
    Purpose: Defines the standard interface and default behaviors for a playable skill.
    """
    key = "base"
    name = "Base Skill"
    category = "General"
    description = "Base skill description."

    # Seconds a character must wait between uses of this skill. Subclasses
    # override; NO_COOLDOWN means the skill is unrestricted.
    cooldown_seconds = NO_COOLDOWN


    def cooldown_key(self) -> str:
        """
        Purpose: Build the cooldown name this skill stores its timer under.

        Entry:
            No conditions.

        Exit/Returns:
            Returns a namespaced cooldown name string.

        Module Globals:
            COOLDOWN_KEY_PREFIX read.

        Methodology:
            Keying on self.key gives every skill its own timer. The value this
            replaces was a single character.ndb.last_harvest_time shared by
            every gathering skill, so cutting a pole would have blocked mining
            a rock once a second gathering skill existed.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/01/2026
        """
        cooldown_name = f"{COOLDOWN_KEY_PREFIX}{self.key}"

        return cooldown_name


    def is_off_cooldown(self, character: object) -> bool:
        """
        Purpose: Report whether this skill is ready to be used again.

        Entry:
            character is a valid Evennia Character with a cooldowns handler.

        Exit/Returns:
            Returns True if the skill may be used now.

        Module Globals:
            NO_COOLDOWN read.

        Methodology:
            A skill declaring NO_COOLDOWN is always ready. Otherwise defer to
            the contrib handler, whose ready() treats an unknown cooldown name
            as ready -- so a character's first use needs no special case.

        Notes/References:
            evennia.contrib.game_systems.cooldowns.CooldownHandler.

        Author: Nick Hobar
        Creation date: 08/01/2026
        """
        if self.cooldown_seconds <= NO_COOLDOWN:
            return True

        cooldown_name = self.cooldown_key()
        is_ready = character.cooldowns.ready(cooldown_name)

        return is_ready


    def arm_cooldown(self, character: object) -> None:
        """
        Purpose: Start this skill's cooldown on the given character.

        Entry:
            character is a valid Evennia Character with a cooldowns handler.

        Exit/Returns:
            No conditions.

        Module Globals:
            NO_COOLDOWN read.

        Methodology:
            Called only after a use succeeds, so a failed attempt does not
            cost the player their next action. The handler stores an absolute
            expiry timestamp in a persistent Attribute.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/01/2026
        """
        if self.cooldown_seconds <= NO_COOLDOWN:
            return

        cooldown_name = self.cooldown_key()
        character.cooldowns.add(cooldown_name, self.cooldown_seconds)


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