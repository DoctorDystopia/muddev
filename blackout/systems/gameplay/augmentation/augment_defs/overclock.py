"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: Overclock, the roll augment (DESIGN-0015, section 4.5). One
             augment rolls, and every other stays deterministic. On each
             light, Overclock rolls a strength in [low, AUG_ROLL_HIGH], and
             the level moves the low end up. The roll adds to every lit
             stat augment. A relight rerolls, and a relight costs Grit, so
             the reroll is a gamble with a price.
"""

from systems.gameplay.augmentation import constants as aug_const

from .base_augment import BaseAugment


# One hundred, for a percent.
_PERCENT: float = 100.0


class Overclock(BaseAugment):
    """
    Purpose: Roll a strength at each light, and add it to every lit stat
    augment. Overclock boosts no channel of its own: `modifies` names the
    strength, and rules.active_rules reads the roll into each other bonus.

    Every number is a placeholder until Nick tunes it. The name is a
    working name.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """

    key = "overclock"
    name = "Overclock"
    description = "Runs every other augment hot. Rolls its strength each time it comes online."
    family = aug_const.FAMILY_MODIFIER
    modifies = aug_const.MODIFIES_STRENGTH
    rolls = True
    drain = 4.0
    pct_per_level = 0.0
    unlock_level = 15
    sockets = (aug_const.SOCKET_NEURAL, aug_const.SOCKET_HEAD)

    def roll_low(self, level: int) -> float:
        """The low end of the roll at a level. It never passes the high end."""
        low = aug_const.AUG_ROLL_LOW + aug_const.AUG_ROLL_LOW_PER_LEVEL * level

        return min(low, aug_const.AUG_ROLL_HIGH)

    def roll_for(self, level: int, rng) -> float:
        """
        Purpose: Roll the strength of one light.

        Entry:
            level is the Augmentation level of the holder.
            rng is a random.Random. A test passes a seeded one.

        Exit/Returns:
            Returns a float in [roll_low(level), AUG_ROLL_HIGH], a bonus in
            the form of augment_bonus.

        Module Globals:
            aug_const.AUG_ROLL_HIGH read.

        Methodology:
            One rng.uniform. The handler stores the result, and the rules
            read it at each action, so a light rolls one time.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        low = self.roll_low(level)

        return rng.uniform(low, aug_const.AUG_ROLL_HIGH)

    def effect_line(self, level: int) -> str:
        """The roll range at this level, as the tip says it."""
        return aug_const.AUG_TIP_ROLL.format(
            low=self.roll_low(level) * _PERCENT,
            high=aug_const.AUG_ROLL_HIGH * _PERCENT)
