"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Player versus player: the flag, and the rule that reads it.

             A player can attack another player only when BOTH have the PvP
             flag on. The flag is off by default. The player turns it on and
             off in the Combat tab, or with `pvp on` and `pvp off`.

             This module is the one owner of that rule. Three callers read it:

               - CmdAttack, which refuses BEFORE it walks, so a player is not
                 walked across the map to an attack that cannot happen.
               - BlackoutCombatHandler._validate_attack, the choke point every
                 attack passes through, whoever queued it.
               - Character.extra_actions, which offers `Attack` on a player
                 only when that player has the flag on.

             The rule applies only when BOTH sides are players. A hostile NPC
             attacks a player whatever the flag says, and a player attacks a
             hostile NPC whatever the flag says.
"""

from evennia.utils import logger

from systems.gameplay.combat import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

# The class attribute that marks a player character. Declared on the
# Character typeclass, so every character already in the database has it with
# no migration. An NPC does not declare it, so an NPC is never a PvP side.
_PVP_CAPABLE_ATTR: str = "pvp_capable"


# ─── Private helper routines ─────────────────────────────────────────────────

def _state_word(enabled: bool) -> str:
    """The word for the flag state, as the messages print it."""
    if enabled:
        return const.PVP_STATE_ON

    return const.PVP_STATE_OFF


def _publish(character) -> None:
    """
    Purpose: Tell every client that must know about a changed flag.

    Entry:
        character - the character whose flag changed.

    Exit/Returns:
        No return value.

    Module Globals:
        None.

    Methodology:
        Three readers show the flag, so three sends:

          1. The Combat tab of the owner, which shows the toggle.
          2. The dossier of the owner, which shows the flag in Vitals.
          3. The entity row of the character, for every observer nearby.
             The row carries the `Attack` action only when the flag is on, so
             an observer must get the row again when the flag moves.

        The third send uses emit_entity_arrived. The client upserts an entity
        row by id, so a second `add` for a known id replaces the row in place.

        Wrapped, because a feed send must never stop a gameplay write that
        already happened.

    Notes/References:
        systems/interface/statefeed/events.py owns all three emitters.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    from systems.interface.statefeed import events as feed

    try:
        feed.emit_combat_options(character)
        feed.refresh_summary(character)

        location = getattr(character, "location", None)

        if location is not None:
            feed.emit_entity_arrived(location, character)
    except Exception as exc:
        logger.log_err(f"pvp._publish: {character} feed send failed: {exc!r}")


# ─── Public routines ─────────────────────────────────────────────────────────

def is_player(entity) -> bool:
    """
    Purpose: Tell if an entity is a player character, for the PvP rule.

    Entry:
        entity - any object, or None.

    Exit/Returns:
        Returns True for a player character. Returns False for an NPC, an
        item, and None.

    Module Globals:
        _PVP_CAPABLE_ATTR read.

    Methodology:
        Reads a class attribute through getattr, so this module does not
        import the typeclass layer. Do not use `has_account` here. A player who
        logs out still owns a player character, and the rule must not change
        when the owner disconnects.

    Notes/References:
        typeclasses/characters.py declares the attribute.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    capable = getattr(entity, _PVP_CAPABLE_ATTR, False)

    return bool(capable)


def pvp_enabled(entity) -> bool:
    """
    Purpose: Tell if a player character has the PvP flag on.

    Entry:
        entity - any object, or None.

    Exit/Returns:
        Returns True only for a player character with the flag on.

    Module Globals:
        const.PVP_ENABLED_ATTR read.

    Methodology:
        Returns False for anything that is not a player, so a caller can ask
        this of any object with no check first.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    if not is_player(entity):
        return False

    enabled = entity.attributes.get(const.PVP_ENABLED_ATTR, default=False)

    return bool(enabled)


def attack_refusal(attacker, target) -> str:
    """
    Purpose: Say why `attacker` cannot attack `target`, if the PvP rule
             forbids it.

    Entry:
        attacker - the combatant who wants to attack.
        target   - the combatant to attack.

    Exit/Returns:
        Returns "" when the PvP rule allows the attack. Otherwise returns the
        message to show the attacker.

    Module Globals:
        const.PVP_ATTACKER_OFF_MSG, const.PVP_TARGET_OFF_MSG read.

    Methodology:
        The rule applies only when both sides are players. It says nothing
        about any other rule: a dead target, a target out of reach, and an
        empty quiver are for the combat handler to refuse.

        The attacker's own flag is checked first. That refusal is the one the
        attacker can fix, so it is the more useful message.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    both_players = is_player(attacker) and is_player(target)

    if not both_players:
        return ""

    attacker_on = pvp_enabled(attacker)

    if not attacker_on:
        return const.PVP_ATTACKER_OFF_MSG

    target_on = pvp_enabled(target)

    if not target_on:
        return const.PVP_TARGET_OFF_MSG.format(name=target.key)

    return ""


def command_for(enabled: bool) -> str:
    """
    Purpose: The line a player types to put the flag in the given state.

    Entry:
        enabled - True for the line that turns the flag on.

    Exit/Returns:
        Returns `pvp on` or `pvp off`.

    Module Globals:
        const.PVP_ARG_ON, const.PVP_ARG_OFF read.

    Methodology:
        Made HERE and nowhere else, so the Combat tab sends the same line
        that a telnet player types. The command's own `key` is read, not
        typed again. style_options.command_for uses the same arrangement.

        The import is deferred so that this module and the command module do
        not import each other at load time.

    Notes/References:
        commands/combat_cmds.py CmdPvp parses exactly this form.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    from commands.combat_cmds import CmdPvp

    if enabled:
        argument = const.PVP_ARG_ON
    else:
        argument = const.PVP_ARG_OFF

    return f"{CmdPvp.key} {argument}"


def set_pvp(character, enabled: bool) -> tuple:
    """
    Purpose: Turn the PvP flag of a player character on or off.

    Entry:
        character - a player character.
        enabled   - the state to put the flag in.

    Exit/Returns:
        Returns (changed, message). `changed` is False when the flag did not
        move, and `message` then says why.

    Module Globals:
        const.PVP_* read.

    Methodology:
        The flag cannot go OFF during a fight. Without this lock, a player
        who starts to lose can turn PvP off, and the attack of the other
        player stops on the next check. The flag can go ON at any time,
        because that gives no player an advantage.

        The lock reads `in_combat`, which every combat teardown path keeps
        current. It covers a fight with an NPC too. That is the simpler
        rule, and a player can finish a fight with an NPC first.

    Notes/References:
        _publish sends the change to every client that shows it.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    current = pvp_enabled(character)

    if current == enabled:
        state = _state_word(enabled)

        return False, const.PVP_ALREADY_MSG.format(state=state)

    fighting = bool(getattr(character, "in_combat", False))

    if not enabled and fighting:
        return False, const.PVP_LOCKED_IN_COMBAT_MSG

    character.attributes.add(const.PVP_ENABLED_ATTR, enabled)
    _publish(character)

    if enabled:
        return True, const.PVP_TURNED_ON_MSG

    return True, const.PVP_TURNED_OFF_MSG


def status(character) -> dict:
    """
    Purpose: Describe the PvP flag for the Combat tab.

    Entry:
        character - the puppeted character.

    Exit/Returns:
        Returns {"enabled", "command"}. `command` is the line that flips the
        flag.

    Module Globals:
        None.

    Methodology:
        The server names the command, so the tab needs no rule of its own.

        THE PAYLOAD DOES NOT SAY WHETHER THE FLAG IS LOCKED. The lock follows
        `in_combat`, which moves at every combat start and end. A lock field
        would thus need a send at each of those, or the tab would show a stale
        lock. set_pvp refuses `pvp off` during a fight and says why, so the
        tab can always send the command. Only set_pvp moves `enabled`, and
        set_pvp publishes the tab.

    Notes/References:
        style_options.combat_options puts this in the char_combat payload.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    enabled = pvp_enabled(character)
    command = command_for(not enabled)

    return {"enabled": enabled, "command": command}
