
from systems.progression.skills.registry import SKILL_REGISTRY


# Public constant definitions
SKILL_COLOR = "|c"
TITLE_COLOR = "|w"
HIGHLIGHT_COLOR = "|y"
SUCCESS_COLOR = "|g"
RESET_COLOR = "|n"
PROGRESS_BAR_WIDTH = 20
PROGRESS_FILL_CHAR = "#"
PROGRESS_EMPTY_CHAR = "."



def _build_xp_bar(current_xp: int, total_needed: int) -> str:
    """
    Purpose: Builds a text-based progress bar for XP display.

    Entry:
        current_xp is a non-negative integer
        total_needed is a positive integer

    Exit/Returns:
        Returns a string like "[#####.......] 50/100".

    Module Globals:
        PROGRESS_BAR_WIDTH read
        PROGRESS_FILL_CHAR read
        PROGRESS_EMPTY_CHAR read
        HIGHLIGHT_COLOR read
        SUCCESS_COLOR read
        RESET_COLOR read

    Methodology:
        Calculates fill ratio clamped to [0, 1]. Builds a bar
        string with colored fill and remainder characters.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    if total_needed <= 0:
        progress_string = f"{SUCCESS_COLOR}[MAX LEVEL]{RESET_COLOR}"

        return progress_string

    fill_ratio = current_xp / total_needed

    if fill_ratio > 1.0:
        fill_ratio = 1.0

    fill_count = int(fill_ratio * PROGRESS_BAR_WIDTH)
    empty_count = PROGRESS_BAR_WIDTH - fill_count

    fill_part = PROGRESS_FILL_CHAR * fill_count
    empty_part = PROGRESS_EMPTY_CHAR * empty_count

    progress_string = (
        f"[{HIGHLIGHT_COLOR}{fill_part}{RESET_COLOR}"
        f"{empty_part}] "
        f"{current_xp}/{total_needed}"
    )

    return progress_string



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

            xp_bar = _build_xp_bar(current_xp, total_needed)

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
        bar, description, and unlock status into a detailed display.

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

    xp_bar = _build_xp_bar(current_xp, total_needed)

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
