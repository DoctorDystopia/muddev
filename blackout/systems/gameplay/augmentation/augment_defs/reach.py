"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: Reach, the aura augment (DESIGN-0015, section 4.4). It widens
             the ring of the lit aura. The aura handler asks
             rules.reach_bonus for the tiles at each pulse, and the ring
             cache rebuilds when the radius moves.
"""

from systems.gameplay.augmentation import constants as aug_const

from .base_augment import BaseAugment


class Reach(BaseAugment):
    """
    Purpose: Add tiles to the radius of the lit aura. The tiles follow the
    power level, not the level: power level k of AUG_POWER_LEVELS gives
    AUG_REACH_TILES x k / AUG_POWER_LEVELS tiles, rounded, so the dial
    reads 1, 2, 3.

    Every number is a placeholder until Nick tunes it. The name is a
    working name.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """

    key = "reach"
    name = "Reach"
    description = "Pushes your aura out past its ring."
    family = aug_const.FAMILY_AURA
    modifies = aug_const.MODIFIES_REACH
    drain = 5.0
    pct_per_level = 0.0
    unlock_level = 25
    sockets = (aug_const.SOCKET_NEURAL, aug_const.SOCKET_HEAD)

    def tiles_for(self, power_level: int) -> int:
        """The tiles that this augment adds at one power level. At least 1."""
        share = self.power_level_share(power_level)
        tiles = round(aug_const.AUG_REACH_TILES * share)

        return max(1, int(tiles))

    def effect_line(self, level: int) -> str:
        """The tiles at the top power level, as the tip says it."""
        tiles = self.tiles_for(aug_const.AUG_POWER_LEVELS)

        return aug_const.AUG_TIP_REACH.format(tiles=tiles)
