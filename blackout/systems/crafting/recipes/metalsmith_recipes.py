from ..blackout_recipe import BlackoutRecipe


class RustyMetalDustRecipe(BlackoutRecipe):
    "Grind a rusty metal chunk into fine dust using a hammer."

    name = "rusty metal dust"
    category = "Metalsmithing"
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
    category = "Metalsmithing"
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


class RustyScrapSwordRecipe(BlackoutRecipe):
    "Hammer rusty scrap metal into a crude sword at an anvil."

    name = "rusty scrap sword"
    category = "Metalsmithing"
    required_skill = "metalsmith"
    required_level = 2
    xp_reward = 50
    skill_category = "production"

    consumable_tags = ["rusty_scrap_metal"]
    consumable_names = ["Rusty Scrap Metal"]

    tool_tags = ["hammer", "anvil"]
    tool_names = ["Hammer", "Anvil"]

    output_item_keys = ["rusty_scrap_sword"]

    success_message = "You hammer the rusty scrap metal into a rough but serviceable sword."
