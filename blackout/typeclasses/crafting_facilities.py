"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: CraftingFacility base typeclass and the craft command attached
             to facilities.
"""

from evennia import Command, CmdSet
from evennia import DefaultObject
from systems.interface.menus.base_menu import start_blackout_menu

from commands.constants import HELP_CATEGORY_CRAFTING
from systems.interface.statefeed.constants import ASSET_KIND_STATION
from typeclasses.objects import ObjectParent
from systems.interface.statefeed import constants as feed_const

# Every line this module sends a player is crafting, so the routing tag is
# bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/interface/statefeed/constants.py.
_MSG_CRAFTING = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_CRAFTING}


CRAFT_COMMAND_KEY = "craft"
CRAFT_COMMAND_LOCKS = "cmd:all()"
CRAFT_CMD_SET_KEY = "crafting_facility_cmdset"
CRAFT_CMD_SET_PRIORITY = 10
CRAFT_MENU_MODULE_PATH = "systems.interface.menus.crafting_menu"

# `craft cancel` stops the running batch. No recipe is keyed or named
# "cancel", and find_facility_recipe is never asked for this word.
CRAFT_CANCEL_ARG = "cancel"

MSG_NO_SUCH_RECIPE = "You cannot make '{recipe}' here."
MSG_CANCELLED = "Crafting cancelled."
MSG_NOTHING_TO_CANCEL = "You are not crafting anything."


def _craft_count(caller, recipe_key, count) -> int:
    """Map a parsed quantity to a batch size. Omitted is one, `all` is the
    most the materials allow. start_batch clamps every count again."""
    from systems.gameplay.crafting import crafting_service
    from systems.interface.menus.base_menu import QUANTITY_ALL_KEYWORD

    if count is None:
        return 1

    if count == QUANTITY_ALL_KEYWORD:
        most = crafting_service.get_max_craftable(caller, recipe_key)
        return max(1, most)

    return max(1, int(count))


def perform_craft(caller, facility, args: str) -> bool:
    """
    Purpose: Start a craft batch that a typed line names.

    Entry:
        caller   - the crafting Character.
        facility - the facility the command hangs on.
        args     - "<recipe> [quantity|all]", a key or a name.

    Exit/Returns:
        Returns True when a batch started. Messages the caller on every exit.

    Module Globals:
        MSG_NO_SUCH_RECIPE read.

    Methodology:
        1. Split the recipe from the count, as `sell` and `buy` do.
        2. Find the recipe among this facility's own. If there is none, refuse.
        3. Start the batch through craft_batch, the routine the menu uses.

        No confirm step. The menu confirms because a player walks a list to
        reach its craft row. This line names the recipe and the count, and a
        pop-up click is a choice the player made on purpose, as in OSRS.

    Notes/References:
        The crafting pop-up sends this line from each recipe slot.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    from commands.inventory_cmds import split_item_and_count
    from systems.gameplay.crafting import craft_batch, crafting_service

    recipe_text, count = split_item_and_count(args.strip())
    recipe_key, _recipe_cls = crafting_service.find_facility_recipe(
        facility, recipe_text)

    if recipe_key is None:
        caller.msg((MSG_NO_SUCH_RECIPE.format(recipe=recipe_text), _MSG_CRAFTING))
        return False

    batch_size = _craft_count(caller, recipe_key, count)
    started, message = craft_batch.start_batch(caller, recipe_key, batch_size)
    caller.msg((message, _MSG_CRAFTING))

    return started


def cancel_craft(caller) -> bool:
    """Stop the running batch, say so, and redraw an open pop-up.

    A cancel moves no item, so emit_inventory never hears of it. The pop-up
    shows the batch, so this sends it again itself.
    """
    from systems.gameplay.crafting import craft_batch
    from systems.interface.popups import service as popup_service

    cancelled = craft_batch.cancel_batch(caller)
    message = MSG_CANCELLED if cancelled else MSG_NOTHING_TO_CANCEL
    caller.msg((message, _MSG_CRAFTING))
    popup_service.publish_if_open(caller)

    return cancelled


class CmdCraft(Command):
    """
    Purpose: Opens this crafting facility, or crafts at it.

    Usage:
        craft
        craft <recipe> [quantity|all]
        craft cancel

    A bare `craft` opens a pop-up in a graphical client and the crafting menu
    everywhere else. `craft <recipe>` starts making that recipe here, and
    `craft cancel` stops what you are making.

    Entry:
        self.caller is a valid Evennia Character object
        self.obj is the crafting facility object

    Exit/Returns:
        No conditions. Launches an EvMenu on the caller.

    Module Globals:
        CRAFT_MENU_MODULE_PATH read

    Methodology:
        Launches the crafting EvMenu. Passes the facility
        object as a kwarg for potential facility-specific logic.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key = CRAFT_COMMAND_KEY
    locks = CRAFT_COMMAND_LOCKS
    help_category = HELP_CATEGORY_CRAFTING


    def func(self) -> None:
        """
        Purpose: Executes the craft command, opening the crafting menu.

        Entry:
            self.caller is a valid Character
            self.obj is the crafting facility Object

        Exit/Returns:
            No conditions

        Module Globals:
            CRAFT_MENU_MODULE_PATH read

        Methodology:
            Starts the styled menu using the shared crafting menu module.
            Passes facility=self.obj to the start node via startnode_input --
            EvMenu's own **kwargs only become attributes on the menu
            instance, they are not forwarded to the start node.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        caller = self.caller
        facility = self.obj
        argument = self.args.strip()

        if argument.lower() == CRAFT_CANCEL_ARG:
            cancel_craft(caller)
            return

        if argument:
            perform_craft(caller, facility, argument)
            return

        # A pop-up, if a session can draw one. Not beside the menu: the
        # menu takes every line the pop-up sends. See CmdBank.func.
        from systems.interface.popups import service as popup_service
        from systems.interface.popups.popup_defs.crafting import CRAFTING_POPUP_KEY

        wants = popup_service.wants_popup(caller)

        if wants:
            opened = popup_service.open_popup(caller, CRAFTING_POPUP_KEY, facility)

            if opened:
                return

        caller.msg((f"(You approach the {facility.key}.)", _MSG_CRAFTING))

        start_blackout_menu(
            caller,
            CRAFT_MENU_MODULE_PATH,
            startnode="start",
            startnode_input=("", {"facility": facility}),
        )



class CraftCmdSet(CmdSet):
    """
    Purpose: Stores the craft command for crafting facilities.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        CRAFT_CMD_SET_KEY read
        CRAFT_CMD_SET_PRIORITY read

    Methodology:
        Adds CmdCraft to the cmdset during creation.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key = CRAFT_CMD_SET_KEY
    priority = CRAFT_CMD_SET_PRIORITY


    def at_cmdset_creation(self) -> None:
        """
        Purpose: Populates the cmdset with the craft command.

        Entry:
            No conditions

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Instantiates and adds CmdCraft to this cmdset.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        # `toggle craft confirm` is NOT here: it is the player's preference and
        # must work away from a workbench. See commands/crafting_cmds.py.
        craft_command = CmdCraft()
        self.add(craft_command)



class CraftingFacility(ObjectParent, DefaultObject):
    """
    Purpose: A workbench or facility where players can craft items.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        At creation, adds the CraftCmdSet persistently.
        Optionally stores a list of recipe categories or
        specific recipes available at this facility.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """

    # How a graphical client should draw this and what it may send to use it.
    # Read by systems/interface/statefeed/serializers.py through getattr, so the feed
    # never imports the typeclass layer. Without these a facility is
    # indistinguishable from a dropped item and a client offers to pick it up
    # -- which is exactly what happened to the Foundry Furnace.
    #
    # The verb is bare because CraftCmdSet hangs on THIS object: `craft` needs
    # no target, the cmdset's owner is the target. Subclasses name their own
    # asset_key so a renderer can tell a furnace from an anvil.
    asset_kind = ASSET_KIND_STATION
    asset_key = "crafting_facility"
    interact_verb = CRAFT_COMMAND_KEY


    def at_object_creation(self) -> None:
        """
        Purpose: Called once when the crafting facility is first created.

        Entry:
            No conditions

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Calls parent creation. Adds CraftCmdSet persistently.
            Sets a default description.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        parent_class = super()
        parent_class.at_object_creation()

        self.cmdset.add_default(CraftCmdSet, persistent=True)

        self.db.desc = "A sturdy workbench covered in tools and scrap."
