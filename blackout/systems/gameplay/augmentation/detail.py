"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: What an augment IS, for one holder, as ability rows
             (DESIGN-0015, Phase 3). The twin of auras/detail.py.

             One owner, two readers. The telnet `aug` listing prints its
             rows from here, and the composer in systems/gameplay/abilities.py
             puts them on the rail after the aura rows. Thus, the listing
             and the rail cannot describe an augment differently.

             Each row is a toggle with a power level dial. The last row is
             the set row: one button that lights every socketed augment, or
             puts every one out. Since Phase 5, the rows are the SOCKETED
             augments only (section 4.7): the rig decides what the rail
             shows, and the rig pop-up shows the whole catalogue.
"""

from systems.interface.statefeed import constants as feed_const

from . import constants as aug_const
from . import pool
from . import sockets
from .handler import get_augment_handler_for


# One hundred, for a percent.
_PERCENT: float = 100.0


# ─── Private helper routines ─────────────────────────────────────────────────

def _tip_lines(augment, level: int, roll: float) -> list:
    """The tip of one augment, with the roll of a lit roll augment last."""
    lines = augment.tip_lines(level)

    if roll > 0.0:
        lines.append(aug_const.AUG_TIP_ROLL_NOW.format(percent=roll * _PERCENT))

    return lines


def _next_power_level(power_level: int) -> int:
    """The power level after `power_level` on the dial. The top one wraps
    to the first."""
    if power_level >= aug_const.AUG_POWER_LEVELS:
        return aug_const.AUG_POWER_LEVEL_MIN

    return power_level + 1


def _power_level_commands(augment, power_level: int, allowed: bool) -> list:
    """
    Purpose: Name the line of each power level button of one augment row.

    Entry:
        augment     - the augment of the row.
        power_level - the power level it burns at, 0 when it is out.
        allowed     - what can_activate says of the holder.

    Exit/Returns:
        Returns a list with one str for each power level, the lowest first.
        Item 0 is AUG_POWER_LEVEL_MIN.

    Module Globals:
        aug_const.AUG_POWER_LEVEL_MIN, AUG_POWER_LEVELS,
        AUG_IGNITE_POWER_LEVEL_TEMPLATE read.

    Methodology:
        Each line is `aug <name> <power level>`: the line that lights an out
        augment at that power level, and moves a lit one to it. The line of
        the current power level is "", because it changes nothing. A holder
        that `aug` refuses gets "" on every button.

    Notes/References:
        The client draws "" as a button that does nothing, the rule of an
        empty `command`.

    Author: Nick Hobar
    Creation date: 11/12/2026
    """
    commands = []
    first = aug_const.AUG_POWER_LEVEL_MIN
    last = aug_const.AUG_POWER_LEVELS

    for each in range(first, last + 1):
        if not allowed or each == power_level:
            commands.append("")
            continue

        commands.append(aug_const.AUG_IGNITE_POWER_LEVEL_TEMPLATE.format(
            name=augment.name, power_level=each))

    return commands


def _note(roll: float) -> str:
    """The mark after the name: the roll of a lit roll augment, or ""."""
    if roll <= 0.0:
        return ""

    return aug_const.AUG_ROLL_NOTE.format(percent=roll * _PERCENT)


def _row(augment, holder, lit: dict, rolls: dict, level: int) -> dict:
    """One ability row for one augment and one holder."""
    allowed, reason = augment.can_activate(holder)
    power_level = int(lit.get(augment.key, 0))
    roll = float(rolls.get(augment.key, 0.0))
    power_level_command = ""

    if power_level > 0:
        state = feed_const.ABILITY_STATE_ACTIVE
        command = aug_const.AUG_EXTINGUISH_TEMPLATE.format(name=augment.name)
        power_level_command = aug_const.AUG_IGNITE_POWER_LEVEL_TEMPLATE.format(
            name=augment.name, power_level=_next_power_level(power_level))
    elif allowed:
        state = feed_const.ABILITY_STATE_READY
        command = aug_const.AUG_IGNITE_TEMPLATE.format(name=augment.name)
    else:
        state = feed_const.ABILITY_STATE_LOCKED
        command = ""

    row = {
        "key": str(augment.key),
        "name": str(augment.name),
        "kind": feed_const.ABILITY_KIND_TOGGLE,
        "state": state,
        "command": command,
        "reason": str(reason),
        feed_const.ABILITY_POWER_LEVEL_KEY: power_level,
        feed_const.ABILITY_POWER_LEVELS_KEY: aug_const.AUG_POWER_LEVELS,
        feed_const.ABILITY_POWER_LEVEL_COMMAND_KEY: power_level_command,
        feed_const.ABILITY_POWER_LEVEL_COMMANDS_KEY: _power_level_commands(
            augment, power_level, allowed),
        feed_const.ABILITY_NOTE_KEY: _note(roll),
        feed_const.TIP_KEY: {
            feed_const.TIP_TITLE_KEY: str(augment.name),
            feed_const.TIP_LINES_KEY: _tip_lines(augment, level, roll),
        },
    }

    return row


def _set_row(any_lit: bool) -> dict:
    """The set row: `aug set` when nothing burns, `aug off` when anything does."""
    if any_lit:
        state = feed_const.ABILITY_STATE_ACTIVE
        command = aug_const.AUG_EXTINGUISH_ALL_COMMAND
    else:
        state = feed_const.ABILITY_STATE_READY
        command = aug_const.AUG_SET_COMMAND

    row = {
        "key": aug_const.AUG_SET_ROW_KEY,
        "name": aug_const.AUG_SET_ROW_NAME,
        "kind": feed_const.ABILITY_KIND_SET,
        "state": state,
        "command": command,
        "reason": "",
        feed_const.ABILITY_NOTE_KEY: "",
        feed_const.TIP_KEY: {
            feed_const.TIP_TITLE_KEY: aug_const.AUG_SET_ROW_NAME,
            feed_const.TIP_LINES_KEY: list(aug_const.AUG_SET_TIP_LINES),
        },
    }

    return row


def _lit_and_rolls(holder) -> tuple:
    """The lit power levels and the rolls of a holder, in one lookup."""
    handler = get_augment_handler_for(holder)

    if handler is None:
        return {}, {}

    lit = {augment.key: power_level
           for augment, power_level in handler.lit_augments()}
    rolls = {key: handler.roll_of(key) for key in lit}

    return lit, rolls


# ─── Public routines ─────────────────────────────────────────────────────────

def ability_rows(holder) -> list:
    """
    Purpose: Describe every socketed augment of a holder, one row for each,
             and the set row last.

    Entry:
        holder - the character. One with no skills handler gets every gated
                 augment as locked, which is what can_activate says of it.

    Exit/Returns:
        Returns a list of rows, in the order of augments_in_order among the
        socketed augments, then the set row. Each augment row is `{key,
        name, kind, state, command, reason, power_level, power_levels,
        power_level_command, power_level_commands, note, tip}`. The set row
        has no power level keys. Every value survives json.dumps.

    Module Globals:
        None.

    Methodology:
        The lit set, the rolls, and the level are read one time, before
        the loop. The handler is a script lookup, and a listing must not
        make one for each row. The rig decides the rows (Phase 5).

    Notes/References:
        The telnet `aug` listing and the composer both read this.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    lit, rolls = _lit_and_rolls(holder)
    level = pool.level(holder)
    rows = []

    for augment in sockets.socketed_augments(holder):
        rows.append(_row(augment, holder, lit, rolls, level))

    rows.append(_set_row(bool(lit)))

    return rows


def catalogue_tip(augment, level: int) -> list:
    """The tip lines of one augment for the rig, where nothing burns."""
    return _tip_lines(augment, level, 0.0)
