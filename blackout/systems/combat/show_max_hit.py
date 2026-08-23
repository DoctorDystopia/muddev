"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Snapshot of the melee damage ceiling -- combat_calc.max_melee_hit
             swept across the whole Brawn band and the whole equipment-bonus
             band, with every weapon in ITEM_DB plotted on it.

Answers the question that currently needs hand arithmetic: what is the largest
number this game can put on the screen right now, and how much of it comes
from levelling versus from gear.

Run it:
    ../evenv/Scripts/python.exe systems/combat/show_max_hit.py
"""

from __future__ import annotations

import sys
from pathlib import Path


# The game directory has to be importable before `systems.*` resolves.
# Running this file directly puts systems/combat/ on sys.path, not blackout/,
# so the insert happens here rather than inside _snapshot_env -- by the time
# that module could fix the path, importing it has already failed.
_GAME_DIR: str = str(Path(__file__).resolve().parents[2])

if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

import matplotlib.pyplot as plt
import numpy as np

from systems.combat import _snapshot_env as env


# Public constant definitions

# The equipment strength bonus the heatmap sweeps up to. Well past anything in
# ITEM_DB today (the best is single digits) so the surface shows where the
# content could go, not only where it is.
STRENGTH_BONUS_CEILING: int = 150

# Brawn levels the printed table samples. A 128-row table is unreadable; these
# are the decade marks plus both ends and the spawn level.
SAMPLED_LEVELS: tuple = (0, 1, 10, 25, 50, 75, 100, 127)

# Equipment key the whole snapshot turns on.
STRENGTH_BONUS_KEY: str = "melee_strength_bonus"

# The weapon style that maximises damage. Named rather than inferred because
# the table needs one comparable style across weapons whose style keys differ.
DAMAGE_WEAPON_STYLE: str = "aggressive"


# Private constant definitions

# Column widths for the printed tables.
_NAME_WIDTH: int = 26
_STYLE_WIDTH: int = 12
_SLOT_WIDTH: int = 12
_NUMBER_WIDTH: int = 6

# Contour lines drawn over the heatmap, in damage. Chosen to bracket the
# interesting band rather than to divide the range evenly.
_CONTOUR_LEVELS: tuple = (5, 10, 15, 20, 25, 30, 35)

# Figure geometry.
_FIGURE_WIDTH_INCHES: float = 15.0
_FIGURE_HEIGHT_INCHES: float = 6.5
_SUBPLOT_ROWS: int = 1
_SUBPLOT_COLUMNS: int = 2

# Styling for the real-gear markers laid over the heatmap.
_GEAR_MARKER: str = "o"
_GEAR_MARKER_SIZE: float = 55.0
_GEAR_MARKER_COLOR: str = "white"
_GEAR_MARKER_EDGE: str = "black"
_GEAR_MARKER_Z: int = 3
_GRID_ALPHA: float = 0.3
_LINE_WIDTH: float = 2.0
_CONTOUR_WIDTH: float = 0.8

# Lowest equipment bonus the surface starts from.
_BONUS_FLOOR: int = 0

# Flags a table row shown at a stance other than aggressive.
_FALLBACK_MARK: str = " *"

# Flags a weapon carrying combat_rules. Its max hit here is the OSRS formula,
# which a rules definition owning roll_damage or max_hit does not obey.
_UNMODELLED_MARK: str = " +"


# Private helper routines

def _aggressive_stance_bonus() -> int:
    """The invisible Brawn boost an aggressive stance grants."""
    from systems.progression.skills.constants import BRAWN_SKILL_KEY

    combat_const = env.combat_constants()
    boost = combat_const.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE

    return boost[BRAWN_SKILL_KEY]


def _damage_style_key(profile) -> str:
    """Return the style key on `profile` whose weapon_style maximises damage.

    Returns (style_key, is_aggressive). Every weapon defines its styles under
    its own flavour names -- a dagger "lunge" and a battleaxe "hack" are both
    aggressive -- so selecting on the weapon_style field rather than on the
    key is what lets weapons be compared against each other at all.

    A profile declaring no aggressive option (the gadgets do not) falls back
    to its first style and reports False, because such a row is NOT comparable
    with the rest of the table: it carries a different stance bonus, so its
    numbers would read as a weaker weapon rather than as a missing style.
    """
    for style_key, style in profile.combat_styles.items():
        if style.get("weapon_style") == DAMAGE_WEAPON_STYLE:
            return style_key, True

    first_key = next(iter(profile.combat_styles))

    return first_key, False


def _max_hit_curve(strength_bonus: int, stance_bonus: int) -> list:
    """Max hit at every Brawn level for one fixed equipment strength bonus."""
    from systems.combat import combat_calc

    levels = env.level_range()
    curve = []

    for level in levels:
        effective = combat_calc.effective_level(level, stance_bonus=stance_bonus)
        hit = combat_calc.max_melee_hit(effective, strength_bonus)
        curve.append(hit)

    return curve


def _weapon_rows() -> list:
    """One row per weapon plus unarmed: profile, style, stance, bonus, curve."""
    from systems.progression.skills.constants import BRAWN_SKILL_KEY

    profiles = env.weapon_profiles()
    unarmed = env.unarmed_profile()
    ordered = [unarmed]
    ordered.extend(profiles.values())

    rows = []

    for profile in ordered:
        style_key, is_aggressive = _damage_style_key(profile)
        style = profile.combat_styles[style_key]
        boost = style.get("weapon_style_level_boost") or {}
        stance = boost.get(BRAWN_SKILL_KEY, env.NO_STANCE_BONUS)
        bonus = profile.combat_stat_bonuses.get(STRENGTH_BONUS_KEY, _BONUS_FLOOR)
        curve = _max_hit_curve(bonus, stance)

        rows.append({
            "profile": profile,
            "style_key": style_key,
            "is_aggressive": is_aggressive,
            "stance": stance,
            "bonus": bonus,
            "curve": curve,
        })

    return rows


def _print_weapon_table(rows: list) -> None:
    """Print max hit per weapon at the sampled Brawn levels."""
    levels = env.level_range()
    header = (f"{'Weapon':<{_NAME_WIDTH}} | {'Style':<{_STYLE_WIDTH}} | "
              f"{'Str':>4} | {'Spd':>3} |")

    for level in SAMPLED_LEVELS:
        header += f" {level:>{_NUMBER_WIDTH}}"

    print("Max hit by Brawn level -- aggressive stance where the weapon has one")
    print(header)
    print("-" * len(header))

    fallback_seen = False
    unmodelled_seen = False

    for row in rows:
        profile = row["profile"]
        marker = "" if row["is_aggressive"] else _FALLBACK_MARK
        fallback_seen = fallback_seen or not row["is_aggressive"]
        rules_mark = _UNMODELLED_MARK if profile.combat_rules else ""
        unmodelled_seen = unmodelled_seen or bool(profile.combat_rules)
        style_label = f"{row['style_key']}{marker}"
        name_label = f"{profile.name}{rules_mark}"
        line = (f"{name_label:<{_NAME_WIDTH}} | "
                f"{style_label:<{_STYLE_WIDTH}} | "
                f"{row['bonus']:>4} | {profile.attack_speed:>3} |")

        for level in SAMPLED_LEVELS:
            index = levels.index(level)
            hit = row["curve"][index]
            line += f" {hit:>{_NUMBER_WIDTH}}"

        print(line)

    if fallback_seen:
        print()
        print(f"  {_FALLBACK_MARK} no aggressive style; shown at its own stance "
              f"and not comparable with the rows above")

    if unmodelled_seen:
        print(f"  {_UNMODELLED_MARK} carries combat_rules: this is the OSRS "
              f"formula, NOT the weapon's real damage.")
        print("    See show_rules_map.py and show_damage_distribution.py.")


def _print_gear_ceiling(totals: dict, items: list) -> None:
    """Print the best strength loadout in ITEM_DB and the max hit it reaches."""
    from systems.combat import combat_calc

    combat_const = env.combat_constants()
    bonus = totals.get(STRENGTH_BONUS_KEY, _BONUS_FLOOR)
    top_level = combat_const.MAX_BASE_SKILL_LEVEL
    stance = _aggressive_stance_bonus()
    effective = combat_calc.effective_level(top_level, stance_bonus=stance)
    ceiling = combat_calc.max_melee_hit(effective, bonus)

    print()
    print("Best strength loadout currently in ITEM_DB")

    for item_def in items:
        item_bonus = item_def.combat_stat_bonuses.get(STRENGTH_BONUS_KEY, _BONUS_FLOOR)
        slot_label = item_def.use_slot.label
        print(f"  {slot_label:<{_SLOT_WIDTH}} {item_def.name:<{_NAME_WIDTH}} "
              f"{item_bonus:>+4}")

    print(f"  {'TOTAL':<{_SLOT_WIDTH}} {'':<{_NAME_WIDTH}} {bonus:>+4}")
    print(f"  Max hit at Brawn {top_level}, aggressive stance: {ceiling}")


def _build_surface(levels, bonuses, stance: int):
    """Max hit for every (equipment bonus, Brawn level) pair in the grid."""
    from systems.combat import combat_calc

    surface = np.zeros((bonuses.size, levels.size), dtype=int)

    for row_index, bonus in enumerate(bonuses):
        for col_index, level in enumerate(levels):
            effective = combat_calc.effective_level(int(level), stance_bonus=stance)
            hit = combat_calc.max_melee_hit(effective, int(bonus))
            surface[row_index, col_index] = hit

    return surface


def _plot_weapon_curves(axes, rows: list) -> None:
    """Draw max hit versus Brawn level, one line per weapon."""
    levels = env.level_range()

    for row in rows:
        label = f"{row['profile'].name} ({row['bonus']:+d} str)"
        axes.plot(levels, row["curve"], linewidth=_LINE_WIDTH, label=label)

    axes.set_title("Max hit vs Brawn level")
    axes.set_xlabel("Brawn level")
    axes.set_ylabel("Max hit")
    axes.grid(True, linestyle="--", alpha=_GRID_ALPHA)
    axes.legend(fontsize="small")


def _plot_bonus_surface(axes, figure, rows: list) -> None:
    """Draw the max-hit surface over Brawn level and equipment strength bonus."""
    levels = np.array(env.level_range())
    bonuses = np.arange(_BONUS_FLOOR, STRENGTH_BONUS_CEILING + 1)
    stance = _aggressive_stance_bonus()
    surface = _build_surface(levels, bonuses, stance)
    contour_levels = list(_CONTOUR_LEVELS)

    mesh = axes.pcolormesh(levels, bonuses, surface, shading="auto")
    contours = axes.contour(levels, bonuses, surface, levels=contour_levels,
                            colors="white", linewidths=_CONTOUR_WIDTH)
    axes.clabel(contours, inline=True, fontsize="x-small", fmt="%d")

    top_level = levels[-1]

    for row in rows:
        axes.scatter(top_level, row["bonus"], marker=_GEAR_MARKER,
                     s=_GEAR_MARKER_SIZE, c=_GEAR_MARKER_COLOR,
                     edgecolors=_GEAR_MARKER_EDGE, zorder=_GEAR_MARKER_Z)

    axes.set_title("Max hit surface (dots: strength bonuses that exist today)")
    axes.set_xlabel("Brawn level")
    axes.set_ylabel("Equipment strength bonus")
    figure.colorbar(mesh, ax=axes, label="Max hit")


# Public routines

def main() -> None:
    """
    Purpose: Print the max-hit tables and render the two-panel figure.

    Entry:
        No conditions. Bootstraps the game environment itself.

    Exit/Returns:
        Returns nothing. Prints to stdout and opens a matplotlib window.

    Module Globals:
        STRENGTH_BONUS_KEY read.

    Methodology:
        Table first, figure second, matching show_skills_graph.py -- the
        numbers stay in the terminal scrollback after the plot window closes.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    env.bootstrap()

    rows = _weapon_rows()
    _print_weapon_table(rows)

    totals, items = env.best_loadout(STRENGTH_BONUS_KEY)
    _print_gear_ceiling(totals, items)

    figure, (left_axes, right_axes) = plt.subplots(
        _SUBPLOT_ROWS, _SUBPLOT_COLUMNS,
        figsize=(_FIGURE_WIDTH_INCHES, _FIGURE_HEIGHT_INCHES),
    )
    _plot_weapon_curves(left_axes, rows)
    _plot_bonus_surface(right_axes, figure, rows)

    figure.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
