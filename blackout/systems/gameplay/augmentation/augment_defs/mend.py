"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: Mend, the regen augment (DESIGN-0015, section 4.4). It
             shortens the wait between HP regen ticks. The regen sweep
             (combat/hp_regen.py) asks rules.regen_interval_share for the
             share of the interval that a holder keeps, and heals a share
             more at each sweep.
"""

from systems.gameplay.augmentation import constants as aug_const

from .base_augment import BaseAugment


# One hundred, for a percent.
_PERCENT: float = 100.0


class Mend(BaseAugment):
    """
    Purpose: Shorten the HP regen interval of the holder by a share of the
    level. Mend boosts no channel of an action.

    Every number is a placeholder until Nick tunes it. The name is a
    working name.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """

    key = "mend"
    name = "Mend"
    description = "Knits you back together faster. Shortens the wait between regen ticks."
    family = aug_const.FAMILY_REGEN
    modifies = aug_const.MODIFIES_REGEN
    drain = 2.0
    pct_per_level = 0.004
    unlock_level = 30
    sockets = (aug_const.SOCKET_BODY, aug_const.SOCKET_SKELETON)

    def effect_line(self, level: int) -> str:
        """The cut of the interval at this level, as the tip says it."""
        percent = self.bonus_for(level, aug_const.AUG_STEPS) * _PERCENT

        return aug_const.AUG_TIP_REGEN.format(percent=percent)
