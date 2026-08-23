"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Skill category Processing - Foundry recipe definitions.
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
    consumable_names = ["rusty metal chunk"]

    tool_tags = ["furnace"]
    tool_names = ["furnace"]

    output_item_keys = ["rusty_scrap_metal"]

    success_message = "You smelt the rusty metal chunk into a piece of scrap metal."



class RustyMetalDustRecipe(BlackoutRecipe):
    "Grind a rusty metal chunk into fine dust using a hammer."

    name = "rusty metal dust"
    category = CATEGORY_FOUNDRY
    required_skill = "foundry"
    required_level = 0
    xp_reward = 15
    skill_category = "processing"

    consumable_tags = ["rusty_metal_chunk"]
    consumable_names = ["rusty metal chunk"]

    tool_tags = ["hammer"]
    tool_names = ["hammer"]

    output_item_keys = ["rusty_metal_dust"]

    success_message = "You grind the rusty metal chunk into a fine dust."



class ScrapMetalRecipe(BlackoutRecipe):
    "Smelt a metal chunk into usable scrap metal in a foundry furnace."

    name = "scrap metal"
    category = CATEGORY_FOUNDRY
    required_skill = "foundry"
    required_level = 0
    xp_reward = 20
    skill_category = "processing"

    consumable_tags = ["metal_chunk"]
    consumable_names = ["metal chunk"]

    tool_tags = ["furnace"]
    tool_names = ["furnace"]

    output_item_keys = ["scrap_metal"]

    success_message = "You smelt the metal chunk into a piece of scrap metal."



class MetalDustRecipe(BlackoutRecipe):
    "Grind a metal chunk into fine dust using a hammer."

    name = "metal dust"
    category = CATEGORY_FOUNDRY
    required_skill = "foundry"
    required_level = 0
    xp_reward = 30
    skill_category = "processing"

    consumable_tags = ["metal_chunk"]
    consumable_names = ["metal chunk"]

    tool_tags = ["hammer"]
    tool_names = ["hammer"]

    output_item_keys = ["metal_dust"]

    success_message = "You grind the metal chunk into a fine dust."