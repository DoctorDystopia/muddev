"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: The Moderator Egg typeclass, and the one command that opens it.

             The egg carries its command on its OWN cmdset rather than adding
             one to CharacterCmdSet, which is the same shape TalkativeNPC and
             the crafting facilities use. Evennia's cmdhandler merges cmdsets
             from `location.contents_get() + caller.contents_get() +
             [location]` (see evennia/commands/cmdhandler.py), so a CARRIED
             egg contributes `egg` and a pocketed one does not. That is the
             property worth having: the power is attached to an object a
             moderator can put down, hand over and take back, rather than to a
             permission bit that is invisible until it is used.
"""

from evennia import Command, CmdSet

from commands.constants import HELP_CATEGORY_ADMIN
from systems.menus.base_menu import start_blackout_menu
from typeclasses.items import BaseItem


# Public constant definitions

EGG_COMMAND_KEY = "egg"

# Admin, not Developer. Superusers bypass every lock in Evennia and so pass
# this without being named, and an Admin who is trusted with `boot` is trusted
# with a menu that spawns a sword. The two genuinely dangerous entries -- ban
# and unban -- are delegated to Evennia's own commands, which keep their own
# Developer lock, so an Admin holding the egg is refused by THOSE and told so.
# One lock here, checked once, is the whole permission story for this tool;
# systems/devtools/actions.py deliberately checks nothing.
EGG_COMMAND_LOCKS = "cmd:perm(Admin)"

EGG_CMD_SET_KEY = "moderator_egg_cmdset"

# Matches TALK_CMD_SET_PRIORITY. Nothing else binds `egg`, so this only has to
# beat the default cmdset, but sharing the number with the other object-hosted
# cmdset keeps object commands at one altitude.
EGG_CMD_SET_PRIORITY = 10

EGG_MENU_MODULE = "systems.menus.dev_egg_menu"

EGG_DEFAULT_DESC = (
    "A smooth ovoid of dull ceramic, warm to the touch and heavier than it "
    "has any right to be."
)



class CmdEgg(Command):
    """
    Open the Moderator Egg.

    Usage:
        egg

    Opens the moderator toolkit: spawn items, god mode, restore, teleport,
    grant XP or levels, and boot or ban an account.

    Requires the egg in your inventory and Admin permission. Every action
    taken through it is written to the server log.
    """

    key = EGG_COMMAND_KEY
    locks = EGG_COMMAND_LOCKS
    help_category = HELP_CATEGORY_ADMIN


    def func(self) -> None:
        """
        Purpose: Open the moderator menu on the caller.

        Entry:
            self.caller is the Character that typed `egg`, already past the
            command's lock. self.obj is the egg itself, set by Evennia to the
            object whose cmdset supplied this command.

        Exit/Returns:
            No return value. Starts a BlackoutEvMenu on the caller.

        Module Globals:
            EGG_MENU_MODULE read.

        Methodology:
            The egg is passed into the menu as `egg=` so nodes can name the
            object they were opened from without searching for it. The menu
            does not currently need it; passing it now costs nothing and is
            what the NPC dialogues do with `npc=`.

            No permission check here. The lock did it -- func() does not run
            for a caller that failed `cmd:perm(Admin)`.

        Notes/References:
            Launched through start_blackout_menu, never a bare EvMenu, or the
            egg opts out of the shared footer, styling and closing line.

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        caller = self.caller
        egg = self.obj

        start_blackout_menu(
            caller,
            EGG_MENU_MODULE,
            startnode="start",
            egg=egg,
        )



class EggCmdSet(CmdSet):
    """
    Purpose: Carries the `egg` command on the egg itself.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        EGG_CMD_SET_KEY, EGG_CMD_SET_PRIORITY read.

    Methodology:
        Adds CmdEgg at cmdset creation.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """

    key = EGG_CMD_SET_KEY
    priority = EGG_CMD_SET_PRIORITY


    def at_cmdset_creation(self) -> None:
        """
        Purpose: Populate the cmdset with the egg command.

        Entry:
            No conditions.

        Exit/Returns:
            No conditions.

        Module Globals:
            None.

        Methodology:
            Instantiates and adds CmdEgg.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        egg_command = CmdEgg()
        self.add(egg_command)



class ModeratorEgg(BaseItem):
    """
    Purpose: A carried moderator toolkit. Inert in anyone else's hands.

    Entry:
        Spawned from the "moderator_egg" ItemDef, which is where its value,
        weight, description and tradeable=False live.

    Exit/Returns:
        No conditions.

    Module Globals:
        EGG_DEFAULT_DESC read.

    Methodology:
        Attaches EggCmdSet persistently at creation, so the command survives a
        reload without anything having to re-attach it.

        `add` rather than `add_default`: a default cmdset is the one an object
        falls back to when every other is removed, which is the right shape for
        an NPC that must always be talkable. The egg is one command that either
        applies or does not, and add() keeps it out of that fallback slot.

    Notes/References:
        Inheriting BaseItem rather than Object is what makes the egg a real
        inventory item -- `is_stackable` is the attribute Character's
        at_pre_object_receive and at_object_receive test for before routing an
        incoming object into the 32-slot grid. An egg that skipped BaseItem
        would land in contents with no slot: invisible to `inv`, uncounted, and
        still real.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """

    def at_object_creation(self) -> None:
        """
        Purpose: Attach the egg's command set on first creation.

        Entry:
            No conditions.

        Exit/Returns:
            No conditions.

        Module Globals:
            EGG_DEFAULT_DESC read.

        Methodology:
            Call the parent hook, add EggCmdSet persistently, then seed a
            description for an egg created outside the ItemDef path (a
            builder's `create`), which would otherwise have none.

        Notes/References:
            The ItemDef's own desc overwrites this seed when the egg is
            spawned the normal way, because attributes are written after
            creation by the prototype.

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        parent_class = super()
        parent_class.at_object_creation()

        self.cmdset.add(EggCmdSet, persistent=True)

        self.db.desc = EGG_DEFAULT_DESC
