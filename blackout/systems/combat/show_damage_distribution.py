"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Monte Carlo snapshot of what combat actually rolls, as opposed to
             what it averages.

Three things this exists to settle:

1. The open question in combat_calc.py. roll_damage is uniform on [0, max_hit];
   a triangular alternative sits commented out directly beneath it, unresolved
   since 08/08. Both are simulated here side by side so the choice can be made
   on the variance numbers rather than on intuition.

2. Whether the expected-value model the other snapshots use is actually right.
   show_dps_matrix divides hit_chance * max_hit / 2 by the weapon cadence;
   this runs the real pipeline and compares.

3. What the rules-carrying weapons really do. A weapon whose combat_rules
   replace the damage roll or the whole action is NOT described by the OSRS
   formulas at all, so the analytic snapshots report fiction for it. Only a
   simulation through resolve_action tells the truth.

Run it:
    ../evenv/Scripts/python.exe systems/combat/show_damage_distribution.py
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path


# The game directory has to be importable before `systems.*` resolves.
_GAME_DIR: str = str(Path(__file__).resolve().parents[2])

if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

import matplotlib.pyplot as plt
import numpy as np

from systems.combat import _snapshot_env as env


# Public constant definitions

# Swings drawn for each per-swing damage histogram.
SWING_TRIALS: int = 200000

# Complete fights simulated for each time-to-kill distribution.
FIGHT_TRIALS: int = 20000

# Seed for every draw in this snapshot, so two runs agree and a surprising
# number can be re-examined rather than re-rolled.
RNG_SEED: int = 20260822

# Player level the distributions are measured at. The mid-band is where the
# damage numbers are large enough for a distribution's shape to be visible and
# small enough to still be quantised by the integer roll.
REFERENCE_LEVEL: int = 50

# NPC the fight simulations are run against. The deepest HP pool in NPC_DB
# gives the longest fight, and therefore the most swings for variance to
# average out over -- the hardest test for a mean-based model.
REFERENCE_NPC_KEY: str = "big_mutant"

# Percentiles reported for every simulated distribution.
REPORTED_PERCENTILES: tuple = (5, 50, 95)


# Private constant definitions

# Column widths for the printed tables.
_NAME_WIDTH: int = 24
_NUMBER_WIDTH: int = 10

# Figure geometry.
_FIGURE_WIDTH_INCHES: float = 18.0
_FIGURE_HEIGHT_INCHES: float = 6.0
_SUBPLOT_ROWS: int = 1
_SUBPLOT_COLUMNS: int = 3

# Styling.
_GRID_ALPHA: float = 0.3
_HISTOGRAM_ALPHA: float = 0.6
_BAR_WIDTH: float = 0.4
_TICK_TEXT_SIZE: str = "x-small"

# Names for the two candidate damage distributions.
_UNIFORM_LABEL: str = "uniform (live)"
_TRIANGULAR_LABEL: str = "triangular (commented out)"

# The triangular roll averages two draws and breaks the .5 tie by coin flip.
# These name the two branches of that flip.
_ROUND_DOWN: int = 0

# A fight that never ends has to stop somewhere. Ten thousand swings at the
# slowest cadence is over four hours of game time -- far past any real fight,
# so hitting it means the attacker cannot win, not that the cap is too low.
_MAX_FIGHT_SWINGS: int = 10000

# Reported when a fight hit the swing cap without landing a kill.
_UNRESOLVED_LABEL: str = "unresolved"


# Private helper routines -- the two candidate damage rolls

def _uniform_roll(max_hit: int, rng) -> int:
    """The live roll: uniform on [0, max_hit] inclusive."""
    return rng.randint(0, max_hit)


def _triangular_roll(max_hit: int, rng) -> int:
    """The commented-out alternative: mean of two uniform draws.

    Reproduced verbatim from the block beneath combat_calc.roll_damage,
    including the coin flip that decides whether the .5 case floors or ceils.
    Without that flip the average of two integers biases downward, which is
    the detail the original author called out and the reason it is a coin
    flip rather than a plain round().
    """
    tie_break = rng.randint(0, 1)
    first = rng.randint(0, max_hit)
    second = rng.randint(0, max_hit)
    total = first + second

    if tie_break == _ROUND_DOWN:
        return math.floor(total / 2.0)

    return math.ceil(total / 2.0)


# Private helper routines -- simulation

def _reference_pair(profile):
    """Return (player, npc) for the level and target this snapshot uses."""
    npcs = env.npc_combatants()
    target = npcs[REFERENCE_NPC_KEY]
    player = env.player_combatant(REFERENCE_LEVEL, profile)

    return player, target


def _best_style(player, target) -> str:
    """The style key with the highest analytic DPS against the target."""
    evaluated = env.evaluate_styles(player, target)
    best_key = None
    best_dps = None

    for style_key, metrics in evaluated.items():
        if best_dps is None or metrics.damage_per_second > best_dps:
            best_key = style_key
            best_dps = metrics.damage_per_second

    return best_key


def _swing_damages(metrics, roll_function, rng) -> np.ndarray:
    """Draw SWING_TRIALS swings under one damage distribution.

    Accuracy is rolled first and damage second, the same order and the same
    draw count BaseActionRules.resolve uses, so a miss contributes a real zero
    rather than being dropped from the sample.
    """
    damages = np.zeros(SWING_TRIALS, dtype=int)

    for index in range(SWING_TRIALS):
        if rng.random() >= metrics.clamped_hit_chance:
            continue

        damages[index] = roll_function(metrics.max_hit, rng)

    return damages


def _fight_lengths(metrics, hit_points: int, roll_function, rng) -> tuple:
    """Simulate FIGHT_TRIALS complete fights.

    Returns (lengths, truncated): seconds to kill per trial, and how many
    trials hit the swing cap without landing a kill. A truncated trial's
    length is a FLOOR, not a measurement, so the count has to travel with the
    sample -- silently keeping the capped value would pull the mean down and
    make an unwinnable fight look merely slow.
    """
    lengths = np.zeros(FIGHT_TRIALS)
    truncated = 0

    for trial in range(FIGHT_TRIALS):
        remaining = hit_points
        swings = 0

        while remaining > 0 and swings < _MAX_FIGHT_SWINGS:
            swings += 1

            if rng.random() >= metrics.clamped_hit_chance:
                continue

            remaining -= roll_function(metrics.max_hit, rng)

        if remaining > 0:
            truncated += 1

        lengths[trial] = swings * metrics.seconds_per_swing

    return lengths, truncated


def _simulated_damage(player, style_key: str, target, rng) -> np.ndarray:
    """Damage per swing through the REAL pipeline, rules definitions included."""
    damages = np.zeros(SWING_TRIALS, dtype=int)

    for index in range(SWING_TRIALS):
        result = env.simulate_swing(player, style_key, target, rng)
        damages[index] = result.damage

    return damages


# Private helper routines -- printing

def _describe(samples: np.ndarray) -> dict:
    """Mean, standard deviation and the reported percentiles of a sample."""
    percentiles = np.percentile(samples, REPORTED_PERCENTILES)
    described = {
        "mean": float(samples.mean()),
        "stdev": float(samples.std()),
    }

    for position, percentile in enumerate(REPORTED_PERCENTILES):
        described[f"p{percentile}"] = float(percentiles[position])

    return described


def _print_distribution_table(title: str, rows: dict, unit: str) -> None:
    """Print one comparison block of distribution statistics."""
    header = f"  {'distribution':<{_NAME_WIDTH}} {'mean':>{_NUMBER_WIDTH}} "
    header += f"{'stdev':>{_NUMBER_WIDTH}}"

    for percentile in REPORTED_PERCENTILES:
        header += f" {'p' + str(percentile):>{_NUMBER_WIDTH}}"

    print()
    print(title)
    print(header)

    for label, described in rows.items():
        line = (f"  {label:<{_NAME_WIDTH}} {described['mean']:>{_NUMBER_WIDTH}.3f} "
                f"{described['stdev']:>{_NUMBER_WIDTH}.3f}")

        for percentile in REPORTED_PERCENTILES:
            value = described[f"p{percentile}"]
            line += f" {value:>{_NUMBER_WIDTH}.3f}"

        print(line)

    print(f"  Units: {unit}")


def _print_truncation(uniform_cut: int, triangular_cut: int) -> None:
    """Report any fights that hit the swing cap without resolving."""
    if uniform_cut == 0 and triangular_cut == 0:
        print(f"  Every fight resolved inside the {_MAX_FIGHT_SWINGS}-swing cap.")
        return

    print(f"  {_UNRESOLVED_LABEL}: {uniform_cut} uniform and {triangular_cut} "
          f"triangular trials hit the {_MAX_FIGHT_SWINGS}-swing cap.")
    print("  Those rows are floors, not measurements -- the statistics above")
    print("  understate the true time to kill by an unknown amount.")


def _print_model_check(profiles: list, rng) -> list:
    """Compare the analytic mean damage against the simulated pipeline mean.

    Returns the rows so the plot can reuse them rather than re-simulating.
    """
    npcs = env.npc_combatants()
    target = npcs[REFERENCE_NPC_KEY]
    rows = []

    print()
    print(f"MODEL CHECK -- analytic vs simulated mean damage per swing "
          f"(level {REFERENCE_LEVEL} vs {target.name})")
    print(f"  {'Weapon':<{_NAME_WIDTH}} {'analytic':>{_NUMBER_WIDTH}} "
          f"{'simulated':>{_NUMBER_WIDTH}} {'error':>{_NUMBER_WIDTH}}  rules")

    for profile in profiles:
        player = env.player_combatant(REFERENCE_LEVEL, profile)
        style_key = _best_style(player, target)
        metrics = env.swing_metrics(player, style_key, target)
        simulated = _simulated_damage(player, style_key, target, rng)
        measured = float(simulated.mean())
        analytic = metrics.average_damage
        error = measured - analytic
        rule_label = ", ".join(profile.combat_rules) or "-"

        rows.append({
            "name": profile.name,
            "analytic": analytic,
            "simulated": measured,
            "error": error,
            "rules": rule_label,
        })

        print(f"  {profile.name:<{_NAME_WIDTH}} {analytic:>{_NUMBER_WIDTH}.3f} "
              f"{measured:>{_NUMBER_WIDTH}.3f} {error:>+{_NUMBER_WIDTH}.3f}  "
              f"{rule_label}")

    print("  A non-zero error on a weapon with no rules would mean the")
    print("  expected-value model in show_dps_matrix is wrong. On a weapon WITH")
    print("  rules it means the OSRS formulas never described it in the first")
    print("  place -- the analytic snapshots cannot model those rows.")

    return rows


# Private helper routines -- plotting

def _plot_swing_histograms(axes, uniform: np.ndarray,
                           triangular: np.ndarray) -> None:
    """Draw the two candidate per-swing damage distributions together."""
    top = max(uniform.max(), triangular.max())
    bins = np.arange(0, top + 2) - 0.5

    axes.hist(uniform, bins=bins, alpha=_HISTOGRAM_ALPHA, density=True,
              label=_UNIFORM_LABEL)
    axes.hist(triangular, bins=bins, alpha=_HISTOGRAM_ALPHA, density=True,
              label=_TRIANGULAR_LABEL)

    axes.set_title(f"Damage per swing at level {REFERENCE_LEVEL}")
    axes.set_xlabel("Damage (0 includes misses)")
    axes.set_ylabel("Probability")
    axes.grid(True, linestyle="--", alpha=_GRID_ALPHA)
    axes.legend(fontsize="small")


def _plot_fight_histograms(axes, uniform: np.ndarray,
                           triangular: np.ndarray) -> None:
    """Draw the two candidate time-to-kill distributions together."""
    axes.hist(uniform, bins=60, alpha=_HISTOGRAM_ALPHA, density=True,
              label=_UNIFORM_LABEL)
    axes.hist(triangular, bins=60, alpha=_HISTOGRAM_ALPHA, density=True,
              label=_TRIANGULAR_LABEL)

    axes.set_title(f"Time to kill {REFERENCE_NPC_KEY}")
    axes.set_xlabel("Seconds")
    axes.set_ylabel("Probability density")
    axes.grid(True, linestyle="--", alpha=_GRID_ALPHA)
    axes.legend(fontsize="small")


def _plot_model_check(axes, rows: list) -> None:
    """Draw analytic against simulated mean damage, one pair of bars per weapon."""
    labels = [row["name"] for row in rows]
    analytic = [row["analytic"] for row in rows]
    simulated = [row["simulated"] for row in rows]
    positions = np.arange(len(labels))

    axes.barh(positions - _BAR_WIDTH / 2, analytic, height=_BAR_WIDTH,
              label="analytic (combat_calc)")
    axes.barh(positions + _BAR_WIDTH / 2, simulated, height=_BAR_WIDTH,
              label="simulated (rules pipeline)")

    axes.set_yticks(positions)
    axes.set_yticklabels(labels, fontsize=_TICK_TEXT_SIZE)
    axes.set_title("Where the analytic model breaks")
    axes.set_xlabel("Mean damage per swing")
    axes.grid(True, axis="x", linestyle="--", alpha=_GRID_ALPHA)
    axes.legend(fontsize="small")


# Public routines

def main() -> None:
    """
    Purpose: Simulate the damage distributions and print the comparison tables.

    Entry:
        No conditions. Bootstraps the game environment itself.

    Exit/Returns:
        Returns nothing. Prints to stdout and opens a matplotlib window.

    Module Globals:
        RNG_SEED, SWING_TRIALS, FIGHT_TRIALS read.

    Methodology:
        The uniform-versus-triangular comparison runs on the DEFAULT path
        only, because that is the roll the open question is about -- a d20
        sword replaces roll_damage outright and would not change either way.
        The model check then runs every weapon through the real pipeline,
        which is where the rules-carrying weapons diverge.

    Notes/References:
        One seeded Random drives every draw, so the whole snapshot is
        reproducible from RNG_SEED alone.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    env.bootstrap()

    rng = random.Random(RNG_SEED)
    unarmed = env.unarmed_profile()
    weapons = env.weapon_profiles()

    plain = [unarmed]
    plain.extend(
        profile for profile in weapons.values() if not profile.combat_rules
    )
    reference_profile = plain[-1]
    player, target = _reference_pair(reference_profile)
    style_key = _best_style(player, target)
    metrics = env.swing_metrics(player, style_key, target)

    print(f"Reference: {reference_profile.name}, style {style_key}, "
          f"level {REFERENCE_LEVEL}, target {target.name} ({target.max_hp} hp)")
    print(f"  hit chance {metrics.clamped_hit_chance:.4f}, "
          f"max hit {metrics.max_hit}, "
          f"cadence {metrics.seconds_per_swing:.1f}s")

    uniform_swings = _swing_damages(metrics, _uniform_roll, rng)
    triangular_swings = _swing_damages(metrics, _triangular_roll, rng)
    _print_distribution_table(
        "PER-SWING DAMAGE",
        {
            _UNIFORM_LABEL: _describe(uniform_swings),
            _TRIANGULAR_LABEL: _describe(triangular_swings),
        },
        "damage",
    )

    uniform_fights, uniform_cut = _fight_lengths(
        metrics, target.max_hp, _uniform_roll, rng
    )
    triangular_fights, triangular_cut = _fight_lengths(
        metrics, target.max_hp, _triangular_roll, rng
    )
    _print_distribution_table(
        "TIME TO KILL",
        {
            _UNIFORM_LABEL: _describe(uniform_fights),
            _TRIANGULAR_LABEL: _describe(triangular_fights),
        },
        "seconds",
    )
    _print_truncation(uniform_cut, triangular_cut)

    all_profiles = [unarmed]
    all_profiles.extend(weapons.values())
    rows = _print_model_check(all_profiles, rng)

    figure, (left_axes, middle_axes, right_axes) = plt.subplots(
        _SUBPLOT_ROWS, _SUBPLOT_COLUMNS,
        figsize=(_FIGURE_WIDTH_INCHES, _FIGURE_HEIGHT_INCHES),
    )
    _plot_swing_histograms(left_axes, uniform_swings, triangular_swings)
    _plot_fight_histograms(middle_axes, uniform_fights, triangular_fights)
    _plot_model_check(right_axes, rows)

    figure.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
