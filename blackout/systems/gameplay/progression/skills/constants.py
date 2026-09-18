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



# ─── Skill categories ───────────────────────────────────────────────────────
# Each skill class declares one of these as its `category`. The skills pane
# bands its grid by this value, and the Godot palette colours each band by
# the same string. A crafting category is a different fact. It lives in
# systems/gameplay/crafting/constants.py.
SKILL_CATEGORY_COMBAT = "Combat"
SKILL_CATEGORY_GATHERING = "Gathering"
SKILL_CATEGORY_PROCESSING = "Processing"
SKILL_CATEGORY_PRODUCTION = "Production"

SKILL_CATEGORIES = (
    SKILL_CATEGORY_COMBAT,
    SKILL_CATEGORY_GATHERING,
    SKILL_CATEGORY_PROCESSING,
    SKILL_CATEGORY_PRODUCTION,
)



# ─── Skill keys ─────────────────────────────────────────────────────────────
# The one spelling of each skill key. Each skill class reads its `key` from
# here. So does every system that names a skill: recipes, gathering nodes,
# combat maths, equipment gates, and quest rewards. A rename is then a
# one-line change, not a search for string literals.

# Combat
SKILL_KEY_FORTITUDE = "fortitude"
SKILL_KEY_STRIKE = "strike"
SKILL_KEY_BRAWN = "brawn"
SKILL_KEY_DEFENSE = "defense"
SKILL_KEY_GUNS = "guns"
SKILL_KEY_BALLISTICS = "ballistics"

# Gathering
SKILL_KEY_CUTTING = "cutting"
SKILL_KEY_BUTCHERY = "butchery"
SKILL_KEY_BRAIN_FARMING = "brain_farming"

# Processing
SKILL_KEY_FOUNDRY = "foundry"
SKILL_KEY_RENDERING = "rendering"
SKILL_KEY_CURING = "curing"

# Production
SKILL_KEY_METALSMITH = "metalsmith"
SKILL_KEY_GUNSMITH = "gunsmith"
SKILL_KEY_GASTRONOMY = "gastronomy"



# ─── Skill keys by category ─────────────────────────────────────────────────
# Each tuple holds every skill that declares that category.
# progression/tests/test_skill_constants.py compares each tuple with
# SKILL_REGISTRY, so a tuple cannot drift from the skill classes.

# Every skill axis that an ActionContext snapshots before resolution.
# Fortitude is in the tuple because rules definitions read it (the glass
# cannon amulet reads the Brawn-over-Fortitude surplus). A swing does not
# resolve against it.
SKILL_KEYS_CATEGORY_COMBAT = (
    SKILL_KEY_FORTITUDE,
    SKILL_KEY_STRIKE,
    SKILL_KEY_BRAWN,
    SKILL_KEY_DEFENSE,
    SKILL_KEY_GUNS,
    SKILL_KEY_BALLISTICS,
)

# Every skill that works a node in GATHERABLE_REGISTRY. The gathering command
# set builds one verb for each entry. A key here with no skill class behind it
# gives a node a verb that resolves to nothing.
SKILL_KEYS_CATEGORY_GATHERING = (
    SKILL_KEY_CUTTING,
    SKILL_KEY_BUTCHERY,
    SKILL_KEY_BRAIN_FARMING,
)

SKILL_KEYS_CATEGORY_PROCESSING = (
    SKILL_KEY_FOUNDRY,
    SKILL_KEY_RENDERING,
    SKILL_KEY_CURING,
)

SKILL_KEYS_CATEGORY_PRODUCTION = (
    SKILL_KEY_METALSMITH,
    SKILL_KEY_GUNSMITH,
    SKILL_KEY_GASTRONOMY,
)
