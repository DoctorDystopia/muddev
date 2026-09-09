"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Skill category Production - Metalsmith recipe definitions.
"""



from ..blackout_recipe import BlackoutRecipe
from ..constants import CATEGORY_METALSMITH



class RustyScrapDaggerRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude dagger at an anvil."

    name = "rusty scrap dagger"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 0
    xp_reward = 25
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_dagger"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable dagger."



class RustyScrapAxeRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude axe at an anvil."

    name = "rusty scrap axe"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 0
    xp_reward = 25
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_axe"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable axe."



class RustyScrapBootsRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude boots at an anvil."

    name = "rusty scrap boots"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 3
    xp_reward = 25
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_boots"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable boots."



class RustyScrapShortswordRecipe(BlackoutRecipe):
    "Hammer two rusty scrap metal sheets into a crude shortsword at an anvil."

    name = "rusty scrap shortsword"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 4
    xp_reward = 50
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
    xp_reward = 50
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_spear"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable spear."



class RustyScrapSquareShieldRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude square shield at an anvil."

    name = "rusty scrap square shield"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 8
    xp_reward = 50
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_square_shield"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable square shield."



class RustyScrapBattleaxeRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude battleaxe at an anvil."

    name = "rusty scrap battleaxe"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 10
    xp_reward = 75
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_battleaxe"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable battleaxe."



class RustyScrapChainbodyRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude chainbody at an anvil."

    name = "rusty scrap chainbody"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 11
    xp_reward = 75
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_chainbody"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable chainbody."



class ScrapShortswordRecipe(BlackoutRecipe):
    "Hammer two scrap metal sheets into a crude shortsword at an anvil."

    name = "scrap shortsword"
    category = CATEGORY_METALSMITH
    required_skill = "metalsmith"
    required_level = 14
    xp_reward = 70
    skill_category = "production"

    consumable_tags = ["scrap_metal", "scrap_metal"]
    consumable_names = ["scrap metal", "scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_shortsword"]

    success_message = "You hammer the scrap metal into a rough but serviceable shortsword."