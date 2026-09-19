"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: The crafting pop-up: every recipe a station makes in one grid,
             and the quantity row under it. Modelled on the OSRS smithing
             interface. The inventory pane beside it shows the materials.

             A TIMED STATION SHOWS ITS SLOTS. When the station's recipes defer
             their output (the curing chamber), timers() reads the deferred
             handler's timer_report, and the client draws one bar per slot in
             the side panel. No line here names curing.

             IT CRAFTS NOTHING. A recipe slot carries `craft <recipe> <n>`, a
             line on the station's own cmdset, and craft_batch starts the same
             paced batch the crafting menu starts. The recipe list, the gates
             and the counts come from crafting_service, so the pop-up and the
             menu cannot disagree about what a station makes.

             A RECIPE YOU CANNOT MAKE STILL SHOWS, DIM. OSRS draws every bar a
             smith cannot use yet, because the list says what the skill is
             for. A click on a dim slot sends the craft anyway, and the server
             answers with what is missing.

             ONE DEFINITION SERVES EVERY STATION. The furnace, the anvil and
             the curing chamber differ in their recipes, which the station
             declares, and in their name, which title_for reads.
"""

from systems.gameplay.crafting import craft_batch, crafting_service
from systems.interface.statefeed import constants as feed_const
from typeclasses.crafting_facilities import (
    CRAFT_CANCEL_ARG,
    CRAFT_COMMAND_KEY,
)
from world.item_database import ITEM_DB

from .base_popup import (
    BasePopup,
    definition_row,
    grid,
    quantity_actions,
)


# ─── Public constant definitions ─────────────────────────────────────────────

CRAFTING_POPUP_KEY: str = "crafting"
CRAFTING_POPUP_TITLE: str = "crafting station"

RECIPE_GRID_KEY: str = "recipes"
RECIPE_GRID_TITLE: str = "Recipes"

# The deferred-handler method that gives the side panel its data.
TIMER_REPORT_METHOD: str = "timer_report"

VERB_MAKE_LABEL: str = "Make"
PROMPT_MAKE: str = "Make how many?"

# A recipe slot names its recipe by KEY, which never collides.
CRAFT_TEMPLATE: str = (
    f"{CRAFT_COMMAND_KEY} {{recipe}} {feed_const.ACTION_AMOUNT_PLACEHOLDER}")

CANCEL_COMMAND: str = f"{CRAFT_COMMAND_KEY} {CRAFT_CANCEL_ARG}"
CANCEL_LABEL: str = "Stop crafting"

BATCH_STATUS_TEMPLATE: str = "Making {name} ({crafted}/{total})"
IDLE_STATUS: str = "Choose a recipe."

MATERIALS_TEMPLATE: str = "Needs {materials}"
MISSING_TEMPLATE: str = "Missing: {reasons}"
REASON_SEPARATOR: str = "; "
INFO_SEPARATOR: str = "\n"


# ─── Private helper routines ─────────────────────────────────────────────────

def _output_def(recipe_cls):
    """The ItemDef a recipe makes first, or None for a recipe with no output
    in ITEM_DB. The slot draws that item, as OSRS draws the bar you make."""
    for item_key in getattr(recipe_cls, "output_item_keys", []) or []:
        item_def = ITEM_DB.get(item_key)

        if item_def is not None:
            return item_def

    return None


def _recipe_info(caller, recipe_key, recipe_cls) -> str:
    """The tooltip lines of one recipe: what it needs, and what is missing."""
    lines = []
    materials = crafting_service.get_material_summary(recipe_cls)

    if materials:
        lines.append(MATERIALS_TEMPLATE.format(materials=materials))

    can_craft, reasons = crafting_service.check_craftable(caller, recipe_key)

    if not can_craft and reasons:
        joined = REASON_SEPARATOR.join(reasons)
        lines.append(MISSING_TEMPLATE.format(reasons=joined))

    return INFO_SEPARATOR.join(lines)


def _recipe_row(caller, recipe_key, recipe_cls, index, mode):
    """
    Purpose: Render one recipe of the station.

    Entry:
        caller     - the crafting Character.
        recipe_key - the recipe's registry key.
        recipe_cls - the recipe class.
        index      - its position in the recipe grid.
        mode       - the active quantity mode.

    Exit/Returns:
        Returns one row dict, or None for a recipe with nothing to draw.

    Module Globals:
        None.

    Methodology:
        1. Count how many the player can make now. That bounds X and All.
        2. If the count is zero, draw the slot dim and keep one Make action.
        3. Show the skill gate under the name, and the materials on hover.

    Notes/References:
        get_max_craftable and check_craftable are what craft_batch asks too,
        so a slot that is lit starts a batch.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    item_def = _output_def(recipe_cls)

    if item_def is None:
        return None

    most = crafting_service.get_max_craftable(caller, recipe_key)
    template = CRAFT_TEMPLATE.replace("{recipe}", recipe_key)
    actions = quantity_actions(
        VERB_MAKE_LABEL, template, mode, max(most, 1), PROMPT_MAKE)
    detail = crafting_service.skill_requirement_text(
        recipe_cls.required_skill, recipe_cls.required_level)
    info = _recipe_info(caller, recipe_key, recipe_cls)

    return definition_row(item_def, index, 1, actions, name=recipe_cls.name,
                          detail=detail, enabled=most > 0, info=info)


# ─── Public classes ──────────────────────────────────────────────────────────

class CraftingPopup(BasePopup):
    """A station's recipes, and its timed slots, anchored to the station."""

    key = CRAFTING_POPUP_KEY
    title = CRAFTING_POPUP_TITLE
    room_bound = True
    uses_quantity = True

    def title_for(self, caller, anchor) -> str:
        """The station names itself: "Foundry Furnace", "Anvil"."""
        return str(getattr(anchor, "key", "") or self.title)

    def status(self, caller, anchor) -> str:
        """The running batch. A deferred stage's slots are the side panel's,
        from timers(), not text on this line."""
        batch = craft_batch.get_active_batch(caller)

        if not batch:
            return IDLE_STATUS

        return BATCH_STATUS_TEMPLATE.format(
            name=batch["recipe_name"], crafted=batch["crafted"],
            total=batch["total"])

    def grids(self, caller, anchor, mode) -> list:
        """
        Purpose: Build the recipe grid.

        Entry:
            caller - a Character with an inventory handler.
            anchor - the crafting station.
            mode   - the active quantity mode.

        Exit/Returns:
            Returns one grid dict.

        Module Globals:
            None.

        Methodology:
            1. Sync the inventory, so the counts read what is really carried.
            2. Draw one slot for each recipe the station makes, in recipe
               order.

        Notes/References:
            Each craft of a batch moves materials off the character and the
            product onto it. So emit_inventory marks this pop-up stale at
            each step, and the counts and the status follow the batch.

        Author: Nick Hobar
        Creation date: 09/18/2026
        """
        caller.inventory.sync()

        recipe_rows = []

        for recipe_key, recipe_cls in crafting_service.get_recipes_for_facility(anchor):
            row = _recipe_row(caller, recipe_key, recipe_cls, len(recipe_rows), mode)

            if row is not None:
                recipe_rows.append(row)

        recipes = grid(RECIPE_GRID_KEY, RECIPE_GRID_TITLE, len(recipe_rows), recipe_rows)

        return [recipes]

    def timers(self, caller, anchor) -> dict:
        """The station's timed slots, or {} for a station whose work ends at
        once. Read from the deferred handler, so a second timed stage needs
        only its own timer_report."""
        handler = crafting_service.get_deferred_handler_for_facility(caller, anchor)
        report = getattr(handler, TIMER_REPORT_METHOD, None)

        if not callable(report):
            return {}

        return report()

    def actions(self, caller, anchor) -> list:
        """
        Purpose: The buttons under the grids: stop a batch, and anything else
                 the station affords.

        Entry:
            caller - the crafting Character.
            anchor - the crafting station.

        Exit/Returns:
            Returns a list of {label, command} dicts.

        Module Globals:
            CANCEL_COMMAND, CANCEL_LABEL read.

        Methodology:
            1. While a batch runs, offer Stop crafting.
            2. Add the station's own extra actions, less `craft`, which is
               this pop-up. The curing chamber's `collect` arrives this way,
               so no line here names curing.

        Notes/References:
            The labels come from the station, as the right-click menu in the
            world gets them.

        Author: Nick Hobar
        Creation date: 09/18/2026
        """
        buttons = []
        running = craft_batch.is_batch_active(caller)

        if running:
            buttons.append({"label": CANCEL_LABEL, "command": CANCEL_COMMAND})

        source = getattr(anchor, "extra_actions", None)
        declared = []

        if callable(source):
            declared = source()

        for action in declared:
            command = str(action.get("command", ""))

            if not command or command.split(" ")[0] == CRAFT_COMMAND_KEY:
                continue

            label = str(action.get("label", "") or command.capitalize())
            buttons.append({"label": label, "command": command})

        return buttons
