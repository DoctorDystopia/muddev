"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Snapshot of what combat pays -- the XP economy, joined to the
             progression curve show_skills_graph.py already plots.

The two systems are tuned in different files and have never been looked at
together. This closes that gap: it takes the damage-per-second from the same
model show_dps_matrix uses, runs it through the real XP award path, and
converts the result into the only unit that matters to a player -- hours.

Built to answer:

  * Is `controlled` competitive? It trains four skills at a third of the rate,
    which looks like a penalty and may not be one.
  * What does the integer rounding in _plan_style_xp do at low damage, where
    Blackout's numbers actually live?
  * How long is the grind to the level cap, per style, against real content?

Run it:
    ../evenv/Scripts/python.exe systems/combat/show_xp_economy.py
"""

from __future__ import annotations

import sys
from pathlib import Path


# The game directory has to be importable before `systems.*` resolves.
_GAME_DIR: str = str(Path(__file__).resolve().parents[2])

if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

import matplotlib.pyplot as plt

from systems.combat import _snapshot_env as env


# Public constant definitions

# Damage values the rounding table walks. Blackout's real hits sit at the
# bottom of this range for most of the level band, which is exactly where
# int(round(rate * damage)) stops being a rounding detail.
SAMPLED_DAMAGE: tuple = (1, 2, 3, 4, 5, 8, 10, 16)

# Levels the time-to-level table reports.
SAMPLED_LEVELS: tuple = (10, 25, 50, 75, 100, 127)

# NPC the damage-per-second reference is measured against.
REFERENCE_NPC_KEY: str = "big_mutant"

# Player level the XP-per-hour reference is measured at. Mid-band, so the rate
# is neither the spawn floor nor the cap.
REFERENCE_LEVEL: int = 50

# Seconds in an hour, for the XP-per-hour conversion.
SECONDS_PER_HOUR: float = 3600.0


# Private constant definitions

# Column widths for the printed tables.
_STYLE_WIDTH: int = 12
_SKILL_WIDTH: int = 34
_NUMBER_WIDTH: int = 10
_LEVEL_WIDTH: int = 9

# Figure geometry.
_FIGURE_WIDTH_INCHES: float = 18.0
_FIGURE_HEIGHT_INCHES: float = 6.0
_SUBPLOT_ROWS: int = 1
_SUBPLOT_COLUMNS: int = 3

# Styling.
_GRID_ALPHA: float = 0.3
_LINE_WIDTH: float = 2.0
_HOURS_AXIS_SCALE: str = "log"
_XP_AXIS_SCALE: str = "log"

# A style with no damage-dealing rate cannot ever finish a level.
_NEVER_HOURS: float = float("inf")
_NEVER_LABEL: str = "never"


# Module globals

# A stand-in attacker for _plan_style_xp, which only checks that `skills` is
# not None before planning. Passing the real award routine a shim is what lets
# this snapshot report the EXACT integers the game grants, rounding included,
# instead of a re-derivation that could drift from it.
class _PlanningStub:
    """Minimal attacker stand-in: _plan_style_xp reads nothing else off it."""

    skills = object()


# Private helper routines

def _style_table() -> dict:
    """Map each weapon_style name to the skills it trains and its rate.

    Reads combat.py's own private style-to-rate map rather than rebuilding it
    from the constants. The private access is deliberate: that dict is the
    thing under test, and a local copy would keep reporting the old numbers
    after a retune.
    """
    from systems.combat.combat import _WEAPON_STYLE_XP_MAP
    from systems.combat import constants as const

    skills_by_style = {
        "accurate": const.ACCURATE_XP_SKILLS,
        "aggressive": const.AGGRESSIVE_XP_SKILLS,
        "controlled": const.CONTROLLED_XP_SKILLS,
        "defensive": const.DEFENSIVE_XP_SKILLS,
    }
    table = {}

    for style_name, rate in _WEAPON_STYLE_XP_MAP.items():
        table[style_name] = {
            "rate": rate,
            "skills": skills_by_style.get(style_name, ()),
        }

    return table


def _awards_for(style_name: str, skills: tuple, damage: int) -> list:
    """Run the real award planner for one style at one damage value."""
    from systems.combat.combat import _plan_style_xp

    style = {
        "weapon_style": style_name,
        "weapon_style_xp_skill": skills,
    }
    attacker = _PlanningStub()

    return _plan_style_xp(attacker, style, damage)


def _total_xp(awards: list) -> int:
    """Sum every skill's award into one number."""
    total = 0

    for _skill_key, amount in awards:
        total += amount

    return total


def _award_for_skill(awards: list, skill_key: str) -> int:
    """The amount one named skill received, or zero."""
    for awarded_key, amount in awards:
        if awarded_key == skill_key:
            return amount

    return 0


def _cumulative_xp() -> list:
    """Total XP required to stand at each level, index equalling the level."""
    from systems.progression.skills.logic import calculate_xp_needed

    levels = env.level_range()
    totals = []
    running = 0

    for level in levels:
        totals.append(running)
        running += calculate_xp_needed(level)

    return totals


def _reference_damage_rate() -> tuple:
    """Return (damage_per_second, mean_damage, weapon_name) for the reference.

    Picks the highest-DPS weapon that carries no combat_rules. A rules weapon
    would make the XP numbers depend on a die this module does not model --
    show_damage_distribution owns that -- so it is excluded rather than
    silently averaged in.
    """
    npcs = env.npc_combatants()
    target = npcs[REFERENCE_NPC_KEY]
    unarmed = env.unarmed_profile()
    candidates = [unarmed]
    candidates.extend(
        profile for profile in env.weapon_profiles().values()
        if not profile.combat_rules
    )

    best_name = None
    best_dps = None
    best_damage = None

    for profile in candidates:
        player = env.player_combatant(REFERENCE_LEVEL, profile)
        evaluated = env.evaluate_styles(player, target)

        for _style_key, metrics in evaluated.items():
            if best_dps is not None and metrics.damage_per_second <= best_dps:
                continue

            best_name = profile.name
            best_dps = metrics.damage_per_second
            best_damage = metrics.average_damage

    return best_dps, best_damage, best_name


def _hours_to_level(style_name: str, skills: tuple, skill_key: str,
                    level: int, damage_per_second: float,
                    mean_damage: float) -> float:
    """Hours of sustained combat to take one skill from zero to `level`."""
    totals = _cumulative_xp()
    required = totals[level]

    if mean_damage <= 0.0:
        return _NEVER_HOURS

    awards = _awards_for(style_name, skills, round(mean_damage))
    per_hit = _award_for_skill(awards, skill_key)

    if per_hit <= 0:
        return _NEVER_HOURS

    swings_per_second = damage_per_second / mean_damage
    xp_per_second = per_hit * swings_per_second
    seconds_required = required / xp_per_second

    return seconds_required / SECONDS_PER_HOUR


# Private helper routines -- printing

def _print_style_rates(styles: dict) -> None:
    """Print what each style trains and at what per-damage rate."""
    print("XP rates by weapon style")
    print(f"  {'style':<{_STYLE_WIDTH}} {'rate/dmg':>{_NUMBER_WIDTH}} "
          f"{'skills trained':<{_SKILL_WIDTH}}")

    for style_name, entry in styles.items():
        skill_label = ", ".join(entry["skills"])
        print(f"  {style_name:<{_STYLE_WIDTH}} {entry['rate']:>{_NUMBER_WIDTH}.3f} "
              f"{skill_label:<{_SKILL_WIDTH}}")

    print("  Fortitude overrides the style rate with its own (see")
    print("  XP_PER_DAMAGE_BY_SKILL), so its column is never the style's rate.")


def _print_rounding_table(styles: dict) -> None:
    """Print total XP per hit at each sampled damage, exposing the rounding."""
    header = f"  {'style':<{_STYLE_WIDTH}} |"

    for damage in SAMPLED_DAMAGE:
        header += f" {damage:>{_LEVEL_WIDTH}}"

    print()
    print("TOTAL XP PER HIT by damage dealt -- int(round(rate * damage)) per skill")
    print(header)
    print("  " + "-" * (len(header) - 2))

    for style_name, entry in styles.items():
        line = f"  {style_name:<{_STYLE_WIDTH}} |"

        for damage in SAMPLED_DAMAGE:
            awards = _awards_for(style_name, entry["skills"], damage)
            total = _total_xp(awards)
            line += f" {total:>{_LEVEL_WIDTH}}"

        print(line)

    print("  Rounding is per skill, then summed. A style splitting one pool")
    print("  across more skills rounds more often, so these totals are NOT the")
    print("  clean multiples the rate table implies.")


def _print_time_to_level(styles: dict, damage_per_second: float,
                         mean_damage: float, weapon_name: str) -> None:
    """Print hours to take each style's primary skill to the sampled levels."""
    print()
    print(f"HOURS TO LEVEL -- sustained combat with {weapon_name} "
          f"at {damage_per_second:.2f} DPS (level {REFERENCE_LEVEL}, "
          f"mean hit {mean_damage:.2f})")
    header = f"  {'style / skill':<{_SKILL_WIDTH}} |"

    for level in SAMPLED_LEVELS:
        header += f" {level:>{_LEVEL_WIDTH}}"

    print(header)
    print("  " + "-" * (len(header) - 2))

    for style_name, entry in styles.items():
        for skill_key in entry["skills"]:
            label = f"{style_name} / {skill_key}"
            line = f"  {label:<{_SKILL_WIDTH}} |"

            for level in SAMPLED_LEVELS:
                hours = _hours_to_level(style_name, entry["skills"], skill_key,
                                        level, damage_per_second, mean_damage)

                if hours == _NEVER_HOURS:
                    line += f" {_NEVER_LABEL:>{_LEVEL_WIDTH}}"
                    continue

                line += f" {hours:>{_LEVEL_WIDTH}.1f}"

            print(line)


# Private helper routines -- plotting

def _plot_total_xp_per_hit(axes, styles: dict) -> None:
    """Draw total XP awarded per hit against damage, for every style."""
    damages = list(range(1, max(SAMPLED_DAMAGE) + 1))

    for style_name, entry in styles.items():
        totals = []

        for damage in damages:
            awards = _awards_for(style_name, entry["skills"], damage)
            totals.append(_total_xp(awards))

        axes.plot(damages, totals, linewidth=_LINE_WIDTH, marker="o",
                  label=style_name)

    axes.set_title("Total XP per hit (all skills summed)")
    axes.set_xlabel("Damage dealt")
    axes.set_ylabel("XP granted")
    axes.grid(True, linestyle="--", alpha=_GRID_ALPHA)
    axes.legend(fontsize="small")


def _plot_hours_curve(axes, styles: dict, damage_per_second: float,
                      mean_damage: float) -> None:
    """Draw hours to reach each level, one line per style's primary skill."""
    levels = env.level_range()

    for style_name, entry in styles.items():
        primary = entry["skills"][0]
        hours = []

        for level in levels:
            value = _hours_to_level(style_name, entry["skills"], primary, level,
                                    damage_per_second, mean_damage)

            if value == _NEVER_HOURS:
                hours.append(float("nan"))
                continue

            hours.append(value)

        axes.plot(levels, hours, linewidth=_LINE_WIDTH,
                  label=f"{style_name} / {primary}")

    axes.set_yscale(_HOURS_AXIS_SCALE)
    axes.set_title("Hours of combat to reach a level")
    axes.set_xlabel("Target level")
    axes.set_ylabel("Hours")
    axes.grid(True, linestyle="--", alpha=_GRID_ALPHA)
    axes.legend(fontsize="small")


def _plot_xp_curve(axes) -> None:
    """Draw the cumulative XP requirement the hours curve is derived from."""
    levels = env.level_range()
    totals = _cumulative_xp()

    axes.plot(levels, totals, linewidth=_LINE_WIDTH, color="tab:purple")
    axes.set_yscale(_XP_AXIS_SCALE)
    axes.set_title("Cumulative XP to stand at a level")
    axes.set_xlabel("Level")
    axes.set_ylabel("Total XP")
    axes.grid(True, linestyle="--", alpha=_GRID_ALPHA)


# Public routines

def main() -> None:
    """
    Purpose: Print the XP rate, rounding and time-to-level tables, then render
    the three-panel figure.

    Entry:
        No conditions. Bootstraps the game environment itself.

    Exit/Returns:
        Returns nothing. Prints to stdout and opens a matplotlib window.

    Module Globals:
        SAMPLED_DAMAGE, SAMPLED_LEVELS read.

    Methodology:
        Every XP number comes from combat.py's own _plan_style_xp, so the
        rounding behaviour reported here is the rounding the game performs.
        The damage-per-second reference comes from the same analytic model
        show_dps_matrix uses, restricted to weapons without combat_rules.

    Notes/References:
        Hours assume uninterrupted combat with a target that never runs out.
        They are a comparison between styles, not a played-time estimate.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    env.bootstrap()

    styles = _style_table()
    damage_per_second, mean_damage, weapon_name = _reference_damage_rate()

    _print_style_rates(styles)
    _print_rounding_table(styles)
    _print_time_to_level(styles, damage_per_second, mean_damage, weapon_name)

    figure, (left_axes, middle_axes, right_axes) = plt.subplots(
        _SUBPLOT_ROWS, _SUBPLOT_COLUMNS,
        figsize=(_FIGURE_WIDTH_INCHES, _FIGURE_HEIGHT_INCHES),
    )
    _plot_total_xp_per_hit(left_axes, styles)
    _plot_hours_curve(middle_axes, styles, damage_per_second, mean_damage)
    _plot_xp_curve(right_axes)

    figure.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
