"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/14/2026
Description: Skill category Production - Gunsmith recipe definitions.
"""



from systems.gameplay.progression.skills import constants as skill_constants
from ..blackout_recipe import BlackoutRecipe
from ..constants import CRAFT_CATEGORY_GUNSMITH



# ---------------------------------
# --- RUSTY SCRAP METAL RECIPES ---
# ---------------------------------

class RustyScrapShortbowRecipe(BlackoutRecipe):
    "Bend rusty scrap metal around a scrap frame and string it at a Gunsmith Bench."

    name = "rusty scrap shortbow"
    category = CRAFT_CATEGORY_GUNSMITH
    required_skill = skill_constants.SKILL_KEY_GUNSMITH
    required_level = 0
    xp_reward = 25
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal", "mutant_raider_sinew"]
    consumable_names = ["rusty scrap metal", "mutant raider sinew"]

    tool_tags = ["gunbench"]
    tool_names = ["gunsmith bench"]

    output_item_keys = ["rusty_scrap_shortbow"]

    success_message = "You bend the rusty scrap metal to a curve and string it with sinew."



class RustyScrapArrowRecipe(BlackoutRecipe):
    """Cut and head ten arrows from one piece of rusty scrap metal.

    TEN OUTPUTS FROM ONE INPUT, and the first recipe in the game to make more
    than one item. output_item_keys is a LIST of keys and the crafting
    service builds one object per entry, so ten identical keys make ten
    objects -- and the arrow is stackable, so a character's at_object_receive
    merges them into one stack of ten as they arrive.

    No sinew. The bow takes the string, so the bow and the arrow compete for
    metal alone and a player chooses which to spend it on.
    """

    name = "rusty scrap arrow"
    category = CRAFT_CATEGORY_GUNSMITH
    required_skill = skill_constants.SKILL_KEY_GUNSMITH
    required_level = 0
    xp_reward = 15
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["rusty_scrap_metal"]
    consumable_names = ["rusty scrap metal"]

    tool_tags = ["gunbench"]
    tool_names = ["gunsmith bench"]

    output_item_keys = ["rusty_scrap_arrow"] * 10

    success_message = "You cut and head a bundle of ten rusty scrap arrows."



# class RustyScrapAxeRecipe(BlackoutRecipe):
#     "Hammer rusty scrap metal into a crude axe at an anvil."

#     name = "rusty scrap axe"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 0
#     xp_reward = 25
#     skill_category = "production"

#     consumable_tags = ["rusty_scrap_metal"]
#     consumable_names = ["rusty scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["rusty_scrap_axe"]

#     success_message = "You hammer the rusty scrap metal into a rough but serviceable axe."



# class RustyScrapBootsRecipe(BlackoutRecipe):
#     "Hammer rusty scrap metal into a crude boots at an anvil."

#     name = "rusty scrap boots"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 3
#     xp_reward = 25
#     skill_category = "production"

#     consumable_tags = ["rusty_scrap_metal"]
#     consumable_names = ["rusty scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["rusty_scrap_boots"]

#     success_message = "You hammer the rusty scrap metal into a rough but serviceable boots."



# class RustyScrapShortswordRecipe(BlackoutRecipe):
#     "Hammer two rusty scrap metal sheets into a crude shortsword at an anvil."

#     name = "rusty scrap shortsword"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 4
#     xp_reward = 50
#     skill_category = "production"

#     consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
#     consumable_names = ["rusty scrap metal", "rusty scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["rusty_scrap_shortsword"]

#     success_message = "You hammer the rusty scrap metal into a rough but serviceable shortsword."



# class RustyScrapScimitarRecipe(BlackoutRecipe):
#     "Hammer two rusty scrap metal sheets into a crude scimitar at an anvil."

#     name = "rusty scrap scimitar"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 5
#     xp_reward = 50
#     skill_category = "production"

#     consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
#     consumable_names = ["rusty scrap metal", "rusty scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["rusty_scrap_scimitar"]

#     success_message = "You hammer the rusty scrap metal into a rough but serviceable scimitar."



# class RustyScrapSpearRecipe(BlackoutRecipe):
#     "Hammer rusty scrap metal into a crude spear at an anvil."

#     name = "rusty scrap spear"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 5
#     xp_reward = 50
#     skill_category = "production"

#     consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
#     consumable_names = ["rusty scrap metal", "rusty scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["rusty_scrap_spear"]

#     success_message = "You hammer the rusty scrap metal into a rough but serviceable spear."



# class RustyScrapGreatHelmRecipe(BlackoutRecipe):
#     "Hammer rusty scrap metal into a crude great helm at an anvil."

#     name = "rusty scrap great helm"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 7
#     xp_reward = 50
#     skill_category = "production"

#     consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
#     consumable_names = ["rusty scrap metal", "rusty scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["rusty_scrap_great_helm"]

#     success_message = "You hammer the rusty scrap metal into a rough but serviceable great helm."



# class RustyScrapSquareShieldRecipe(BlackoutRecipe):
#     "Hammer rusty scrap metal into a crude square shield at an anvil."

#     name = "rusty scrap square shield"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 8
#     xp_reward = 50
#     skill_category = "production"

#     consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal"]
#     consumable_names = ["rusty scrap metal", "rusty scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["rusty_scrap_square_shield"]

#     success_message = "You hammer the rusty scrap metal into a rough but serviceable square shield."



# class RustyScrapBattleaxeRecipe(BlackoutRecipe):
#     "Hammer rusty scrap metal into a crude battleaxe at an anvil."

#     name = "rusty scrap battleaxe"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 10
#     xp_reward = 75
#     skill_category = "production"

#     consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal", "rusty_scrap_metal"]
#     consumable_names = ["rusty scrap metal", "rusty scrap metal", "rusty scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["rusty_scrap_battleaxe"]

#     success_message = "You hammer the rusty scrap metal into a rough but serviceable battleaxe."



# class RustyScrapChainbodyRecipe(BlackoutRecipe):
#     "Hammer rusty scrap metal into a crude chainbody at an anvil."

#     name = "rusty scrap chainbody"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 11
#     xp_reward = 75
#     skill_category = "production"

#     consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal", "rusty_scrap_metal"]
#     consumable_names = ["rusty scrap metal", "rusty scrap metal", "rusty scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["rusty_scrap_chainbody"]

#     success_message = "You hammer the rusty scrap metal into a rough but serviceable chainbody."



# class RustyScrapGreatswordRecipe(BlackoutRecipe):
#     "Hammer rusty scrap metal into a crude greatsword at an anvil."

#     name = "rusty scrap greatsword"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 12
#     xp_reward = 75
#     skill_category = "production"

#     consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal", "rusty_scrap_metal"]
#     consumable_names = ["rusty scrap metal", "rusty scrap metal", "rusty scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["rusty_scrap_greatsword"]

#     success_message = "You hammer the rusty scrap metal into a rough but serviceable greatsword."



# class RustyScrapPlatelegsRecipe(BlackoutRecipe):
#     "Hammer rusty scrap metal into a crude platelegs at an anvil."

#     name = "rusty scrap platelegs"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 13
#     xp_reward = 75
#     skill_category = "production"

#     consumable_tags = ["rusty_scrap_metal", "rusty_scrap_metal", "rusty_scrap_metal"]
#     consumable_names = ["rusty scrap metal", "rusty scrap metal", "rusty scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["rusty_scrap_platelegs"]

#     success_message = "You hammer the rusty scrap metal into a rough but serviceable platelegs."



# ---------------------------
# --- SCRAP METAL RECIPES ---
# ---------------------------

class ScrapShortbowRecipe(BlackoutRecipe):
    """Build the tier 2 bow at a Gunsmith Bench.

    TAKES PRIME SINEW BESIDE THE METAL. The tier 1 recipe already takes
    ordinary sinew, so a tier 2 recipe on metal alone would have been the
    NARROWER of the two -- which runs against the fan-out the skill framework
    asks for: a later recipe should draw on more of the tree, not less.
    """

    name = "scrap shortbow"
    category = CRAFT_CATEGORY_GUNSMITH
    required_skill = skill_constants.SKILL_KEY_GUNSMITH
    required_level = 10
    xp_reward = 35
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal", "mutant_raider_prime_sinew"]
    consumable_names = ["scrap metal", "mutant raider prime sinew"]

    tool_tags = ["gunbench"]
    tool_names = ["gunsmith bench"]

    output_item_keys = ["scrap_shortbow"]

    success_message = "You bend the scrap metal to a curve and string it with prime sinew."



class ScrapArrowRecipe(BlackoutRecipe):
    """Cut and head ten arrows from one piece of scrap metal.
    """

    name = "scrap arrow"
    category = CRAFT_CATEGORY_GUNSMITH
    required_skill = skill_constants.SKILL_KEY_GUNSMITH
    required_level = 10
    xp_reward = 15
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_metal"]
    consumable_names = ["scrap metal"]

    tool_tags = ["gunbench"]
    tool_names = ["gunsmith bench"]

    output_item_keys = ["scrap_arrow"] * 10

    success_message = "You cut and head a bundle of ten scrap arrows."



class CopperShortbowRecipe(BlackoutRecipe):
    """Build the tier 3 bow at a Gunsmith Bench.

    TAKES GIANT SINEW, WHICH IS WHY THE MUTANT GIANT EXISTS AT THIS LEVEL.
    The copper_shortbow ItemDef has been in world/item_defs/weapons.py since
    the copper tier shipped, with no recipe to make one -- the bow ladder
    stopped at scrap because the string ladder did.

    The string tier follows the metal tier one for one: rusty scrap and raider
    sinew at 0, scrap and raider prime sinew at 10, copper and giant sinew at
    20. A player who reaches Cutting 20 for the copper pole reaches Butchery
    20 for the giant corpse at about the same time.
    """

    name = "copper shortbow"
    category = CRAFT_CATEGORY_GUNSMITH
    required_skill = skill_constants.SKILL_KEY_GUNSMITH
    required_level = 20
    xp_reward = 50
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    consumable_tags = ["scrap_copper", "mutant_giant_sinew"]
    consumable_names = ["scrap copper", "mutant giant sinew"]

    tool_tags = ["gunbench"]
    tool_names = ["gunsmith bench"]

    output_item_keys = ["copper_shortbow"]

    success_message = "You bend the copper to a curve and string it with giant sinew."



# class ScrapAxeRecipe(BlackoutRecipe):
#     "Hammer scrap metal into a crude axe at an anvil."

#     name = "scrap axe"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 10
#     xp_reward = 35
#     skill_category = "production"

#     consumable_tags = ["scrap_metal"]
#     consumable_names = ["scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["scrap_axe"]

#     success_message = "You hammer the scrap metal into a rough but serviceable axe."



# class ScrapBootsRecipe(BlackoutRecipe):
#     "Hammer scrap metal into a crude boots at an anvil."

#     name = "scrap boots"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 13
#     xp_reward = 35
#     skill_category = "production"

#     consumable_tags = ["scrap_metal"]
#     consumable_names = ["scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["scrap_boots"]

#     success_message = "You hammer the scrap metal into a rough but serviceable boots."



# class ScrapShortswordRecipe(BlackoutRecipe):
#     "Hammer two scrap metal sheets into a crude shortsword at an anvil."

#     name = "scrap shortsword"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 14
#     xp_reward = 70
#     skill_category = "production"

#     consumable_tags = ["scrap_metal", "scrap_metal"]
#     consumable_names = ["scrap metal", "scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["scrap_shortsword"]

#     success_message = "You hammer the scrap metal into a rough but serviceable shortsword."



# class ScrapScimitarRecipe(BlackoutRecipe):
#     "Hammer two scrap metal sheets into a crude scimitar at an anvil."

#     name = "scrap scimitar"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 15
#     xp_reward = 70
#     skill_category = "production"

#     consumable_tags = ["scrap_metal", "scrap_metal"]
#     consumable_names = ["scrap metal", "scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["scrap_scimitar"]

#     success_message = "You hammer the scrap metal into a rough but serviceable scimitar."



# class ScrapSpearRecipe(BlackoutRecipe):
#     "Hammer scrap metal into a crude spear at an anvil."

#     name = "scrap spear"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 15
#     xp_reward = 70
#     skill_category = "production"

#     consumable_tags = ["scrap_metal", "scrap_metal"]
#     consumable_names = ["scrap metal", "scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["scrap_spear"]

#     success_message = "You hammer the scrap metal into a rough but serviceable spear."



# class ScrapGreatHelmRecipe(BlackoutRecipe):
#     "Hammer scrap metal into a crude great helm at an anvil."

#     name = "scrap great helm"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 17
#     xp_reward = 70
#     skill_category = "production"

#     consumable_tags = ["scrap_metal", "scrap_metal"]
#     consumable_names = ["scrap metal", "scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["scrap_great_helm"]

#     success_message = "You hammer the scrap metal into a rough but serviceable great helm."



# class ScrapSquareShieldRecipe(BlackoutRecipe):
#     "Hammer scrap metal into a crude square shield at an anvil."

#     name = "scrap square shield"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 18
#     xp_reward = 70
#     skill_category = "production"

#     consumable_tags = ["scrap_metal", "scrap_metal"]
#     consumable_names = ["scrap metal", "scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["scrap_square_shield"]

#     success_message = "You hammer the scrap metal into a rough but serviceable square shield."



# class ScrapBattleaxeRecipe(BlackoutRecipe):
#     "Hammer scrap metal into a crude battleaxe at an anvil."

#     name = "scrap battleaxe"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 20
#     xp_reward = 105
#     skill_category = "production"

#     consumable_tags = ["scrap_metal", "scrap_metal", "scrap_metal"]
#     consumable_names = ["scrap metal", "scrap metal", "scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["scrap_battleaxe"]

#     success_message = "You hammer the scrap metal into a rough but serviceable battleaxe."



# class ScrapChainbodyRecipe(BlackoutRecipe):
#     "Hammer scrap metal into a crude chainbody at an anvil."

#     name = "scrap chainbody"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 21
#     xp_reward = 105
#     skill_category = "production"

#     consumable_tags = ["scrap_metal", "scrap_metal", "scrap_metal"]
#     consumable_names = ["scrap metal", "scrap metal", "scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["scrap_chainbody"]

#     success_message = "You hammer the scrap metal into a rough but serviceable chainbody."



# class ScrapGreatswordRecipe(BlackoutRecipe):
#     "Hammer scrap metal into a crude greatsword at an anvil."

#     name = "scrap greatsword"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 22
#     xp_reward = 105
#     skill_category = "production"

#     consumable_tags = ["scrap_metal", "scrap_metal", "scrap_metal"]
#     consumable_names = ["scrap metal", "scrap metal", "scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["scrap_greatsword"]

#     success_message = "You hammer the scrap metal into a rough but serviceable greatsword."



# class ScrapPlatelegsRecipe(BlackoutRecipe):
#     "Hammer scrap metal into a crude platelegs at an anvil."

#     name = "scrap platelegs"
#     category = CRAFT_CATEGORY_METALSMITH
#     required_skill = "metalsmith"
#     required_level = 23
#     xp_reward = 105
#     skill_category = "production"

#     consumable_tags = ["scrap_metal", "scrap_metal", "scrap_metal"]
#     consumable_names = ["scrap metal", "scrap metal", "scrap metal"]

#     tool_tags = ["hammer", "anvil"]
#     tool_names = ["hammer", "anvil"]

#     output_item_keys = ["scrap_platelegs"]

#     success_message = "You hammer the scrap metal into a rough but serviceable platelegs."