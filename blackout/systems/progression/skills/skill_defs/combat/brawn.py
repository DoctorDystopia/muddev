"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Implementation of the Brawn combat skill (damage axis).
"""

from systems.progression.skills.skill_defs.base_skill import BaseSkill


class Brawn(BaseSkill):
    """
    Purpose: Defines the Brawn skill. Blackout's melee-damage axis — feeds
    combat_calc.effective_level on the brawn skill axis. OSRS
    calls this "Strength"; we name it Brawn because Blackout already has
    a "Strength" Augmentation concept pending.

    Notes/References:
        Effective Level math is wired in batch 2's BlackoutCombatHandler.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """

    key = "brawn"
    name = "Brawn"
    category = "Combat"
    description = "Raw melee power. Determines how hard you hit."

    def get_unlock_requirements(self, character: object) -> bool:
        """
        Purpose: Brawn is always unlocked for all characters.

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
        Purpose: Brawn has no standalone `execute` action; it is a passive
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
            No-op. Combat handler reads character.skills.get_level('brawn')
            when computing attacker_eff_str.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        pass
