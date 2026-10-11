"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/07/2026
Description: The `milestone_growth` buff: more accuracy level and damage
             level for each pick milestone that the task passed after the
             first. The buff grows with the task. DESIGN-0012, Phase 5.
"""

from systems.gameplay.exterminator import constants as ext_const

from .base_buff import BaseExterminatorBuff



# Pick 0 comes when the player takes the task. It gives no step (Nick,
# 10/07/2026). Thus the buff gives +0 at the start, one step at 33%, and two
# steps at 66%.
_MILESTONES_WITH_NO_STEP: int = 1



class MilestoneGrowthBuff(BaseExterminatorBuff):
    """
    Purpose: Add accuracy and damage levels for each pick milestone after
             the first.

    Entry:
        No conditions. The collector adds the buff only against the task
        type.

    Exit/Returns:
        Not applicable. A rules definition.

    Module Globals:
        _MILESTONES_WITH_NO_STEP, ext_const.RARITY_* read.

    Methodology:
        1. If the holder defends, stop. Accuracy and damage belong to the
           attacker.
        2. steps = the picks earned in the task, less the first one, and
           never below 0. ExterminatorHandler.picks_earned is the reader.
        3. Add steps x the strength to flat_pre of two channels of the
           active style: accuracy and damage.

    Notes/References:
        The milestones that the task passed count, not the picks that the
        player used. A banked pick still grows the buff.
        The numbers are the vault example (+1) at 1x, 1.5x, 2x, and 3x
        (Nick, 10/07/2026). TBD.

    Author: Nick Hobar
    Creation date: 10/07/2026
    """

    key = ext_const.BUFF_MILESTONE_GROWTH
    archetype = ext_const.BUFF_MILESTONE_GROWTH
    name = "Growth"  # TBD name
    description = (
        "+{value} accuracy level and damage level against your task type for "
        "each pick milestone after the first."
    )

    strengths = {
        ext_const.RARITY_COMMON: 1,
        ext_const.RARITY_RARE: 2,
        ext_const.RARITY_EPIC: 2,
        ext_const.RARITY_LEGENDARY: 3,
    }

    def steps(self, holder) -> int:
        """The pick milestones after the first that the task of the holder passed."""
        handler = getattr(holder, "exterminator", None)

        if handler is None:
            return 0

        earned = handler.picks_earned()

        return max(earned - _MILESTONES_WITH_NO_STEP, 0)

    def contribute_modifiers(self, context, bag) -> None:
        """Add the levels for each step when the holder attacks."""
        if not self.holder_attacks(context, bag):
            return

        holder = self.holder_of(context, bag)
        bonus = self.steps(holder) * self.strength(holder)

        if bonus <= 0:
            return

        bag.add_flat_pre(context.accuracy_channel(), bonus)
        bag.add_flat_pre(context.damage_channel(), bonus)
