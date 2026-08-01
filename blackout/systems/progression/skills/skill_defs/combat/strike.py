"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Implementation of the Melee combat skill (accuracy axis).
"""

from systems.progression.skills.skill_defs.base_skill import BaseSkill


class Strike(BaseSkill):
    """
    Purpose: Defines the Strike skill. Blackout's melee-accuracy axis —
    feeds combat_calc.effective_level on the strike skill axis.
    OSRS calls this "Attack".

    Notes/References:
        Effective Level math is wired in batch 2's BlackoutCombatHandler.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """

    key = "strike"
    name = "Strike"
    category = "Combat"
    description = "Proficiency with melee weapons. Determines attack accuracy."

    def get_unlock_requirements(self, character: object) -> bool:
        """
        Purpose: Strike is always unlocked for all characters.

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
        Purpose: Strike has no standalone `execute` action; it is a passive
        stat consumed by the combat handler's swing resolution. Satisfies
        BaseSkill's contract.

        Entry:
            character is a valid Evennia Character object
            target is unused

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            No-op. Combat handler reads character.skills.get_level('strike')
            when computing attacker_eff_atk.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        pass
