"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Metalsmith-category recipe definitions (forging).
"""

from ..blackout_recipe import BlackoutRecipe
from ..constants import CATEGORY_METALSMITH


class RustyMetalDustRecipe(BlackoutRecipe):
    "Grind a rusty metal chunk into fine dust using a hammer."

    name = "rusty metal dust"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 0
    xp_reward = 15
    skill_category = "production"

    consumable_tags = ["rusty_metal_chunk"]
    consumable_names = ["rusty metal chunk"]

    tool_tags = ["hammer"]
    tool_names = ["hammer"]

    output_item_keys = ["rusty_metal_dust"]

    success_message = "You grind the rusty metal chunk into a fine dust."


class RustyScrapAxeRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude axe at an anvil."

    name = "rusty scrap axe"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 0
    xp_reward = 30
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_axe"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable axe."


class RustyScrapShortswordRecipe(BlackoutRecipe):
    "Hammer two rusty scrap metal sheets into a crude shortsword at an anvil."

    name = "rusty scrap shortsword"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 4
    xp_reward = 60
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_shortsword"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable shortsword."


class RustyScrapSpearRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude spear at an anvil."

    name = "rusty scrap spear"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 5
    xp_reward = 60
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_spear"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable spear."


class RustyScrapChainbodyRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude chainbody at an anvil."

    name = "rusty scrap chainbody"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 11
    xp_reward = 90
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_chainbody"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable chainbody."