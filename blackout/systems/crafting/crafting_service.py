"""
Crafting service layer for Blackout.

Provides a clean API for recipe discovery, prerequisite checking, and
crafting execution. This is the sole point of contact for all game code
(menus, commands, NPC dialogues, tests) with the underlying Evennia
crafting contrib.

Usage:
    from systems.crafting.crafting_service import (
        get_categories,
        get_recipes_in_category,
        get_recipe_class,
        check_craftable,
        get_recipe_display_data,
        perform_craft,
    )
"""



from evennia.contrib.game_systems.crafting.crafting import (
    _load_recipes,
    _RECIPE_CLASSES,
    craft as contrib_craft,
)

_CONSUMABLE_TAG_CATEGORY = "crafting_material"
_TOOL_TAG_CATEGORY = "crafting_tool"



def _ensure_recipes_loaded():
    _load_recipes()


def _count_tagged_items(caller, tag_value, tag_category):
    count = 0

    for item in caller.contents:
        tags = item.tags.get(category=tag_category, return_list=True)
        if tag_value in tags:
            count += 1

    for item in caller.equipment.all():
        tags = item.tags.get(category=tag_category, return_list=True)
        if tag_value in tags:
            count += 1

    return count


def _has_tool_available(caller, tag_value):
    for item in caller.contents:
        tags = item.tags.get(category=_TOOL_TAG_CATEGORY, return_list=True)
        if tag_value in tags:
            return True
        
    for item in caller.equipment.all():
        tags = item.tags.get(category=_TOOL_TAG_CATEGORY, return_list=True)
        if tag_value in tags:
            return True
        
    if caller.location:
        for item in caller.location.contents:
            tags = item.tags.get(category=_TOOL_TAG_CATEGORY, return_list=True)
            if tag_value in tags:
                return True
            
    return False


def get_categories(facility=None):
    """Discover recipe categories, optionally filtered by facility.

    Args:
        facility: Optional CraftingFacility object with allowed_categories.

    Returns:
        dict mapping category name to list of recipe keys.
    """
    _ensure_recipes_loaded()
    categories = {}

    for recipe_key, recipe_cls in _RECIPE_CLASSES.items():
        cat = getattr(recipe_cls, "category", "Uncategorized")
        if facility is not None:
            allowed = getattr(facility, "allowed_categories", None)
            if allowed is not None and cat not in allowed:
                continue
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(recipe_key)

    return categories


def get_recipes_in_category(category):
    """Get all recipes belonging to a category.

    Returns:
        list of (recipe_key, recipe_cls) tuples.
    """
    _ensure_recipes_loaded()

    return [
        (key, cls)
        for key, cls in _RECIPE_CLASSES.items()
        if getattr(cls, "category", "Uncategorized") == category
    ]


def get_recipe_class(recipe_key):
    """Get the recipe class for a given recipe key, or None if not found."""
    _ensure_recipes_loaded()

    return _RECIPE_CLASSES.get(recipe_key)


def check_craftable(caller, recipe_key):
    """Determine if caller can craft the given recipe.

    Returns:
        Tuple of (can_craft: bool, reasons: list[str]). When can_craft is
        False, reasons contains human-readable descriptions of what's
        missing (skill, materials, or tools).
    """
    recipe_cls = get_recipe_class(recipe_key)

    if not recipe_cls:
        return False, ["Recipe not found."]

    reasons = []
    meets_skill = True
    if recipe_cls.required_skill:
        meets_skill = caller.skills.meets_prerequisite(
            recipe_cls.required_skill, recipe_cls.required_level
        )
        if not meets_skill:
            reasons.append(
                f"Requires {recipe_cls.required_skill} Lv.{recipe_cls.required_level}"
            )

    for mat_tag in recipe_cls.consumable_tags:
        owned = _count_tagged_items(caller, mat_tag, _CONSUMABLE_TAG_CATEGORY)
        required = recipe_cls.consumable_tags.count(mat_tag)
        if owned < required:
            mat_name = (
                recipe_cls.consumable_names[recipe_cls.consumable_tags.index(mat_tag)]
                if recipe_cls.consumable_names
                else mat_tag
            )
            reasons.append(f"Missing {mat_name} ({owned}/{required})")

    for tool_tag in recipe_cls.tool_tags:
        if not _has_tool_available(caller, tool_tag):
            tool_name = (
                recipe_cls.tool_names[recipe_cls.tool_tags.index(tool_tag)]
                if recipe_cls.tool_names
                else tool_tag
            )
            reasons.append(f"Missing tool: {tool_name}")

    can_craft = meets_skill and not reasons

    return can_craft, reasons


def get_recipe_display_data(caller, recipe_key):
    """Get all data needed to render a recipe detail view.

    Returns:
        dict with keys: name, description, category, required_skill,
        required_level, xp_reward, output_names, can_craft,
        meets_skill, material_details, tool_details.
        Returns None if recipe_key is not found.
    """
    recipe_cls = get_recipe_class(recipe_key)

    if not recipe_cls:
        return None

    material_details = []
    for mat_tag in recipe_cls.consumable_tags:
        mat_name = (
            recipe_cls.consumable_names[recipe_cls.consumable_tags.index(mat_tag)]
            if recipe_cls.consumable_names
            else mat_tag
        )
        owned = _count_tagged_items(caller, mat_tag, _CONSUMABLE_TAG_CATEGORY)
        required = recipe_cls.consumable_tags.count(mat_tag)
        material_details.append(
            {
                "name": mat_name,
                "tag": mat_tag,
                "owned": owned,
                "required": required,
                "met": owned >= required,
            }
        )

    tool_details = []
    for tool_tag in recipe_cls.tool_tags:
        tool_name = (
            recipe_cls.tool_names[recipe_cls.tool_tags.index(tool_tag)]
            if recipe_cls.tool_names
            else tool_tag
        )
        available = _has_tool_available(caller, tool_tag)
        tool_details.append(
            {"name": tool_name, "tag": tool_tag, "available": available}
        )

    meets_skill = True
    if recipe_cls.required_skill:
        meets_skill = caller.skills.meets_prerequisite(
            recipe_cls.required_skill, recipe_cls.required_level
        )

    all_materials_met = all(m["met"] for m in material_details)
    all_tools_met = all(t["available"] for t in tool_details)
    can_craft = meets_skill and all_materials_met and all_tools_met

    output_names = (
        recipe_cls.output_names
        if recipe_cls.output_names
        else [prot.get("key", "item") for prot in recipe_cls.output_prototypes]
    )

    return {
        "name": recipe_cls.name,
        "description": getattr(recipe_cls, "description", recipe_cls.__doc__ or ""),
        "category": getattr(recipe_cls, "category", "Uncategorized"),
        "required_skill": recipe_cls.required_skill,
        "required_level": recipe_cls.required_level,
        "xp_reward": recipe_cls.xp_reward,
        "output_names": output_names,
        "can_craft": can_craft,
        "meets_skill": meets_skill,
        "material_details": material_details,
        "tool_details": tool_details,
    }


def perform_craft(caller, recipe_key):
    """Gather all applicable materials and tools and execute the craft.

    This is the execution boundary between game code and the Evennia
    contrib. The contrib's recipe handles all validation, consumption,
    spawning, and messaging internally.

    Args:
        caller: The character performing the craft.
        recipe_key: Name of the recipe to execute.

    Returns:
        List of spawned objects on success, or None on failure.
    """
    recipe_cls = get_recipe_class(recipe_key)

    if not recipe_cls:
        return None

    consumables = [
        obj
        for obj in caller.contents
        if obj.tags.get(category=_CONSUMABLE_TAG_CATEGORY, return_list=True)
    ]

    tools = []
    for obj in caller.contents:
        if obj.tags.get(category=_TOOL_TAG_CATEGORY, return_list=True):
            tools.append(obj)

    for obj in caller.equipment.all():
        if obj.tags.get(category=_TOOL_TAG_CATEGORY, return_list=True):
            tools.append(obj)
            
    if caller.location:
        for obj in caller.location.contents:
            if obj.tags.get(category=_TOOL_TAG_CATEGORY, return_list=True):
                tools.append(obj)

    result = contrib_craft(
        caller, recipe_key, *(tools + consumables), raise_exception=False
    )

    if result:
        for obj in result:
            obj.location = caller

    return result
