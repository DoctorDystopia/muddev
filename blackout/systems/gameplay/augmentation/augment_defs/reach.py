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
    step, not the level: step k of AUG_STEPS gives AUG_REACH_TILES x k /
    AUG_STEPS tiles, rounded, so the dial reads 1, 2, 3.

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

    def tiles_for(self, step: int) -> int:
        """The tiles that this augment adds at one step. At least 1."""
        share = self.step_share(step)
        tiles = round(aug_const.AUG_REACH_TILES * share)

        return max(1, int(tiles))

    def effect_line(self, level: int) -> str:
        """The tiles at the top step, as the tip says it."""
        return aug_const.AUG_TIP_REACH.format(tiles=self.tiles_for(aug_const.AUG_STEPS))
