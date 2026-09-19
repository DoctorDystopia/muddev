"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Skill category Production - Metalsmith recipe definitions.
"""



from systems.gameplay.progression.skills import constants as skill_constants
from ..blackout_recipe import BlackoutRecipe
from ..constants import CRAFT_CATEGORY_METALSMITH



# ---------------------------------
# --- RUSTY SCRAP METAL RECIPES ---
# ---------------------------------

class RustyScrapDaggerRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude dagger at an anvil."

    name = "rusty scrap dagger"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 0
    xp_reward = 25
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_dagger"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable dagger."



class RustyScrapAxeRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude axe at an anvil."

    name = "rusty scrap axe"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 0
    xp_reward = 25
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_axe"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable axe."



class RustyScrapHideCapeRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal and mutant raider cured hide into a crude cape at an anvil."

    name = "rusty scrap hide cape"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 1
    xp_reward = 25
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal", "mutant_raider_cured_hide"]
    consumable_names = ["rusty scrap metal", "mutant raider cured hide"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_hide_cape"]

    success_message = "You hammer the rusty scrap metal and mutant raider cured hide into a rough but serviceable rusty scrap hide cape."



class RustyScrapBootsRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude boots at an anvil."

    name = "rusty scrap boots"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 3
    xp_reward = 25
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_boots"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable boots."



class RustyScrapShortswordRecipe(BlackoutRecipe):
    "Hammer two rusty scrap metal sheets into a crude shortsword at an anvil."

    name = "rusty scrap shortsword"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 4
    xp_reward = 50
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_shortsword"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable shortsword."



class RustyScrapScimitarRecipe(BlackoutRecipe):
    "Hammer two rusty scrap metal sheets into a crude scimitar at an anvil."

    name = "rusty scrap scimitar"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 5
    xp_reward = 50
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_scimitar"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable scimitar."



class RustyScrapSpearRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude spear at an anvil."

    name = "rusty scrap spear"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 5
    xp_reward = 50
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_spear"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable spear."



class RustyScrapGreatHelmRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude great helm at an anvil."

    name = "rusty scrap great helm"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 7
    xp_reward = 50
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_great_helm"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable great helm."



class RustyScrapSquareShieldRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude square shield at an anvil."

    name = "rusty scrap square shield"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 8
    xp_reward = 50
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_square_shield"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable square shield."



class RustyScrapBattleaxeRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude battleaxe at an anvil."

    name = "rusty scrap battleaxe"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 10
    xp_reward = 75
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_battleaxe"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable battleaxe."



class RustyScrapChainbodyRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude chainbody at an anvil."

    name = "rusty scrap chainbody"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 11
    xp_reward = 75
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_chainbody"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable chainbody."



class RustyScrapGreatswordRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude greatsword at an anvil."

    name = "rusty scrap greatsword"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 12
    xp_reward = 75
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_greatsword"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable greatsword."



class RustyScrapPlatelegsRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude platelegs at an anvil."

    name = "rusty scrap platelegs"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 13
    xp_reward = 75
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal", "rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal", "rusty scrap metal", "rusty scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["rusty_scrap_platelegs"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable platelegs."



# ---------------------------
# --- SCRAP METAL RECIPES ---
# ---------------------------

class ScrapDaggerRecipe(BlackoutRecipe):
    "Hammer scrap metal into a crude dagger at an anvil."

    name = "scrap dagger"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 10
    xp_reward = 35
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal"]
    consumable_names = ["scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_dagger"]

    success_message = "You hammer the scrap metal into a rough but serviceable dagger."



class ScrapAxeRecipe(BlackoutRecipe):
    "Hammer scrap metal into a crude axe at an anvil."

    name = "scrap axe"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 10
    xp_reward = 35
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal"]
    consumable_names = ["scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_axe"]

    success_message = "You hammer the scrap metal into a rough but serviceable axe."



class ScrapCapeRecipe(BlackoutRecipe):
    "Hammer scrap metal and mutant raider prime cured hide into a crude cape at an anvil."

    name = "scrap hide cape"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 11
    xp_reward = 50
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal", "mutant_raider_prime_cured_hide"]
    consumable_names = ["scrap metal", "mutant raider prime cured hide"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_hide_cape"]

    success_message = "You hammer the scrap metal and prime cured hide into a rough but serviceable scrap hide cape."


class ScrapBootsRecipe(BlackoutRecipe):
    "Hammer scrap metal into a crude boots at an anvil."

    name = "scrap boots"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 13
    xp_reward = 35
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal"]
    consumable_names = ["scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_boots"]

    success_message = "You hammer the scrap metal into a rough but serviceable boots."



class ScrapShortswordRecipe(BlackoutRecipe):
    "Hammer two scrap metal sheets into a crude shortsword at an anvil."

    name = "scrap shortsword"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 14
    xp_reward = 70
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal", "scrap_metal"]
    consumable_names = ["scrap metal", "scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_shortsword"]

    success_message = "You hammer the scrap metal into a rough but serviceable shortsword."



class ScrapScimitarRecipe(BlackoutRecipe):
    "Hammer two scrap metal sheets into a crude scimitar at an anvil."

    name = "scrap scimitar"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 15
    xp_reward = 70
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal", "scrap_metal"]
    consumable_names = ["scrap metal", "scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_scimitar"]

    success_message = "You hammer the scrap metal into a rough but serviceable scimitar."



class ScrapSpearRecipe(BlackoutRecipe):
    "Hammer scrap metal into a crude spear at an anvil."

    name = "scrap spear"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 15
    xp_reward = 70
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal", "scrap_metal"]
    consumable_names = ["scrap metal", "scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_spear"]

    success_message = "You hammer the scrap metal into a rough but serviceable spear."



class ScrapGreatHelmRecipe(BlackoutRecipe):
    "Hammer scrap metal into a crude great helm at an anvil."

    name = "scrap great helm"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 17
    xp_reward = 70
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal", "scrap_metal"]
    consumable_names = ["scrap metal", "scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_great_helm"]

    success_message = "You hammer the scrap metal into a rough but serviceable great helm."



class ScrapSquareShieldRecipe(BlackoutRecipe):
    "Hammer scrap metal into a crude square shield at an anvil."

    name = "scrap square shield"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 18
    xp_reward = 70
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal", "scrap_metal"]
    consumable_names = ["scrap metal", "scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_square_shield"]

    success_message = "You hammer the scrap metal into a rough but serviceable square shield."



class ScrapBattleaxeRecipe(BlackoutRecipe):
    "Hammer scrap metal into a crude battleaxe at an anvil."

    name = "scrap battleaxe"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 20
    xp_reward = 105
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal", "scrap_metal", "scrap_metal"]
    consumable_names = ["scrap metal", "scrap metal", "scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_battleaxe"]

    success_message = "You hammer the scrap metal into a rough but serviceable battleaxe."



class ScrapChainbodyRecipe(BlackoutRecipe):
    "Hammer scrap metal into a crude chainbody at an anvil."

    name = "scrap chainbody"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 21
    xp_reward = 105
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal", "scrap_metal", "scrap_metal"]
    consumable_names = ["scrap metal", "scrap metal", "scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_chainbody"]

    success_message = "You hammer the scrap metal into a rough but serviceable chainbody."



class ScrapGreatswordRecipe(BlackoutRecipe):
    "Hammer scrap metal into a crude greatsword at an anvil."

    name = "scrap greatsword"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 22
    xp_reward = 105
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal", "scrap_metal", "scrap_metal"]
    consumable_names = ["scrap metal", "scrap metal", "scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_greatsword"]

    success_message = "You hammer the scrap metal into a rough but serviceable greatsword."



class ScrapPlatelegsRecipe(BlackoutRecipe):
    "Hammer scrap metal into a crude platelegs at an anvil."

    name = "scrap platelegs"
    category = CRAFT_CATEGORY_METALSMITH
    required_skill = skill_constants.SKILL_KEY_METALSMITH
    required_level = 23
    xp_reward = 105
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal", "scrap_metal", "scrap_metal"]
    consumable_names = ["scrap metal", "scrap metal", "scrap metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["hammer", "anvil"]

    output_item_keys = ["scrap_platelegs"]

    success_message = "You hammer the scrap metal into a rough but serviceable platelegs."