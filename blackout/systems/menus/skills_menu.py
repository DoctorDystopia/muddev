"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: EvMenu nodes for the skills panel: category list, per-skill
             detail, and XP meters.
"""

from items.equipment.skill_requirements import get_equippables_for_skill
from systems.combat.auras.registry import get_auras_for_skill
from systems.crafting.crafting_service import (
    get_material_summary,
    get_recipes_for_skill,
)
from systems.progression.skills.gatherables import (
    get_gatherable_item_name,
    get_gatherables_for_skill,
)
from systems.progression.skills.registry import SKILL_REGISTRY
from systems.ui.colors import (
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SKILL_COLOR,
    SUCCESS_COLOR,
    TITLE_COLOR,
)
from systems.ui.meters import build_xp_meter



def _get_categories(caller: object) -> dict:
    """
    Purpose: Organizes the caller's skills by category for menu display.

    Entry:
        caller is a valid Evennia Character object with db.skills

    Exit/Returns:
        Returns a dict mapping category_name -> list of (skill_key, skill_data, skill_class).

    Module Globals:
        SKILL_REGISTRY read

    Methodology:
        Iterates the master registry and groups installed skills
        by their category attribute.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    caller_skills = caller.db.skills
    categories_dict = {}

    for skill_key, skill_class in SKILL_REGISTRY.items():
        skill_data = caller_skills.get(skill_key)

        if skill_data is None:
            caller.skills.init_all_skills()
            skill_data = caller.db.skills.get(skill_key, {"level": 0, "xp": 0})

        category_name = skill_class.category

        if category_name not in categories_dict:
            categories_dict[category_name] = []

        skill_tuple = (skill_key, skill_data, skill_class)
        categories_dict[category_name].append(skill_tuple)

    return categories_dict



def start(caller: object, **kwargs) -> tuple:
    categories_dict = _get_categories(caller)

    text_parts = [f"{TITLE_COLOR}--- Skills Overview ---{RESET_COLOR}"]

    for category_name in sorted(categories_dict.keys()):
        skill_list = categories_dict[category_name]
        text_parts.append(f"\n{HIGHLIGHT_COLOR}{category_name}:{RESET_COLOR}")

        for skill_key, skill_data, skill_class in skill_list:
            if skill_data is None:
                continue

            current_level = skill_data["level"]
            current_xp = skill_data["xp"]

            total_xp = caller.skills.get_total_xp(skill_key)

            xp_tuple = caller.skills.get_xp_level(skill_key)
            total_needed = xp_tuple[1]
            remaining = xp_tuple[2]

            next_level_at = total_xp + remaining

            xp_bar = build_xp_meter(current_xp, total_needed)

            skill_instance = skill_class()
            is_unlocked = skill_instance.get_unlock_requirements(caller)

            unlock_status = (
                f"{SUCCESS_COLOR}Unlocked{RESET_COLOR}"
                if is_unlocked
                else f"{HIGHLIGHT_COLOR}Locked{RESET_COLOR}"
            )

            text_parts.append(
                f"  {SKILL_COLOR}{skill_class.name}{RESET_COLOR} "
                f"(Level {TITLE_COLOR}{current_level}{RESET_COLOR}) - {unlock_status}"
            )
            text_parts.append(f"    XP: {total_xp}")
            text_parts.append(f"    Next level at: {next_level_at}")
            text_parts.append(f"    Remaining: {remaining}")
            text_parts.append(f"    {xp_bar}")

    text = "\n".join(text_parts)

    options_list = []

    for category_name in sorted(categories_dict.keys()):
        for skill_key, skill_data, skill_class in categories_dict[category_name]:
            if skill_data is None:
                continue
            options_list.append({
                "desc": f"{skill_class.name} details",
                "goto": ("node_skill_detail", {"skill_key": skill_key}),
            })

    options_list.append({"desc": "Exit skills panel", "goto": "node_exit"})

    return text, tuple(options_list)



def node_category_detail(caller: object, **kwargs) -> tuple:
    """
    Purpose: Displays all skills within a selected category.

    Entry:
        caller is a valid Evennia Character object
        kwargs["category"] is the category name string

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        TITLE_COLOR read
        HIGHLIGHT_COLOR read
        RESET_COLOR read

    Methodology:
        Filters skills by category and generates numbered options.
        Each option navigates to the skill detail view.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    category_name = kwargs.get("category", "Unknown")
    categories_dict = _get_categories(caller)
    skill_list = categories_dict.get(category_name, [])

    text = f"{TITLE_COLOR}--- {category_name} Skills ---{RESET_COLOR}\nSelect a skill to view details."

    options_list = []

    for skill_key, skill_data, skill_class in skill_list:
        if skill_data is None:
            continue
        current_level = skill_data["level"]
        desc_string = f"{skill_class.name} (Level {current_level})"

        option_dict = {
            "desc": desc_string,
            "goto": ("node_skill_detail", {"skill_key": skill_key}),
        }
        options_list.append(option_dict)

    options_list.append({"desc": "Back to skill categories", "goto": "start"})

    options_tuple = tuple(options_list)

    return text, options_tuple



def _format_unlock_section(header: str, current_level: int, unlock_rows: list) -> str:
    """
    Purpose: Render one "<Header>:" block of skill-gated unlocks.

    Entry:
        header is the section title, e.g. "Gathering Unlocks".
        current_level is the caller's level in the skill being displayed.
        unlock_rows is a list of (display_name, required_level, extra_text)
        tuples. extra_text may be "".

    Exit/Returns:
        Returns the formatted block as a string, or "" if unlock_rows is
        empty.

    Module Globals:
        HIGHLIGHT_COLOR, SKILL_COLOR, SUCCESS_COLOR, RESET_COLOR read.

    Methodology:
        Shared by every unlock category (recipes, gathering, equipment,
        abilities) so the menu renders all four identically instead of each
        category hand-rolling its own loop.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    if not unlock_rows:
        return ""

    lines = [f"\n\n{HIGHLIGHT_COLOR}{header}:{RESET_COLOR}"]

    for display_name, required_level, extra_text in unlock_rows:
        is_row_unlocked = current_level >= required_level
        level_color = SUCCESS_COLOR if is_row_unlocked else HIGHLIGHT_COLOR

        line = (
            f"  {SKILL_COLOR}{display_name}{RESET_COLOR} "
            f"({level_color}Level {required_level}{RESET_COLOR})"
        )
        if extra_text:
            line += f" - {extra_text}"

        lines.append(line)

    return "\n".join(lines)


def _build_recipe_rows(skill_key: str) -> list:
    """
    Purpose: Build unlock rows for every recipe this skill unlocks.

    Entry:
        skill_key is a valid skill key string.

    Exit/Returns:
        Returns a list of (name, required_level, extra_text) tuples, where
        extra_text names the required materials, or "" if the recipe needs
        none.

    Module Globals:
        None

    Methodology:
        One row per entry from crafting_service.get_recipes_for_skill.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    rows = []

    for _recipe_key, recipe_cls in get_recipes_for_skill(skill_key):
        material_summary = get_material_summary(recipe_cls)
        extra_text = f"requires {material_summary}" if material_summary else ""
        row = (recipe_cls.name, recipe_cls.required_level, extra_text)
        rows.append(row)

    return rows


def _build_gatherable_rows(skill_key: str) -> list:
    """
    Purpose: Build unlock rows for every gathering node this skill unlocks.

    Entry:
        skill_key is a valid skill key string.

    Exit/Returns:
        Returns a list of (name, required_level, extra_text) tuples, where
        extra_text names the yielded item.

    Module Globals:
        None

    Methodology:
        One row per entry from gatherables.get_gatherables_for_skill.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    rows = []

    for gatherable_def in get_gatherables_for_skill(skill_key):
        item_name = get_gatherable_item_name(gatherable_def)
        extra_text = f"yields {item_name}"
        row = (gatherable_def.node_name, gatherable_def.required_level, extra_text)
        rows.append(row)

    return rows


def _build_equippable_rows(skill_key: str) -> list:
    """
    Purpose: Build unlock rows for every equippable item this skill unlocks.

    Entry:
        skill_key is a valid skill key string.

    Exit/Returns:
        Returns a list of (name, required_level, extra_text) tuples, with
        extra_text always "".

    Module Globals:
        None

    Methodology:
        One row per entry from skill_requirements.get_equippables_for_skill.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    rows = []

    for item_def in get_equippables_for_skill(skill_key):
        row = (item_def.name, item_def.req_level, "")
        rows.append(row)

    return rows


def _build_aura_rows(skill_key: str) -> list:
    """
    Purpose: Build unlock rows for every ability/aura this skill unlocks.

    Entry:
        skill_key is a valid skill key string.

    Exit/Returns:
        Returns a list of (name, required_level, extra_text) tuples, with
        extra_text always "".

    Module Globals:
        None

    Methodology:
        One row per entry from auras.registry.get_auras_for_skill.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    rows = []

    for aura in get_auras_for_skill(skill_key):
        row = (aura.name, aura.unlock_level, "")
        rows.append(row)

    return rows


def node_skill_detail(caller: object, **kwargs) -> tuple:
    """
    Purpose: Shows detailed information for a specific skill.

    Entry:
        caller is a valid Evennia Character object
        kwargs["skill_key"] is the skill identifier string

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        SKILL_COLOR read
        TITLE_COLOR read
        HIGHLIGHT_COLOR read
        RESET_COLOR read
        SKILL_REGISTRY read

    Methodology:
        Retrieves skill class and data. Formats level, XP progress
        bar, description, and unlock status into a detailed display, then
        appends one "Unlocks" section per skill-gated system (crafting
        recipes, gathering nodes, equippable items, abilities/auras) via
        _build_*_rows and _format_unlock_section.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    skill_key = kwargs.get("skill_key", "")
    skill_class = SKILL_REGISTRY.get(skill_key)

    if skill_class is None:
        text = f"{HIGHLIGHT_COLOR}Skill '{skill_key}' not found.{RESET_COLOR}"
        options = ({"desc": "Back", "goto": "node_category_detail"},)

        return text, options

    skill_data = caller.db.skills.get(skill_key, {"level": 0, "xp": 0})
    current_level = skill_data["level"]
    current_xp = skill_data["xp"]

    total_xp = caller.skills.get_total_xp(skill_key)

    xp_tuple = caller.skills.get_xp_level(skill_key)
    total_needed = xp_tuple[1]
    remaining = xp_tuple[2]

    next_level_at = total_xp + remaining

    xp_bar = build_xp_meter(current_xp, total_needed)

    skill_instance = skill_class()
    is_unlocked = skill_instance.get_unlock_requirements(caller)

    if is_unlocked:
        unlock_status = f"{SUCCESS_COLOR}Unlocked{RESET_COLOR}"
    else:
        unlock_status = f"{HIGHLIGHT_COLOR}Locked{RESET_COLOR}"

    text = (
        f"{SKILL_COLOR}{skill_class.name}{RESET_COLOR}\n"
        f"Category: {skill_class.category}\n"
        f"Level: {TITLE_COLOR}{current_level}{RESET_COLOR}\n"
        f"XP: {total_xp}\n"
        f"Next level at: {next_level_at}\n"
        f"Remaining: {remaining}\n"
        f"Progress: {xp_bar}\n"
        f"Status: {unlock_status}\n\n"
        f"{skill_class.description}"
    )

    # Every skill-gated system (crafting, gathering, equipment, abilities)
    # feeds this same renderer through its own row-builder, so adding a
    # fifth category means adding one _build_x_rows helper and one line
    # here -- not a fifth hand-rolled loop.
    unlock_sections = (
        ("Unlocks", _build_recipe_rows(skill_key)),
        ("Gathering Unlocks", _build_gatherable_rows(skill_key)),
        ("Equipment Unlocks", _build_equippable_rows(skill_key)),
        ("Ability Unlocks", _build_aura_rows(skill_key)),
    )

    for header, unlock_rows in unlock_sections:
        text += _format_unlock_section(header, current_level, unlock_rows)

    options = (
        {"desc": "Back to category", "goto": ("node_category_detail", {"category": skill_class.category})},
        {"desc": "Back to skill list", "goto": "start"},
    )

    return text, options



def node_exit(caller: object, **kwargs) -> tuple:
    """
    Purpose: Exit node that closes the skills menu.

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
    text = "Closing skills panel."

    return text, None
