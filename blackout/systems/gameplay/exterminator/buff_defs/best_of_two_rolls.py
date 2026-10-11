"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/07/2026
Description: The `best_of_two_rolls` buff: roll the damage two times against
             a task creature, and keep the higher roll.

             A seam buff. It owns `roll_damage`. Against the task type, it
             replaces the die of a weapon that owns that seam too: the toy
             sword and the bit blade. The card shows the conflict warning.
             Against every other target, the weapon keeps its die.
             DESIGN-0012, Phase 5.
"""

from systems.gameplay.exterminator import constants as ext_const

from .base_buff import BaseExterminatorBuff



# The count of damage rolls. The rarity does not change it (Nick,
# 10/07/2026): every rarity rolls two times.
DAMAGE_ROLL_COUNT: int = 2



class BestOfTwoRollsBuff(BaseExterminatorBuff):
    """
    Purpose: Roll the OSRS damage roll DAMAGE_ROLL_COUNT times, and keep the
             highest.

    Entry:
        No conditions. The collector adds the buff only against the task
        type.

    Exit/Returns:
        Not applicable. A rules definition.

    Module Globals:
        DAMAGE_ROLL_COUNT read.

    Methodology:
        Each roll is the default roll of BaseActionRules (super()). That
        roll reads the max hit through context.rules. Thus, a max hit buff
        and the damage channel still apply to each roll. Keep the highest
        damage.

        Each roll draws one rng.randint. The draws come after the accuracy
        draw, as the default roll does.

    Notes/References:
        `strengths` is empty, so the card shows a rarity that changes
        nothing. The vault note tags this archetype S (`roll_damage`).

    Author: Nick Hobar
    Creation date: 10/07/2026
    """

    key = ext_const.BUFF_BEST_OF_TWO_ROLLS
    archetype = ext_const.BUFF_BEST_OF_TWO_ROLLS
    name = "Second Roll"  # TBD name
    description = (
        f"Against your task type, roll damage {DAMAGE_ROLL_COUNT} times and "
        f"keep the highest roll."
    )

    def roll_damage(self, context, result) -> None:
        """Roll the default damage roll several times, and keep the highest.

        Keeps the die face of the kept roll with its damage. Each call of
        super() writes `rolled`, so the last roll would otherwise mark a max
        hit for a roll that the buff threw away.
        """
        best = None

        for _roll in range(DAMAGE_ROLL_COUNT):
            super().roll_damage(context, result)
            candidate = (result.damage, result.rolled)

            if best is None or candidate > best:
                best = candidate

        result.damage, result.rolled = best
