"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: Plating, the defense augment (DESIGN-0015, section 4.4).
"""

from systems.gameplay.augmentation import constants as aug_const

from .base_augment import BaseAugment


class Plating(BaseAugment):
    """
    Purpose: Boost the Defense level against every action. The channel is
    the defender channel, so this augment matters on the side that takes
    the hit.

    Every number is a placeholder until Nick tunes it. The name is a
    working name.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """

    key = "plating"
    name = "Plating"
    description = "Hardens your skin. Boosts your Defense against every attack."
    family = aug_const.FAMILY_DEFENSE
    drain = 3.0
    pct_per_level = 0.002
    unlock_level = 10
    sockets = (aug_const.SOCKET_BODY, aug_const.SOCKET_SKELETON)
