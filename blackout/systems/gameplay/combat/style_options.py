"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/12/2026
Description: What a character's combat options ARE -- the wielded weapon, its
             styles, which one is active and the command that picks each --
             described once, as data.

             TWO READERS, ONE DESCRIPTION. The combat options EvMenu renders
             this into text and CHANNEL_CHAR_COMBAT ships it to a graphical
             client as it stands, so the two screens cannot disagree about
             which style is active or what it trains. It is the arrangement
             systems/gameplay/progression/skills/detail.py makes for a skill.

             THE SERVER NAMES EVERY COMMAND. Each style row carries the whole
             line a telnet player would type to pick it (`combatoptions
             guard`), composed by command_for and nowhere else. A row that
             cannot be picked carries an empty command, which every client
             already reads as "the server declines".

             BARE HANDS LIST ONE STYLE, AND IT CANNOT BE PICKED. The unarmed
             table declares four, but there is no object to store a choice on,
             so combat always resolves UNARMED_DEFAULT_COMBAT_STYLE. Offering
             the other three would be buttons that change nothing. The same
             row stands in for a held item that declares no styles, because
             that is the style _resolve_style_and_speed falls back to for it.
"""



from systems.core.tick import constants as tick_const
from systems.gameplay.combat import constants as const
from systems.gameplay.combat import pvp
from systems.gameplay.combat.combat import (
    active_combat_style_key,
    available_combat_styles,
    combat_profile,
    held_weapon,
)



# ─── Public constant definitions ─────────────────────────────────────────────

# Printed when a style is switched, by the command and the menu alike, so the
# two paths onto one action read the same.
STYLE_SWITCHED_TEMPLATE: str = "You switch to {name} style."



# ─── Private constant definitions ────────────────────────────────────────────

# Decimal places the attack speed in seconds is rounded to. A whole number of
# 0.6s ticks is exact at one place; the rounding only removes float noise.
_SPEED_SECONDS_DIGITS: int = 1



# ─── Private helper routines ─────────────────────────────────────────────────

def _skill_keys(value) -> tuple:
    """A style's XP skill field as a tuple: it may be one key or several."""
    if not value:
        return ()

    if isinstance(value, str):
        return (value,)

    return tuple(value)



def _skill_entry(skill_key: str, amount=None) -> dict:
    """One skill named by key and by display name, with an optional amount.

    Deferred import for the reason combat_options_menu gave: this module is
    reachable from typeclass import time, before the skill registry's package
    walk is safe to trigger.
    """
    from systems.gameplay.progression.skills.registry import SKILL_REGISTRY

    skill_class = SKILL_REGISTRY.get(skill_key)
    entry = {
        "skill_key": str(skill_key),
        "name": str(getattr(skill_class, "name", skill_key)),
    }

    if amount is not None:
        entry["amount"] = int(amount)

    return entry



def _style_row(style_key: str, style: dict, active: bool,
               selectable: bool, base_speed: int = 0,
               base_range: int = 0) -> dict:
    """One style as plain values. `command` is empty when it cannot be picked.

    Carries the SPEED AND REACH THIS STYLE WOULD GIVE, not the speed and
    reach the weapon has now. A player choosing between styles has to be able
    to see what rapid buys and what snipe buys before picking one -- a screen
    that only reported the active style's numbers would make both invisible
    until after the choice.
    """
    boosts = []

    for skill_key, amount in (style.get("weapon_style_level_boost") or {}).items():
        boosts.append(_skill_entry(skill_key, amount))

    xp_skills = []

    for skill_key in _skill_keys(style.get("weapon_style_xp_skill")):
        xp_skills.append(_skill_entry(skill_key))

    command = command_for(style_key) if selectable else ""

    speed_ticks = max(
        const.MIN_ATTACK_SPEED_TICKS,
        base_speed + int(style.get(const.STYLE_ATTACK_SPEED_DELTA_KEY, 0) or 0),
    )
    range_tiles = max(
        const.MELEE_REACH_TILES,
        base_range + int(style.get(const.STYLE_RANGE_BONUS_KEY, 0) or 0),
    )

    return {
        "key": str(style_key),
        "name": str(style_key).title(),
        "attack_type": str(style.get("attack_type", "")),
        "weapon_style": str(style.get("weapon_style", "")),
        "boosts": boosts,
        "xp_skills": xp_skills,
        "speed_ticks": speed_ticks,
        "speed_seconds": round(speed_ticks * tick_const.TICK_SECONDS,
                               _SPEED_SECONDS_DIGITS),
        "range_tiles": range_tiles,
        "active": bool(active),
        "command": command,
    }



def _weapon_rows(weapon) -> list:
    """Every style the weapon declares, in its ItemDef's order.

    The weapon's OWN speed and reach are read once and passed to each row,
    which then applies that style's delta. Reading them per row would read
    the same two attributes four times on a screen that opens often.
    """
    styles = available_combat_styles(weapon)
    active_key = active_combat_style_key(weapon)
    base_speed = getattr(weapon.db, "attack_speed", None) or const.UNARMED_ATTACK_SPEED_TICKS
    base_range = getattr(weapon.db, "max_range", None) or const.MELEE_REACH_TILES
    rows = []

    for style_key, style in styles.items():
        is_active = style_key == active_key
        rows.append(
            _style_row(style_key, style, is_active, selectable=True,
                       base_speed=base_speed, base_range=base_range)
        )

    return rows



def _unarmed_rows() -> list:
    """The one style bare hands fight with. See the module docstring."""
    style_key = const.UNARMED_DEFAULT_COMBAT_STYLE
    style = const.UNARMED_COMBAT_STYLES[style_key]

    return [
        _style_row(style_key, style, active=True, selectable=False,
                   base_speed=const.UNARMED_ATTACK_SPEED_TICKS,
                   base_range=const.MELEE_REACH_TILES)
    ]



def _combat_level(character) -> int:
    """The character's combat level, or 0 for anything without skills.

    Deferred import: the combat level package imports the skill registry at
    module scope.
    """
    if getattr(character, "skills", None) is None:
        return 0

    from systems.gameplay.combat.combat_level.logic import get_combat_level

    level = get_combat_level(character)

    return int(level)



# ─── Public routines ─────────────────────────────────────────────────────────

def command_for(style_key: str) -> str:
    """
    Purpose: The line a player types to switch to one combat style.

    Entry:
        style_key - a key in the wielded weapon's combat_styles table.

    Exit/Returns:
        Returns the command string.

    Module Globals:
        None.

    Methodology:
        Composed HERE and nowhere else, so the command a graphical client
        sends and the command a telnet player types are the same string by
        construction. The command's own `key` is read rather than retyped,
        which is detail.command_for's arrangement for `skills <skill>`.

        The deferred import is what stops this module and the command module
        from importing each other at load time.

    Notes/References:
        commands/combat_cmds.py CmdCombatOptions parses exactly this form.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    from commands.combat_cmds import CmdCombatOptions

    command = f"{CmdCombatOptions.key} {style_key}"

    return command



def resolve_style_key(weapon, argument: str) -> str:
    """
    Purpose: Turn what a player typed into a style key on `weapon`.

    Entry:
        weapon   - the wielded weapon.
        argument - the text after the command. May be any case.

    Exit/Returns:
        Returns the matching style key, or "" when nothing matches.

    Module Globals:
        None.

    Methodology:
        Case-insensitive and exact. A style's display name is its key
        title-cased, so what the player read off either screen resolves. No
        prefix matching: `l` could mean `lunge` or `lash` on a later weapon,
        and a wrong guess changes how the next swing trains without a word.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    wanted = argument.strip().lower()

    for style_key in available_combat_styles(weapon):
        if str(style_key).lower() == wanted:
            return style_key

    return ""



def combat_options(character) -> dict:
    """
    Purpose: Describe everything the combat options screen shows.

    Entry:
        character - the puppeted Character. Anything without an equipment
                    handler is a supported no-op.

    Exit/Returns:
        Returns {} for an object with no equipment handler, otherwise:
            weapon_name          - the wielded item's key, or bare hands
            armed                - True when an item is wielded
            combat_level         - the character's combat level
            attack_speed_ticks   - ticks between swings
            attack_speed_seconds - the same, in seconds
            styles               - [style row, ...] in the weapon's order
            pvp                  - {enabled, command}, from pvp.status

    Module Globals:
        const.UNARMED_WEAPON_NAME, tick_const.TICK_SECONDS read.

    Methodology:
        Attack speed is read off combat_profile, the one place the combat
        handler resolves it, rather than off the weapon's attribute -- so what
        this screen reports is what the next fight will actually use.

        Seconds ship beside ticks because the tick length is the server's and
        is not exported to any client; a client dividing by its own copy of
        0.6 would be a second owner of the tick.

    Notes/References:
        See _style_row for the per-style shape.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    if getattr(character, "equipment", None) is None:
        return {}

    weapon = held_weapon(character)
    profile = combat_profile(character)
    ticks = int(profile["attack_speed"])
    seconds = round(ticks * tick_const.TICK_SECONDS, _SPEED_SECONDS_DIGITS)

    rows = _weapon_rows(weapon) if weapon is not None else []

    if not rows:
        rows = _unarmed_rows()

    if weapon is not None:
        weapon_name = str(weapon.key)
    else:
        weapon_name = const.UNARMED_WEAPON_NAME

    return {
        "weapon_name": weapon_name,
        "armed": weapon is not None,
        "combat_level": _combat_level(character),
        "attack_speed_ticks": ticks,
        "attack_speed_seconds": seconds,
        "styles": rows,
        "pvp": pvp.status(character),
    }
