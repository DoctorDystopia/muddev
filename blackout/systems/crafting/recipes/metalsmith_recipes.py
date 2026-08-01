from ..blackout_recipe import BlackoutRecipe
from ..constants import CATEGORY_METALSMITHING


class RustyMetalDustRecipe(BlackoutRecipe):
    "Grind a rusty metal chunk into fine dust using a hammer."

    name = "rusty metal dust"
    category = CATEGORY_METALSMITHING
    required_skill = "metalsmith"
    required_level = 0
    xp_reward = 10
    skill_category = "production"

    consumable_tags = ["rusty_metal_chunk"]
    consumable_names = ["Rusty Metal Chunk"]

    tool_tags = ["hammer"]
    tool_names = ["Hammer"]

    output_item_keys = ["rusty_metal_dust"]

    success_message = "You grind the rusty metal chunk into a fine dust."


class RustyScrapAxeRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude axe at an anvil."

    name = "rusty scrap axe"
    category = CATEGORY_METALSMITHING
    required_skill = "metalsmith"
    required_level = 0
    xp_reward = 30
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal"]
    consumable_names = ["Rusty Scrap Metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["Hammer", "Anvil"]

    output_item_keys = ["rusty_scrap_axe"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable axe."


class RustyScrapShortswordRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude shortsword at an anvil."

    name = "rusty scrap shortsword"
    category = CATEGORY_METALSMITHING
    required_skill = "metalsmith"
    required_level = 2
    xp_reward = 50
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal"]
    consumable_names = ["Rusty Scrap Metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["Hammer", "Anvil"]

    output_item_keys = ["rusty_scrap_shortsword"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable shortsword."


class RustyScrapSpearRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude spear at an anvil."

    name = "rusty scrap spear"
    category = CATEGORY_METALSMITHING
    required_skill = "metalsmith"
    required_level = 3
    xp_reward = 60
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal"]
    consumable_names = ["Rusty Scrap Metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["Hammer", "Anvil"]

    output_item_keys = ["rusty_scrap_spear"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable spear."
