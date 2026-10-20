"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/03/2026
Description: Righteous Fire — a Fortitude-scaled damage aura that burns every
             hostile within a radius of the caster on the global combat tick.
"""

from systems.gameplay.combat import constants as const
from systems.gameplay.progression.skills.constants import SKILL_KEY_FORTITUDE

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
RIGHTEOUS_FIRE_RADIUS = 2

# Fortitude level required to switch the aura on. Characters spawn at level 10,
# so this is a genuine mid-early goal rather than a starting ability.
RIGHTEOUS_FIRE_UNLOCK_LEVEL = 25

# Share of the max HP of the caster that each pulse burns from the caster.
# The burn lands on every pulse, with or without a target, and it can kill
# (Nick, 10/20/2026). The share is the same at every level. Thus, 0.02
# burns a caster at full HP to 0 in 50 pulses, about two minutes. HP regen
# gives back 1 HP each minute, so it changes that time very little.
RIGHTEOUS_FIRE_SELF_BURN_PCT = 0.02



class RighteousFire(BaseAura):
    """
    Purpose: A toggled aura burning every hostile in radius, scaling with (and
    granting experience to) the caster's Fortitude skill.

    Fortitude is deliberately both the scaling skill and the experience skill.
    Fortitude already sets max HP one-to-one (constants.HP_PER_FORTITUDE_LEVEL),
    so levelling it widens the caster's health pool AND the aura's damage
    together, the aura gets stronger exactly as the character gets tougher,
    which is the risk/reward shape the mechanic is modelled on.

    The aura also burns its caster on every pulse. The player must put it
    out before it kills them.
    """

    key = "righteous_fire"
    name = "Righteous Fire"
    description = ("Use your Fortitude to wreathe yourself in scouring flame, searing every hostile around you.")

    radius = RIGHTEOUS_FIRE_RADIUS
    tick_interval = const.AURA_DEFAULT_TICK_INTERVAL
    damage_pct = RIGHTEOUS_FIRE_DAMAGE_PCT
    self_burn_pct = RIGHTEOUS_FIRE_SELF_BURN_PCT

    scaling_skill = SKILL_KEY_FORTITUDE
    xp_skill = SKILL_KEY_FORTITUDE
    unlock_level = RIGHTEOUS_FIRE_UNLOCK_LEVEL
