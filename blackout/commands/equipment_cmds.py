
"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Commands for equipment and inventory management.

             `equip` with no argument still opens the EvMenu it always has.
             With an argument it equips directly, and `unequip` is its inverse.

             Those argument forms exist because an EvMenu cannot be driven by a
             graphical client. A menu is a stateful cmdset that captures the
             player's TEXT input, so a 3D pane firing `equip` would trap them
             in a menu they never opened -- and the pane's standing rule is
             that it sends only what a telnet player could type. Drag-to-equip
             had nothing to send until these existed.
"""



from commands.command import Command
from commands.constants import HELP_CATEGORY_GENERAL
from commands.inventory_cmds import resolve_carried_item
from evennia import CmdSet
from items.equipment.constants import WieldLocation
from items.equipment.handler import EquipmentError
from systems.ui.colors import ERROR_COLOR, RESET_COLOR, SUCCESS_COLOR


# Public constant definitions
EQUIPMENT_MODULE_PATH = "systems.menus.equipment_menu"

# What a player may type in place of a slot value. WieldLocation.value spells
# slots with underscores ("main_hand"); nobody types that, so a space is
# accepted and folded to the canonical form.
SLOT_WORD_SEPARATOR: str = " "
SLOT_VALUE_SEPARATOR: str = "_"


# ─── Private helper routines ─────────────────────────────────────────────────

def _resolve_slot(text: str):
    """Return the WieldLocation `text` names, or None.

    Accepts the canonical value ("main_hand") and the spaced form a player
    would actually type ("main hand"). Matching is done against the enum rather
    than a lookup table here, so a new slot needs no edit in this module --
    the same reason WieldLocation.label is derived rather than tabulated.
    """
    folded = text.strip().lower().replace(
        SLOT_WORD_SEPARATOR, SLOT_VALUE_SEPARATOR
    )

    for slot in WieldLocation:
        if slot.value == folded:
            return slot

    return None


def _resolve_equipped_item(caller, text: str):
    """
    Purpose: Resolve "main hand" or "toy sword" to a currently equipped item.

    Entry:
        caller - the puppeted Character.
        text   - a raw argument, already stripped and non-empty.

    Exit/Returns:
        Returns the equipped object, or None having already messaged the
        caller.

    Module Globals:
        None.

    Methodology:
        Slot name first, item name second, mirroring resolve_carried_item's
        slot-before-name ordering so the two commands behave the same way.

        Name matching is done by hand rather than through caller.search
        because EquipmentHandler.equip holds equipped items at location=None.
        They are in no contents list anywhere, so Evennia's search cannot see
        them -- which is correct for every other command and is exactly why
        this one needs its own lookup.

    Notes/References:
        Exact matches win over partial ones, so a "sword" that is also the
        prefix of "sword of something" resolves to the item actually named.

    Author: Nick Hobar
    Creation date: 08/15/2026
    """
    handler = caller.equipment
    slot = _resolve_slot(text)

    if slot is not None:
        item = handler.slots.get(slot)

        if item is None:
            caller.msg(
                f"{ERROR_COLOR}Nothing is equipped in your "
                f"{slot.label}.{RESET_COLOR}"
            )
            return None

        return item

    wanted = text.lower()
    equipped = handler.all()
    exact = [item for item in equipped if item.key.lower() == wanted]

    if exact:
        return exact[0]

    partial = [item for item in equipped if wanted in item.key.lower()]

    if not partial:
        caller.msg(
            f"{ERROR_COLOR}You have nothing equipped called "
            f"'{text}'.{RESET_COLOR}"
        )
        return None

    if len(partial) > 1:
        names = ", ".join(item.key for item in partial)
        caller.msg(
            f"{ERROR_COLOR}Which one? You are wearing: {names}.{RESET_COLOR}"
        )
        return None

    return partial[0]


# ─── Public routines / Classes ───────────────────────────────────────────────

class CmdEquipment(Command):
    """
    wear or wield something, or open the equipment screen

    Usage:
      equip
      equip <slot number>
      equip <item name>

    With no argument this opens the equipment menu. With one it equips the
    named item straight from your inventory, where <slot number> is the number
    shown beside it by `inventory`.

    Example:
      equip 7
      equip toy sword
    """

    key = "equip"
    aliases = ["equipment", "wear"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_GENERAL


    def func(self) -> None:
        """
        Purpose: Equip a named item, or launch the equipment menu.

        Entry:
            self.caller is a valid Evennia Character object.
            self.args is an optional slot number or item name.

        Exit/Returns:
            No return value. Messages the caller either way.

        Module Globals:
            EQUIPMENT_MODULE_PATH read.

        Methodology:
            The no-argument path is untouched and still opens the menu, so no
            player's muscle memory changes. Both paths converge on
            EquipmentHandler.equip, which owns the skill gate and the capacity
            check -- this command adds no rule of its own, it only resolves a
            target and reports the outcome.

        Notes/References:
            No feed emit here. EquipmentHandler.equip publishes it, so the
            menu path gets the same update without this command and the
            menu each remembering to send one.

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        caller = self.caller
        target_text = self.args.strip()

        if not target_text:
            from evennia.utils.evmenu import EvMenu

            EvMenu(
                caller,
                EQUIPMENT_MODULE_PATH,
                startnode="start",
            )
            return

        _slot, item = resolve_carried_item(caller, target_text)

        if item is None:
            return

        try:
            caller.equipment.equip(item)
        except EquipmentError as equip_err:
            caller.msg(f"{ERROR_COLOR}{equip_err}{RESET_COLOR}")
            return

        caller.msg(f"{SUCCESS_COLOR}You equip {item.key}.{RESET_COLOR}")



class CmdUnequip(Command):
    """
    take off something you are wearing or wielding

    Usage:
      unequip <slot>
      unequip <item name>

    Returns an equipped item to your inventory. <slot> is a slot name such as
    'main hand' or 'body'.

    Note for maintainers: never write a vertical bar in this command's
    player-facing text. Evennia's ANSI parser reads "|i" as a markup code and
    eats it, so "unequip <slot|item>" reaches the player as "unequip
    <slottem>".

    Example:
      unequip main hand
      unequip toy sword
    """

    key = "unequip"
    aliases = ["remove"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_GENERAL


    def func(self) -> None:
        """
        Purpose: Return an equipped item to the inventory grid.

        Entry:
            self.caller is a valid Evennia Character object.
            self.args names a slot or an equipped item.

        Exit/Returns:
            No return value. Messages the caller either way.

        Module Globals:
            None.

        Methodology:
            Delegates to EquipmentHandler.unequip, which owns the "your
            inventory is full" refusal. Resolving the target here and the rule
            there is the same split CmdEquipment uses.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 08/15/2026
        """
        caller = self.caller
        target_text = self.args.strip()

        if not target_text:
            caller.msg("Usage: unequip <slot or item>")
            return

        if not hasattr(caller, "equipment"):
            caller.msg(f"{ERROR_COLOR}You cannot equip anything.{RESET_COLOR}")
            return

        item = _resolve_equipped_item(caller, target_text)

        if item is None:
            return

        try:
            caller.equipment.unequip(item)
        except EquipmentError as unequip_err:
            caller.msg(f"{ERROR_COLOR}{unequip_err}{RESET_COLOR}")
            return

        caller.msg(f"{SUCCESS_COLOR}You remove {item.key}.{RESET_COLOR}")



class EquipmentCmdSet(CmdSet):
    """
    Purpose: CmdSet containing equipment management commands.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        Adds CmdEquipment and CmdUnequip to the cmdset during creation.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key = "EquipmentCmdSet"


    def at_cmdset_creation(self) -> None:
        """
        Purpose: Populates the cmdset with equipment commands.

        Entry:
            No conditions

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Instantiates and adds the equipment commands to this cmdset.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        equip_cmd = CmdEquipment()
        unequip_cmd = CmdUnequip()
        self.add(equip_cmd)
        self.add(unequip_cmd)
