"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Foundry-category recipe definitions (smelting).
"""

from ..blackout_recipe import BlackoutRecipe
from ..constants import CATEGORY_FOUNDRY


class RustyScrapMetalRecipe(BlackoutRecipe):
    "Smelt a rusty metal chunk into usable scrap metal in a foundry furnace."

    name = "rusty scrap metal"
    category = CATEGORY_FOUNDRY
    required_skill = "foundry"
    required_level = 0
    xp_reward = 10
    skill_category = "processing"

    consumable_tags = ["rusty_metal_chunk"]
    consumable_names = ["Rusty Metal Chunk"]

    tool_tags = ["furnace"]
    tool_names = ["Furnace"]

    output_item_keys = ["rusty_scrap_metal"]

    success_message = "You smelt the rusty metal chunk into a piece of scrap metal."
