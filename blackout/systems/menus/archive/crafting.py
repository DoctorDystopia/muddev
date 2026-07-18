
# DEPRECATED: This legacy crafting system has been replaced by
# systems/menus/crafting_menu.py (Evennia contrib-based).
#
# The recipe concepts below should be re-implemented as Metalsmith
# recipes in systems/crafting/recipes/metalsmith_recipes.py using BlackoutRecipe.
#
#   - Makeshift Pickaxe (was cutting Lv.2, 3x Rusty Metal Chunk)
#   - Scrap Armor      (was cutting Lv.3, 5x Rusty Metal Chunk)

from dataclasses import dataclass, field

from evennia import create_object


# Public constant definitions
TITLE_COLOR = "|w"
HIGHLIGHT_COLOR = "|y"
SUCCESS_COLOR = "|g"
ERROR_COLOR = "|r"
RESET_COLOR = "|n"
RECIPE_SEPARATOR_NUM = 60
RECIPE_SEPARATOR = "-" * RECIPE_SEPARATOR_NUM

_DEFAULT_MATERIALS_FACTORY = dict



@dataclass
class RecipeBlueprint:
    """
    Purpose: Defines a single craftable recipe with its requirements and results.

    Entry:
        All fields are required at construction time.

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        Standard data container for recipe definitions.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key: str
    name: str
    category: str
    description: str
    required_skill: str
    required_level: int
    materials: dict = field(default_factory=_DEFAULT_MATERIALS_FACTORY)
    result_key: str = ""
    result_quantity: int = 1
    xp_reward: int = 0
    result_typeclass: str = "typeclasses.objects.Object"



# Legacy recipes (commented out — to be re-implemented as Metalsmith recipes)
# RECIPE_REGISTRY = {
#     "make_shift_pickaxe": RecipeBlueprint(
#         key="make_shift_pickaxe",
#         name="Makeshift Pickaxe",
#         category="Tools",
#         description="A crude pickaxe for breaking rocks and mineral deposits.",
#         required_skill="metalsmith",
#         required_level=0,
#         materials={"Rusty Metal Chunk": 3},
#         result_key="makeshift pickaxe",
#         result_quantity=1,
#         xp_reward=25,
#         result_typeclass="typeclasses.items.ToolItem",
#     ),
#     "make_scrap_armor": RecipeBlueprint(
#         key="make_scrap_armor",
#         name="Scrap Armor",
#         category="Armor",
#         description="Body armor pieced together from salvaged metal plates.",
#         required_skill="metalsmith",
#         required_level=0,
#         materials={"Rusty Metal Chunk": 5},
#         result_key="scrap armor",
#         result_quantity=1,
#         xp_reward=40,
#         result_typeclass="typeclasses.items.EquippableItem",
#     ),
# }
RECIPE_REGISTRY = {}



def _check_materials(caller: object, recipe: RecipeBlueprint) -> list:
    """
    Purpose: Checks if the caller has the required materials for a recipe.

    Entry:
        caller is a valid Evennia Character object
        recipe is a valid RecipeBlueprint instance

    Exit/Returns:
        Returns a list of missing material descriptions (empty if all present).

    Module Globals:
        None

    Methodology:
        Iterates the recipe's material requirements. Counts matching
        items in the caller's contents. Appends missing materials to
        the result list.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    missing_list = []

    for material_key, required_count in recipe.materials.items():
        owned_count = sum(
            1 for item in caller.contents
            if item.key.lower() == material_key.lower()
        )

        if owned_count < required_count:
            needed = required_count - owned_count
            missing_string = f"{material_key} (need {needed} more)"
            missing_list.append(missing_string)

    return missing_list



def _consume_materials(caller: object, recipe: RecipeBlueprint) -> None:
    """
    Purpose: Removes required materials from the caller's inventory.

    Entry:
        caller is a valid Evennia Character object
        recipe is a valid RecipeBlueprint instance

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        Iterates material requirements. Destroys matching items
        from caller.contents until the required count is met.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    for material_key, required_count in recipe.materials.items():
        remaining = required_count

        for item in list(caller.contents):
            if remaining <= 0:
                break

            item_matches = item.key.lower() == material_key.lower()

            if item_matches:
                item.delete()
                remaining -= 1



def _grant_result(caller: object, recipe: RecipeBlueprint) -> None:
    """
    Purpose: Creates the crafted item and awards XP to the caller.

    Entry:
        caller is a valid Evennia Character object
        recipe is a valid RecipeBlueprint instance

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        Creates the result object(s) via create_object. Adds XP
        through the caller.skills handler.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    quantity = recipe.result_quantity

    for _ in range(quantity):
        create_object(
            recipe.result_typeclass,
            key=recipe.result_key,
            location=caller,
            home=caller,
        )

    if recipe.xp_reward > 0 and recipe.required_skill:
        caller.skills.add_xp(recipe.required_skill, recipe.xp_reward)



def start(caller: object, **kwargs) -> tuple:
    """
    Purpose: Entry node for the crafting menu.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        TITLE_COLOR read
        RESET_COLOR read
        RECIPE_REGISTRY read

    Methodology:
        Groups available recipes by category. Generates an option
        for each category. Selecting a category navigates to the
        category recipe list.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    categories_dict = {}

    for recipe_key, recipe in RECIPE_REGISTRY.items():
        category = recipe.category

        if category not in categories_dict:
            categories_dict[category] = []

        categories_dict[category].append(recipe_key)

    text = f"{TITLE_COLOR}--- Crafting Menu ---{RESET_COLOR}\nSelect a category to browse recipes."

    options_list = []

    for category_name in sorted(categories_dict.keys()):
        recipe_count = len(categories_dict[category_name])
        desc_string = f"{category_name} ({recipe_count} recipes)"

        option_dict = {
            "desc": desc_string,
            "goto": ("node_category", {"category": category_name}),
        }
        options_list.append(option_dict)

    options_list.append({"desc": "Exit crafting menu", "goto": "node_exit"})

    options_tuple = tuple(options_list)

    return text, options_tuple



def node_category(caller: object, **kwargs) -> tuple:
    """
    Purpose: Displays all recipes within a selected category.

    Entry:
        caller is a valid Evennia Character object
        kwargs["category"] is the category name string

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        TITLE_COLOR read
        HIGHLIGHT_COLOR read
        RESET_COLOR read
        RECIPE_REGISTRY read

    Methodology:
        Filters RECIPE_REGISTRY by category. Generates options
        for each recipe. Shows requirements summary per recipe.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    category_name = kwargs.get("category", "Unknown")

    text = f"{TITLE_COLOR}--- {category_name} Recipes ---{RESET_COLOR}"

    options_list = []

    for recipe_key, recipe in RECIPE_REGISTRY.items():
        recipe_in_category = recipe.category == category_name

        if recipe_in_category:
            material_strings = []

            for mat_key, mat_count in recipe.materials.items():
                material_strings.append(f"{mat_count}x {mat_key}")

            materials_string = ", ".join(material_strings)
            desc_string = (
                f"{recipe.name} [{materials_string}]"
                f" (Req: {recipe.required_skill} Lv.{recipe.required_level})"
            )

            option_dict = {
                "desc": desc_string,
                "goto": ("node_recipe_detail", {"recipe_key": recipe_key}),
            }
            options_list.append(option_dict)

    options_list.append({"desc": "Back to categories", "goto": "start"})

    options_tuple = tuple(options_list)

    return text, options_tuple



def node_recipe_detail(caller: object, **kwargs) -> tuple:
    """
    Purpose: Shows detailed information about a specific recipe.

    Entry:
        caller is a valid Evennia Character object
        kwargs["recipe_key"] is the recipe identifier string

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        TITLE_COLOR read
        HIGHLIGHT_COLOR read
        SUCCESS_COLOR read
        ERROR_COLOR read
        RESET_COLOR read
        RECIPE_REGISTRY read

    Methodology:
        Displays recipe details including description, materials,
        requirements, and output. Checks if the player meets
        skill prerequisites and material availability.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    recipe_key = kwargs.get("recipe_key", "")
    recipe = RECIPE_REGISTRY.get(recipe_key)

    if recipe is None:
        text = f"{ERROR_COLOR}Recipe not found.{RESET_COLOR}"
        options = ({"desc": "Back to categories", "goto": "start"},)

        return text, options

    material_lines = []
    for mat_key, mat_count in recipe.materials.items():
        owned_count = sum(
            1 for item in caller.contents
            if item.key.lower() == mat_key.lower()
        )
        owned_string = f"({owned_count} owned)"
        material_lines.append(f"  {mat_count}x {mat_key} {owned_string}")

    materials_string = "\n".join(material_lines)

    meets_skill = caller.skills.meets_prerequisite(
        recipe.required_skill, recipe.required_level
    )

    if meets_skill:
        skill_status = f"{SUCCESS_COLOR}Met{RESET_COLOR}"
    else:
        skill_status = f"{ERROR_COLOR}Requires {recipe.required_skill} Lv.{recipe.required_level}{RESET_COLOR}"

    missing_list = _check_materials(caller, recipe)

    if missing_list:
        material_status = f"{ERROR_COLOR}Missing: {', '.join(missing_list)}{RESET_COLOR}"
    else:
        material_status = f"{SUCCESS_COLOR}All materials available{RESET_COLOR}"

    can_craft = meets_skill and not missing_list

    text = (
        f"{TITLE_COLOR}{recipe.name}{RESET_COLOR}\n"
        f"{RECIPE_SEPARATOR}\n"
        f"{recipe.description}\n\n"
        f"{HIGHLIGHT_COLOR}Category:{RESET_COLOR} {recipe.category}\n"
        f"{HIGHLIGHT_COLOR}Skill Requirement:{RESET_COLOR} {skill_status}\n"
        f"{HIGHLIGHT_COLOR}Output:{RESET_COLOR} {recipe.result_key} x{recipe.result_quantity}\n"
        f"{HIGHLIGHT_COLOR}XP Reward:{RESET_COLOR} {recipe.xp_reward}\n\n"
        f"{HIGHLIGHT_COLOR}Materials:{RESET_COLOR}\n{materials_string}\n"
        f"{HIGHLIGHT_COLOR}Material Status:{RESET_COLOR} {material_status}"
    )

    if can_craft:
        options = (
            {"desc": f"Craft {recipe.name}", "goto": ("node_confirm_craft", {"recipe_key": recipe_key})},
            {"desc": "Back to category", "goto": ("node_category", {"category": recipe.category})},
            {"desc": "Back to categories", "goto": "start"},
        )
    else:
        options = (
            {"desc": "Back to category", "goto": ("node_category", {"category": recipe.category})},
            {"desc": "Back to categories", "goto": "start"},
        )

    return text, options



def node_confirm_craft(caller: object, **kwargs) -> tuple:
    """
    Purpose: Confirmation step before executing a craft.

    Entry:
        caller is a valid Evennia Character object
        kwargs["recipe_key"] is the recipe identifier string

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        TITLE_COLOR read
        HIGHLIGHT_COLOR read
        RESET_COLOR read
        RECIPE_REGISTRY read

    Methodology:
        Double-checks requirements. Shows a confirm prompt.
        If confirmed, executes the craft and reports results.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    recipe_key = kwargs.get("recipe_key", "")
    recipe = RECIPE_REGISTRY.get(recipe_key)

    if recipe is None:
        text = f"{ERROR_COLOR}Recipe not found.{RESET_COLOR}"
        options = ({"desc": "Back to categories", "goto": "start"},)

        return text, options

    missing_list = _check_materials(caller, recipe)

    if missing_list:
        text = (
            f"{ERROR_COLOR}Cannot craft: missing materials.{RESET_COLOR}\n"
            f"{HIGHLIGHT_COLOR}Missing:{RESET_COLOR} {', '.join(missing_list)}"
        )
        options = (
            {"desc": "Back to recipe details", "goto": ("node_recipe_detail", {"recipe_key": recipe_key})},
        )

        return text, options

    text = (
        f"{TITLE_COLOR}Confirm Craft:{RESET_COLOR} {recipe.name}\n\n"
        f"This will consume the required materials and produce "
        f"{recipe.result_key} x{recipe.result_quantity}.\n\n"
        f"{HIGHLIGHT_COLOR}Proceed?{RESET_COLOR}"
    )

    options = (
        {"desc": f"Yes, craft {recipe.name}", "goto": ("_execute_craft", {"recipe_key": recipe_key})},
        {"desc": "No, go back", "goto": ("node_recipe_detail", {"recipe_key": recipe_key})},
    )

    return text, options



def _execute_craft(caller: object,
                   raw_string: str,
                   **kwargs) -> str:
    """
    Purpose: Executes the crafting action: consumes materials,
             creates result, awards XP.

    Entry:
        caller is a valid Evennia Character object
        raw_string is the raw input string (unused)
        kwargs["recipe_key"] is the recipe identifier string

    Exit/Returns:
        Returns the string "node_craft_result" to show the result.

    Module Globals:
        RECIPE_REGISTRY read

    Methodology:
        Retrieves the recipe blueprint. Calls _consume_materials
        and _grant_result in sequence.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    recipe_key = kwargs.get("recipe_key", "")
    recipe = RECIPE_REGISTRY.get(recipe_key)

    if recipe is None:
        return_node = "start"

        return return_node

    _consume_materials(caller, recipe)
    _grant_result(caller, recipe)

    return_node = "node_craft_result"

    return return_node, {"recipe_key": recipe_key}



def node_craft_result(caller: object, **kwargs) -> tuple:
    """
    Purpose: Shows the result of a successful craft.

    Entry:
        caller is a valid Evennia Character object
        kwargs["recipe_key"] is the recipe identifier string

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        SUCCESS_COLOR read
        HIGHLIGHT_COLOR read
        RESET_COLOR read
        RECIPE_REGISTRY read

    Methodology:
        Displays success message with the crafted item name
        and XP awarded.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    recipe_key = kwargs.get("recipe_key", "")
    recipe = RECIPE_REGISTRY.get(recipe_key)

    if recipe is None:
        text = f"{SUCCESS_COLOR}Crafting complete!{RESET_COLOR}"
    else:
        text = (
            f"{SUCCESS_COLOR}Crafting successful!{RESET_COLOR}\n\n"
            f"You crafted: {HIGHLIGHT_COLOR}{recipe.result_key}{RESET_COLOR} "
            f"x{recipe.result_quantity}\n"
            f"Gained: {HIGHLIGHT_COLOR}{recipe.xp_reward} XP{RESET_COLOR} "
            f"in {recipe.required_skill}."
        )

    options = (
        {"desc": "Craft another item", "goto": "start"},
        {"desc": "Exit crafting menu", "goto": "node_exit"},
    )

    return text, options



def node_exit(caller: object, **kwargs) -> tuple:
    """
    Purpose: Exit node that closes the crafting menu.

    Entry:
        caller is a valid Evennia Character object

    Exit/Returns:
        Returns a tuple of (text, None) to signal menu exit.

    Module Globals:
        None

    Methodology:
        Returns no options, causing EvMenu to close automatically.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    text = "Closing crafting menu."

    return text, None
