"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: EvMenu nodes for the skills panel: category list, per-skill
             detail, and XP meters.

             The per-skill SHEET is not written here. It lives in
             systems/progression/skills/detail.py, because two other readers
             need it without an EvMenu anywhere: the `skills <skill>` argument
             form, and the CHANNEL_CHAR_SKILLS payload a graphical client
             draws. What stays here is what a menu owns -- which node "back"
             returns to, and what to print when a key names nothing.
"""

from systems.menus.base_menu import back_option
from systems.progression.skills import detail as skill_detail
from systems.progression.skills.registry import SKILL_REGISTRY
from systems.ui.colors import (
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SKILL_COLOR,
    SUCCESS_COLOR,
    TITLE_COLOR,
)
from systems.ui.meters import build_xp_meter


# Public constant definitions
# Spoken by BlackoutEvMenu.close_menu, however the menu is closed.
CLOSING_TEXT = "Closing skills panel."



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

    options_list.append(back_option("Back to skill categories", "start"))

    options_tuple = tuple(options_list)

    return text, options_tuple



def node_skill_detail(caller: object, **kwargs) -> tuple:
    """
    Purpose: Shows detailed information for a specific skill.

    Entry:
        caller is a valid Evennia Character object
        kwargs["skill_key"] is the skill identifier string

    Exit/Returns:
        Returns a tuple of (text, options) for the EvMenu node.

    Module Globals:
        SKILL_REGISTRY read
        HIGHLIGHT_COLOR read
        RESET_COLOR read

    Methodology:
        The sheet itself is rendered by systems/progression/skills/detail.py,
        which is also what `skills <skill>` prints and what
        CHANNEL_CHAR_SKILLS ships as data. This node contributes the two
        things a menu owns and the renderer cannot: where "back" goes, and
        what to say when the key names nothing.

        An empty render is the renderer's way of saying the key is unknown --
        the same answer the registry lookup gave before -- so there is one
        check here rather than a lookup followed by a render that repeats it.

    Notes/References:
        The four unlock sections moved to detail.py on 08/28/2026, when the
        text sheet stopped being reachable only from inside a menu.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    skill_key = kwargs.get("skill_key", "")
    text = skill_detail.render_detail(caller, skill_key)

    if not text:
        missing = f"{HIGHLIGHT_COLOR}Skill '{skill_key}' not found.{RESET_COLOR}"
        options = (back_option("Back", "node_category_detail"),)

        return missing, options

    skill_class = SKILL_REGISTRY[skill_key]
    options = (
        {"desc": "Back to skill list", "goto": "start"},
        back_option(
            "Back to category",
            ("node_category_detail", {"category": skill_class.category}),
        ),
    )

    return text, options
