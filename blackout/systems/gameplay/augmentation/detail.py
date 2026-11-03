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

             Each row is a toggle with a step dial. The last row is the set
             row: one button that lights every socketed augment, or puts
             every one out. Since Phase 5, the rows are the SOCKETED
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


def _next_step(step: int) -> int:
    """The step after `step` on the dial. The top step wraps to the first."""
    if step >= aug_const.AUG_STEPS:
        return aug_const.AUG_STEP_MIN

    return step + 1


def _note(roll: float) -> str:
    """The mark after the name: the roll of a lit roll augment, or ""."""
    if roll <= 0.0:
        return ""

    return aug_const.AUG_ROLL_NOTE.format(percent=roll * _PERCENT)


def _row(augment, holder, lit: dict, rolls: dict, level: int) -> dict:
    """One ability row for one augment and one holder."""
    allowed, reason = augment.can_activate(holder)
    step = int(lit.get(augment.key, 0))
    roll = float(rolls.get(augment.key, 0.0))
    step_command = ""

    if step > 0:
        state = feed_const.ABILITY_STATE_ACTIVE
        command = aug_const.AUG_EXTINGUISH_TEMPLATE.format(name=augment.name)
        step_command = aug_const.AUG_IGNITE_STEP_TEMPLATE.format(
            name=augment.name, step=_next_step(step))
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
        feed_const.ABILITY_STEP_KEY: step,
        feed_const.ABILITY_STEPS_KEY: aug_const.AUG_STEPS,
        feed_const.ABILITY_STEP_COMMAND_KEY: step_command,
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
    """The lit steps and the rolls of a holder, in one handler lookup."""
    handler = get_augment_handler_for(holder)

    if handler is None:
        return {}, {}

    lit = {augment.key: step for augment, step in handler.lit_augments()}
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
        name, kind, state, command, reason, step, steps, step_command,
        note, tip}`. The set row has no step keys. Every value survives
        json.dumps.

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
