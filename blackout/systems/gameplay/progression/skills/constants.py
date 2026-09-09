"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Configuration limits and multipliers for the skill progression system.
"""



# Constants for XP calculation
BASE_CURVE_MULTIPLIER = 300
EXPONENTIAL_BASE = 2
LEVELS_PER_DOUBLING = 10.0  # Tweaked from OSRS's default of 7
XP_SCALING_FACTOR = 0.25    # Equivalent to dividing by 4

# Constants for skill level boundaries
DEFAULT_START_LEVEL = 0
DEFAULT_START_XP = 0
MIN_BASE_SKILL_LEVEL = 0
MAX_BASE_SKILL_LEVEL = 127

# Skill keys referenced by name from code outside the skill_defs tree. Kept
# here so a rename is a one-line change rather than a grep for string
# literals -- Fortitude in particular is read by the combat layer, the
# level-up side-effect table, and character creation.
FORTITUDE_SKILL_KEY = "fortitude"

# The three combat axes a melee swing resolves against. These are read by the
# swing pipeline, by the weapon-style level-boost dicts in the combat
# constants, and by any rules definition that reads a wearer's own stats.
STRIKE_SKILL_KEY = "strike"
BRAWN_SKILL_KEY = "brawn"
DEFENSE_SKILL_KEY = "defense"

# Every skill axis an ActionContext snapshots before resolution. Fortitude is in
# the list because rules definitions read it (the glass cannon amulet keys off
# the Brawn-over-Fortitude surplus), not because a swing resolves against it.
COMBAT_SKILL_KEYS = (
    STRIKE_SKILL_KEY,
    BRAWN_SKILL_KEY,
    DEFENSE_SKILL_KEY,
    FORTITUDE_SKILL_KEY,
)