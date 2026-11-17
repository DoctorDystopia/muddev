"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/14/2026
Description: Nitro, the movement augment (Nick, 11/14/2026). It adds tiles
             to each tick of a walk or a run. At each tick, the walk reads
             the tiles from rules.tile_bonus. The walk keeps the part of a
             tile as its tile carry.
"""

from fractions import Fraction

from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.movement import constants as walk_const

from .base_augment import BaseAugment


class Nitro(BaseAugment):
    """
    Purpose: Add tiles to each tick of the walk or the run of the holder.
    Power level k adds AUG_NITRO_TILES x k / AUG_POWER_LEVELS tiles. The
    dial thus reads a third, two thirds, and one whole tile. The walk adds
    the bonus to its walk or run speed, up to the speed cap (Nick,
    11/14/2026).

    Nick named Nitro and its sockets. The drain, the level gate, and the
    description are placeholders until Nick tunes them.

    Author: Nick Hobar
    Creation date: 11/14/2026
    """

    key = "nitro"
    name = "Nitro"
    description = "Speeds up your walk and your run."
    family = aug_const.FAMILY_MOVEMENT
    modifies = aug_const.MODIFIES_SPEED
    drain = 4.0
    pct_per_level = 0.0
    unlock_level = 35
    sockets = (aug_const.SOCKET_SKELETON, aug_const.SOCKET_LEG_R, aug_const.SOCKET_LEG_L)

    def tiles_for(self, power_level: int) -> Fraction:
        """
        Purpose: The tiles that this augment adds to each tick at one power
                 level.

        Entry:
            power_level is an int in [AUG_POWER_LEVEL_MIN, AUG_POWER_LEVELS].

        Exit/Returns:
            Returns the tiles as a Fraction. Power level AUG_POWER_LEVELS
            gives AUG_NITRO_TILES.

        Module Globals:
            aug_const.AUG_NITRO_TILES, AUG_POWER_LEVELS read.

        Methodology:
            The power level share of `power_level_share`, as an exact
            fraction. The walk adds the part of a tile to its carry on each
            tick. Three float thirds do not make 1.0 in every order. A carry
            that stops at 0.9999 never gives its tile.

        Notes/References:
            The carry is in walk._take_tiles.

        Author: Nick Hobar
        Creation date: 11/14/2026
        """
        share = Fraction(power_level, aug_const.AUG_POWER_LEVELS)

        return aug_const.AUG_NITRO_TILES * share

    def effect_line(self, level: int) -> str:
        """The tiles at the top power level and the speed cap, as the tip
        says them."""
        tiles = self.tiles_for(aug_const.AUG_POWER_LEVELS)

        return aug_const.AUG_TIP_SPEED.format(tiles=tiles, cap=walk_const.MAX_TILES_PER_TICK)
