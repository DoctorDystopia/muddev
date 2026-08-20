"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/17/2026
Description: Overrides the default `drop` command so it can name a target
that a graphical client is able to point at.

             Two additions over vanilla, for two different callers:

             `drop <slot>` is the unambiguous form and the one the 3D
             inventory pane sends. It is the same slot-before-name ordering
             `equip` uses -- see commands.inventory_cmds.resolve_carried_item,
             which documents why a pane must never send a bare name.

             `drop <name>` with several identical copies carried resolves to
             the lowest-numbered one rather than printing a multimatch wall.
             That path is for the player TYPING, who otherwise has to retype
             the target with a "-1" suffix they were just shown.
"""

from commands.inventory_cmds import parse_slot_number
from evennia import default_cmds
from evennia.commands.cmdset import CmdSet
from evennia.utils import utils
from systems.ui.colors import ERROR_COLOR, RESET_COLOR

# Private constant definitions

_MIN_AMBIGUOUS_MATCHES = 2
_LOWEST_STACK_SUFFIX = "-1"


# Private helper routines

def _is_single_stacked_group(caller, matches) -> bool:
    """
    Purpose: Decide whether an ambiguous set of search matches is really
        just one item duplicated in the caller's inventory, rather than
        several distinct items that happen to share a partial name match.

    Entry:
        caller  - the searching Character, passed through to
                  get_display_name so grouping matches what Evennia's own
                  multimatch error would show the player.
        matches - the raw (unfiltered) list of objects a quiet search
                  returned.

    Exit/Returns:
        Returns True only when every match shares the same display name,
        meaning a plain "drop <name>" is unambiguous in intent even though
        the search itself is not. Returns False for 0 or 1 matches, or for
        a mix of distinct items, where auto-resolving could hand the
        player the wrong object.

    Module Globals:
        _MIN_AMBIGUOUS_MATCHES read.

    Methodology:
        Mirrors commands.get_cmds._is_single_stacked_group, which solves
        the identical problem for `get`. Duplicated rather than imported
        because the two commands search different candidate pools
        (inventory here, room contents there) and keeping the helper local
        to each file matches this repo's existing convention.

    Notes/References:
        See commands/get_cmds.py for the "get" side of this same fix.

    Author: Nick Hobar
    Creation date: 08/17/2026
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


class DropCmd(default_cmds.CmdDrop):
    """
    drop something

    Usage:
      drop <slot number>
      drop <obj>
      drop <count> <obj>

    Lets you drop an object from your inventory into the location you are
    currently in. <slot number> is the number shown beside the item by
    `inventory`, and is the unambiguous way to name one of several identical
    copies.

    Example:
      drop 7
      drop rusty metal chunk
      drop 3 rusty metal chunk
    """

    def _resolve_by_slot(self, caller):
        """
        Purpose: Resolve a bare `drop <slot number>` to the one item that
            occupies that grid slot.

        Entry:
            caller - the puppeted Character. self.args is the raw argument.

        Exit/Returns:
            Returns the object in that slot; None when the argument is not a
            slot number at all, which leaves the name path to handle it.
            Messages the caller and returns None for a valid-but-empty slot.

        Module Globals:
            None.

        Methodology:
            Tried BEFORE the name path, matching resolve_carried_item's
            slot-before-name ordering so `drop 7` and `equip 7` mean the same
            kind of thing. This is the form the 3D pane sends, because a slot
            is the only target it can name that the server will resolve to the
            item the player actually clicked.

            An out-of-range number returns None rather than erroring, so
            `drop 99` still reaches the name path and fails as "you aren't
            carrying 99" -- the same words a mistyped name produces.

            The count form (`drop 3 chunk`) never lands here: parse() has
            already split the leading number into self.number, so self.args
            holds the name alone.

        Notes/References:
            parse_slot_number owns the 1-based to 0-based conversion and the
            bounds check; this routine adds only the empty-slot message.

        Author: Nick Hobar
        Creation date: 08/17/2026
        """
        index = parse_slot_number(self.args)

        if index < 0:
            return None

        inventory = getattr(caller, "inventory", None)

        if inventory is None:
            return None

        item = inventory.get_slot_content(index)

        if item is None:
            self.msg(f"{ERROR_COLOR}Slot {self.args} is empty.{RESET_COLOR}")
            return None

        return item

    def func(self):
        """
        Purpose: Move the targeted carried object(s) into the caller's
            current location and announce the drop.

        Entry:
            self.caller is a puppeted Character in a valid location.
            self.args is a slot number, an item name, or a name preceded
            by a count that parse() has already split off.

        Exit/Returns:
            No return value. Sends feedback to the caller and, on
            success, an announcement to the room.

        Methodology:
            Three ways in, in this order:

            1. A bare slot number, which the 3D pane sends and which names
               exactly one item. See _resolve_by_slot.
            2. A name plus a count ("drop 3 chunk"), handled by vanilla's
               `stacked` search.
            3. A bare name. When it is ambiguous ONLY because several
               identical copies are carried, resolve to the lowest-numbered
               one rather than printing a multimatch wall the player would
               have to retype past. See _is_single_stacked_group.

            Case 3 is deliberately NOT what the pane relies on. It picks the
            first copy, which is right for a player typing a name they cannot
            disambiguate anyway and wrong for a click on a specific item --
            that is the bug case 1 exists to fix.

        Notes/References: see commands/get_cmds.py for the `get` side of the
            case-3 auto-resolve, and commands/inventory_cmds.py
            resolve_carried_item for the slot-before-name convention.

        Author: Nick Hobar
        Creation date: 08/17/2026
        """
        caller = self.caller

        if not self.args:
            self.msg("Drop what?")
            return

        by_slot = None

        if not self.number:
            by_slot = self._resolve_by_slot(caller)

            if by_slot is None and parse_slot_number(self.args) >= 0:
                # A valid slot number that was empty. _resolve_by_slot has
                # already said so; falling through would report it a second
                # time as a missing item name.
                return

        if by_slot is not None:
            objs = [by_slot]
        else:
            if not self.number:
                quiet_matches = utils.make_iter(
                    caller.search(self.args, location=caller, quiet=True)
                )
                if _is_single_stacked_group(caller, quiet_matches):
                    self.args = self.args + _LOWEST_STACK_SUFFIX

            objs = caller.search(
                self.args,
                location=caller,
                nofound_string=f"You aren't carrying {self.args}.",
                multimatch_string=f"You carry more than one {self.args}:",
                stacked=self.number,
            )
            if not objs:
                return
            objs = utils.make_iter(objs)

        for obj in objs:
            if not obj.at_pre_drop(caller):
                return

        moved = []
        for obj in objs:
            if obj.move_to(caller.location, quiet=True, move_type="drop"):
                moved.append(obj)
                obj.at_drop(caller)

        if not moved:
            self.msg("That can't be dropped.")
        else:
            obj_name = moved[0].get_numbered_name(len(moved), caller, return_string=True)
            caller.location.msg_contents(f"$You() $conj(drop) {obj_name}.", from_obj=caller)


class DropCmdSet(CmdSet):
    """
    Purpose: Wraps DropCmd for registration on CharacterCmdSet.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """

    key = "DropCmdSet"

    def at_cmdset_creation(self):
        self.add(DropCmd())
