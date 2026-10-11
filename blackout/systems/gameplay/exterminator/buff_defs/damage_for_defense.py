"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/07/2026
Description: The `damage_for_defense` buff: more max hit and less defense
             bonus, against the task type only. The rarity scales the max
             hit. The cost stays the same at every rarity (Nick, 10/07/2026),
             so a rarer card is a better trade. DESIGN-0012, Phase 5.
"""

from systems.gameplay.combat import constants as combat_const
from systems.gameplay.exterminator import constants as ext_const

from .base_buff import BaseExterminatorBuff



# The part of the defense bonus that the holder loses when a task creature
# attacks. 0.25 is -25%. TBD number.
DEFENSE_BONUS_CUT: float = 0.25

_PERCENT: int = 100



class DamageForDefenseBuff(BaseExterminatorBuff):
    """
    Purpose: Raise the max hit of the holder against a task creature.
             Lower the defense bonus of the holder when one attacks.

    Entry:
        No conditions. The collector adds the buff to the attacker rules or
        to the defender rules only against the task type.

    Exit/Returns:
        Not applicable. A rules definition.

    Module Globals:
        DEFENSE_BONUS_CUT, combat_const.CHANNEL_MAX_HIT,
        combat_const.CHANNEL_DEFENSE_BONUS, ext_const.RARITY_* read.

    Methodology:
        When the holder attacks, the strength goes into the augment stage of
        the max hit channel: +0.30 is +30%.

        When the holder defends, -DEFENSE_BONUS_CUT goes into the augment
        stage of the defense bonus channel. Only a positive defense bonus
        gets the cut. A cut of a negative bonus would move it toward 0, and
        the cost would become a gain.

    Notes/References:
        The numbers are the vault example (+30%) at 1x, 1.5x, 2x, and 3x
        (Nick, 10/07/2026). TBD.

    Author: Nick Hobar
    Creation date: 10/07/2026
    """

    key = ext_const.BUFF_DAMAGE_FOR_DEFENSE
    archetype = ext_const.BUFF_DAMAGE_FOR_DEFENSE
    name = "Trade Defense"  # TBD name
    description = (
        f"+{{value:.0%}} max hit and -{round(DEFENSE_BONUS_CUT * _PERCENT)}% "
        f"defense bonus against your task type."
    )

    strengths = {
        ext_const.RARITY_COMMON: 0.30,
        ext_const.RARITY_RARE: 0.45,
        ext_const.RARITY_EPIC: 0.60,
        ext_const.RARITY_LEGENDARY: 0.90,
    }

    def contribute_modifiers(self, context, bag) -> None:
        """More max hit when the holder attacks. Less defense bonus when it defends."""
        if self.holder_attacks(context, bag):
            holder = self.holder_of(context, bag)
            bag.add_augment_bonus(combat_const.CHANNEL_MAX_HIT, self.strength(holder))
            return

        defense_bonus = context.defense_equip_bonus()

        if defense_bonus <= 0:
            return

        bag.add_augment_bonus(combat_const.CHANNEL_DEFENSE_BONUS, -DEFENSE_BONUS_CUT)
