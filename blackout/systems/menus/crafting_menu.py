"""
Crafting menu for Blackout.

This menu provides a guided crafting interface through EvMenu. All
crafting logic (recipe discovery, prerequisite checking, execution)
is handled by systems.crafting.crafting_service - this module only
manages display formatting and navigation flow.
"""



import systems.crafting.crafting_service as crafting_service



TITLE_COLOR = "|w"
HIGHLIGHT_COLOR = "|y"
SUCCESS_COLOR = "|g"
ERROR_COLOR = "|r"
RESET_COLOR = "|n"
RECIPE_SEPARATOR = "-" * 60



def start(caller, **kwargs):
    facility = kwargs.get("facility")
    categories = crafting_service.get_categories(facility=facility)
    text = (
        f"{TITLE_COLOR}--- Crafting Menu ---{RESET_COLOR}\n"
        "Select a category to browse recipes."
    )
    options = []

    for category_name in sorted(categories.keys()):
        recipe_count = len(categories[category_name])
        options.append(
            {
                "desc": f"{category_name} ({recipe_count} recipes)",
                "goto": ("node_category", {"category": category_name}),
            }
        )
    options.append({"desc": "Exit crafting menu", "goto": "node_exit"})

    return text, options


def node_category(caller, **kwargs):
    category_name = kwargs.get("category", "Unknown")
    recipes = crafting_service.get_recipes_in_category(category_name)
    text = f"{TITLE_COLOR}--- {category_name} Recipes ---{RESET_COLOR}"
    options = []

    for recipe_key, recipe_cls in recipes:
        mat_strings = []

        for mat_tag in recipe_cls.consumable_tags:
            mat_strings.append(
                recipe_cls.consumable_names[
                    recipe_cls.consumable_tags.index(mat_tag)
                ]

                if recipe_cls.consumable_names
                else mat_tag
            )
        materials = ", ".join(mat_strings)
        options.append(
            {
                "desc": f"{recipe_cls.name} [{materials}]"
                f" (Req: {recipe_cls.required_skill} Lv.{recipe_cls.required_level})",
                "goto": ("node_recipe_detail", {"recipe_key": recipe_key}),
            }
        )
    options.append({"desc": "Back to categories", "goto": "start"})

    return text, options


def node_recipe_detail(caller, **kwargs):
    recipe_key = kwargs.get("recipe_key", "")
    display = crafting_service.get_recipe_display_data(caller, recipe_key)

    if not display:
        text = f"{ERROR_COLOR}Recipe not found.{RESET_COLOR}"
        return text, ({"desc": "Back to categories", "goto": "start"},)

    material_lines = []

    for md in display["material_details"]:
        material_lines.append(f"  {md['name']} ({md['owned']} owned)")

    materials_str = "\n".join(material_lines)

    if display["required_skill"]:
        if display["meets_skill"]:
            skill_status = f"{SUCCESS_COLOR}Met{RESET_COLOR}"
        else:
            skill_status = (
                f"{ERROR_COLOR}Requires {display['required_skill']}"
                f" Lv.{display['required_level']}{RESET_COLOR}"
            )
    else:
        skill_status = "None"

    if display["can_craft"]:
        material_status = f"{SUCCESS_COLOR}All requirements met{RESET_COLOR}"
    else:
        missing_parts = []

        for md in display["material_details"]:
            if not md["met"]:
                missing_parts.append(
                    f"{md['name']} ({md['owned']}/{md['required']})"
                )

        for td in display["tool_details"]:
            if not td["available"]:
                missing_parts.append(f"Tool: {td['name']}")

        material_status = (
            f"{ERROR_COLOR}Missing: {', '.join(missing_parts)}{RESET_COLOR}"
        )

    output_str = ", ".join(display["output_names"])

    text = (
        f"{TITLE_COLOR}{display['name']}{RESET_COLOR}\n"
        f"{RECIPE_SEPARATOR}\n"
        f"{display['description']}\n\n"
        f"{HIGHLIGHT_COLOR}Category:{RESET_COLOR} {display['category']}\n"
        f"{HIGHLIGHT_COLOR}Skill Requirement:{RESET_COLOR} {skill_status}\n"
        f"{HIGHLIGHT_COLOR}Output:{RESET_COLOR} {output_str}\n"
        f"{HIGHLIGHT_COLOR}XP Reward:{RESET_COLOR} {display['xp_reward']}\n\n"
        f"{HIGHLIGHT_COLOR}Materials:{RESET_COLOR}\n{materials_str}\n"
        f"{HIGHLIGHT_COLOR}Status:{RESET_COLOR} {material_status}"
    )

    if display["can_craft"]:
        recipe_cls = crafting_service.get_recipe_class(recipe_key)
        require_confirm = getattr(recipe_cls, "require_confirm", True)
        caller_confirm = caller.db.craft_confirm
        if caller_confirm is None:
            caller_confirm = True
        needs_confirm = require_confirm and caller_confirm
        target = "node_confirm_craft" if needs_confirm else execute_craft

        options = (
            {
                "desc": f"Craft {display['name']}",
                "goto": (
                    target,
                    {"recipe_key": recipe_key},
                ),
            },
            {
                "desc": "Back to category",
                "goto": (
                    "node_category",
                    {"category": display["category"]},
                ),
            },
            {"desc": "Back to categories", "goto": "start"},
        )
    else:
        options = (
            {
                "desc": "Back to category",
                "goto": (
                    "node_category",
                    {"category": display["category"]},
                ),
            },
            {"desc": "Back to categories", "goto": "start"},
        )

    return text, options


def node_confirm_craft(caller, **kwargs):
    recipe_key = kwargs.get("recipe_key", "")
    recipe_cls = crafting_service.get_recipe_class(recipe_key)

    if not recipe_cls:
        text = f"{ERROR_COLOR}Recipe not found.{RESET_COLOR}"

        return text, ({"desc": "Back to categories", "goto": "start"},)

    can_craft, reasons = crafting_service.check_craftable(caller, recipe_key)

    if not can_craft:
        text = f"{ERROR_COLOR}Cannot craft: {'; '.join(reasons)}.{RESET_COLOR}"

        return text, (
            {
                "desc": "Back to recipe details",
                "goto": (
                    "node_recipe_detail",
                    {"recipe_key": recipe_key},
                ),
            },
        )

    output_names = (
        recipe_cls.output_names
        if recipe_cls.output_names
        else [prot.get("key", "item") for prot in recipe_cls.output_prototypes]
    )
    output_str = ", ".join(output_names)

    text = (
        f"{TITLE_COLOR}Confirm Craft:{RESET_COLOR} {recipe_cls.name}\n\n"
        f"This will consume the required materials and produce {output_str}.\n\n"
        f"{HIGHLIGHT_COLOR}Proceed?{RESET_COLOR}"
    )
    options = (
        {
            "desc": f"Yes, craft {recipe_cls.name}",
            "goto": (execute_craft, {"recipe_key": recipe_key}),
        },
        {
            "desc": "No, go back",
            "goto": (
                "node_recipe_detail",
                {"recipe_key": recipe_key},
            ),
        },
    )

    return text, options


def execute_craft(caller, raw_string, **kwargs):
    recipe_key = kwargs.get("recipe_key", "")
    result = crafting_service.perform_craft(caller, recipe_key)

    if result:
        return "node_craft_result", {"recipe_key": recipe_key}
    
    caller.msg(f"{ERROR_COLOR}Crafting failed.{RESET_COLOR}")

    return "start"


def node_craft_result(caller, **kwargs):
    recipe_key = kwargs.get("recipe_key", "")
    recipe_cls = crafting_service.get_recipe_class(recipe_key)

    if recipe_cls:
        output_names = (
            recipe_cls.output_names

            if recipe_cls.output_names
            else [prot.get("key", "item") for prot in recipe_cls.output_prototypes]
        )
        output_str = ", ".join(
            f"{HIGHLIGHT_COLOR}{name}{RESET_COLOR}" for name in output_names
        )
        text = (
            f"{SUCCESS_COLOR}Crafting successful!{RESET_COLOR}\n\n"
            f"You crafted: {output_str}\n"
            f"Gained: {HIGHLIGHT_COLOR}{recipe_cls.xp_reward} XP{RESET_COLOR} "
            f"in {recipe_cls.required_skill}."
        )
    else:
        text = f"{SUCCESS_COLOR}Crafting complete!{RESET_COLOR}"

    options = (
        {"desc": "Craft another item", "goto": "start"},
        {"desc": "Exit crafting menu", "goto": "node_exit"},
    )

    return text, options


def node_exit(caller, **kwargs):
    text = "Closing crafting menu."
    
    return text, None
