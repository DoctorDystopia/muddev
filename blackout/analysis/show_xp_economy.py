"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Snapshot of what combat pays -- the XP economy, joined to the
             progression curve show_skills_graph.py already plots.

The two systems are tuned in different files. This snapshot joins them. It
runs the real XP planner from combat.py over the damage distribution of a real
swing, and it changes the result into the only unit that matters to a
player: hours.

Built to answer:

  * Is `controlled` competitive? It trains four skills at a third of the rate,
    which looks like a penalty and may not be one.
  * What does the integer rounding in _plan_style_xp do at low damage, where
    Blackout's numbers actually live?
  * How long is the grind to a level, per style, against real content?

Run it:
    ../evenv/Scripts/python.exe analysis/show_xp_economy.py
"""

from __future__ import annotations

import sys
from pathlib import Path


# The game directory has to be importable before `systems.*` resolves.
_GAME_DIR: str = str(Path(__file__).resolve().parents[1])

if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

import matplotlib.pyplot as plt

from analysis import _snapshot_env as env


# Public constant definitions

# Damage values the rounding table walks. Blackout's real hits sit at the
# bottom of this range for most of the level band, which is exactly where
# int(round(rate * damage)) stops being a rounding detail.
SAMPLED_DAMAGE: tuple = (1, 2, 3, 4, 5, 8, 10, 16)

# Levels the time-to-level table reports.
SAMPLED_LEVELS: tuple = (10, 25, 50, 75, 100, 127)

# NPC every swing in the time-to-level model is measured against.
REFERENCE_NPC_KEY: str = "big_mutant"

# Player level at which the reference weapon is chosen: the plain weapon with
# the highest DPS against the reference NPC. The weapon stays the same at every
# level of the curve, so the rows compare styles, not weapons.
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

# A level that pays no XP per swing can never be cleared.
_NEVER_HOURS: float = float("inf")
_NEVER_LABEL: str = "never"

# Message for a planning skills handler that something tried to use.
_PLANNER_GRANTED_MESSAGE: str = "the XP planner must plan XP, never grant it"


# Private data structures

class _PlanningSkills:
    """A skills handler that satisfies XpEarner and grants nothing.

    _plan_style_xp plans only for an attacker whose .skills is an XpEarner.
    XpEarner is a runtime_checkable Protocol, so isinstance checks that its
    three methods exist. The old stub used a bare object(), which fails that
    check. The planner then returned an empty plan for every hit, and every
    number in this snapshot printed as zero.

    Each method raises, because the planner must never call one. A call means
    that the planner started to grant XP.
    """

    def add_xp(self, skill_key: str, amount: int) -> None:
        """Refuse: planning must not grant XP."""
        raise RuntimeError(_PLANNER_GRANTED_MESSAGE)

    def get_total_xp(self, skill_key: str) -> int:
        """Refuse: the planner has no reason to read XP."""
        raise RuntimeError(_PLANNER_GRANTED_MESSAGE)

    def meets_prerequisite(self, skill_key: str, required_level: int) -> bool:
        """Refuse: the planner has no reason to check a level."""
        raise RuntimeError(_PLANNER_GRANTED_MESSAGE)


class _PlanningStub:
    """Minimal attacker stand-in: _plan_style_xp reads only .skills off it.

    Passing the real award routine a stub is what lets this snapshot report
    the EXACT integers the game grants, rounding included, instead of a
    re-derivation that could drift from it.
    """

    skills = _PlanningSkills()


# Private helper routines

def _style_table() -> dict:
    """Map each weapon_style name to the skills it trains and its rate.

    Reads combat.py's own private style-to-rate map rather than rebuilding it
    from the constants. The private access is deliberate: that dict is the
    thing under test, and a local copy would keep reporting the old numbers
    after a retune.
    """
    from systems.gameplay.combat.combat import _WEAPON_STYLE_XP_MAP
    from systems.gameplay.combat import constants as const

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


def _synthetic_style(style_name: str, skills: tuple) -> dict:
    """The two style keys the planner reads, for a style no weapon names."""
    return {
        "weapon_style": style_name,
        "weapon_style_xp_skill": skills,
    }


def _awards_for(style: dict, damage: int) -> list:
    """Run the real award planner for one style dict at one damage value."""
    from systems.gameplay.combat.combat import _plan_style_xp

    return _plan_style_xp(_PlanningStub(), style, damage)


def _require_planner_awards(styles: dict) -> None:
    """Stop the run if the planner pays nothing for a hit that must pay.

    Every style rate is above zero, so a plan with no XP at the highest
    sampled damage means that the planner refused the stub. The old stub
    failed in exactly this way and printed a table of zeros with no error.
    """
    top_damage = max(SAMPLED_DAMAGE)

    for style_name, entry in styles.items():
        style = _synthetic_style(style_name, entry["skills"])
        awards = _awards_for(style, top_damage)

        if awards:
            continue

        raise RuntimeError(
            f"_plan_style_xp awarded no XP for a {top_damage}-damage "
            f"{style_name} hit. The planning stub no longer passes the "
            f"planner's gate, so every number here would be zero."
        )


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


def _start_level(skill_key: str) -> int:
    """The level character creation gives a skill.

    Every skill starts at DEFAULT_START_LEVEL. Fortitude is the one exception:
    seed_fortitude_on_creation sets it to FORTITUDE_START_LEVEL.
    """
    from systems.gameplay.progression.skills import constants as skill_const

    combat_const = env.combat_constants()

    if skill_key == skill_const.SKILL_KEY_FORTITUDE:
        return combat_const.FORTITUDE_START_LEVEL

    return skill_const.DEFAULT_START_LEVEL


def _cumulative_xp() -> list:
    """Total XP required to stand at each level, index equalling the level."""
    from systems.gameplay.progression.skills.logic import calculate_xp_needed

    levels = env.level_range()
    totals = []
    running = 0

    for level in levels:
        totals.append(running)
        running += calculate_xp_needed(level)

    return totals


def _expected_award(style: dict, skill_key: str, metrics) -> float:
    """Mean XP that one swing pays one skill, misses and the roll included.

    A miss pays nothing, because ActionAttack._land_hit runs only on a hit. A
    hit rolls uniform damage on [0, max_hit], and the planner rounds each
    award to an integer. Rounding is not linear, so the mean award is NOT the
    award for the mean damage. The old model used round(mean damage), and the
    mean it rounded already included the misses.
    """
    outcomes = metrics.max_hit + 1
    paid = 0

    for damage in range(outcomes):
        awards = _awards_for(style, damage)
        paid += _award_for_skill(awards, skill_key)

    mean_on_hit = paid / outcomes

    return metrics.clamped_hit_chance * mean_on_hit


def _reference() -> tuple:
    """Return (weapon profile, target Combatant) for the time-to-level model."""
    npcs = env.npc_combatants()
    target = npcs[REFERENCE_NPC_KEY]
    profile, _style_key, _metrics = env.best_plain_weapon(REFERENCE_LEVEL, target)

    return profile, target


def _style_keys_by_name(profile) -> dict:
    """Map each weapon_style name to the first style key that uses it."""
    keys = {}

    for style_key, style in profile.combat_styles.items():
        keys.setdefault(style.get("weapon_style"), style_key)

    return keys


def _hours_curve(profile, target, style_key: str, skill_key: str) -> list:
    """Hours of combat to reach every level of one skill, from its start level.

    Returns a list indexed by level. An entry at or below the start level is
    0.0. An entry is _NEVER_HOURS once a level on the way pays no XP.

    The rate is computed again at every level, for a player at that uniform
    level. A player who trains gets stronger, so a rate held at one level
    overstates the hours at the top of the curve and understates them at the
    bottom.
    """
    from systems.gameplay.progression.skills.logic import calculate_xp_needed

    style = profile.combat_styles[style_key]
    start = _start_level(skill_key)
    hours = []
    running = 0.0

    for level in env.level_range():
        if level <= start:
            hours.append(0.0)
            continue

        cleared = level - 1
        player = env.player_combatant(cleared, profile)
        metrics = env.swing_metrics(player, style_key, target)
        per_swing = _expected_award(style, skill_key, metrics)

        if per_swing <= 0.0:
            running = _NEVER_HOURS
        else:
            xp_per_second = per_swing / metrics.seconds_per_swing
            running += calculate_xp_needed(cleared) / xp_per_second / SECONDS_PER_HOUR

        hours.append(running)

    return hours


def _training_curves(styles: dict, profile, target) -> dict:
    """Hours curves keyed (style name, skill key), or None for a missing style."""
    keys = _style_keys_by_name(profile)
    curves = {}

    for style_name, entry in styles.items():
        style_key = keys.get(style_name)

        for skill_key in entry["skills"]:
            if style_key is None:
                curves[(style_name, skill_key)] = None
                continue

            curves[(style_name, skill_key)] = _hours_curve(
                profile, target, style_key, skill_key
            )

    return curves


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

    print("  Fortitude earns its own rate from every style (see")
    print("  XP_PER_DAMAGE_BY_SKILL), not the rate in this column.")


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
        style = _synthetic_style(style_name, entry["skills"])
        line = f"  {style_name:<{_STYLE_WIDTH}} |"

        for damage in SAMPLED_DAMAGE:
            total = _total_xp(_awards_for(style, damage))
            line += f" {total:>{_LEVEL_WIDTH}}"

        print(line)

    print("  Rounding is per skill, then summed. A style splitting one pool")
    print("  across more skills rounds more often, so these totals are NOT the")
    print("  clean multiples the rate table implies.")


def _print_time_to_level(styles: dict, profile, target, curves: dict) -> None:
    """Print hours to take each style's skills to the sampled levels."""
    print()
    print(f"HOURS TO LEVEL -- {profile.name} against {target.name}, "
          f"player at a uniform level, rate recomputed at every level")
    print(f"  Weapon chosen at level {REFERENCE_LEVEL} for the highest DPS. "
          f"Each skill starts at its creation level.")
    header = f"  {'style / skill':<{_SKILL_WIDTH}} |"

    for level in SAMPLED_LEVELS:
        header += f" {level:>{_LEVEL_WIDTH}}"

    print(header)
    print("  " + "-" * (len(header) - 2))

    for style_name, entry in styles.items():
        for skill_key in entry["skills"]:
            label = f"{style_name} / {skill_key}"
            curve = curves[(style_name, skill_key)]

            if curve is None:
                print(f"  {label:<{_SKILL_WIDTH}} | "
                      f"({profile.name} has no {style_name} style)")
                continue

            line = f"  {label:<{_SKILL_WIDTH}} |"

            for level in SAMPLED_LEVELS:
                hours = curve[level]

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
        style = _synthetic_style(style_name, entry["skills"])
        totals = [_total_xp(_awards_for(style, damage)) for damage in damages]

        axes.plot(damages, totals, linewidth=_LINE_WIDTH, marker="o",
                  label=style_name)

    axes.set_title("Total XP per hit (all skills summed)")
    axes.set_xlabel("Damage dealt")
    axes.set_ylabel("XP granted")
    axes.grid(True, linestyle="--", alpha=_GRID_ALPHA)
    axes.legend(fontsize="small")


def _plot_hours_curve(axes, styles: dict, curves: dict) -> None:
    """Draw hours to reach each level, one line per style's primary skill."""
    levels = env.level_range()

    for style_name, entry in styles.items():
        primary = entry["skills"][0]
        curve = curves[(style_name, primary)]

        if curve is None:
            continue

        hours = [float("nan") if value in (0.0, _NEVER_HOURS) else value
                 for value in curve]
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
        Returns nothing. Prints to stdout and opens a matplotlib window. Raises
        RuntimeError if the XP planner refuses the planning stub.

    Module Globals:
        SAMPLED_DAMAGE, SAMPLED_LEVELS, REFERENCE_NPC_KEY, REFERENCE_LEVEL read.

    Methodology:
        Every XP number comes from combat.py's own _plan_style_xp, so the
        rounding behaviour reported here is the rounding the game performs.
        Hours use the expected award of one swing: the hit chance times the
        mean award over every damage the roll can give. The swing numbers come
        from the same analytic model show_dps_matrix uses, restricted to
        weapons without combat_rules.

    Notes/References:
        Hours assume uninterrupted combat with a target that never runs out,
        and a player whose four combat skills rise together. They compare
        styles. They are not a played-time estimate.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    env.bootstrap()

    styles = _style_table()
    _require_planner_awards(styles)

    profile, target = _reference()
    curves = _training_curves(styles, profile, target)

    _print_style_rates(styles)
    _print_rounding_table(styles)
    _print_time_to_level(styles, profile, target, curves)

    figure, (left_axes, middle_axes, right_axes) = plt.subplots(
        _SUBPLOT_ROWS, _SUBPLOT_COLUMNS,
        figsize=(_FIGURE_WIDTH_INCHES, _FIGURE_HEIGHT_INCHES),
    )
    _plot_total_xp_per_hit(left_axes, styles)
    _plot_hours_curve(middle_axes, styles, curves)
    _plot_xp_curve(right_axes)

    figure.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
