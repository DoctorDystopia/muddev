"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/07/2026
Description: The `defense_seal` buff: more defense bonus when a task
             creature attacks the holder.

             The vault note gives it a burn-off. The seal goes after N hits
             taken, and it comes back at the next pick. The burn-off needs an
             on-hit hook, and that hook does not exist yet (Phase 6). This
             buff is the seal with no burn-off. DESIGN-0012, Phase 5.
"""

from systems.gameplay.combat import constants as combat_const
from systems.gameplay.exterminator import constants as ext_const

from .base_buff import BaseExterminatorBuff



class DefenseSealBuff(BaseExterminatorBuff):
    """
    Purpose: Add to the defense bonus of the holder when a task creature
             attacks the holder.

    Entry:
        No conditions. The collector adds the buff to the defender rules
        only when the attacker is of the task type.

    Exit/Returns:
        Not applicable. A rules definition.

    Module Globals:
        combat_const.CHANNEL_DEFENSE_BONUS, ext_const.RARITY_* read.

    Methodology:
        The bonus goes into flat_pre of the defense bonus channel, in the
        bag of the holder. The accuracy seam reads that channel from the
        DEFENDER bag. Thus, the buff does nothing when the holder attacks.

    Notes/References:
        The numbers are the vault example (+15) at 1x, 1.5x, 2x, and 3x
        (Nick, 10/07/2026). TBD.

    Author: Nick Hobar
    Creation date: 10/07/2026
    """

    key = ext_const.BUFF_DEFENSE_SEAL
    archetype = ext_const.BUFF_DEFENSE_SEAL
    name = "Task Defense"  # TBD name
    description = "+{value} defense bonus against attacks from your task type."

    strengths = {
        ext_const.RARITY_COMMON: 15,
        ext_const.RARITY_RARE: 23,
        ext_const.RARITY_EPIC: 30,
        ext_const.RARITY_LEGENDARY: 45,
    }

    def contribute_modifiers(self, context, bag) -> None:
        """Add the defense bonus when the holder defends."""
        if self.holder_attacks(context, bag):
            return

        holder = self.holder_of(context, bag)
        bonus = self.strength(holder)

        bag.add_flat_pre(combat_const.CHANNEL_DEFENSE_BONUS, bonus)
