"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Implementation of the Fortitude combat skill (max HP scaling).
"""

from systems.progression.skills.skill_defs.base_skill import BaseSkill


class Fortitude(BaseSkill):
    """
    Purpose: Defines the Fortitude skill. Blackout's hitpoint stat. A
    character's max_hp equals their Fortitude level (OSRS Hitpoints
    analog — call it Hitpoints-equivalent in the math, but the in-world
    stat name is Fortitude, a post-apocalyptic resilience concept).

    Notes/References:
        Seed level 10 at character creation (per constants). Like OSRS,
        Fortitude is the one skill that does NOT start at the global
        DEFAULT_START_LEVEL (which is 0 here).

    Author: Nick Hobar
    Creation date: 07/26/2026
    """

    key = "fortitude"
    name = "Fortitude"
    category = "Combat"
    description = "Constitution and resilience. Determines maximum hitpoints."

    def get_unlock_requirements(self, character: object) -> bool:
        """
        Purpose: Fortitude is always unlocked for all characters.

        Entry:
            character is a valid Evennia Character object

        Exit/Returns:
            Returns True unconditionally.

        Module Globals:
            None

        Methodology:
            Pure-True base implementation.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        return True

    def execute(self, character: object, target: object) -> None:
        """
        Purpose: Fortitude has no active execution pathway. It is a passive
        stat used as the upper bound on HP. This method exists only to
        satisfy the BaseSkill interface contract.

        Entry:
            character is a valid Evennia Character object
            target is unused (pass None)

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            No-op. Sub-classes / combat handler reads character.skills.get_level
            ('fortitude') directly when computing max_hp.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        pass
