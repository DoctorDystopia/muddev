"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/14/2026
Description: Snapshot of the skill XP curve -- the XP to clear each level, and
             the total XP to stand at each level, for every legal level.

Answers: how much XP does a level cost, and how much of the whole curve sits
in its last few levels?

Run it:
    ../evenv/Scripts/python.exe analysis/show_skills_graph.py
"""

from __future__ import annotations

import sys
from pathlib import Path


# The game directory has to be importable before `analysis.*` resolves.
# Running this file directly puts analysis/ on sys.path, not blackout/.
_GAME_DIR: str = str(Path(__file__).resolve().parents[1])

if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

import matplotlib.pyplot as plt

from analysis import _snapshot_env as env


# Private constant definitions

# Column widths for the printed table.
_LEVEL_WIDTH: int = 7
_TOTAL_WIDTH: int = 19
_NEXT_WIDTH: int = 13
_PERCENT_WIDTH: int = 8

# Printed in the next-level column of the top level. add_xp's curve still
# prices a level above the cap, but no skill may legally stand there.
_CAP_LABEL: str = "cap"

# Figure geometry.
_FIGURE_WIDTH_INCHES: float = 10.0
_FIGURE_HEIGHT_INCHES: float = 6.0

# Styling.
_LINE_WIDTH: float = 2.0
_LINE_COLOR: str = "tab:blue"
_GRID_ALPHA: float = 0.7


# Private helper routines

def _curve_rows() -> list:
    """One (level, XP to stand there, XP to clear it) row per legal level.

    The XP to stand at a level is the sum of the costs of every level below
    it. That is the same sum logic.get_total_xp makes for a character, because
    a skill starts at level 0 and add_xp clears one level at a time.
    """
    from systems.gameplay.progression.skills.logic import calculate_xp_needed

    rows = []
    running = 0

    for level in env.level_range():
        needed = calculate_xp_needed(level)
        rows.append((level, running, needed))
        running += needed

    return rows


def _print_table(rows: list) -> None:
    """Print the curve, with each total as a share of the total at the cap."""
    top_level, top_total, _top_needed = rows[-1]

    print(f"{'Level':<{_LEVEL_WIDTH}} | {'XP to stand here':>{_TOTAL_WIDTH}} | "
          f"{'XP to next':>{_NEXT_WIDTH}} | {'% of cap':>{_PERCENT_WIDTH}}")
    print("-" * (_LEVEL_WIDTH + _TOTAL_WIDTH + _NEXT_WIDTH + _PERCENT_WIDTH + 9))

    for level, total, needed in rows:
        share = total / top_total * env.PERCENT_SCALE
        next_label = _CAP_LABEL if level == top_level else f"{needed:,}"
        print(f"{level:<{_LEVEL_WIDTH}} | {total:>{_TOTAL_WIDTH},} | "
              f"{next_label:>{_NEXT_WIDTH}} | {share:>{_PERCENT_WIDTH - 1}.2f}%")


def _plot_curve(rows: list) -> None:
    """Draw the total XP to stand at each level."""
    levels = [level for level, _total, _needed in rows]
    totals = [total for _level, total, _needed in rows]

    plt.figure(figsize=(_FIGURE_WIDTH_INCHES, _FIGURE_HEIGHT_INCHES))
    plt.plot(levels, totals, color=_LINE_COLOR, linewidth=_LINE_WIDTH)
    plt.title(f"Total XP vs. level ({levels[0]} to {levels[-1]})")
    plt.xlabel("Level")
    plt.ylabel("Total cumulative XP")
    plt.grid(True, linestyle="--", alpha=_GRID_ALPHA)
    plt.tight_layout()


# Public routines

def main() -> None:
    """
    Purpose: Print the XP curve table, then render the curve.

    Entry:
        No conditions. Bootstraps the game environment itself.

    Exit/Returns:
        Returns nothing. Prints to stdout and opens a matplotlib window.

    Module Globals:
        None.

    Methodology:
        Every cost comes from logic.calculate_xp_needed, so the table is the
        curve the game uses. Table first, figure second: the numbers stay in
        the terminal after the plot window closes.

    Notes/References:
        The old version called django.setup() at import time and put the
        current working directory on sys.path, so it ran only from blackout/
        and an import started the game environment. bootstrap() inside the
        __main__ guard fixes both.

    Author: Nick Hobar
    Creation date: 09/14/2026
    """
    env.bootstrap()

    rows = _curve_rows()
    _print_table(rows)
    _plot_curve(rows)

    plt.show()


if __name__ == "__main__":
    main()
