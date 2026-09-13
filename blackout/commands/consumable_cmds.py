"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: `eat` — the command behind the food chain's last stage.

             On the CHARACTER's cmdset rather than a facility's, unlike every
             other verb in this chain. Butchery needs a corpse, rendering needs
             a cooker, curing needs a chamber; eating needs only a bag, and the
             moment it mattered most is the one where the player is nowhere near
             a building.
"""



from evennia import Command, CmdSet

from commands.constants import HELP_CATEGORY_CRAFTING
from commands.inventory_cmds import resolve_carried_item
from systems.gameplay.consumables import constants as consumable_const
from systems.gameplay.consumables import service as consumables



class CmdEat(Command):
    """
    Eat something you are carrying.

    Usage:
        eat <slot number>
        eat <item name>

    Restores hit points, capped at your maximum -- eating at full health
    destroys the food and heals nothing. Eating briefly delays your next bite,
    and in a fight it delays your next attack.
    """

    key = "eat"
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_CRAFTING


    def func(self) -> None:
        """
        Purpose: Resolve the named item and eat it.

        Entry:
            self.caller is a puppeted Character. self.args may be empty.

        Exit/Returns:
            No conditions.

        Module Globals:
            consumable_const read.

        Methodology:
            Resolution is resolve_carried_item's, shared with `equip`, `drop`
            and `inspect` -- slot number first, then name. That is what lets the
            graphical pane send `eat 7` and a telnet player type
            `eat cured chuck`, and it is the reason the pane can be honest about
            which of three identical chucks it means.

            Everything after resolution is the service's. This command decides
            nothing about what food is, what it heals or how long the delays
            are; it refuses an empty argument and hands over an object.

        Notes/References:
            systems/gameplay/consumables/service.py eat().

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        caller = self.caller
        argument = self.args.strip()

        if not argument:
            caller.msg(consumable_const.MSG_NOTHING_NAMED)
            return

        _index, item = resolve_carried_item(caller, argument)

        if item is None:
            return

        consumables.eat(caller, item)



class ConsumableCmdSet(CmdSet):
    """Stores the consumable commands available to every character."""

    key = "consumable_cmdset"
    priority = 1


    def at_cmdset_creation(self) -> None:
        eat_command = CmdEat()
        self.add(eat_command)
