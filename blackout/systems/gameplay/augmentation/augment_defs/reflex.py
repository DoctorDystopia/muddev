"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: Reflex, the accuracy augment (DESIGN-0015, section 4.4).
"""

from systems.gameplay.augmentation import constants as aug_const

from .base_augment import BaseAugment


class Reflex(BaseAugment):
    """
    Purpose: Boost the accuracy level of the active style. Strike for a
    melee swing, Guns for a shot. One augment serves both, because the
    channel follows the style.

    Every number is a placeholder until Nick tunes it. The name is a
    working name.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """

    key = "reflex"
    name = "Reflex"
    description = "Sharpens your aim. Boosts the accuracy of your swings and shots."
    family = aug_const.FAMILY_ACCURACY
    drain = 3.0
    pct_per_level = 0.002
    unlock_level = aug_const.NO_UNLOCK_LEVEL
    sockets = (aug_const.SOCKET_HEAD, aug_const.SOCKET_ARM_L, aug_const.SOCKET_ARM_R)
