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
# Declaring the literal in either place is what caused the Metalsmith/
# Metalsmithing mismatch that hid every anvil recipe.
CATEGORY_FOUNDRY = "Foundry"
CATEGORY_METALSMITHING = "Metalsmithing"

# Every category the game knows about, for validation and UI ordering.
CRAFTING_CATEGORIES = (
    CATEGORY_FOUNDRY,
    CATEGORY_METALSMITHING,
)
