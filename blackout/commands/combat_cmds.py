"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Twitch combat commands — attack, hold, flee, wield.
"""

from evennia import CmdSet, Command

from commands.constants import HELP_CATEGORY_COMBAT
from systems.combat import combat_msg, constants as const
from systems.combat.auras.aura_handler import ensure_aura_handler, get_aura_handler_for
from systems.combat.auras.registry import AURA_REGISTRY, find_aura
from systems.combat.combat import active_combat_style_key, ensure_combat_handler, held_weapon
from systems.combat.rules.introspect import describe_action_rules, describe_registry


# Argument that switches the active aura off rather than naming one to light.
AURA_OFF_ARG = "off"

# Argument that widens @combatrules from "my gear" to "everything registered".
COMBAT_RULES_ALL_ARG = "all"


class CmdAttack(Command):
    """Culture: attack <target> — begin twitch melee against the designated creature."""

    key = "attack"
    aliases = ["kill", "hit", "fight"]
    help_category = HELP_CATEGORY_COMBAT

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

        weapon = held_weapon(caller)
        weapon_name = weapon.key if weapon is not None else const.UNARMED_WEAPON_NAME
        style_key = active_combat_style_key(weapon) if weapon is not None else const.UNARMED_DEFAULT_COMBAT_STYLE
        style_name = (style_key or const.UNARMED_DEFAULT_COMBAT_STYLE).title()
        caller.msg(
            f"|gYou begin attacking |w{target.key}|g with |w{weapon_name}|g "
            f"using |w{style_name}|g style.|n"
        )

        # Opening HP readout. Without it the first bar the player sees is the
        # one AFTER a hit has already landed, so there is nothing to read the
        # drop against.
        opening_hp = combat_msg.format_hp_status(
            target.key, target.hp, target.max_hp
        )
        caller.msg(opening_hp)


class CmdHold(Command):
    """Command hold — stop auto-attacking, await further instructions."""

    key = "hold"
    help_category = HELP_CATEGORY_COMBAT

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
    help_category = HELP_CATEGORY_COMBAT

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
    help_category = HELP_CATEGORY_COMBAT

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


class CmdAura(Command):
    """Command aura [<name>|off] — toggle a damage aura, or list what you have.

    An aura keeps burning every hostile around you on the combat tick until you
    switch it off. It costs no action and does not interrupt attacking.

    Usage:
        aura                  list your auras and which one is lit
        aura righteous fire   ignite an aura
        aura off              extinguish the active aura
    """

    key = "aura"
    aliases = ["auras"]
    help_category = HELP_CATEGORY_COMBAT

    def func(self) -> None:
        caller = self.caller
        argument = self.args.strip()

        if not argument:
            self._list_auras()
            return

        if argument.lower() == AURA_OFF_ARG:
            self._extinguish()
            return

        self._ignite(argument)

    def _list_auras(self) -> None:
        """Show every registered aura and mark the one currently burning."""
        caller = self.caller

        if not AURA_REGISTRY:
            caller.msg("You know of no auras.")
            return

        handler = get_aura_handler_for(caller)
        active_aura = handler.get_aura() if handler is not None else None
        active_key = active_aura.key if active_aura is not None else None

        lines = ["|wAuras|n"]

        for aura in AURA_REGISTRY.values():
            allowed, reason = aura.can_activate(caller)

            if aura.key == active_key:
                status = "|gburning|n"
            elif allowed:
                status = "|xready|n"
            else:
                status = f"|r{reason}|n"

            lines.append(f"  |y{aura.name}|n — {status}")

        caller.msg("\n".join(lines))

    def _extinguish(self) -> None:
        """Stop the caller's active aura, if any."""
        caller = self.caller

        handler = get_aura_handler_for(caller)
        if handler is None:
            caller.msg("You have no aura burning.")
            return

        aura = handler.get_aura()
        handler.stop_aura()

        if aura is not None:
            caller.msg(combat_msg.format_aura_deactivate(aura))

    def _ignite(self, argument: str) -> None:
        """Resolve a name to an aura and switch it on."""
        caller = self.caller

        aura = find_aura(argument)
        if aura is None:
            caller.msg(f"You know no aura called '{argument}'.")
            return

        allowed, reason = aura.can_activate(caller)
        if not allowed:
            caller.msg(f"|r{reason}|n")
            return

        # Re-lighting the aura already burning is a no-op rather than a silent
        # cadence reset -- otherwise spamming the command would delay every
        # pulse forever.
        handler = get_aura_handler_for(caller)
        if handler is not None and handler.get_aura() is aura:
            caller.msg(f"{aura.name} is already burning.")
            return

        handler = ensure_aura_handler(caller)
        handler.activate(aura)

        caller.msg(combat_msg.format_aura_activate(aura))


class CmdCombatRules(Command):
    """Command @combatrules [all] — show which rules govern your actions.

    An action resolves nine seams by priority across every equipment slot, so
    what a given weapon actually does depends on everything else worn with it.
    This is the only place that resolution is readable: logging it as it
    happens would print roughly a hundred lines a minute per combatant.

    Usage:
        @combatrules       what your current gear does to your actions
        @combatrules all   every rules definition the game knows about
    """

    key = "@combatrules"
    aliases = ["combatrules"]
    locks = "cmd:perm(Builder)"
    help_category = HELP_CATEGORY_COMBAT

    def func(self) -> None:
        caller = self.caller
        argument = self.args.strip().lower()

        if argument == COMBAT_RULES_ALL_ARG:
            caller.msg(describe_registry())
            return

        caller.msg(describe_action_rules(caller))


class CmdCombatOptions(Command):
    """Command combatoptions — pick which combat style your wielded weapon uses.

    Each weapon offers a handful of named styles (e.g. a shortsword's
    accurate/aggressive/defensive stances). The active style decides which
    stat gets an invisible level boost for the swing and which skill(s)
    earn XP from the damage dealt. Switching is free and instant.

    Usage:
        combatoptions   (aliases: stance, combatstyle)
    """

    key = "combatoptions"
    aliases = ["stance", "combatstyle"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_COMBAT

    def func(self) -> None:
        caller = self.caller

        from evennia.utils.evmenu import EvMenu

        EvMenu(
            caller,
            "systems.menus.combat_options_menu",
            startnode="start",
        )


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
        aura_cmd = CmdAura()
        combat_rules_cmd = CmdCombatRules()
        combat_options_cmd = CmdCombatOptions()

        self.add(attack_cmd)
        self.add(hold_cmd)
        self.add(flee_cmd)
        self.add(wield_cmd)
        self.add(aura_cmd)
        self.add(combat_rules_cmd)
        self.add(combat_options_cmd)
