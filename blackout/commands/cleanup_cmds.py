"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/16/2026
Description: Admin cleanup commands for bulk item destruction.
"""

from commands.command import Command
from commands.constants import HELP_CATEGORY_ADMIN
from evennia import CmdSet
from systems.statefeed import constants as feed_const

# Every line this module sends a player is the server speaking as itself, so
# the routing tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_SYSTEM = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_SYSTEM}



class CmdDestroyItems(Command):
    """
    Purpose: Destroys all items matching a given name from inventory.
    Supports local (caller's inventory) and global (all characters) scope.

    Entry:
        self.caller is a valid Evennia Character object
        self.args expects format: "all [global] <item name>"

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        Parses the argument string for the 'all' prefix, optional 'global'
        keyword, and the item name. Searches the appropriate scope for
        items with matching names and deletes them.

    Notes/References:
        Does NOT conflict with Evennia's built-in @destroy command.

    Author: Nick Hobar
    Creation date: 07/16/2026
    """
    key = "purge"
    locks = "cmd:perm(Builder)"
    help_category = HELP_CATEGORY_ADMIN


    def func(self) -> None:
        """
        Purpose: Executes the destroy items command.

        Entry:
            self.caller is a valid Evennia Character object
            self.args is the command arguments string

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Parses the argument string. If the first word is "all",
            checks for an optional "global" keyword. Searches inventory
            (or all characters if global) and deletes matching items.
            Reports the count of deleted items.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/16/2026
        """
        caller = self.caller
        clean_args = self.args.strip()

        if not clean_args:
            caller.msg(("Usage: destroy all [global] <item name>", _MSG_SYSTEM))
            return

        if not clean_args.lower().startswith("all "):
            caller.msg(("Usage: destroy all [global] <item name>", _MSG_SYSTEM))
            return

        rest = clean_args[4:].strip()
        if not rest:
            caller.msg(("Usage: destroy all [global] <item name>", _MSG_SYSTEM))
            return

        is_global = rest.lower().startswith("global ")
        if is_global:
            item_name = rest[7:].strip()
        else:
            item_name = rest

        if not item_name:
            caller.msg(("Usage: destroy all [global] <item name>", _MSG_SYSTEM))
            return

        if is_global:
            from typeclasses.characters import Character
            total = 0
            for char in Character.objects.all():
                count = 0
                for item in list(char.contents):
                    if item.key.lower() == item_name.lower():
                        item.delete()
                        count += 1
                for item in list(char.equipment.all()):
                    if item.key.lower() == item_name.lower():
                        char.equipment.remove(item)
                        item.delete()
                        count += 1
                if count:
                    total += count
            caller.msg(
                (f"Globally destroyed {total} items named '{item_name}'.", _MSG_SYSTEM))
        else:
            count = 0
            for item in list(caller.contents):
                if item.key.lower() == item_name.lower():
                    item.delete()
                    count += 1
            for item in list(caller.equipment.all()):
                if item.key.lower() == item_name.lower():
                    caller.equipment.remove(item)
                    item.delete()
                    count += 1
            caller.msg(
                (f"Destroyed {count} items named '{item_name}' from your inventory.",
                 _MSG_SYSTEM))



class CleanupCmdSet(CmdSet):
    """
    Purpose: CmdSet containing cleanup and item destruction commands.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        Adds CmdDestroyItems to the cmdset during creation.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/16/2026
    """
    key = "CleanupCmdSet"


    def at_cmdset_creation(self) -> None:
        """
        Purpose: Populates the cmdset with cleanup commands.

        Entry:
            No conditions

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Instantiates and adds CmdDestroyItems to this cmdset.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/16/2026
        """
        self.add(CmdDestroyItems())
