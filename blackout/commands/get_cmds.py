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
from systems.statefeed import constants as feed_const

# Every line this module sends a player is about your inventory, so the
# routing tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_INVENTORY = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_INVENTORY}

# Private constant definitions

_MIN_AMBIGUOUS_MATCHES = 2
_LOWEST_STACK_SUFFIX = "-1"


# Private helper routines

def _is_single_stacked_group(caller, matches) -> bool:
    """
    Purpose: Decide whether an ambiguous set of search matches is really
        just one item duplicated on the ground, rather than several
        distinct items that happen to share a partial name match.

    Entry:
        caller  - the searching Character, passed through to
                  get_display_name so grouping matches what Evennia's own
                  multimatch error would show the player.
        matches - the raw (unfiltered) list of objects a quiet search
                  returned.

    Exit/Returns:
        Returns True only when every match shares the same display name,
        meaning a plain "get <name>" is unambiguous in intent even though
        the search itself is not. Returns False for 0 or 1 matches, or
        for a mix of distinct items (e.g. "sword" matching both "long
        sword" and "short sword"), where auto-resolving could hand the
        player the wrong object.

    Module Globals:
        _MIN_AMBIGUOUS_MATCHES read.

    Methodology:
        Mirrors the grouping key `evennia.utils.utils.at_search_result`
        uses to number multimatch results ("chunk-1", "chunk-2", ...):
        `get_display_name`. Matching that key is what guarantees the
        first entry here is the same object the engine would label "-1".

    Author: Nick Hobar
    Creation date: 08/15/2026
    """
    if len(matches) < _MIN_AMBIGUOUS_MATCHES:
        return False

    names = set()
    for match in matches:
        if hasattr(match, "get_display_name"):
            names.add(match.get_display_name(caller))
        else:
            names.add(str(match))

    return len(names) == 1


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
            except for two changes:

            1. When the player gives no explicit count and the target
               name is ambiguous only because several copies of the
               same item are lying around (a loot drop that spawned
               separate instances instead of one quantity-N stack),
               resolve to the lowest-numbered copy ("<name>-1") instead
               of making the player retype the target with a suffix
               they cannot see without a matching text-channel message.
               See `_is_single_stacked_group`. A click in the 3D pane
               sends the bare name via `interact_command`
               (systems/statefeed/serializers.py) and has no way to
               supply a suffix, so without this the pane's "get" affords
               nothing once a stack has more than one instance.
            2. The grouped display name is resolved from the still-live
               search results before any object is moved. Blackout's
               `InventoryHandler.add_item` merges stackable pickups into
               an existing stack and deletes the moved object as part of
               that merge (typeclasses/characters.py `at_object_receive`),
               which nulls its primary key. Vanilla resolves the display
               name from `moved[0]` *after* the move loop, so it
               dereferences a deleted object and raises ValueError.
               Resolving the name first avoids that.

        Notes/References: see CLAUDE.md "Evennia gotchas found the
            hard way" item 4 for the same delete-during-move hazard.

        Author: Nick Hobar
        Creation date: 08/14/2026
        """
        caller = self.caller

        if not self.args:
            self.msg(("Get what?", _MSG_INVENTORY))
            return

        if not self.number:
            quiet_matches = utils.make_iter(
                caller.search(self.args, location=caller.location, quiet=True)
            )
            if _is_single_stacked_group(caller, quiet_matches):
                self.args = self.args + _LOWEST_STACK_SUFFIX

        objs = caller.search(self.args, location=caller.location, stacked=self.number)
        if not objs:
            return
        objs = utils.make_iter(objs)

        if len(objs) == 1 and caller == objs[0]:
            self.msg(("You can't get yourself.", _MSG_INVENTORY))
            return

        for obj in objs:
            if not obj.access(caller, "get"):
                if obj.db.get_err_msg:
                    self.msg((obj.db.get_err_msg, _MSG_INVENTORY))
                else:
                    self.msg(("You can't get that.", _MSG_INVENTORY))
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
            self.msg(("That can't be picked up.", _MSG_INVENTORY))
        else:
            caller.location.msg_contents(
                (f"$You() $conj(pick) up {obj_name}.", _MSG_INVENTORY), from_obj=caller)


class GetCmdSet(CmdSet):
    """
    Purpose: Wraps GetCmd for registration on CharacterCmdSet.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """

    key = "GetCmdSet"

    def at_cmdset_creation(self):
        self.add(GetCmd())
