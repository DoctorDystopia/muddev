"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/03/2026
Description: Righteous Fire — a Fortitude-scaled damage aura that burns every
             hostile within a radius of the caster on the global combat tick.
"""

from systems.combat import constants as const
from systems.progression.skills.constants import FORTITUDE_SKILL_KEY

from .base_aura import BaseAura


# Public constant definitions

# Share of the caster's Fortitude level dealt per pulse. At the level-10 spawn
# point this is 1 damage (via the AURA_MIN_DAMAGE floor), at the level-127 cap
# it is 12 per pulse across every enemy in radius simultaneously.

# Tuned against the melee baseline rather than picked: one pulse every
# tick_interval matches one weapon swing, so a single enemy in radius takes
# roughly a second weapon's worth of damage, and the aura's real value is that
# the same pulse hits everything in range at once.
RIGHTEOUS_FIRE_DAMAGE_PCT = 0.10

# Radius in grid tiles. Two tiles under the euclidean metric covers 13 rooms --
# the caster's own room, the four orthogonal neighbours, the four diagonals, and
# the four tiles two steps out on the axes. The box corners are trimmed.
RIGHTEOUS_FIRE_RADIUS = 1

# Fortitude level required to switch the aura on. Characters spawn at level 10,
# so this is a genuine mid-early goal rather than a starting ability.
RIGHTEOUS_FIRE_UNLOCK_LEVEL = 25



class RighteousFire(BaseAura):
    """
    Purpose: A toggled aura burning every hostile in radius, scaling with (and
    granting experience to) the caster's Fortitude skill.

    Fortitude is deliberately both the scaling skill and the experience skill.
    Fortitude already sets max HP one-to-one (constants.HP_PER_FORTITUDE_LEVEL),
    so levelling it widens the caster's health pool AND the aura's damage
    together, the aura gets stronger exactly as the character gets tougher,
    which is the risk/reward shape the mechanic is modelled on.
    """

    key = "righteous_fire"
    name = "Righteous Fire"
    description = ("Use your Fortitude to wreathe yourself in scouring flame, searing every hostile around you.")

    radius = RIGHTEOUS_FIRE_RADIUS
    tick_interval = const.AURA_DEFAULT_TICK_INTERVAL
    damage_pct = RIGHTEOUS_FIRE_DAMAGE_PCT

    scaling_skill = FORTITUDE_SKILL_KEY
    xp_skill = FORTITUDE_SKILL_KEY
    unlock_level = RIGHTEOUS_FIRE_UNLOCK_LEVEL
