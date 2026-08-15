"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Talkative and shopkeeper NPC typeclasses, plus the talk command.
"""

from evennia import Command, CmdSet
from evennia import DefaultObject
from evennia.utils.evmenu import EvMenu

from commands.constants import HELP_CATEGORY_GENERAL
from systems.statefeed.constants import ASSET_KIND_NPC
from typeclasses.objects import ObjectParent
from .spawners import register_spawner, spawn_once
from systems.menus.base_menu import start_blackout_menu


# Public constant definitions
TALK_COMMAND_KEY = "talk"
TALK_COMMAND_LOCKS = "cmd:all()"
TALK_CMD_SET_KEY = "npc_talk_cmdset"
TALK_CMD_SET_PRIORITY = 10

SHOPKEEP_DIALOGUE_MODULE = "systems.menus.npc_dialogues.npc_shopkeep"
SHOPKEEP_CLEANUP_SCRIPT = "scripts.shopkeep_inventory_cleanup.ShopkeepCleanup"



class CmdTalk(Command):
    """
    Purpose: Initiates a menu-driven conversation with an NPC.

    Entry:
        self.caller is a valid Evennia Character object
        self.obj is the NPC with a db.menu_module path

    Exit/Returns:
        No conditions. Launches an EvMenu on the caller.

    Module Globals:
        TALK_COMMAND_KEY read
        TALK_COMMAND_LOCKS read

    Methodology:
        Sends a brief introduction message to the caller,
        then launches EvMenu using the NPC's stored module path.
        Passes the NPC itself as a keyword argument for menu nodes.

    Notes/References:
        Pattern from evennia.contrib.tutorials.talking_npc.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key = TALK_COMMAND_KEY
    locks = TALK_COMMAND_LOCKS
    help_category = HELP_CATEGORY_GENERAL


    def func(self) -> None:
        """
        Purpose: Executes the talk command, launching the dialogue menu.

        Entry:
            self.caller is a valid Character
            self.obj is the NPC object

        Exit/Returns:
            No conditions (menu lifecycle managed by EvMenu)

        Module Globals:
            None

        Methodology:
            Retrieves the menu module path from the NPC's db attribute.
            Passes npc=self.obj as a kwarg for dialogue node access.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        caller = self.caller
        npc = self.obj
        menu_module_path = npc.db.menu_module

        menu_module_is_valid = bool(menu_module_path)

        if not menu_module_is_valid:
            caller.msg(f"{npc.key} has nothing to say right now.")
            return

        caller.msg(f"(You walk up and talk to {npc.key}.)")

        if menu_module_path == SHOPKEEP_DIALOGUE_MODULE:
            start_blackout_menu(
                caller,
                menu_module_path,
                startnode="start",
                npc=npc,
            )
        else:
            EvMenu(
                caller,
                menu_module_path,
                startnode="start",
                npc=npc,
            )



class TalkCmdSet(CmdSet):
    """
    Purpose: Stores the talk command for an NPC.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        TALK_CMD_SET_KEY read
        TALK_CMD_SET_PRIORITY read

    Methodology:
        Adds CmdTalk to the cmdset during creation.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key = TALK_CMD_SET_KEY
    priority = TALK_CMD_SET_PRIORITY


    def at_cmdset_creation(self) -> None:
        """
        Purpose: Populates the cmdset with the talk command.

        Entry:
            No conditions

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Instantiates and adds CmdTalk to this cmdset.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        talk_command = CmdTalk()
        self.add(talk_command)



class TalkativeNPC(ObjectParent, DefaultObject):
    """
    Purpose: An NPC that can engage in menu-driven conversations.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        At creation, adds the TalkCmdSet persistently.
        Expects db.menu_module to be set (string path to
        a dialogue module containing EvMenu node functions).

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """

    # How a graphical client draws this and what it may send to use it. Read
    # by systems/statefeed/serializers.py through getattr.
    #
    # `asset_kind` has to be declared because nothing else identifies this as
    # an NPC: it is not an Evennia character, and `db.npc_key` belongs to the
    # hostile NPC_DB stat blocks, which a shopkeeper has no business carrying.
    # Without it a shopkeeper served as a generic item, and the 3D pane offered
    # to pick one up.
    #
    # `talk` rather than `attack` is the whole point of declaring the verb here
    # instead of letting a client infer one from the kind: both are NPCs, and
    # only one of them is a fight.
    asset_kind = ASSET_KIND_NPC
    asset_key = "talkative_npc"
    interact_verb = TALK_COMMAND_KEY


    def at_object_creation(self) -> None:
        """
        Purpose: Called once when the NPC is first created.

        Entry:
            No conditions

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Calls the parent creation hook. Adds the TalkCmdSet
            persistently so the talk command is always available.
            Sets default description and initializes the menu
            module path to None.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        parent_class = super()
        parent_class.at_object_creation()

        self.cmdset.add_default(TalkCmdSet, persistent=True)

        self.db.desc = "A mysterious figure in the wastes."
        self.db.menu_module = None


class ShopkeepNPC(TalkativeNPC):
    """
    An NPC that buys and sells items. Extends TalkativeNPC with
    shop-specific attributes and auto-attaches the cleanup script.
    """

    asset_key = "shopkeeper"

    def at_object_creation(self) -> None:
        super().at_object_creation()
        self.db.menu_module = SHOPKEEP_DIALOGUE_MODULE
        self.db.shopdef_key = "oasis_shop"
        self.db.desc = "A shopkeeper attending a stall of salvaged goods."
        self.db.max_held_items = 20
        self.scripts.add(SHOPKEEP_CLEANUP_SCRIPT)


@register_spawner("Shopkeeper")
def spawn_shopkeep(room):
    shopkeep = spawn_once(
        room,
        "typeclasses.npcs.ShopkeepNPC",
        key="Shopkeeper",
    )

    # Stamped unconditionally, not just on first creation: spawn_once returns
    # the pre-existing shopkeep on a map rebuild, and re-applying the def keeps
    # an already-placed NPC in step with edits to these values.
    shopkeep.db.desc = "A tiny robot with a stall full of salvaged goods."
    shopkeep.db.shopdef_key = "oasis_shop"
