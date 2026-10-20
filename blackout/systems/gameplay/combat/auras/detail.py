"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/20/2026
Description: What an ability IS, for one caster, in a structured form.

             One owner, two readers. The telnet `aura` listing prints its
             rows from here, and statefeed/abilities.py sends them to the
             Godot ability rail. Thus, the two cannot describe an aura
             differently. It is the arrangement of
             systems/gameplay/progression/skills/detail.py, one system
             over.

             Every aura is an ability of the kind ABILITY_KIND_TOGGLE. A
             later ability with a cast and a cooldown is one more kind, and
             one more row builder here.
"""

from systems.core.tick import constants as tick_const
from systems.gameplay.combat import constants as const
from systems.interface.statefeed import constants as feed_const

from .aura_defs.base_aura import NO_UNLOCK_REQUIREMENT
from .registry import AURA_REGISTRY


# ─── Private constant definitions ────────────────────────────────────────────

# The tip lines of an aura. Player-facing text, so the voice stays.
_LINE_SCALES: str = "Scales with {skill}."
_LINE_RADIUS_SELF: str = "Burns the hostiles on your own tile."
_LINE_RADIUS: str = "Reaches {radius} tile(s) around you."
_LINE_CADENCE: str = "Pulses every {seconds:.1f}s."
_LINE_UNLOCK: str = "Needs {skill} {level}."


# ─── Private helper routines ─────────────────────────────────────────────────

def _skill_name(skill_key) -> str:
    """The display name of a skill key, or the key when none is registered.

    Imported inside the routine. The skill registry walks every skill
    definition on first import, and skills/detail.py reads this package.
    """
    from systems.gameplay.progression.skills.registry import SKILL_REGISTRY

    skill_class = SKILL_REGISTRY.get(skill_key)

    if skill_class is None:
        return str(skill_key).title()

    return str(skill_class.name)


def _active_key(caster) -> str:
    """The key of the aura that burns on the caster, or an empty string.

    Imported inside the routine. The handler module imports the statefeed
    events, and the feed reads this module.
    """
    from .aura_handler import get_aura_handler_for

    handler = get_aura_handler_for(caster)

    if handler is None:
        return ""

    aura = handler.get_aura()

    if aura is None:
        return ""

    return str(aura.key)


def _tip_lines(aura) -> list:
    """The lines of the tip of one aura, from its own data."""
    lines = [str(aura.description)]

    if aura.cost:
        lines.append(str(aura.cost))

    if aura.scaling_skill:
        lines.append(_LINE_SCALES.format(skill=_skill_name(aura.scaling_skill)))

    if aura.radius > 0:
        lines.append(_LINE_RADIUS.format(radius=aura.radius))
    else:
        lines.append(_LINE_RADIUS_SELF)

    seconds = aura.tick_interval * tick_const.TICK_SECONDS
    lines.append(_LINE_CADENCE.format(seconds=seconds))

    if aura.unlock_level > NO_UNLOCK_REQUIREMENT:
        lines.append(_LINE_UNLOCK.format(
            skill=_skill_name(aura.scaling_skill), level=aura.unlock_level,
        ))

    return lines


def _row(aura, caster, active_key: str) -> dict:
    """One ability row for one aura and one caster."""
    allowed, reason = aura.can_activate(caster)

    if aura.key == active_key:
        state = feed_const.ABILITY_STATE_ACTIVE
        command = const.AURA_EXTINGUISH_COMMAND
    elif allowed:
        state = feed_const.ABILITY_STATE_READY
        command = const.AURA_IGNITE_TEMPLATE.format(name=aura.name)
    else:
        state = feed_const.ABILITY_STATE_LOCKED
        command = ""

    row = {
        "key": str(aura.key),
        "name": str(aura.name),
        "kind": feed_const.ABILITY_KIND_TOGGLE,
        "state": state,
        "command": command,
        "reason": str(reason),
        feed_const.TIP_KEY: {
            feed_const.TIP_TITLE_KEY: str(aura.name),
            feed_const.TIP_LINES_KEY: _tip_lines(aura),
        },
    }

    return row


# ─── Public routines ─────────────────────────────────────────────────────────

def ability_rows(caster) -> list:
    """
    Purpose: Describe every ability of a caster, one row for each aura.

    Entry:
        caster - the character. One with no skills handler gets every aura
                 as locked, which is what can_activate says of it.

    Exit/Returns:
        Returns a list of rows, in the order of AURA_REGISTRY. Each row is
        `{key, name, kind, state, command, reason, tip}`. See
        CHANNEL_CHAR_ABILITIES in statefeed/constants.py for each field.
        Every value survives json.dumps.

    Module Globals:
        AURA_REGISTRY read.

    Methodology:
        The active aura is read one time, before the loop. The handler is
        a script lookup, and a listing of twelve auras must not make twelve
        of them.

    Notes/References:
        The telnet `aura` listing and statefeed/abilities.py both read this.

    Author: Nick Hobar
    Creation date: 10/20/2026
    """
    active_key = _active_key(caster)
    rows = []

    for aura in AURA_REGISTRY.values():
        rows.append(_row(aura, caster, active_key))

    return rows
