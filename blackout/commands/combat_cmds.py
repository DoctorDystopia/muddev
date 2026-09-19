"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Twitch combat commands — attack, hold, flee, wield.
"""

from evennia import CmdSet, Command

from commands.constants import HELP_CATEGORY_COMBAT
from systems.gameplay.combat import combat_msg, constants as const, pvp, reach, style_options
from systems.gameplay.combat.protocols import Combatant
from systems.gameplay.combat.auras.aura_handler import ensure_aura_handler, get_aura_handler_for
from systems.gameplay.combat.auras.registry import AURA_REGISTRY, find_aura
from systems.core.tick import debug as tick_debug
from systems.gameplay.combat.combat import (
    active_combat_style_key,
    available_combat_styles,
    combat_profile,
    ensure_combat_handler,
    held_weapon,
    set_combat_style,
)
from systems.gameplay.combat.rules.introspect import describe_action_rules, describe_registry
from systems.interface.ui import colors
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed

# Every line this module sends a player is combat, so the routing tag is
# bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/interface/statefeed/constants.py.
_MSG_COMBAT = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_COMBAT}


# Argument that switches the active aura off rather than naming one to light.
AURA_OFF_ARG = "off"

# Argument that widens @combatrules from "my gear" to "everything registered".
COMBAT_RULES_ALL_ARG = "all"


class CmdAttack(Command):
    """Culture: attack <target> — begin twitch combat against the designated creature.

    A target your weapon cannot reach is walked to, not refused. The walk ends
    at the nearest tile the weapon covers it from, so a sword closes onto the
    tile and a bow stops at its own range and opens fire.
    """

    key = "attack"
    aliases = ["kill", "hit", "fight"]
    help_category = HELP_CATEGORY_COMBAT

    def func(self) -> None:
        caller = self.caller

        target_name = self.args.strip()
        if not target_name:
            caller.msg(("Attack what?", _MSG_COMBAT))
            return

        # The search must cover everything this command can act on, and this
        # command walks to what it cannot reach -- so it covers the whole
        # engagement radius, not the weapon's. caller.search looks in the room
        # and the inventory, which is one tile of the world, and a player who
        # clicked a raider four tiles away read "You see no such thing".
        #
        # The walk used to be the CLIENT's: it wrapped every far entity's verb
        # in `goto (x,y) then ...`. That is right for a verb that acts where it
        # stands and wrong for `attack`, which walked an archer onto a raider
        # to fire a shot that was legal from where it stood. See
        # SELF_APPROACHING_VERBS.
        # use_dbref, so `attack #75931` resolves for an ordinary player. A
        # name is not an identity: six raiders on one island share one key,
        # and a click on the third of them asked the player which one they
        # meant. The client now sends the dbref the server named, and the
        # candidate list still bounds it -- a dbref outside this radius
        # resolves to nothing, exactly as a name outside it does.
        radius = reach.reach_tiles(combat_profile(caller))
        candidates = reach.search_candidates(caller, const.ENGAGEMENT_RADIUS_TILES)

        target = caller.search(target_name, candidates=candidates, use_dbref=True)
        if target is None:
            return

        if not isinstance(target, Combatant):
            caller.msg((f"You can't attack {target.key}.", _MSG_COMBAT))
            return

        # The PvP rule, BEFORE the walk. The combat handler refuses the same
        # attack at queue time, but by then a far target has already walked
        # the player across the map for nothing.
        refusal = pvp.attack_refusal(caller, target)

        if refusal:
            caller.msg((refusal, _MSG_COMBAT))
            return

        # Out of reach is not a refusal any more. It is a walk, to the NEAREST
        # tile the weapon covers the target from -- which is the target's own
        # tile for every melee weapon, so nothing about closing on a raider
        # with a sword changed.
        if not reach.in_reach(caller, target, radius):
            self._walk_into_range(target, radius)
            return

        # Per twitch-tutorial combat_twitch.py:335, give EACH side its own
        # handler. The target's handler registers it as a combatant for
        # get_sides/check_stop_combat, and -- since the AI landed -- is also
        # what gives a hostile somewhere to be asked for an action: the
        # controller seam in BlackoutCombatHandler.tick consults db.ai_behavior
        # whenever a combatant has no pending action. Still nothing queues one
        # for the target HERE; retaliation begins when the first hit lands and
        # at_damage records who threw it.
        ensure_combat_handler(target)
        handler = ensure_combat_handler(caller)

        handler.queue_action({"kind": "attack", "target": target})

        weapon = held_weapon(caller)
        weapon_name = weapon.key if weapon is not None else const.UNARMED_WEAPON_NAME
        style_key = active_combat_style_key(weapon) if weapon is not None else const.UNARMED_DEFAULT_COMBAT_STYLE
        style_name = (style_key or const.UNARMED_DEFAULT_COMBAT_STYLE).title()
        caller.msg(
            (f"|gYou begin attacking |w{target.key}|g with |w{weapon_name}|g "
            f"using |w{style_name}|g style.|n", _MSG_COMBAT)
        )

        # Opening HP readout. Without it the first bar the player sees is the
        # one AFTER a hit has already landed, so there is nothing to read the
        # drop against.
        opening_hp = combat_msg.format_hp_status(
            target.key, target.hp, target.max_hp
        )
        caller.msg((opening_hp, _MSG_COMBAT))

    def _walk_into_range(self, target, radius: int) -> None:
        """
        Purpose: Walk the caller to the nearest tile its weapon covers
                 `target` from, and attack on arrival.

        Entry:
            target - the entity to close on.
            radius - the caller's reach in tiles, from reach.reach_tiles.

        Exit/Returns:
            No return value. Messages the caller and starts a walk, or
            messages the refusal and starts nothing.

        Module Globals:
            feed_const.ENTITY_APPROACH_TEMPLATE read.

        Methodology:
            THE DESTINATION IS A RING, NOT THE TARGET'S TILE. rooms_in_reach
            asked of the TARGET returns every tile this weapon could shoot it
            from, and the walk goes to whichever of them is nearest. A melee
            weapon covers one tile, its own, so a sword walks exactly where it
            always walked; a bow stops seven tiles out and opens fire from
            there.

            The walk goes through `goto (x,y) then attack <name>` -- the same
            string the client used to build for itself, parsed by the same
            command. The follow-up runs on ARRIVAL and only on arrival, so a
            blocked path ends in a walk that stopped, never in a second
            attempt to close.

        Notes/References:
            A target that shares no geometry with the caller -- another map,
            another Z, a room off the grid -- has no ring to walk to. That is
            the refusal the reach message already words, and it names both
            numbers.

        Author: Nick Hobar
        Creation date: 09/17/2026
        """
        caller = self.caller
        destination = reach.nearest_tile_in_reach(caller, target, radius)

        if destination is None:
            distance = reach.tile_distance(caller, target)
            caller.msg(
                (combat_msg.format_out_of_reach(target, distance, radius),
                 _MSG_COMBAT)
            )
            return

        x, y, _z = destination.xyz
        dbref = feed_const.ENTITY_DBREF_TEMPLATE.format(dbref=target.id)
        command = (
            feed_const.ENTITY_APPROACH_TEMPLATE
            .replace("{x}", str(x))
            .replace("{y}", str(y))
            .replace("{command}", f"{self.key} {dbref}")
        )

        caller.execute_cmd(command)


class CmdHold(Command):
    """Command hold — stop auto-attacking, await further instructions."""

    key = "hold"
    help_category = HELP_CATEGORY_COMBAT

    def func(self) -> None:
        caller = self.caller
        handler = caller.combat
        if handler is None:
            caller.msg(("You aren't in combat.", _MSG_COMBAT))
            return

        handler.queue_action({"kind": "hold"})
        caller.msg(("|xYou hold your attack.|n", _MSG_COMBAT))


class CmdFlee(Command):
    """Command flee — attempt to escape combat."""

    key = "flee"
    aliases = ["run", "escape"]
    help_category = HELP_CATEGORY_COMBAT

    def func(self) -> None:
        caller = self.caller
        handler = caller.combat
        if handler is None:
            caller.msg(("You aren't in combat.", _MSG_COMBAT))
            return

        handler.queue_action({"kind": "flee"})
        caller.msg(("|xYou brace to flee on your next opening.|n", _MSG_COMBAT))


class CmdWield(Command):
    """Command wield <weapon> — quickly equip a weapon during combat."""

    key = "wield"
    help_category = HELP_CATEGORY_COMBAT

    def func(self) -> None:
        caller = self.caller
        handler = caller.combat
        if handler is None:
            caller.msg(
                ("You aren't in combat, so just equip with the 'equip' command.",
                 _MSG_COMBAT))
            return

        weapon_key = self.args.strip()
        if not weapon_key:
            caller.msg(("Usage: wield <weapon>", _MSG_COMBAT))
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
            caller.msg(("You know of no auras.", _MSG_COMBAT))
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

        caller.msg(("\n".join(lines), _MSG_COMBAT))

    def _extinguish(self) -> None:
        """Stop the caller's active aura, if any."""
        caller = self.caller

        handler = get_aura_handler_for(caller)
        if handler is None:
            caller.msg(("You have no aura burning.", _MSG_COMBAT))
            return

        aura = handler.get_aura()
        handler.stop_aura()

        if aura is not None:
            caller.msg((combat_msg.format_aura_deactivate(aura), _MSG_COMBAT))

    def _ignite(self, argument: str) -> None:
        """Resolve a name to an aura and switch it on."""
        caller = self.caller

        aura = find_aura(argument)
        if aura is None:
            caller.msg((f"You know no aura called '{argument}'.", _MSG_COMBAT))
            return

        allowed, reason = aura.can_activate(caller)
        if not allowed:
            caller.msg((f"|r{reason}|n", _MSG_COMBAT))
            return

        # Re-lighting the aura already burning is a no-op rather than a silent
        # cadence reset -- otherwise spamming the command would delay every
        # pulse forever.
        handler = get_aura_handler_for(caller)
        if handler is not None and handler.get_aura() is aura:
            caller.msg((f"{aura.name} is already burning.", _MSG_COMBAT))
            return

        handler = ensure_aura_handler(caller)
        handler.activate(aura)

        caller.msg((combat_msg.format_aura_activate(aura), _MSG_COMBAT))


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
            caller.msg((describe_registry(), _MSG_COMBAT))
            return

        caller.msg((describe_action_rules(caller), _MSG_COMBAT))


class CmdCombatOptions(Command):
    """Command combatoptions [<style>] — pick which combat style your wielded weapon uses.

    Each weapon offers a handful of named styles (e.g. a shortsword's
    accurate/aggressive/defensive stances). The active style decides which
    stat gets an invisible level boost for the swing and which skill(s)
    earn XP from the damage dealt. Switching is free and instant.

    Usage:
        combatoptions           open the combat options menu
        combatoptions <style>   switch straight to a style, e.g. combatoptions guard

    Aliases: stance, combatstyle

    The second form is also what the graphical client's Combat tab sends when
    a style is clicked -- the same line, so every check here applies to both.
    """

    key = "combatoptions"
    aliases = ["stance", "combatstyle"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_COMBAT

    def func(self) -> None:
        argument = self.args.strip()

        if not argument:
            self._open_menu()
            return

        self._switch(argument)

    def _open_menu(self) -> None:
        """Open the EvMenu, republishing the Combat tab on the way in.

        The publish is the `skills` command's arrangement: a player asking
        about combat options is a reason for a graphical client's tab to be
        current, and it pre-checks its subscription so telnet pays nothing.
        """
        caller = self.caller

        from systems.interface.menus.base_menu import start_blackout_menu

        feed.emit_combat_options(caller)

        start_blackout_menu(
            caller,
            "systems.interface.menus.combat_options_menu",
            startnode="start",
        )

    def _switch(self, argument: str) -> None:
        """Resolve a typed style against the wielded weapon and make it active.

        set_combat_style does the republishing -- the dossier and the Combat
        tab -- so this path and the menu's cannot publish differently.
        """
        caller = self.caller
        weapon = held_weapon(caller)

        if weapon is None:
            caller.msg(
                ("You have no weapon equipped, so there is no style to choose.",
                 _MSG_COMBAT))
            return

        style_key = style_options.resolve_style_key(weapon, argument)

        if not style_key:
            self._refuse_unknown(weapon, argument)
            return

        style_name = style_key.title()

        if style_key == active_combat_style_key(weapon):
            caller.msg((f"You are already using {style_name} style.", _MSG_COMBAT))
            return

        set_combat_style(weapon, style_key, combatant=caller)

        switched = style_options.STYLE_SWITCHED_TEMPLATE.format(name=style_name)
        caller.msg(
            (f"{colors.SUCCESS_COLOR}{switched}{colors.RESET_COLOR}", _MSG_COMBAT))

    def _refuse_unknown(self, weapon, argument: str) -> None:
        """Say the style does not exist, and name the ones that do."""
        caller = self.caller
        styles = available_combat_styles(weapon)

        if not styles:
            caller.msg(
                (f"{weapon.key} has no combat styles to choose from.", _MSG_COMBAT))
            return

        names = ", ".join(str(style_key).title() for style_key in styles)
        caller.msg(
            (f"{weapon.key} has no style called '{argument}'. "
             f"Choose from: {names}.", _MSG_COMBAT))


class CmdPvp(Command):
    """Command pvp [on|off] — let other players fight you, or stop them.

    With PvP on, you can attack another player who also has PvP on, and that
    player can attack you. With PvP off, no player can attack you, and you
    cannot attack a player. Hostile creatures attack you either way.

    You cannot turn PvP off during a fight.

    Usage:
        pvp          show whether PvP is on
        pvp on       turn PvP on
        pvp off      turn PvP off

    The Combat tab of the graphical client sends the same line.
    """

    key = "pvp"
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_COMBAT

    def func(self) -> None:
        caller = self.caller
        argument = self.args.strip().lower()

        if argument == const.PVP_ARG_ON:
            self._set(True)
            return

        if argument == const.PVP_ARG_OFF:
            self._set(False)
            return

        enabled = pvp.pvp_enabled(caller)
        state = const.PVP_STATE_ON if enabled else const.PVP_STATE_OFF
        caller.msg((const.PVP_USAGE_MSG.format(state=state), _MSG_COMBAT))

    def _set(self, enabled: bool) -> None:
        """Move the flag, and say what happened.

        pvp.set_pvp owns the lock and the republish, so this command and any
        later caller cannot move the flag differently.
        """
        _changed, message = pvp.set_pvp(self.caller, enabled)
        self.caller.msg((message, _MSG_COMBAT))


class CmdTickDebug(Command):
    """Command tickdebug [all|quiet|status|off] — watch the engine's 0.6s tick.

    Blackout resolves combat on one server-wide 0.6s tick, and everything that
    feels like timing — when a swing lands, when an aura pulses, why a fight
    seems to stutter — is a counter on that tick you otherwise cannot see.
    This prints it.

    A streamed line reads:

        [t 01432] 0.601s eng 2h | SWING cd 3/4 attack -> raider | rf 2/4

    the tick number, how long the tick actually took against the 0.6s nominal,
    how many handlers the engine is driving, then your own weapon cooldown and
    aura cadence as remaining/total.

    Usage:
        tickdebug          toggle the stream on or off
        tickdebug quiet    only ticks where something happens (the default)
        tickdebug all      every tick, ~100 lines a minute
        tickdebug status   one-shot health report, no stream
        tickdebug off      stop streaming

    The stream stops itself after five minutes so a forgotten toggle cannot
    fill your screen indefinitely.
    """

    key = "tickdebug"
    aliases = ["tickdiag"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_COMBAT

    def func(self) -> None:
        caller = self.caller
        argument = self.args.strip().lower()

        if argument == tick_debug.MODE_STATUS:
            report = tick_debug.snapshot(caller)
            caller.msg((report, _MSG_COMBAT))
            return

        if argument == tick_debug.MODE_OFF:
            self._stop()
            return

        if not argument:
            self._toggle()
            return

        if argument not in tick_debug.STREAM_MODES:
            self._usage()
            return

        self._start(argument)

    def _toggle(self) -> None:
        """Bare `tickdebug` — turn the stream on at the default mode, or off."""
        caller = self.caller
        watching = tick_debug.is_watching(caller)

        if watching:
            self._stop()
            return

        self._start(tick_debug.DEFAULT_MODE)

    def _start(self, mode: str) -> None:
        """Begin (or re-aim) the caller's stream, and show a status report first.

        The report goes out before the first line so the stream has something
        to be read against: a bare cooldown counter means little without the
        weapon speed and rotation size the report names.
        """
        caller = self.caller

        report = tick_debug.snapshot(caller)
        caller.msg((report, _MSG_COMBAT))

        tick_debug.attach(caller, mode)
        caller.msg(
            (f"{colors.SUCCESS_COLOR}Tick monitor on ({mode}). "
            f"'tickdebug off' to stop.{colors.RESET_COLOR}", _MSG_COMBAT)
        )

    def _stop(self) -> None:
        """End the caller's stream, saying so only if one was running."""
        caller = self.caller
        was_watching = tick_debug.detach(caller)

        if not was_watching:
            caller.msg(("The tick monitor isn't running.", _MSG_COMBAT))
            return

        caller.msg(
            (f"{colors.DIM_COLOR}Tick monitor off.{colors.RESET_COLOR}", _MSG_COMBAT))

    def _usage(self) -> None:
        """Report the accepted arguments, built from the module's own vocabulary."""
        caller = self.caller
        modes = list(tick_debug.STREAM_MODES)

        modes.append(tick_debug.MODE_STATUS)
        modes.append(tick_debug.MODE_OFF)

        choices = "|".join(modes)
        caller.msg((f"Usage: tickdebug [{choices}]", _MSG_COMBAT))


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
        tick_debug_cmd = CmdTickDebug()
        pvp_cmd = CmdPvp()

        self.add(attack_cmd)
        self.add(pvp_cmd)
        self.add(hold_cmd)
        self.add(flee_cmd)
        self.add(wield_cmd)
        self.add(aura_cmd)
        self.add(combat_rules_cmd)
        self.add(combat_options_cmd)
        self.add(tick_debug_cmd)
