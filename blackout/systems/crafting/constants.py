"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/30/2026
Description: Single source of truth for crafting category names and the Evennia
             tag categories the crafting contrib uses to find materials/tools.
"""



# Public constant definitions

# Tag categories consumed by the Evennia crafting contrib. Recipes declare
# consumable_tags/tool_tags; the contrib looks them up under these categories.
CONSUMABLE_TAG_CATEGORY = "crafting_material"
TOOL_TAG_CATEGORY = "crafting_tool"

# Canonical recipe category names. A recipe's `category` and a facility's
# `allowed_categories` are matched by exact string equality in
# crafting_service.get_categories, so both sides MUST import from here.
CATEGORY_FOUNDRY = "Foundry"
CATEGORY_METALSMITH = "Metalsmith"

# Every category the game knows about, for validation and UI ordering.
CRAFTING_CATEGORIES = (
    CATEGORY_FOUNDRY,
    CATEGORY_METALSMITH,
)

# Seconds a single craft takes by default. A recipe overrides via its own
# craft_seconds class attribute (see BlackoutRecipe); this is the fallback,
# not a tunable every recipe must set.
DEFAULT_CRAFT_SECONDS = 2.0

# Hard ceiling on a single "craft all" batch, independent of materials on
# hand. Recipes with no consumable_tags have nothing to run out of, so
# without this cap "craft all" on a toolless-material recipe would have no
# natural stopping point.
MAX_CRAFT_BATCH_SIZE = 99

# Cooldown name the paced batch loop arms on the crafter between items. One
# key shared by every recipe (not namespaced per-recipe like skills'
# "skill_<key>") because only one craft batch can run on a character at a
# time -- see systems/crafting/craft_batch.py.
CRAFTING_BUSY_COOLDOWN_KEY = "crafting_batch"
