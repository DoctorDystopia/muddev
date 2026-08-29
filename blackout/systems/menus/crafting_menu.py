"""
Crafting menu for Blackout.

This menu provides a guided crafting interface through EvMenu. All
crafting logic (recipe discovery, prerequisite checking, execution)
is handled by systems.crafting.crafting_service - this module only
manages display formatting and navigation flow.
"""



import systems.crafting.craft_batch as craft_batch
import systems.crafting.crafting_service as crafting_service
from systems.menus.base_menu import back_option, cancel_option, parse_quantity
from systems.menus.constants import (
    CONFIRM_NO_KEYS,
    CONFIRM_YES_KEYS,
    QUANTITY_ALL_KEYS,
    QUANTITY_CUSTOM_DESC,
    QUANTITY_CUSTOM_KEYS,
    QUANTITY_ONE_DESC,
    QUANTITY_ONE_KEYS,
)
from systems.ui.colors import (
    ERROR_COLOR,
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    TITLE_COLOR,
)
from systems.statefeed import constants as feed_const

# Every line this module sends a player is crafting, so the routing tag is
# bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_CRAFTING = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_CRAFTING}



RECIPE_SEPARATOR = "-" * 60

# Spoken by BlackoutEvMenu.close_menu, however the menu is closed.
CLOSING_TEXT = "Closing crafting menu."



def _skill_requirement(skill_key, required_level):
    """Name a recipe's skill gate the way the skills sheet does.

    Entry:
        skill_key is a recipe's required_skill; "" for an ungated recipe.
        required_level is its required_level.

    Exit/Returns:
        Returns e.g. "Metalsmith Lv.4", or "" for an ungated recipe.

    Methodology:
        The skill's DISPLAY name, not its key -- "Metalsmith Lv.4" is what a
        player just read on the skills sheet, and "metalsmith Lv.4" is not.
        The import is deferred because the skills registry has no business
        being walked when this module is imported at startup.
    """
    if not skill_key:
        return ""

    from systems.progression.skills.registry import SKILL_REGISTRY

    skill_class = SKILL_REGISTRY.get(skill_key)
    skill_name = getattr(skill_class, "name", skill_key)

    return f"{skill_name} Lv.{required_level}"


def _recipe_line(recipe_cls):
    """Render one recipe as a row of the facility's recipe list.

    Entry:
        recipe_cls is a BlackoutRecipe subclass.

    Exit/Returns:
        Returns e.g. "rusty scrap shortsword (Metalsmith Lv.4)
        - requires 2x rusty scrap metal".

    Methodology:
        The shape the skills sheet prints an unlock in -- name, gate,
        materials -- so the two screens describing the same recipe read the
        same. The material half is get_material_summary's, which is what
        collapses a repeated ingredient into "2x": listing the same scrap
        three times told a player nothing the count does not.

        No colour. Option descriptions land in an EvTable, which measures
        columns with plain len(), so an ANSI code in one widens its row by
        the length of the escape.
    """
    parts = [recipe_cls.name]
    requirement = _skill_requirement(
        recipe_cls.required_skill, recipe_cls.required_level
    )

    if requirement:
        parts.append(f"({requirement})")

    line = " ".join(parts)
    materials = crafting_service.get_material_summary(recipe_cls)

    if materials:
        line += f" - requires {materials}"

    return line


def start(caller, **kwargs):
    facility = kwargs.get("facility")
    recipes = crafting_service.get_recipes_for_facility(facility)
    facility_name = facility.key if facility is not None else "Crafting Menu"
    text = (
        f"{TITLE_COLOR}--- {facility_name} ---{RESET_COLOR}\n"
        "Select a recipe to view its details."
    )
    options = []

    active_batch = craft_batch.get_active_batch(caller)
    if active_batch:
        text += (
            f"\n\n{HIGHLIGHT_COLOR}Currently crafting:{RESET_COLOR} "
            f"{active_batch['recipe_name']} "
            f"({active_batch['crafted']}/{active_batch['total']})"
        )
        options.append(
            {
                "desc": "Cancel active crafting",
                "goto": ("node_cancel_batch", {"facility": facility}),
            }
        )

    for recipe_key, recipe_cls in recipes:
        options.append(
            {
                "desc": _recipe_line(recipe_cls),
                "goto": (
                    "node_recipe_detail",
                    {"recipe_key": recipe_key, "facility": facility},
                ),
            }
        )
    return text, options


def node_recipe_detail(caller, **kwargs):
    recipe_key = kwargs.get("recipe_key", "")
    facility = kwargs.get("facility")
    display = crafting_service.get_recipe_display_data(caller, recipe_key)

    if not display:
        text = f"{ERROR_COLOR}Recipe not found.{RESET_COLOR}"
        return text, (
            back_option("Back to recipes", ("start", {"facility": facility})),
        )

    material_lines = []

    for md in display["material_details"]:
        # "2x rusty scrap metal", the spelling get_material_summary uses on
        # the list and on the skills sheet -- a count is the fact, and a
        # recipe needing three of something said so three times before.
        if md["required"] > 1:
            requirement = f"{md['required']}x {md['name']}"
        else:
            requirement = md["name"]

        material_lines.append(f"  {requirement} ({md['owned']} owned)")

    materials_str = "\n".join(material_lines)

    requirement = _skill_requirement(
        display["required_skill"], display["required_level"]
    )

    if requirement:
        if display["meets_skill"]:
            skill_status = f"{requirement} ({SUCCESS_COLOR}Met{RESET_COLOR})"
        else:
            skill_status = f"{ERROR_COLOR}Requires {requirement}{RESET_COLOR}"
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
        options = (
            {
                "desc": f"Craft {display['name']}",
                "goto": (
                    "node_craft_quantity",
                    {"recipe_key": recipe_key, "facility": facility},
                ),
            },
            back_option("Back to recipes", ("start", {"facility": facility})),
        )
    else:
        options = (
            back_option("Back to recipes", ("start", {"facility": facility})),
        )

    return text, options


def _confirm_required(caller, recipe_cls):
    """Whether a craft of recipe_cls needs the confirm step for this caller.

    Both halves have to opt in: the recipe (require_confirm) and the player
    (their craft_confirm preference, unset meaning "on" by default).
    """
    require_confirm = getattr(recipe_cls, "require_confirm", True)
    caller_confirm = caller.db.craft_confirm
    if caller_confirm is None:
        caller_confirm = True

    return require_confirm and caller_confirm


def _start_batch_and_render(caller, recipe_key, facility, count):
    """Start a craft batch and render the caller back at the recipe list.

    Shared by every path that ends a craft flow without a confirm step --
    called directly (not navigated to) so it can be reused both from a goto
    callable, which must return a node name, and from a node's typed-input
    pass, which must return rendered (text, options).
    """
    started, message = craft_batch.start_batch(caller, recipe_key, count)
    color = SUCCESS_COLOR if started else ERROR_COLOR
    caller.msg((f"{color}{message}{RESET_COLOR}", _MSG_CRAFTING))

    return start(caller, facility=facility)


def node_craft_quantity(caller, **kwargs):
    recipe_key = kwargs.get("recipe_key", "")
    facility = kwargs.get("facility")
    recipe_cls = crafting_service.get_recipe_class(recipe_key)

    if not recipe_cls:
        text = f"{ERROR_COLOR}Recipe not found.{RESET_COLOR}"

        return text, (
            back_option("Back to recipes", ("start", {"facility": facility})),
        )

    if craft_batch.is_batch_active(caller):
        active = craft_batch.get_active_batch(caller)
        text = (
            f"{ERROR_COLOR}You are already crafting {active['recipe_name']} "
            f"({active['crafted']}/{active['total']}).{RESET_COLOR}"
        )

        return text, (
            back_option(
                "Back to recipe details",
                ("node_recipe_detail", {"recipe_key": recipe_key, "facility": facility}),
            ),
        )

    max_qty = crafting_service.get_max_craftable(caller, recipe_key)

    if max_qty < 1:
        can_craft, reasons = crafting_service.check_craftable(caller, recipe_key)
        text = f"{ERROR_COLOR}Cannot craft: {'; '.join(reasons)}.{RESET_COLOR}"

        return text, (
            back_option(
                "Back to recipe details",
                ("node_recipe_detail", {"recipe_key": recipe_key, "facility": facility}),
            ),
        )

    needs_confirm = _confirm_required(caller, recipe_cls)

    def _target(count):
        if needs_confirm:
            return (
                "node_confirm_craft",
                {"recipe_key": recipe_key, "facility": facility, "count": count},
            )

        return (
            execute_craft_batch,
            {"recipe_key": recipe_key, "facility": facility, "count": count},
        )

    text = (
        f"{TITLE_COLOR}--- Craft {recipe_cls.name} ---{RESET_COLOR}\n"
        f"You can craft up to {HIGHLIGHT_COLOR}{max_qty}{RESET_COLOR} right now "
        f"({recipe_cls.craft_seconds:.1f}s per item).\n\n"
        f"{HIGHLIGHT_COLOR}How many to craft?{RESET_COLOR}"
    )
    options = [
        {"key": QUANTITY_ONE_KEYS, "desc": QUANTITY_ONE_DESC, "goto": _target(1)},
        {
            "key": QUANTITY_CUSTOM_KEYS,
            "desc": QUANTITY_CUSTOM_DESC,
            "goto": (
                "node_craft_custom_qty",
                {"recipe_key": recipe_key, "facility": facility, "max_qty": max_qty},
            ),
        },
        {
            "key": QUANTITY_ALL_KEYS,
            "desc": f"All ({max_qty})",
            "goto": _target(max_qty),
        },
        cancel_option(
            ("node_recipe_detail", {"recipe_key": recipe_key, "facility": facility})
        ),
    ]

    return text, options


def node_craft_custom_qty(caller, raw_string, **kwargs):
    """Prompt for a typed quantity, reached via the "X (custom)" option.

    Two-pass, mirroring banking_menu's custom-quantity nodes: the first
    visit renders the prompt and arms a hidden _default option; typing a
    number re-enters with custom_qty_state="awaiting" and this pass parses
    raw_string via the shared parse_quantity.
    """
    recipe_key = kwargs.get("recipe_key", "")
    facility = kwargs.get("facility")
    max_qty = kwargs.get("max_qty", 1)
    recipe_cls = crafting_service.get_recipe_class(recipe_key)

    if not recipe_cls:
        caller.msg((f"{ERROR_COLOR}Recipe not found.{RESET_COLOR}", _MSG_CRAFTING))

        return start(caller, facility=facility)

    text = (
        f"{TITLE_COLOR}--- Craft {recipe_cls.name} ---{RESET_COLOR}\n"
        f"Enter a quantity (1-{max_qty}, or 'all').{RESET_COLOR}"
    )
    custom_options = (
        {
            "key": "_default",
            "goto": (
                "node_craft_custom_qty",
                {
                    "recipe_key": recipe_key,
                    "facility": facility,
                    "max_qty": max_qty,
                    "custom_qty_state": "awaiting",
                },
            ),
        },
        cancel_option(
            ("node_craft_quantity", {"recipe_key": recipe_key, "facility": facility})
        ),
    )

    if kwargs.get("custom_qty_state") != "awaiting":
        return text, custom_options

    count, parse_error = parse_quantity(raw_string, max_qty)

    if parse_error is not None:
        caller.msg((f"{ERROR_COLOR}{parse_error}{RESET_COLOR}", _MSG_CRAFTING))

        return text, custom_options

    if _confirm_required(caller, recipe_cls):
        return node_confirm_craft(
            caller, recipe_key=recipe_key, facility=facility, count=count
        )

    return _start_batch_and_render(caller, recipe_key, facility, count)


def node_confirm_craft(caller, **kwargs):
    recipe_key = kwargs.get("recipe_key", "")
    facility = kwargs.get("facility")
    count = kwargs.get("count", 1)
    recipe_cls = crafting_service.get_recipe_class(recipe_key)

    if not recipe_cls:
        text = f"{ERROR_COLOR}Recipe not found.{RESET_COLOR}"

        return text, (
            back_option("Back to recipes", ("start", {"facility": facility})),
        )

    can_craft, reasons = crafting_service.check_craftable(caller, recipe_key)

    if not can_craft:
        text = f"{ERROR_COLOR}Cannot craft: {'; '.join(reasons)}.{RESET_COLOR}"

        return text, (
            back_option(
                "Back to recipe details",
                ("node_recipe_detail", {"recipe_key": recipe_key, "facility": facility}),
            ),
        )

    max_craftable = crafting_service.get_max_craftable(caller, recipe_key)
    count = max(1, min(count, max_craftable))

    output_names = (
        recipe_cls.output_names
        if recipe_cls.output_names
        else [prot.get("key", "item") for prot in recipe_cls.output_prototypes]
    )
    output_str = ", ".join(output_names)
    est_seconds = recipe_cls.craft_seconds * count

    text = (
        f"{TITLE_COLOR}Confirm Craft:{RESET_COLOR} {recipe_cls.name} x{count}\n\n"
        f"This will consume {count}x the required materials and produce "
        f"{count}x {output_str}.\n"
        f"Estimated time: {est_seconds:.1f}s.\n\n"
        f"{HIGHLIGHT_COLOR}Proceed?{RESET_COLOR}"
    )
    options = (
        {
            "key": CONFIRM_YES_KEYS,
            "desc": f"Yes, craft {recipe_cls.name} x{count}",
            "goto": (
                execute_craft_batch,
                {"recipe_key": recipe_key, "facility": facility, "count": count},
            ),
        },
        {
            "key": CONFIRM_NO_KEYS,
            "desc": "No, go back",
            "goto": (
                "node_recipe_detail",
                {"recipe_key": recipe_key, "facility": facility},
            ),
        },
    )

    return text, options


def execute_craft_batch(caller, raw_string, **kwargs):
    recipe_key = kwargs.get("recipe_key", "")
    facility = kwargs.get("facility")
    count = kwargs.get("count", 1)

    started, message = craft_batch.start_batch(caller, recipe_key, count)
    color = SUCCESS_COLOR if started else ERROR_COLOR
    caller.msg((f"{color}{message}{RESET_COLOR}", _MSG_CRAFTING))

    return "start", {"facility": facility}


def node_cancel_batch(caller, **kwargs):
    facility = kwargs.get("facility")
    cancelled = craft_batch.cancel_batch(caller)

    if cancelled:
        caller.msg((f"{SUCCESS_COLOR}Crafting cancelled.{RESET_COLOR}", _MSG_CRAFTING))

    return start(caller, facility=facility)

