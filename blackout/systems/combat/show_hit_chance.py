"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Snapshot of the accuracy curve -- combat_calc.hit_chance across
             the whole level band, against the real defence bonuses in NPC_DB.

Two things this is built to expose:

1. The shape of the bifurcated curve. hit_chance switches formula at
   R_atk == R_def, and the heatmap makes that ridge visible rather than
   something to be trusted from the docstring.

2. Where the raw curve crosses HIT_CHANCE_CEILING. combat_calc.hit_chance is
   UNCLAMPED, while BaseActionRules.accuracy clamps every result to the
   ceiling even with no modifiers in play. Against a defender with strongly
   negative defence bonuses the two answers already differ, so the reference
   oracle and the live path do not agree at the top of the band.

Run it:
    ../evenv/Scripts/python.exe systems/combat/show_hit_chance.py
"""

from __future__ import annotations

import sys
from pathlib import Path


# The game directory has to be importable before `systems.*` resolves.
# Running this file directly puts systems/combat/ on sys.path, not blackout/.
_GAME_DIR: str = str(Path(__file__).resolve().parents[2])

if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

import matplotlib.pyplot as plt
import numpy as np

from systems.combat import _snapshot_env as env


# Public constant definitions

# How many level steps the plotted curves use. Every level is cheap enough
# here and avoids an interpolation artefact at the branch switch.
CURVE_STEP: int = 1


# Private constant definitions

# Column widths for the printed tables.
_NAME_WIDTH: int = 26
_STYLE_WIDTH: int = 12
_NPC_WIDTH: int = 16
_PERCENT_WIDTH: int = 7

# Figure geometry.
_FIGURE_WIDTH_INCHES: float = 17.0
_FIGURE_HEIGHT_INCHES: float = 6.0
_SUBPLOT_ROWS: int = 1
_SUBPLOT_COLUMNS: int = 3

# Styling.
_GRID_ALPHA: float = 0.3
_LINE_WIDTH: float = 2.0
_CEILING_STYLE: str = "--"
_CEILING_COLOR: str = "crimson"
_BRANCH_COLOR: str = "white"
_BRANCH_WIDTH: float = 1.0
_BAR_HEIGHT: float = 0.7

# The probability axis runs the full [0, 1] band so curves are comparable
# between runs rather than autoscaled to whatever content exists today.
_PROBABILITY_FLOOR: float = 0.0
_PROBABILITY_CEILING: float = 1.0

# Equipment bonus used for the structural heatmap. Zero on both sides isolates
# the level term, which is the thing that panel is about.
_NEUTRAL_BONUS: int = 0


# Private helper routines

def _accurate_stance_bonus() -> int:
    """The invisible Strike boost an accurate stance grants."""
    from systems.progression.skills.constants import STRIKE_SKILL_KEY

    combat_const = env.combat_constants()
    boost = combat_const.MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE

    return boost[STRIKE_SKILL_KEY]


def _attacker_profiles() -> list:
    """Unarmed plus every weapon, in a stable order for tables and legends."""
    unarmed = env.unarmed_profile()
    profiles = env.weapon_profiles()
    ordered = [unarmed]
    ordered.extend(profiles.values())

    return ordered


def _best_style_against(attacker, defender) -> tuple:
    """Return (style_key, metrics) for the style with the highest hit chance.

    Which style is best depends on the DEFENDER: a stab style beats a slash
    style against the floating eye's -42 stab defence and loses against the
    chainbody. Taking the max is what makes the number answer "what would a
    player who chose correctly get" rather than "what does the default style
    happen to give".
    """
    evaluated = env.evaluate_styles(attacker, defender)
    best_key = None
    best_metrics = None

    for style_key, metrics in evaluated.items():
        if best_metrics is None or metrics.raw_hit_chance > best_metrics.raw_hit_chance:
            best_key = style_key
            best_metrics = metrics

    return best_key, best_metrics


def _best_pair_at_level(profiles: list, level: int, defender) -> tuple:
    """Best (profile, style_key, metrics) across every weapon at one level."""
    best_profile = None
    best_style = None
    best_metrics = None

    for profile in profiles:
        attacker = env.player_combatant(level, profile)
        style_key, metrics = _best_style_against(attacker, defender)

        if best_metrics is None or metrics.raw_hit_chance > best_metrics.raw_hit_chance:
            best_profile = profile
            best_style = style_key
            best_metrics = metrics

    return best_profile, best_style, best_metrics


def _print_pair_table(profiles: list, npcs: dict, level: int) -> None:
    """Print best-style hit chance for every weapon against every NPC."""
    header = f"{'Weapon':<{_NAME_WIDTH}} |"

    for combatant in npcs.values():
        header += f" {combatant.name:>{_NPC_WIDTH}}"

    print()
    print(f"Best-style hit chance at player level {level} "
          f"(style chosen per defender)")
    print(header)
    print("-" * len(header))

    for profile in profiles:
        attacker = env.player_combatant(level, profile)
        line = f"{profile.name:<{_NAME_WIDTH}} |"

        for combatant in npcs.values():
            style_key, metrics = _best_style_against(attacker, combatant)
            percent = metrics.clamped_hit_chance * env.PERCENT_SCALE
            cell = f"{percent:5.1f}% {style_key[:6]}"
            line += f" {cell:>{_NPC_WIDTH}}"

        print(line)


def _ceiling_crossings(profiles: list, npcs: dict, level: int) -> list:
    """Every (weapon, NPC) pair whose RAW chance exceeds the live ceiling."""
    combat_const = env.combat_constants()
    ceiling = combat_const.HIT_CHANCE_CEILING
    crossings = []

    for profile in profiles:
        attacker = env.player_combatant(level, profile)

        for combatant in npcs.values():
            style_key, metrics = _best_style_against(attacker, combatant)

            if metrics.raw_hit_chance <= ceiling:
                continue

            crossings.append({
                "weapon": profile.name,
                "style": style_key,
                "npc": combatant.name,
                "raw": metrics.raw_hit_chance,
                "clamped": metrics.clamped_hit_chance,
            })

    return crossings


def _print_ceiling_report(profiles: list, npcs: dict) -> None:
    """Print where combat_calc and the live accuracy seam stop agreeing."""
    combat_const = env.combat_constants()
    ceiling = combat_const.HIT_CHANCE_CEILING
    top_level = combat_const.MAX_BASE_SKILL_LEVEL
    crossings = _ceiling_crossings(profiles, npcs, top_level)

    print()
    print(f"HIT_CHANCE_CEILING report (ceiling {ceiling:.2%}, "
          f"player level {top_level})")

    if not crossings:
        print("  No weapon/NPC pair reaches the ceiling. combat_calc.hit_chance")
        print("  and BaseActionRules.accuracy agree everywhere in current content.")
        return

    print(f"  {'Weapon':<{_NAME_WIDTH}} {'Style':<{_STYLE_WIDTH}} "
          f"{'Target':<{_NPC_WIDTH}} {'raw':>{_PERCENT_WIDTH}} "
          f"{'live':>{_PERCENT_WIDTH}}")

    for crossing in crossings:
        raw_percent = crossing["raw"] * env.PERCENT_SCALE
        live_percent = crossing["clamped"] * env.PERCENT_SCALE
        print(f"  {crossing['weapon']:<{_NAME_WIDTH}} "
              f"{crossing['style']:<{_STYLE_WIDTH}} "
              f"{crossing['npc']:<{_NPC_WIDTH}} "
              f"{raw_percent:>{_PERCENT_WIDTH}.2f} "
              f"{live_percent:>{_PERCENT_WIDTH}.2f}")

    print("  combat_calc.hit_chance is unclamped; the live seam applies the")
    print("  ceiling. Above, the reference oracle and the game disagree.")


def _plot_npc_curves(axes, profiles: list, npcs: dict) -> None:
    """Draw best-weapon hit chance versus player level, one line per NPC."""
    combat_const = env.combat_constants()
    levels = env.level_range()
    sampled = levels[::CURVE_STEP]

    for combatant in npcs.values():
        chances = []

        for level in sampled:
            _profile, _style, metrics = _best_pair_at_level(
                profiles, level, combatant
            )
            chances.append(metrics.raw_hit_chance)

        axes.plot(sampled, chances, linewidth=_LINE_WIDTH, label=combatant.name)

    axes.axhline(combat_const.HIT_CHANCE_CEILING, linestyle=_CEILING_STYLE,
                 color=_CEILING_COLOR, label="HIT_CHANCE_CEILING")
    axes.set_title("Best-weapon hit chance vs player level")
    axes.set_xlabel("Player level (all axes)")
    axes.set_ylabel("P(hit)")
    axes.set_ylim(_PROBABILITY_FLOOR, _PROBABILITY_CEILING)
    axes.grid(True, linestyle="--", alpha=_GRID_ALPHA)
    axes.legend(fontsize="small")


def _build_structural_surface(levels, stance: int):
    """Raw hit chance over attacker Strike and defender Defense, zero gear."""
    from systems.combat import combat_calc

    surface = np.zeros((levels.size, levels.size))

    for row_index, defense_level in enumerate(levels):
        effective_defense = combat_calc.effective_level(int(defense_level))
        defense_roll = combat_calc.melee_defense_roll(
            effective_defense, _NEUTRAL_BONUS
        )

        for col_index, strike_level in enumerate(levels):
            effective_attack = combat_calc.effective_level(
                int(strike_level), stance_bonus=stance
            )
            attack_roll = combat_calc.melee_attack_roll(
                effective_attack, _NEUTRAL_BONUS
            )
            chance = combat_calc.hit_chance(attack_roll, defense_roll)
            surface[row_index, col_index] = chance

    return surface


def _plot_structural_surface(axes, figure) -> None:
    """Draw the pure level-versus-level accuracy surface with its branch line."""
    levels = np.array(env.level_range())
    stance = _accurate_stance_bonus()
    surface = _build_structural_surface(levels, stance)

    mesh = axes.pcolormesh(levels, levels, surface, shading="auto",
                           vmin=_PROBABILITY_FLOOR, vmax=_PROBABILITY_CEILING)

    # The formula switches branch at R_atk == R_def. With equal (zero) gear
    # bonuses on both sides that reduces to defender_defense == strike + stance.
    branch_line = levels + stance
    axes.plot(levels, branch_line, color=_BRANCH_COLOR, linewidth=_BRANCH_WIDTH,
              linestyle=_CEILING_STYLE, label="R_atk = R_def")

    axes.set_title("Accuracy surface, zero equipment bonuses")
    axes.set_xlabel("Attacker Strike level")
    axes.set_ylabel("Defender Defense level")
    axes.set_ylim(levels[0], levels[-1])
    axes.legend(fontsize="small")
    figure.colorbar(mesh, ax=axes, label="P(hit)")


def _plot_ceiling_bars(axes, profiles: list, npcs: dict) -> None:
    """Draw raw hit chance per weapon at max level against the live ceiling."""
    combat_const = env.combat_constants()
    top_level = combat_const.MAX_BASE_SKILL_LEVEL
    labels = []
    values = []

    for combatant in npcs.values():
        for profile in profiles:
            attacker = env.player_combatant(top_level, profile)
            _style_key, metrics = _best_style_against(attacker, combatant)
            labels.append(f"{profile.name} -> {combatant.name}")
            values.append(metrics.raw_hit_chance)

    positions = np.arange(len(labels))
    axes.barh(positions, values, height=_BAR_HEIGHT)
    axes.axvline(combat_const.HIT_CHANCE_CEILING, linestyle=_CEILING_STYLE,
                 color=_CEILING_COLOR, label="HIT_CHANCE_CEILING")
    axes.set_yticks(positions)
    axes.set_yticklabels(labels, fontsize="xx-small")
    axes.set_xlim(_PROBABILITY_FLOOR, _PROBABILITY_CEILING)
    axes.set_title(f"Raw hit chance at level {top_level}")
    axes.set_xlabel("P(hit), unclamped")
    axes.grid(True, axis="x", linestyle="--", alpha=_GRID_ALPHA)
    axes.legend(fontsize="small")


# Public routines

def main() -> None:
    """
    Purpose: Print the accuracy tables and render the three-panel figure.

    Entry:
        No conditions. Bootstraps the game environment itself.

    Exit/Returns:
        Returns nothing. Prints to stdout and opens a matplotlib window.

    Module Globals:
        CURVE_STEP read.

    Methodology:
        Tables at the spawn level and at the cap bracket the band players
        actually traverse; the ceiling report then names every pair where the
        pure formula and the live seam disagree.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    env.bootstrap()

    combat_const = env.combat_constants()
    profiles = _attacker_profiles()
    npcs = env.npc_combatants()

    _print_pair_table(profiles, npcs, combat_const.FORTITUDE_START_LEVEL)
    _print_pair_table(profiles, npcs, combat_const.MAX_BASE_SKILL_LEVEL)
    _print_ceiling_report(profiles, npcs)

    figure, (left_axes, middle_axes, right_axes) = plt.subplots(
        _SUBPLOT_ROWS, _SUBPLOT_COLUMNS,
        figsize=(_FIGURE_WIDTH_INCHES, _FIGURE_HEIGHT_INCHES),
    )
    _plot_npc_curves(left_axes, profiles, npcs)
    _plot_structural_surface(middle_axes, figure)
    _plot_ceiling_bars(right_axes, profiles, npcs)

    figure.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
