"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Snapshot of the derived combat level -- the OSRS-ported number
             that answers "how tough is this combatant".

    Base   = 0.25 * (Fortitude + Defense + floor(Augmentation / 2))
    Branch = 0.325 * (paired skills summed, or a lone skill * 1.5)
    Level  = floor(Base + best branch)

Blackout kept OSRS's literal coefficients while widening the skill range from
1-99 to 0-127, so the familiar 126 ceiling does not apply here. constants.py
predicts "around 162" for a melee-maxed character; this measures it rather
than trusting the comment, and shows what each build shape actually reaches.

Every number comes from the real get_combat_level(), driven through a shim
that satisfies the one interface it needs. Reimplementing the formula here
would let the snapshot and the game disagree, which is the failure mode the
whole snapshot family exists to catch.

Run it:
    ../evenv/Scripts/python.exe systems/combat/show_combat_level.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path


# The game directory has to be importable before `systems.*` resolves.
_GAME_DIR: str = str(Path(__file__).resolve().parents[2])

if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

import matplotlib.pyplot as plt

from systems.combat import _snapshot_env as env


# Public constant definitions

# Levels the printed table samples.
SAMPLED_LEVELS: tuple = (0, 1, 10, 25, 50, 75, 100, 127)

# OSRS's combat level ceiling, drawn for comparison. Blackout is expected to
# exceed it -- the point of the line is to show by how much.
OSRS_COMBAT_LEVEL_CEILING: int = 126

# Build shapes the snapshot compares. Each maps a label to the set of skill
# keys that rise with the sweep; every other combat skill stays at zero.
#
# "melee maxed" is the shape constants.py makes its ~162 prediction about.
# "defense only" and "offense only" bracket it: one feeds the flat base and
# nothing else, the other feeds the branch and nothing else, so together they
# show how much of a combat level each half of the formula is responsible for.
BUILD_SHAPES: dict = {
    "melee maxed": ("fortitude", "defense", "strike", "brawn"),
    "defense only": ("fortitude", "defense"),
    "offense only": ("strike", "brawn"),
}


# Private constant definitions

# Column widths for the printed tables.
_BUILD_WIDTH: int = 16
_NAME_WIDTH: int = 18
_NUMBER_WIDTH: int = 7

# Figure geometry.
_FIGURE_WIDTH_INCHES: float = 13.0
_FIGURE_HEIGHT_INCHES: float = 6.0
_SUBPLOT_ROWS: int = 1
_SUBPLOT_COLUMNS: int = 2

# Styling.
_GRID_ALPHA: float = 0.3
_LINE_WIDTH: float = 2.0
_CEILING_STYLE: str = "--"
_CEILING_COLOR: str = "crimson"
_NPC_MARKER: str = "o"
_NPC_MARKER_SIZE: float = 60.0
_BAR_WIDTH: float = 0.6

# Level assigned to a skill a build shape does not train.
_UNTRAINED_LEVEL: int = 0


# Private data structures

class _SkillsShim:
    """
    Purpose: Satisfy the one interface get_combat_level needs -- an object
    exposing .skills.get_level(skill_key).

    Entry:
        levels maps skill key -> integer level. A key absent from it reads as
        _UNTRAINED_LEVEL.

    Exit/Returns:
        Not applicable -- a stand-in.

    Module Globals:
        _UNTRAINED_LEVEL read.

    Methodology:
        Mirrors HostileNPC._NpcSkillsShim, which exists for the same reason:
        the combat maths duck-types on `.skills` and does not care whether a
        real SkillHandler is behind it. combat_level.logic guards unregistered
        skills itself, so Augmentation resolving to zero here is the same path
        a live Character takes.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """

    def __init__(self, levels: dict) -> None:
        self._levels = levels
        self.skills = self

    def get_level(self, skill_key: str) -> int:
        """Return one skill's level, defaulting to untrained."""
        return self._levels.get(skill_key, _UNTRAINED_LEVEL)


# Private helper routines

def _combat_level_for(levels: dict) -> int:
    """Run the real get_combat_level against a shimmed skill set."""
    from systems.combat.combat_level.logic import get_combat_level

    character = _SkillsShim(levels)

    return get_combat_level(character)


def _build_levels(skill_keys: tuple, level: int) -> dict:
    """Every named skill at `level`, everything else untrained."""
    levels = {}

    for skill_key in skill_keys:
        levels[skill_key] = level

    return levels


def _build_curve(skill_keys: tuple) -> list:
    """Combat level at every skill level, for one build shape."""
    levels = env.level_range()
    curve = []

    for level in levels:
        build = _build_levels(skill_keys, level)
        curve.append(_combat_level_for(build))

    return curve


def _npc_combat_levels() -> list:
    """Combat level for every NPC in NPC_DB, from its own stat block."""
    npcs = env.npc_combatants()
    rows = []

    for combatant in npcs.values():
        build = {
            "strike": combatant.strike_level,
            "brawn": combatant.brawn_level,
            "defense": combatant.defense_level,
            "fortitude": combatant.max_hp,
        }
        rows.append({
            "name": combatant.name,
            "level": _combat_level_for(build),
            "hp": combatant.max_hp,
        })

    return rows


# Private helper routines -- printing

def _print_build_table(curves: dict) -> None:
    """Print combat level at the sampled skill levels, per build shape."""
    levels = env.level_range()
    header = f"  {'build':<{_BUILD_WIDTH}} |"

    for level in SAMPLED_LEVELS:
        header += f" {level:>{_NUMBER_WIDTH}}"

    print("Combat level by uniform skill level")
    print(header)
    print("  " + "-" * (len(header) - 2))

    for label, curve in curves.items():
        line = f"  {label:<{_BUILD_WIDTH}} |"

        for level in SAMPLED_LEVELS:
            index = levels.index(level)
            line += f" {curve[index]:>{_NUMBER_WIDTH}}"

        print(line)


def _print_ceiling(curves: dict) -> None:
    """Print the top of each build shape against the OSRS reference ceiling."""
    combat_const = env.combat_constants()
    top_level = combat_const.MAX_BASE_SKILL_LEVEL

    print()
    print(f"Ceiling at skill level {top_level}")

    for label, curve in curves.items():
        reached = curve[-1]
        over = reached - OSRS_COMBAT_LEVEL_CEILING
        print(f"  {label:<{_BUILD_WIDTH}} {reached:>5}   "
              f"{over:>+5} vs OSRS's {OSRS_COMBAT_LEVEL_CEILING}")

    augmentation_share = math.floor(
        top_level / combat_const.COMBAT_LEVEL_AUGMENTATION_DIVISOR
    )
    augmentation_gain = augmentation_share * combat_const.COMBAT_LEVEL_BASE_WEIGHT
    melee_top = curves["melee maxed"][-1]
    eventual = math.floor(melee_top + augmentation_gain)

    print()
    print("  Augmentation is not a registered skill yet, so it contributes 0 to")
    print(f"  every row above. Maxing it once it ships adds {augmentation_gain:.2f},")
    print(f"  taking a melee-maxed character from {melee_top} to {eventual}.")
    print("  That reconciles the \"around 162\" figure in constants.py: that")
    print("  number is the POST-Augmentation ceiling, not the reachable one.")


def _print_npc_levels(rows: list) -> None:
    """Print each NPC's derived combat level beside its HP pool."""
    print()
    print("NPC combat levels, from their own stat blocks")
    print(f"  {'NPC':<{_NAME_WIDTH}} {'level':>6} {'hp':>6}")

    for row in rows:
        print(f"  {row['name']:<{_NAME_WIDTH}} {row['level']:>6} {row['hp']:>6}")

    print("  Fortitude for an NPC is its max_hp, since the two are the same")
    print("  number by the 1:1 scaling rule -- which makes an 87 hp monster")
    print("  read as a far higher combat level than its level-1 skills imply.")


# Private helper routines -- plotting

def _plot_build_curves(axes, curves: dict) -> None:
    """Draw combat level against skill level, one line per build shape."""
    levels = env.level_range()

    for label, curve in curves.items():
        axes.plot(levels, curve, linewidth=_LINE_WIDTH, label=label)

    axes.axhline(OSRS_COMBAT_LEVEL_CEILING, linestyle=_CEILING_STYLE,
                 color=_CEILING_COLOR,
                 label=f"OSRS ceiling ({OSRS_COMBAT_LEVEL_CEILING})")
    axes.set_title("Combat level vs uniform skill level")
    axes.set_xlabel("Skill level in every trained axis")
    axes.set_ylabel("Combat level")
    axes.grid(True, linestyle="--", alpha=_GRID_ALPHA)
    axes.legend(fontsize="small")


def _plot_npc_levels(axes, rows: list) -> None:
    """Draw each NPC's combat level as a bar."""
    labels = [row["name"] for row in rows]
    values = [row["level"] for row in rows]
    positions = range(len(labels))

    axes.bar(positions, values, width=_BAR_WIDTH)
    axes.set_xticks(list(positions))
    axes.set_xticklabels(labels, fontsize="x-small", rotation=15)
    axes.set_title("Combat level of every NPC in NPC_DB")
    axes.set_ylabel("Combat level")
    axes.grid(True, axis="y", linestyle="--", alpha=_GRID_ALPHA)

    for position, row in enumerate(rows):
        axes.scatter(position, row["level"], marker=_NPC_MARKER,
                     s=_NPC_MARKER_SIZE, color="black", zorder=3)


# Public routines

def main() -> None:
    """
    Purpose: Print the combat-level tables and render the two-panel figure.

    Entry:
        No conditions. Bootstraps the game environment itself.

    Exit/Returns:
        Returns nothing. Prints to stdout and opens a matplotlib window.

    Module Globals:
        BUILD_SHAPES, SAMPLED_LEVELS read.

    Methodology:
        Sweeps each build shape through the real get_combat_level, then reads
        the same function against every NPC's stat block so monsters and
        players land on one comparable scale.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    env.bootstrap()

    curves = {}

    for label, skill_keys in BUILD_SHAPES.items():
        curves[label] = _build_curve(skill_keys)

    _print_build_table(curves)
    _print_ceiling(curves)

    npc_rows = _npc_combat_levels()
    _print_npc_levels(npc_rows)

    figure, (left_axes, right_axes) = plt.subplots(
        _SUBPLOT_ROWS, _SUBPLOT_COLUMNS,
        figsize=(_FIGURE_WIDTH_INCHES, _FIGURE_HEIGHT_INCHES),
    )
    _plot_build_curves(left_axes, curves)
    _plot_npc_levels(right_axes, npc_rows)

    figure.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
