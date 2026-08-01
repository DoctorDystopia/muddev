"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/01/2026
Description: Progress meters for player-facing numeric pairs, wrapping the
             Evennia health_bar contrib so every bar in the game renders the
             same way.
"""



from evennia.contrib.rpg.health_bar import display_meter

from .colors import DIM_COLOR, RESET_COLOR, SUCCESS_COLOR



# Public constant definitions

# Rendered width of a meter, in characters. The contrib pads or truncates its
# base text to exactly this many columns.
METER_WIDTH = 20

# Text shown instead of a bar when there is no next level to progress toward.
# display_meter has no concept of a completed track -- given a zero maximum it
# would clamp to a full bar over nonsense numbers.
MAX_LEVEL_TEXT = "[MAX LEVEL]"

# Text shown instead of a bar for an entity with no usable max_hp. display_meter
# raises a zero maximum to 1 internally, so "0 / 0" would otherwise render as a
# FULL bar -- the exact opposite of what an uninitialised combatant means.
NO_HP_TEXT = "[NO HP DATA]"


# Private constant definitions

# display_meter takes bare Evennia colour LETTERS, not the "|y" markup tokens
# in colors.py -- it assembles "|[" + letter for the background and
# "|" + letter for the text. The palette constants there cannot be passed
# through directly, so the letters are named here instead.
_XP_FILL_LETTER = "y"
_XP_EMPTY_LETTER = "x"
_XP_TEXT_LETTER = "w"

# The contrib picks a fill colour by percentage from this list. Its default is
# a red/yellow/green health gradient, which reads as "danger" on an XP track.
# A single-entry list pins one colour at every fill level.
_XP_FILL_COLORS = [_XP_FILL_LETTER]

# HP keeps the gradient the XP track rejects: a combatant's remaining health IS
# a danger reading, so the bar should turn red as it drains.
#
# The contrib picks by `round(len(list) * percent_full) - 1`, so the list is
# also the weighting -- repeated entries widen a colour's band. Its own 3-entry
# default puts the green/yellow boundary at ~83%, which flags a target at 4/5 HP
# as damaged-and-worrying. These eight entries move the bands to roughly
# green >56%, yellow 31-56%, red below -- i.e. a bar that stays green while the
# fight is going your way and turns red only when it is not.
_HP_FILL_COLORS = ["r", "r", "y", "y", "g", "g", "g", "g"]
_HP_EMPTY_LETTER = "x"
_HP_TEXT_LETTER = "w"



def build_xp_meter(current_xp: int, total_needed: int) -> str:
    """
    Purpose: Render an XP progress pair as a coloured meter.

    Entry:
        current_xp is an integer. Negative and over-full values are tolerated.
        total_needed is an integer. Zero or less means "no next level".

    Exit/Returns:
        Returns a display string carrying Evennia colour markup. Its rendered
        width is METER_WIDTH columns, except for the max-level case.

    Module Globals:
        METER_WIDTH read.
        MAX_LEVEL_TEXT read.
        _XP_FILL_COLORS read.
        _XP_EMPTY_LETTER read.
        _XP_TEXT_LETTER read.
        SUCCESS_COLOR read.
        RESET_COLOR read.

    Methodology:
        Delegate to the health_bar contrib's display_meter, which clamps both
        ends of the range and embeds the "current / total" numbers inside the
        bar. Only the max-level branch is handled locally, because the contrib
        has no equivalent for a track with nothing left to fill.

    Notes/References:
        Replaces skills_menu._build_xp_bar, which drew "[###...] 50/100" by
        hand and clamped only the top of the range -- a negative current_xp
        widened the bar past its nominal width.

    Author: Nick Hobar
    Creation date: 08/01/2026
    """
    if total_needed <= 0:
        max_level_string = f"{SUCCESS_COLOR}{MAX_LEVEL_TEXT}{RESET_COLOR}"

        return max_level_string

    meter_string = display_meter(
        current_xp,
        total_needed,
        length=METER_WIDTH,
        fill_color=_XP_FILL_COLORS,
        empty_color=_XP_EMPTY_LETTER,
        text_color=_XP_TEXT_LETTER,
        show_values=True,
    )

    return meter_string


def build_hp_meter(current_hp: int, max_hp: int) -> str:
    """
    Purpose: Render a hitpoints pair as a coloured meter.

    Entry:
        current_hp is an integer. Negative and over-full values are tolerated.
        max_hp is an integer. Zero or less means the entity has no HP data.

    Exit/Returns:
        Returns a display string carrying Evennia colour markup. Its rendered
        width is METER_WIDTH columns, except for the no-data case.

    Module Globals:
        METER_WIDTH read.
        NO_HP_TEXT read.
        _HP_FILL_COLORS read.
        _HP_EMPTY_LETTER read.
        _HP_TEXT_LETTER read.
        DIM_COLOR read.
        RESET_COLOR read.

    Methodology:
        Same delegation as build_xp_meter, differing only in the fill palette:
        HP keeps the contrib's red/yellow/green gradient so a draining bar
        reads as danger. The zero-maximum branch is handled here because the
        contrib silently raises a zero maximum to 1, which would render an
        uninitialised combatant as a full green bar.

    Notes/References:
        Callers pair this with a name label; the meter itself carries only the
        numbers, so a long combatant name cannot squeeze the bar.

    Author: Nick Hobar
    Creation date: 08/01/2026
    """
    if max_hp <= 0:
        no_data_string = f"{DIM_COLOR}{NO_HP_TEXT}{RESET_COLOR}"

        return no_data_string

    meter_string = display_meter(
        current_hp,
        max_hp,
        length=METER_WIDTH,
        fill_color=_HP_FILL_COLORS,
        empty_color=_HP_EMPTY_LETTER,
        text_color=_HP_TEXT_LETTER,
        show_values=True,
    )

    return meter_string
