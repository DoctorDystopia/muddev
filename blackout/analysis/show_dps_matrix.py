"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Snapshot of the combat balance -- every weapon in ITEM_DB against
             every NPC in NPC_DB, in both directions, as damage per second and
             time to kill.

This is the output that turns four separately-correct formulas into a single
answer to "is this fight winnable". It reports both halves of a fight:

  * outbound -- how long the player takes to kill the NPC.
  * inbound  -- how long the NPC takes to kill the player, wearing the same
                armour the outbound number assumes.

and the ratio of the two, which is the number that actually decides whether an
encounter is content or a death sentence.

Everything here is expected value, not simulation: hit_chance * max_hit / 2 per
swing, divided by the weapon cadence. Variance is deliberately out of scope --
show_damage_distribution.py measures it.

Run it:
    ../evenv/Scripts/python.exe analysis/show_dps_matrix.py
"""

from __future__ import annotations

import sys
from pathlib import Path


# The game directory has to be importable before `systems.*` resolves.
# Running this file directly puts analysis/ on sys.path, not blackout/.
_GAME_DIR: str = str(Path(__file__).resolve().parents[1])

if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

import matplotlib.pyplot as plt
import numpy as np

from analysis import _snapshot_env as env


# Public constant definitions

# The stat the player's armour is chosen on. Every NPC in NPC_DB currently
# attacks crush, so crush defence is the axis worth optimising against.
ARMOUR_SELECTION_STAT: str = "crush_defense_bonus"

# Lowest level the sweeps plot from. Level 0 gives a character 0 max HP, which
# makes every inbound time-to-kill zero and squashes the ratio axis.
SWEEP_FLOOR_LEVEL: int = 1

# A kill ratio of exactly this is an even fight -- both sides drop at the same
# moment. Above it the player wins, below it the NPC does.
EVEN_FIGHT_RATIO: float = 1.0


# Private constant definitions

# Column widths for the printed tables.
_NAME_WIDTH: int = 26
_NPC_WIDTH: int = 16
_NUMBER_WIDTH: int = 8

# Figure geometry.
_FIGURE_WIDTH_INCHES: float = 18.0
_FIGURE_HEIGHT_INCHES: float = 6.5
_SUBPLOT_ROWS: int = 1
_SUBPLOT_COLUMNS: int = 3

# Styling.
_GRID_ALPHA: float = 0.3
_LINE_WIDTH: float = 2.0
_EVEN_LINE_STYLE: str = "--"
_EVEN_LINE_COLOR: str = "crimson"
_CELL_TEXT_SIZE: str = "x-small"
_TICK_TEXT_SIZE: str = "x-small"

# Time-to-kill axis is logarithmic: a level-1 unarmed player and a level-127
# battleaxe player differ by orders of magnitude, and a linear axis renders
# the entire useful band as a flat line against the floor.
_TTK_AXIS_SCALE: str = "log"

# Printed in place of a time-to-kill that never completes.
_NEVER_LABEL: str = "never"

# Flags a weapon carrying combat_rules. Every number on such a row comes from
# the OSRS formulas, which a rules definition does not obey -- so the row is
# fiction. show_rules_map names them; show_damage_distribution measures them
# through the real pipeline.
_UNMODELLED_MARK: str = " *"


# Private helper routines

def _armour_totals() -> tuple:
    """Return (totals, items) for the best armour available, hands excluded."""
    totals, items = env.best_loadout(ARMOUR_SELECTION_STAT, include_hands=False)

    return totals, items


def _player_profiles(armour: dict) -> list:
    """Unarmed plus every weapon, each merged with the same armour set."""
    unarmed = env.unarmed_profile()
    weapons = env.weapon_profiles()
    ordered = [unarmed]
    ordered.extend(weapons.values())

    profiles = []

    for weapon in ordered:
        merged = env.equipped_profile(weapon, armour)
        profiles.append(merged)

    return profiles


def _uniform_player(level: int):
    """Return a player_for callable: a player at `level` on every axis."""
    def player_for(profile):
        return env.player_combatant(level, profile)

    return player_for


def _best_damage_style(attacker, defender) -> tuple:
    """Return (style_key, metrics) for the style with the highest DPS.

    Maximising damage per second rather than hit chance or max hit is the
    whole point: an accurate style that connects more often can still lose to
    an aggressive style that hits harder, and only the product decides.
    """
    evaluated = env.evaluate_styles(attacker, defender)
    best_key = None
    best_metrics = None

    for style_key, metrics in evaluated.items():
        if best_metrics is None:
            best_key = style_key
            best_metrics = metrics
            continue

        if metrics.damage_per_second > best_metrics.damage_per_second:
            best_key = style_key
            best_metrics = metrics

    return best_key, best_metrics


def _best_weapon_for(profiles: list, player_for, defender) -> tuple:
    """Return (profile, style_key, metrics) for the best DPS against one NPC.

    player_for(profile) returns the player Combatant that holds the profile.
    """
    best_profile = None
    best_style = None
    best_metrics = None

    for profile in profiles:
        attacker = player_for(profile)
        style_key, metrics = _best_damage_style(attacker, defender)

        if best_metrics is None:
            best_profile = profile
            best_style = style_key
            best_metrics = metrics
            continue

        if metrics.damage_per_second > best_metrics.damage_per_second:
            best_profile = profile
            best_style = style_key
            best_metrics = metrics

    return best_profile, best_style, best_metrics


def _inbound_metrics(npc, player):
    """Resolve the NPC's swing against the player. Returns SwingMetrics.

    An NPC fights with its active style: the default_combat_style its block
    declares. It never picks the best style against its target, so this
    routine must not pick one either. The old version took the best-DPS
    style, which gives an NPC with several styles a choice the live game does
    not give it.
    """
    style_key = env.active_style_key(npc.profile)

    return env.swing_metrics(npc, style_key, player)


def _kill_ratio(player, npc) -> float:
    """Inbound kill time divided by outbound kill time for one matchup."""
    _style_key, outbound = _best_damage_style(player, npc)
    inbound = _inbound_metrics(npc, player)

    player_seconds = env.time_to_kill(outbound.damage_per_second, npc.max_hp)
    npc_seconds = env.time_to_kill(inbound.damage_per_second, player.max_hp)

    if player_seconds == env.UNKILLABLE_SECONDS:
        return 0.0

    if npc_seconds == env.UNKILLABLE_SECONDS:
        return float("inf")

    return npc_seconds / player_seconds


def _format_seconds(seconds: float) -> str:
    """Render a time to kill, or the never-label for an unkillable target."""
    if seconds == env.UNKILLABLE_SECONDS:
        return _NEVER_LABEL

    return f"{seconds:.1f}s"


def _plottable(seconds: float) -> float:
    """Map an unkillable time to NaN so matplotlib leaves a gap, not a spike."""
    if seconds == env.UNKILLABLE_SECONDS:
        return float("nan")

    return seconds


# Private helper routines -- printing

def _print_armour(items: list) -> None:
    """Print the armour set every player row in this snapshot is wearing."""
    print("Player armour assumed throughout "
          f"(best in slot by {ARMOUR_SELECTION_STAT})")

    if not items:
        print("  (no armour in ITEM_DB)")
        return

    for item_def in items:
        slot_label = item_def.use_slot.label
        bonus = item_def.combat_stat_bonuses.get(ARMOUR_SELECTION_STAT, 0)
        print(f"  {slot_label:<12} {item_def.name:<{_NAME_WIDTH}} {bonus:>+4}")


def _print_outbound(profiles: list, npcs: dict, title: str, player_for) -> None:
    """Print the player's damage per second and kill time against each NPC."""
    header = f"{'Weapon':<{_NAME_WIDTH}} |"

    for combatant in npcs.values():
        label = f"{combatant.name} ({combatant.max_hp}hp)"
        header += f" {label:>{_NPC_WIDTH + _NUMBER_WIDTH}}"

    print()
    print(f"OUTBOUND -- {title}: best-DPS style, DPS and time to kill")
    print(header)
    print("-" * len(header))

    unmodelled_seen = False

    for profile in profiles:
        marker = _UNMODELLED_MARK if profile.combat_rules else ""
        unmodelled_seen = unmodelled_seen or bool(profile.combat_rules)
        label = f"{profile.name}{marker}"
        line = f"{label:<{_NAME_WIDTH}} |"
        attacker = player_for(profile)

        for combatant in npcs.values():
            style_key, metrics = _best_damage_style(attacker, combatant)
            seconds = env.time_to_kill(metrics.damage_per_second, combatant.max_hp)
            time_label = _format_seconds(seconds)
            cell = (f"{style_key[:6]} {metrics.damage_per_second:4.2f}/s "
                    f"{time_label:>7}")
            line += f" {cell:>{_NPC_WIDTH + _NUMBER_WIDTH}}"

        print(line)

    if unmodelled_seen:
        print(f"  {_UNMODELLED_MARK} carries combat_rules: these numbers are the "
              f"OSRS formula, NOT what the weapon does.")
        print("    Run show_rules_map.py and show_damage_distribution.py instead.")


def _print_inbound(profiles: list, npcs: dict, title: str, player_for) -> None:
    """Print each NPC's damage per second and kill time against the player.

    The player is holding the weapon that maximises DPS against the first NPC,
    because a wielded weapon contributes its own defence bonuses to the sum
    and the choice therefore changes these numbers. Naming it in the output
    beats picking one silently.
    """
    first_npc = next(iter(npcs.values()))
    reference, _style, _metrics = _best_weapon_for(profiles, player_for, first_npc)
    player = player_for(reference)

    print()
    print(f"INBOUND -- each NPC, in its own active style, against a {title} in "
          f"the armour above, wielding {reference.name}")
    print(f"  {'NPC':<{_NPC_WIDTH}} {'hit%':>6} {'max':>4} "
          f"{'DPS':>{_NUMBER_WIDTH}} {'kills player in':>16}")

    for combatant in npcs.values():
        metrics = _inbound_metrics(combatant, player)
        seconds = env.time_to_kill(metrics.damage_per_second, player.max_hp)
        percent = metrics.clamped_hit_chance * env.PERCENT_SCALE
        time_label = _format_seconds(seconds)
        print(f"  {combatant.name:<{_NPC_WIDTH}} {percent:>5.1f}% "
              f"{metrics.max_hit:>4} {metrics.damage_per_second:>{_NUMBER_WIDTH}.3f} "
              f"{time_label:>16}")

    print(f"  Player max HP: {player.max_hp}")
    print("  Defence bonuses sum the armour set and the wielded weapon, exactly")
    print("  as EquipmentHandler.total_combat_stat_bonuses sums live gear.")


def _print_kill_ratio(profiles: list, npcs: dict, title: str, player_for) -> None:
    """Print inbound-over-outbound kill time: above 1.0 the player wins."""
    print()
    print(f"KILL RATIO -- {title}: NPC's kill time / player's kill time")
    print(f"  Above {EVEN_FIGHT_RATIO:.1f} the player wins the exchange.")
    header = f"  {'Weapon':<{_NAME_WIDTH}} |"

    for combatant in npcs.values():
        header += f" {combatant.name:>{_NPC_WIDTH}}"

    print(header)
    print("  " + "-" * (len(header) - 2))

    for profile in profiles:
        line = f"  {profile.name:<{_NAME_WIDTH}} |"
        player = player_for(profile)

        for combatant in npcs.values():
            ratio = _kill_ratio(player, combatant)
            line += f" {ratio:>{_NPC_WIDTH}.2f}"

        print(line)


# Private helper routines -- plotting

def _sweep_levels() -> tuple:
    """Every level the plots sweep, floored above the zero-HP degenerate case."""
    levels = env.level_range()
    swept = [level for level in levels if level >= SWEEP_FLOOR_LEVEL]

    return tuple(swept)


def _plot_time_to_kill(axes, profiles: list, npcs: dict) -> None:
    """Draw the player's kill time versus level, one line per NPC."""
    levels = _sweep_levels()

    for combatant in npcs.values():
        times = []

        for level in levels:
            _profile, _style, metrics = _best_weapon_for(
                profiles, _uniform_player(level), combatant
            )
            seconds = env.time_to_kill(metrics.damage_per_second, combatant.max_hp)
            times.append(_plottable(seconds))

        axes.plot(levels, times, linewidth=_LINE_WIDTH, label=combatant.name)

    axes.set_yscale(_TTK_AXIS_SCALE)
    axes.set_title("Time to kill vs player level (best weapon at each level)")
    axes.set_xlabel("Player level (all axes)")
    axes.set_ylabel("Seconds to kill")
    axes.grid(True, linestyle="--", alpha=_GRID_ALPHA)
    axes.legend(fontsize="small")


def _dps_grid(profiles: list, npcs: dict, player_for):
    """Damage per second for every (weapon, NPC) pair for one player build."""
    grid = np.zeros((len(profiles), len(npcs)))
    combatants = list(npcs.values())

    for row_index, profile in enumerate(profiles):
        attacker = player_for(profile)

        for col_index, combatant in enumerate(combatants):
            _style_key, metrics = _best_damage_style(attacker, combatant)
            grid[row_index, col_index] = metrics.damage_per_second

    return grid


def _plot_dps_grid(axes, figure, profiles: list, npcs: dict, title: str,
                   player_for) -> None:
    """Draw the weapon-by-NPC damage-per-second grid with the values written in."""
    grid = _dps_grid(profiles, npcs, player_for)
    weapon_labels = [profile.name for profile in profiles]
    npc_labels = [combatant.name for combatant in npcs.values()]

    image = axes.imshow(grid, aspect="auto")

    for row_index in range(grid.shape[0]):
        for col_index in range(grid.shape[1]):
            axes.text(col_index, row_index, f"{grid[row_index, col_index]:.2f}",
                      ha="center", va="center", color="white",
                      fontsize=_CELL_TEXT_SIZE)

    axes.set_xticks(range(len(npc_labels)))
    axes.set_xticklabels(npc_labels, fontsize=_TICK_TEXT_SIZE, rotation=20)
    axes.set_yticks(range(len(weapon_labels)))
    axes.set_yticklabels(weapon_labels, fontsize=_TICK_TEXT_SIZE)
    axes.set_title(f"Player DPS -- {title}")
    figure.colorbar(image, ax=axes, label="Damage per second")


def _plot_kill_ratio(axes, profiles: list, npcs: dict) -> None:
    """Draw the kill ratio versus level, one line per NPC, best weapon each."""
    levels = _sweep_levels()

    for combatant in npcs.values():
        ratios = []

        for level in levels:
            player_for = _uniform_player(level)
            profile, _style, _metrics = _best_weapon_for(
                profiles, player_for, combatant
            )
            ratios.append(_kill_ratio(player_for(profile), combatant))

        axes.plot(levels, ratios, linewidth=_LINE_WIDTH, label=combatant.name)

    axes.axhline(EVEN_FIGHT_RATIO, linestyle=_EVEN_LINE_STYLE,
                 color=_EVEN_LINE_COLOR, label="even fight")
    axes.set_yscale(_TTK_AXIS_SCALE)
    axes.set_title("Kill ratio vs player level (above the line, player wins)")
    axes.set_xlabel("Player level (all axes)")
    axes.set_ylabel("NPC kill time / player kill time")
    axes.grid(True, linestyle="--", alpha=_GRID_ALPHA)
    axes.legend(fontsize="small")


# Public routines

def main() -> None:
    """
    Purpose: Print the outbound, inbound and kill-ratio tables, then render the
    three-panel figure.

    Entry:
        No conditions. Bootstraps the game environment itself.

    Exit/Returns:
        Returns nothing. Prints to stdout and opens a matplotlib window.

    Module Globals:
        ARMOUR_SELECTION_STAT read.

    Methodology:
        Tables for a new character answer "is the starting content
        survivable"; the plots answer "where does that stop being true". Both
        directions use the same armour set so the two halves of a fight are
        consistent with each other -- reporting outbound damage from a geared
        player and inbound damage against a naked one is the easy way to make
        an encounter look balanced when it is not.

    Notes/References:
        The new-character tables used to show a player at level 1 on every
        axis. Character creation leaves Strike, Brawn and Defense at 0, so
        those rows gave a new character skills it does not have.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    env.bootstrap()

    combat_const = env.combat_constants()
    armour_bonuses, armour_items = _armour_totals()
    profiles = _player_profiles(armour_bonuses)
    npcs = env.npc_combatants()
    spawn_title = env.spawn_label()
    top_level = combat_const.MAX_BASE_SKILL_LEVEL
    top_title = f"uniform player level {top_level}"

    _print_armour(armour_items)
    _print_outbound(profiles, npcs, spawn_title, env.spawn_combatant)
    _print_inbound(profiles, npcs, spawn_title, env.spawn_combatant)
    _print_kill_ratio(profiles, npcs, spawn_title, env.spawn_combatant)
    _print_outbound(profiles, npcs, top_title, _uniform_player(top_level))

    figure, (left_axes, middle_axes, right_axes) = plt.subplots(
        _SUBPLOT_ROWS, _SUBPLOT_COLUMNS,
        figsize=(_FIGURE_WIDTH_INCHES, _FIGURE_HEIGHT_INCHES),
    )
    _plot_time_to_kill(left_axes, profiles, npcs)
    _plot_dps_grid(middle_axes, figure, profiles, npcs, spawn_title,
                   env.spawn_combatant)
    _plot_kill_ratio(right_axes, profiles, npcs)

    figure.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
