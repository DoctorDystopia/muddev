
from evennia import Command, CmdSet
from evennia import DefaultObject
from evennia.utils.evmenu import EvMenu

from typeclasses.objects import ObjectParent


# Public constant definitions
TALK_COMMAND_KEY = "talk"
TALK_COMMAND_LOCKS = "cmd:all()"
TALK_CMD_SET_KEY = "npc_talk_cmdset"
TALK_CMD_SET_PRIORITY = 10



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
    help_category = "General"


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
            return_value = None

            return_value

        caller.msg(f"(You walk up and talk to {npc.key}.)")

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
