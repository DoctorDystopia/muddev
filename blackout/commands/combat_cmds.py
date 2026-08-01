"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Twitch combat commands — attack, hold, flee, wield.
"""

from evennia import CmdSet, Command

from systems.combat.combat import ensure_combat_handler


class CmdAttack(Command):
    """Culture: attack <target> — begin twitch melee against the designated creature."""

    key = "attack"
    aliases = ["kill", "hit", "fight"]
    help_category = "Combat"

    def func(self) -> None:
        caller = self.caller

        target_name = self.args.strip()
        if not target_name:
            caller.msg("Attack what?")
            return

        target = caller.search(target_name)
        if target is None:
            return

        if not hasattr(target, "is_alive"):
            caller.msg(f"You can't attack {target.key}.")
            return

        # Per twitch-tutorial combat_twitch.py:335, give EACH side its own
        # handler. Note this does NOT make the NPC fight back: nothing queues
        # an action for it and there is no AI hook yet. The target's handler
        # exists so it registers as a combatant for get_sides/check_stop_combat.
        ensure_combat_handler(target)
        handler = ensure_combat_handler(caller)

        handler.queue_action({"kind": "attack", "target": target})
        caller.msg(f"|gYou begin attacking |w{target.key}|g.|n")


class CmdHold(Command):
    """Command hold — stop auto-attacking, await further instructions."""

    key = "hold"
    help_category = "Combat"

    def func(self) -> None:
        caller = self.caller
        handler = caller.combat
        if handler is None:
            caller.msg("You aren't in combat.")
            return

        handler.queue_action({"kind": "hold"})
        caller.msg("|xYou hold your attack.|n")


class CmdFlee(Command):
    """Command flee — attempt to escape combat."""

    key = "flee"
    aliases = ["run", "escape"]
    help_category = "Combat"

    def func(self) -> None:
        caller = self.caller
        handler = caller.combat
        if handler is None:
            caller.msg("You aren't in combat.")
            return

        handler.queue_action({"kind": "flee"})
        caller.msg("|xYou brace to flee on your next opening.|n")


class CmdWield(Command):
    """Command wield <weapon> — quickly equip a weapon during combat."""

    key = "wield"
    help_category = "Combat"

    def func(self) -> None:
        caller = self.caller
        handler = caller.combat
        if handler is None:
            caller.msg("You aren't in combat, so just equip with the 'equip' command.")
            return

        weapon_key = self.args.strip()
        if not weapon_key:
            caller.msg("Usage: wield <weapon>")
            return

        weapon = caller.search(weapon_key)
        if weapon is None:
            return

        handler.queue_action({"kind": "wield", "weapon": weapon})


class CombatCmdSet(CmdSet):
    """
    Purpose: CmdSet containing combat management commands.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module Globals:
        None

    Methodology:
        Adds combat commands to the cmdset during creation.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    key = "CombatCmdSet"


    def at_cmdset_creation(self) -> None:
        """
        Purpose: Populates the cmdset with combat commands.

        Entry:
            No conditions

        Exit/Returns:
            No conditions

        Module Globals:
            None

        Methodology:
            Instantiates and adds combat commands to this cmdset.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/13/2026
        """
        attack_cmd = CmdAttack()
        hold_cmd = CmdHold()
        flee_cmd = CmdFlee()
        wield_cmd = CmdWield()

        self.add(attack_cmd)
        self.add(hold_cmd)
        self.add(flee_cmd)
        self.add(wield_cmd)
