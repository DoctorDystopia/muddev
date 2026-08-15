"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Overrides the default `get` command so picking up a
stackable item that merges into an existing inventory stack does not
crash the pickup announcement.
"""

from evennia import default_cmds
from evennia.commands.cmdset import CmdSet
from evennia.utils import utils


class GetCmd(default_cmds.CmdGet):
    """
    pick up something

    Usage:
      get <obj>

    Picks up an object from your location and puts it in your inventory.
    """

    def func(self):
        """
        Purpose: Move the targeted object(s) from the room into the
            caller's inventory and announce the pickup.

        Entry:
            self.caller is a puppeted Character in a valid location.
            self.args is the raw target string typed by the player.

        Exit/Returns:
            No return value. Sends feedback to the caller and, on
            success, an announcement to the room.

        Methodology:
            Identical to `evennia.commands.default.general.CmdGet`,
            except the grouped display name is resolved from the
            still-live search results before any object is moved.
            Blackout's `InventoryHandler.add_item` merges stackable
            pickups into an existing stack and deletes the moved
            object as part of that merge (typeclasses/characters.py
            `at_object_receive`), which nulls its primary key. Vanilla
            resolves the display name from `moved[0]` *after* the
            move loop, so it dereferences a deleted object and raises
            ValueError. Resolving the name first avoids that.

        Notes/References: see CLAUDE.md "Evennia gotchas found the
            hard way" item 4 for the same delete-during-move hazard.

        Author: Nick Hobar
        Creation date: 08/14/2026
        """
        caller = self.caller

        if not self.args:
            self.msg("Get what?")
            return

        objs = caller.search(self.args, location=caller.location, stacked=self.number)
        if not objs:
            return
        objs = utils.make_iter(objs)

        if len(objs) == 1 and caller == objs[0]:
            self.msg("You can't get yourself.")
            return

        for obj in objs:
            if not obj.access(caller, "get"):
                if obj.db.get_err_msg:
                    self.msg(obj.db.get_err_msg)
                else:
                    self.msg("You can't get that.")
                return
            if not obj.at_pre_get(caller):
                return

        obj_name = objs[0].get_numbered_name(len(objs), caller, return_string=True)

        moved = []
        for obj in objs:
            if obj.move_to(caller, quiet=True, move_type="get"):
                moved.append(obj)
                obj.at_get(caller)

        if not moved:
            self.msg("That can't be picked up.")
        else:
            caller.location.msg_contents(f"$You() $conj(pick) up {obj_name}.", from_obj=caller)


class GetCmdSet(CmdSet):
    """
    Purpose: Wraps GetCmd for registration on CharacterCmdSet.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """

    key = "GetCmdSet"

    def at_cmdset_creation(self):
        self.add(GetCmd())
