"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/07/2026
Description: The `accuracy_vs_type` buff: more accuracy level against the
             task type. One buff serves a sword and a bow, because it writes
             to the accuracy channel of the active style. DESIGN-0012,
             Phase 5.
"""

from systems.gameplay.exterminator import constants as ext_const

from .base_buff import BaseExterminatorBuff



class AccuracyVsTypeBuff(BaseExterminatorBuff):
    """
    Purpose: Add accuracy levels to the attack of the holder against a task
             creature.

    Entry:
        No conditions. The collector adds the buff only against the task
        type.

    Exit/Returns:
        Not applicable. A rules definition.

    Module Globals:
        ext_const.BUFF_ACCURACY_VS_TYPE, ext_const.RARITY_* read.

    Methodology:
        The levels go into flat_pre of context.accuracy_channel(): Strike for
        a melee swing, Guns for a shot. flat_pre enters before the
        multiplier stages, as a potion does. The buff does nothing when the
        holder defends, because the accuracy of the action belongs to the
        attacker.

    Notes/References:
        The numbers are the vault example (+3) at 1x, 1.5x, 2x, and 3x
        (Nick, 10/07/2026). TBD.

    Author: Nick Hobar
    Creation date: 10/07/2026
    """

    key = ext_const.BUFF_ACCURACY_VS_TYPE
    archetype = ext_const.BUFF_ACCURACY_VS_TYPE
    name = "Task Accuracy"  # TBD name
    description = "+{value} accuracy level against your task type."

    strengths = {
        ext_const.RARITY_COMMON: 3,
        ext_const.RARITY_RARE: 5,
        ext_const.RARITY_EPIC: 6,
        ext_const.RARITY_LEGENDARY: 9,
    }

    def contribute_modifiers(self, context, bag) -> None:
        """Add the accuracy levels when the holder attacks."""
        if not self.holder_attacks(context, bag):
            return

        holder = self.holder_of(context, bag)
        bonus = self.strength(holder)

        bag.add_flat_pre(context.accuracy_channel(), bonus)
