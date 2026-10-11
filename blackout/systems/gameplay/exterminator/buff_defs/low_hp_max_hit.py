"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/07/2026
Description: The `low_hp_max_hit` buff: more max hit against a task creature
             under an HP line. The rarity scales the bonus. The line stays
             the same (Nick, 10/07/2026). DESIGN-0012, Phase 5.
"""

from systems.gameplay.combat import constants as combat_const
from systems.gameplay.exterminator import constants as ext_const

from .base_buff import BaseExterminatorBuff



# The HP line, as a percent of the max HP of the creature. The buff works
# when the HP of the creature is BELOW the line. TBD number.
LOW_HP_LINE_PERCENT: int = 25

_PERCENT: int = 100



class LowHpMaxHitBuff(BaseExterminatorBuff):
    """
    Purpose: Add to the max hit of the holder against a task creature under
             the HP line.

    Entry:
        No conditions. The collector adds the buff only against the task
        type.

    Exit/Returns:
        Not applicable. A rules definition.

    Module Globals:
        LOW_HP_LINE_PERCENT, combat_const.CHANNEL_MAX_HIT,
        ext_const.RARITY_* read.

    Methodology:
        1. If the holder defends, stop. The max hit belongs to the attacker.
        2. If the defender is at or above the line, stop. The test uses
           integer math: hp x 100 < line x max_hp.
        3. Add the strength to flat_post of the max hit channel.
           flat_post adds after the multipliers. Thus "+4 max hit" is
           always +4.

    Notes/References:
        The buff reads the HP live from the defender, at the start of the
        action.
        The numbers are the vault example (+4) at 1x, 1.5x, 2x, and 3x
        (Nick, 10/07/2026). TBD.

    Author: Nick Hobar
    Creation date: 10/07/2026
    """

    key = ext_const.BUFF_LOW_HP_MAX_HIT
    archetype = ext_const.BUFF_LOW_HP_MAX_HIT
    name = "Finisher"  # TBD name
    description = (
        f"+{{value}} max hit against a task creature under "
        f"{LOW_HP_LINE_PERCENT}% HP."
    )

    strengths = {
        ext_const.RARITY_COMMON: 4,
        ext_const.RARITY_RARE: 6,
        ext_const.RARITY_EPIC: 8,
        ext_const.RARITY_LEGENDARY: 12,
    }

    def is_below_line(self, target) -> bool:
        """Say whether the target is under the HP line. False with no max HP."""
        max_hp = int(getattr(target, "max_hp", 0) or 0)
        hp = int(getattr(target, "hp", 0) or 0)

        if max_hp <= 0:
            return False

        return hp * _PERCENT < LOW_HP_LINE_PERCENT * max_hp

    def contribute_modifiers(self, context, bag) -> None:
        """Add the max hit when the holder attacks a creature under the line."""
        if not self.holder_attacks(context, bag):
            return

        below_line = self.is_below_line(context.defender)

        if not below_line:
            return

        holder = self.holder_of(context, bag)
        bonus = self.strength(holder)

        bag.add_flat_post(combat_const.CHANNEL_MAX_HIT, bonus)
