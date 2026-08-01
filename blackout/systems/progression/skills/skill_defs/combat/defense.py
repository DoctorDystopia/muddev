"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Implementation of the Defense combat skill (defensive axis).
"""

from systems.progression.skills.skill_defs.base_skill import BaseSkill


class Defense(BaseSkill):
    """
    Purpose: Defines the Defense skill. Feeds combat_calc.effective_level
    on the defense axis. Defense XP is granted when the character takes
    damage, NOT when they deal it (the OSRS convention).

    Notes/References:
        Effective Level math wired in batch 2's BlackoutCombatHandler.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """

    key = "defense"
    name = "Defense"
    category = "Combat"
    description = "Proficiency at avoiding and absorbing melee hits."

    def get_unlock_requirements(self, character: object) -> bool:
        """
        Purpose: Defense is always unlocked for all characters.

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
        Purpose: Defense has no standalone `execute` action; it is a
        passive stat consumed when an attacker's swing resolves against
        this character. Satisfies BaseSkill's contract.

        Entry:
            character is a valid Evennia Character object
            target is unused

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            No-op. Combat handler reads character.skills.get_level
            ('defense') when computing defender_eff_def. XP gains flow
            from the handler's per-hit XP award, not from this method.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        pass
