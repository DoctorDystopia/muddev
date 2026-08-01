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