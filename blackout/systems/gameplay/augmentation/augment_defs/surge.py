"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: Surge, the damage augment (DESIGN-0015, section 4.4).
"""

from systems.gameplay.augmentation import constants as aug_const

from .base_augment import BaseAugment


class Surge(BaseAugment):
    """
    Purpose: Boost the damage level of the active style. Brawn for a melee
    swing, Ballistics for a shot.

    Every number is a placeholder until Nick tunes it. The name is a
    working name.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """

    key = "surge"
    name = "Surge"
    description = "Floods your muscles. Boosts the damage of your swings and shots."
    family = aug_const.FAMILY_DAMAGE
    drain = 3.0
    pct_per_level = 0.002
    unlock_level = 5
    sockets = (aug_const.SOCKET_ARM_L, aug_const.SOCKET_ARM_R, aug_const.SOCKET_BODY)
