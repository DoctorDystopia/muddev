"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Shared bootstrap and math scaffolding for the combat snapshot
             scripts -- show_max_hit.py, show_hit_chance.py and
             show_dps_matrix.py all sweep the same pure combat_calc surface
             and differ only in what they tabulate and plot.

Django is deliberately NOT started at import time. show_skills_graph.py calls
django.setup() at module scope, so merely importing it stands a whole game
environment up -- the import hazard CLAUDE.md documents for blackout/scripts/.
Here the snapshot scripts call bootstrap() from inside their own __main__
guard, which leaves this module inert on import.

Every systems.combat / world import therefore lives INSIDE a routine rather
than at the top of the file: those modules read Django settings while being
imported and raise ImproperlyConfigured if bootstrap() has not run yet.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


# Public constant definitions

# Dotted path Evennia expects for this game's Django settings.
DJANGO_SETTINGS_MODULE_PATH: str = "server.conf.settings"

# The environment variable Django reads that path out of.
DJANGO_SETTINGS_ENV_VAR: str = "DJANGO_SETTINGS_MODULE"

# combat_calc.roll_damage is uniform on [0, max_hit] inclusive, whose mean is
# max_hit / 2. Named so the damage-per-second maths does not carry a bare 2.
UNIFORM_ROLL_MEAN_DIVISOR: float = 2.0

# Turns a probability into a percentage for display.
PERCENT_SCALE: float = 100.0

# time_to_kill's answer when the attacker deals no damage at all. A real
# outcome for a low-level swing at a high-defense target, not an error.
UNKILLABLE_SECONDS: float = float("inf")

# Stance boost for a skill axis the active style does not name.
NO_STANCE_BONUS: int = 0


# Private constant definitions

# This file sits at blackout/systems/combat/, so the game directory is two
# parents up. Derived rather than hardcoded so a snapshot runs from any cwd.
_BLACKOUT_ROOT: Path = Path(__file__).resolve().parents[2]

# Per-damage-type equipment keys. The attack type ("stab"/"slash"/"crush") is
# interpolated in, exactly as systems/combat/combat.py does it.
_ATTACK_BONUS_TEMPLATE: str = "{attack_type}_attack_bonus"
_DEFENSE_BONUS_TEMPLATE: str = "{attack_type}_defense_bonus"
_STRENGTH_BONUS_KEY: str = "melee_strength_bonus"

# Value assumed for an equipment key no item in a loadout declares.
_ABSENT_BONUS: int = 0


# Module globals

# Set True by bootstrap() so repeated calls are cheap and harmless.
_environment_ready: bool = False


# Public data structures

@dataclass
class AttackProfile:
    """
    Purpose: Normalise the three things that can swing -- a weapon ItemDef, an
    NpcDef stat block, and the unarmed fallback -- into one shape.

    Entry:
        combat_styles must be non-empty; every snapshot indexes it by style key.

    Exit/Returns:
        Not applicable -- a record.

    Module Globals:
        None.

    Methodology:
        Mirrors the dict combat.combat_profile() hands the live pipeline
        (combat_stat_bonuses / active_combat_style / attack_speed), flattened
        to all styles at once because a snapshot sweeps every style rather
        than resolving the one that happens to be selected.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """

    key: str
    name: str
    attack_speed: int
    combat_stat_bonuses: dict = field(default_factory=dict)
    combat_styles: dict = field(default_factory=dict)

    # Keys into RULES_REGISTRY. A non-empty list means the analytic
    # swing_metrics model does NOT describe this weapon: a rules definition
    # can replace the damage roll or the whole action, and the OSRS formulas
    # then say nothing about what it does. simulate_swing is the only honest
    # way to measure one of these.
    combat_rules: list = field(default_factory=list)


@dataclass
class Combatant:
    """
    Purpose: One side of a swing -- the skill levels the OSRS maths reads plus
    the profile it swings with.

    Entry:
        Levels are on Blackout's 0..127 scale. max_hp is the Fortitude-derived
        pool for a Character, or NpcDef.max_hp for a monster.

    Exit/Returns:
        Not applicable -- a record.

    Module Globals:
        None.

    Methodology:
        Deliberately carries the defender's numbers as well as the attacker's,
        because swing_metrics needs both sides -- the live ActionContext
        carries both for the same reason.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """

    name: str
    strike_level: int
    brawn_level: int
    defense_level: int
    max_hp: int
    profile: AttackProfile


@dataclass
class SwingMetrics:
    """
    Purpose: Every intermediate the OSRS pipeline computes for one swing,
    kept rather than discarded so a snapshot can show the working.

    Entry:
        Populated only by swing_metrics().

    Exit/Returns:
        Not applicable -- a record.

    Module Globals:
        None.

    Methodology:
        raw_hit_chance is combat_calc.hit_chance untouched; clamped_hit_chance
        is that number after HIT_CHANCE_CEILING, which is what the live
        BaseActionRules.accuracy seam actually returns. The two are kept apart
        because they disagree at the top of the level band, and that
        divergence is one of the things worth snapshotting.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """

    effective_attack: int
    effective_strength: int
    effective_defense: int
    attack_roll: int
    defense_roll: int
    raw_hit_chance: float
    clamped_hit_chance: float
    max_hit: int
    average_damage: float
    damage_per_second: float
    seconds_per_swing: float


# Public routines -- environment

def bootstrap() -> None:
    """
    Purpose: Stand up the Evennia/Django environment so the combat modules can
    be imported.

    Entry:
        No conditions. Safe to call more than once.

    Exit/Returns:
        Returns nothing. On return, systems.* and world.* are importable.

    Module Globals:
        _environment_ready read and written.
        _BLACKOUT_ROOT read.
        DJANGO_SETTINGS_ENV_VAR, DJANGO_SETTINGS_MODULE_PATH read.

    Methodology:
        Puts the game directory on sys.path, points Django at the game
        settings, and calls django.setup(). The path comes from __file__
        rather than os.getcwd(), so a snapshot script runs correctly from the
        repo root, from blackout/, or from an IDE with any working directory.

    Notes/References:
        setdefault, not assignment: a caller that has already chosen a
        settings module (a test harness, say) keeps its choice.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    global _environment_ready

    if _environment_ready:
        return

    root_path = str(_BLACKOUT_ROOT)

    if root_path not in sys.path:
        sys.path.insert(0, root_path)

    os.environ.setdefault(DJANGO_SETTINGS_ENV_VAR, DJANGO_SETTINGS_MODULE_PATH)

    import django

    django.setup()

    _environment_ready = True


def combat_constants():
    """
    Purpose: Hand back the combat tunables module after bootstrap.

    Entry:
        bootstrap() must have run.

    Exit/Returns:
        Returns the systems.combat.constants module.

    Module Globals:
        None.

    Methodology:
        One accessor instead of a dozen single-value wrappers. A snapshot
        legitimately reads many tunables (level bounds, the hit-chance
        ceiling, the unarmed block), and forwarding the module keeps
        constants.py the single owner of every one of them.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    from systems.combat import constants as combat_const

    return combat_const


def tick_constants():
    """
    Purpose: Hand back the tick tunables module after bootstrap.

    Entry:
        bootstrap() must have run.

    Exit/Returns:
        Returns the systems.tick.constants module.

    Module Globals:
        None.

    Methodology:
        Same rationale as combat_constants(). TICK_SECONDS is what turns an
        attack speed in ticks into a real-time cadence.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    from systems.tick import constants as tick_const

    return tick_const


def level_range() -> tuple:
    """
    Purpose: Every legal skill level, low to high.

    Entry:
        bootstrap() must have run.

    Exit/Returns:
        Returns a tuple of ints spanning MIN_BASE_SKILL_LEVEL..
        MAX_BASE_SKILL_LEVEL inclusive.

    Module Globals:
        None.

    Methodology:
        Read off the combat constants rather than written as range(128), so a
        retune of the scale moves every snapshot's x-axis with it.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    combat_const = combat_constants()
    levels = range(combat_const.MIN_BASE_SKILL_LEVEL,
                   combat_const.MAX_BASE_SKILL_LEVEL + 1)

    return tuple(levels)


# Public routines -- content accessors

def weapon_profiles() -> dict:
    """
    Purpose: An AttackProfile for every wieldable weapon in the game.

    Entry:
        bootstrap() must have run.

    Exit/Returns:
        Returns dict mapping item key -> AttackProfile, in ITEM_DB order.

    Module Globals:
        None.

    Methodology:
        Selects on combat_styles being populated rather than on typeclass or
        tag: combat_styles is exactly what an attacker needs in order to
        swing, and it is the field the live pipeline reads. Armour carries
        stat bonuses but no styles, so it is excluded here and picked up by
        best_loadout() instead.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    from world.item_database import ITEM_DB

    profiles = {}

    for item_key, item_def in ITEM_DB.items():
        if not item_def.combat_styles:
            continue

        profiles[item_key] = AttackProfile(
            key=item_def.key,
            name=item_def.name,
            attack_speed=item_def.attack_speed,
            combat_stat_bonuses=dict(item_def.combat_stat_bonuses),
            combat_styles=dict(item_def.combat_styles),
            combat_rules=list(item_def.combat_rules),
        )

    return profiles


def unarmed_profile() -> AttackProfile:
    """
    Purpose: The bare-hands AttackProfile, so "no weapon" is a row in every
    snapshot rather than a missing baseline.

    Entry:
        bootstrap() must have run.

    Exit/Returns:
        Returns an AttackProfile carrying the unarmed defaults.

    Module Globals:
        None.

    Methodology:
        Built straight from the UNARMED_* constants the combat handler
        substitutes when both hands are empty, so the snapshot cannot drift
        from what actually happens in game.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    combat_const = combat_constants()

    return AttackProfile(
        key="unarmed",
        name=combat_const.UNARMED_WEAPON_NAME,
        attack_speed=combat_const.UNARMED_ATTACK_SPEED_TICKS,
        combat_stat_bonuses=dict(combat_const.UNARMED_DEFAULT_COMBAT_STATS),
        combat_styles=dict(combat_const.UNARMED_COMBAT_STYLES),
    )


def npc_combatants() -> dict:
    """
    Purpose: A Combatant for every hostile NPC in the game.

    Entry:
        bootstrap() must have run.

    Exit/Returns:
        Returns dict mapping npc key -> Combatant, in NPC_DB order.

    Module Globals:
        None.

    Methodology:
        NpcDef already carries flat skill-axis levels and one stat block,
        which is exactly the Combatant shape -- an NPC has no equipment
        handler, so nothing has to be summed across slots the way a
        Character's gear is.

    Notes/References:
        attack_speed is Optional on NpcDef and falls back to the unarmed
        cadence at create time; the same fallback is applied here.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    from world.npc_database import NPC_DB

    combat_const = combat_constants()
    combatants = {}

    for npc_key, npc_def in NPC_DB.items():
        speed = npc_def.attack_speed or combat_const.UNARMED_ATTACK_SPEED_TICKS
        profile = AttackProfile(
            key=npc_def.key,
            name=npc_def.name,
            attack_speed=speed,
            combat_stat_bonuses=dict(npc_def.combat_stat_bonuses),
            combat_styles=dict(npc_def.combat_styles),
            combat_rules=list(npc_def.combat_rules),
        )
        combatants[npc_key] = Combatant(
            name=npc_def.name,
            strike_level=npc_def.strike_level,
            brawn_level=npc_def.brawn_level,
            defense_level=npc_def.defense_level,
            max_hp=npc_def.max_hp,
            profile=profile,
        )

    return combatants


def player_combatant(level: int, profile: AttackProfile,
                     name: str = "Player") -> Combatant:
    """
    Purpose: A Character at one uniform skill level across every combat axis.

    Entry:
        level is on the 0..127 scale. profile is what the character swings.

    Exit/Returns:
        Returns a Combatant whose strike, brawn, defense and Fortitude all sit
        at `level`, with max_hp derived from Fortitude.

    Module Globals:
        None.

    Methodology:
        A uniform build is the honest default for a sweep: it makes the x-axis
        a single number instead of a four-dimensional space, and any snapshot
        needing an asymmetric build can construct a Combatant directly.

    Notes/References:
        max_hp scales 1:1 with Fortitude per 02_Player/Player_Overview.md,
        expressed here through HP_PER_FORTITUDE_LEVEL rather than assumed.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    combat_const = combat_constants()
    hit_points = level * combat_const.HP_PER_FORTITUDE_LEVEL

    return Combatant(
        name=name,
        strike_level=level,
        brawn_level=level,
        defense_level=level,
        max_hp=hit_points,
        profile=profile,
    )


# Private helper routines -- loadouts

def _stat_bearing_items() -> dict:
    """Group every ItemDef carrying combat stats by the slot it occupies.

    An item with no use_slot, or with an empty stat block, contributes nothing
    to a loadout and is dropped here rather than checked for at every use site.
    """
    from world.item_database import ITEM_DB

    by_slot = {}

    for item_def in ITEM_DB.values():
        if item_def.use_slot is None or not item_def.combat_stat_bonuses:
            continue

        by_slot.setdefault(item_def.use_slot, []).append(item_def)

    return by_slot


def _best_in_slot(candidates: list, stat_key: str):
    """Return the candidate with the highest `stat_key`, or None if empty.

    Ties resolve to the first definition, which is ITEM_DB order -- stable
    across runs, which matters because these picks get printed.
    """
    if not candidates:
        return None

    best_item = None
    best_value = None

    for item_def in candidates:
        value = item_def.combat_stat_bonuses.get(stat_key, _ABSENT_BONUS)

        if best_value is None or value > best_value:
            best_item = item_def
            best_value = value

    return best_item


def _hand_slot_winners(by_slot: dict, stat_key: str) -> list:
    """Resolve the two-handed / one-handed contest for one stat.

    A two-hander occupies MAIN_HAND and OFF_HAND at once, so the two loadouts
    are mutually exclusive and have to be compared as totals rather than
    picked slot by slot.
    """
    from items.equipment.constants import WieldLocation

    main_hand = _best_in_slot(by_slot.get(WieldLocation.MAIN_HAND, []), stat_key)
    off_hand = _best_in_slot(by_slot.get(WieldLocation.OFF_HAND, []), stat_key)
    two_hands = _best_in_slot(by_slot.get(WieldLocation.TWO_HANDS, []), stat_key)

    one_handed = [item for item in (main_hand, off_hand) if item is not None]
    one_handed_total = 0

    for item_def in one_handed:
        one_handed_total += item_def.combat_stat_bonuses.get(stat_key, _ABSENT_BONUS)

    if two_hands is None:
        return one_handed

    two_handed_total = two_hands.combat_stat_bonuses.get(stat_key, _ABSENT_BONUS)

    if two_handed_total > one_handed_total:
        return [two_hands]

    return one_handed


# Public routines -- loadouts

def best_loadout(stat_key: str, include_hands: bool = True) -> tuple:
    """
    Purpose: The strongest set of equipment obtainable today for one stat.

    Entry:
        bootstrap() must have run. stat_key is an equipment bonus key such as
        "melee_strength_bonus" or "slash_defense_bonus". include_hands False
        returns armour only, for a caller supplying its own weapon.

    Exit/Returns:
        Returns (totals, items): a dict of every bonus key summed across the
        chosen items, and the list of ItemDefs chosen.

    Module Globals:
        _ABSENT_BONUS read.

    Methodology:
        Best-in-slot on the named stat, with the hand slots resolved as a
        contest between the best two-hander and the best main-hand plus
        off-hand pair. Totals are then summed exactly the way
        EquipmentHandler.total_combat_stat_bonuses sums a live character's
        gear -- plain per-key accumulation, absent keys skipped.

    Notes/References:
        This is a CONTENT snapshot, not a build recommendation: with four
        weapons and three armour pieces in ITEM_DB the answer is currently
        near-trivial, and the point is to watch that ceiling move as items
        ship.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    from items.equipment.constants import WieldLocation

    by_slot = _stat_bearing_items()
    hand_slots = (WieldLocation.MAIN_HAND, WieldLocation.OFF_HAND,
                  WieldLocation.TWO_HANDS)
    chosen = []

    if include_hands:
        chosen = _hand_slot_winners(by_slot, stat_key)

    for slot, candidates in by_slot.items():
        if slot in hand_slots:
            continue

        winner = _best_in_slot(candidates, stat_key)

        if winner is not None:
            chosen.append(winner)

    totals = {}

    for item_def in chosen:
        for bonus_key, bonus_value in item_def.combat_stat_bonuses.items():
            running = totals.get(bonus_key, _ABSENT_BONUS)
            totals[bonus_key] = running + bonus_value

    return totals, chosen


# Private helper routines -- swing maths

def _effective_levels(attacker: Combatant, defender: Combatant,
                      style: dict) -> tuple:
    """Return (eff_atk, eff_str, eff_def) for one swing.

    The attacker's stance boost applies to the attacker's two offensive axes
    only. The defender is not choosing a style this tick, which is why the
    live BaseActionRules.effective_defense_level passes a zero stance too --
    a defensive stance raises the DEFENDER's own defense on the swings they
    take, not the defense of whoever they are hitting.
    """
    from systems.combat import combat_calc
    from systems.progression.skills.constants import (
        BRAWN_SKILL_KEY,
        STRIKE_SKILL_KEY,
    )

    boost = style.get("weapon_style_level_boost") or {}
    strike_stance = boost.get(STRIKE_SKILL_KEY, NO_STANCE_BONUS)
    brawn_stance = boost.get(BRAWN_SKILL_KEY, NO_STANCE_BONUS)

    effective_attack = combat_calc.effective_level(
        attacker.strike_level, stance_bonus=strike_stance
    )
    effective_strength = combat_calc.effective_level(
        attacker.brawn_level, stance_bonus=brawn_stance
    )
    effective_defense = combat_calc.effective_level(
        defender.defense_level, stance_bonus=NO_STANCE_BONUS
    )

    return effective_attack, effective_strength, effective_defense


def _equipment_bonuses(attacker: Combatant, defender: Combatant,
                       attack_type: str) -> tuple:
    """Return (attack_bonus, strength_bonus, defense_bonus) for one swing.

    The defence number is read off the DEFENDER's stat block. Reading it from
    the attacker's is the specific bug get_defense_bonuses() exists to prevent.
    """
    attack_key = _ATTACK_BONUS_TEMPLATE.format(attack_type=attack_type)
    defense_key = _DEFENSE_BONUS_TEMPLATE.format(attack_type=attack_type)

    attacker_stats = attacker.profile.combat_stat_bonuses
    defender_stats = defender.profile.combat_stat_bonuses

    attack_bonus = attacker_stats.get(attack_key, _ABSENT_BONUS)
    strength_bonus = attacker_stats.get(_STRENGTH_BONUS_KEY, _ABSENT_BONUS)
    defense_bonus = defender_stats.get(defense_key, _ABSENT_BONUS)

    return attack_bonus, strength_bonus, defense_bonus


# Public routines -- swing maths

def swing_metrics(attacker: Combatant, style_key: str,
                  defender: Combatant) -> SwingMetrics:
    """
    Purpose: Compute every number one swing produces, without rolling it.

    Entry:
        bootstrap() must have run. style_key must be a key of
        attacker.profile.combat_styles.

    Exit/Returns:
        Returns a fully populated SwingMetrics.

    Module Globals:
        UNIFORM_ROLL_MEAN_DIVISOR read.

    Methodology:
        Walks the same order the live pipeline does -- effective levels, then
        equipment bonuses, then the two rolls, then hit chance, then the
        damage ceiling -- but takes the EXPECTED damage instead of drawing
        from the rng. Expected damage is hit_chance * max_hit / 2 because the
        damage roll is uniform on [0, max_hit] inclusive; the zero-damage
        connect (the OSRS "0 splat") is already inside that mean.

        Damage per second divides by attack_speed * TICK_SECONDS: attack_speed
        is the number of ticks BETWEEN actions, so a speed-4 weapon acts every
        2.4s (see BlackoutCombatHandler._charge_cooldown).

    Notes/References:
        raw_hit_chance is combat_calc's answer; clamped_hit_chance applies
        HIT_CHANCE_CEILING, which BaseActionRules.accuracy imposes on the live
        path even with no modifiers in play. Expected damage uses the CLAMPED
        number, because that is what the game does.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    from systems.combat import combat_calc

    combat_const = combat_constants()
    tick_const = tick_constants()

    style = attacker.profile.combat_styles[style_key]
    attack_type = style["attack_type"]

    effective_attack, effective_strength, effective_defense = _effective_levels(
        attacker, defender, style
    )
    attack_bonus, strength_bonus, defense_bonus = _equipment_bonuses(
        attacker, defender, attack_type
    )

    attack_roll = combat_calc.melee_attack_roll(effective_attack, attack_bonus)
    defense_roll = combat_calc.melee_defense_roll(effective_defense, defense_bonus)
    raw_chance = combat_calc.hit_chance(attack_roll, defense_roll)
    capped_chance = min(raw_chance, combat_const.HIT_CHANCE_CEILING)
    clamped_chance = max(capped_chance, combat_const.HIT_CHANCE_FLOOR)

    max_hit = combat_calc.max_melee_hit(effective_strength, strength_bonus)
    average_damage = clamped_chance * max_hit / UNIFORM_ROLL_MEAN_DIVISOR
    seconds_per_swing = attacker.profile.attack_speed * tick_const.TICK_SECONDS
    damage_per_second = average_damage / seconds_per_swing

    return SwingMetrics(
        effective_attack=effective_attack,
        effective_strength=effective_strength,
        effective_defense=effective_defense,
        attack_roll=attack_roll,
        defense_roll=defense_roll,
        raw_hit_chance=raw_chance,
        clamped_hit_chance=clamped_chance,
        max_hit=max_hit,
        average_damage=average_damage,
        damage_per_second=damage_per_second,
        seconds_per_swing=seconds_per_swing,
    )


def equipped_profile(weapon: AttackProfile, armour_totals: dict) -> AttackProfile:
    """
    Purpose: Merge a weapon and a set of armour into the profile a Character
    actually fights with.

    Entry:
        bootstrap() must have run. armour_totals is the totals dict from
        best_loadout(..., include_hands=False).

    Exit/Returns:
        Returns a new AttackProfile. The input weapon is not modified.

    Module Globals:
        _ABSENT_BONUS read.

    Methodology:
        Reproduces what combat.combat_profile() does for a Character, and the
        asymmetry in it: stat bonuses SUM across every equipped slot, while
        styles and attack speed come from the wielded weapon alone. Wearing
        two attack-speed items does not average their speeds, which is why
        only one of the three fields aggregates.

    Notes/References:
        The unarmed defaults are the base of the sum, matching
        _resolve_stat_bonuses, so a key no equipped item declares still
        resolves to the unarmed value rather than going missing.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    combat_const = combat_constants()
    merged = dict(combat_const.UNARMED_DEFAULT_COMBAT_STATS)

    for source in (weapon.combat_stat_bonuses, armour_totals):
        for bonus_key, bonus_value in source.items():
            running = merged.get(bonus_key, _ABSENT_BONUS)
            merged[bonus_key] = running + bonus_value

    return AttackProfile(
        key=weapon.key,
        name=weapon.name,
        attack_speed=weapon.attack_speed,
        combat_stat_bonuses=merged,
        combat_styles=dict(weapon.combat_styles),
        combat_rules=list(weapon.combat_rules),
    )


def evaluate_styles(attacker: Combatant, defender: Combatant) -> dict:
    """
    Purpose: Resolve every style the attacker could pick against one defender.

    Entry:
        bootstrap() must have run.

    Exit/Returns:
        Returns dict mapping style key -> SwingMetrics, in the order the
        profile declares its styles.

    Module Globals:
        None.

    Methodology:
        A weapon's four styles differ in attack type as well as in stance, so
        which one is best is a property of the DEFENDER's armour, not of the
        weapon alone -- a stab style beats a slash style against the floating
        eye and loses against the chainbody. Sweeping all four and letting the
        caller take the max is the only way to answer "what would a player who
        picked correctly actually get".

    Notes/References:
        Four styles per weapon makes this cheap enough to call inside a level
        sweep; there is no need to cache it.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    results = {}

    for style_key in attacker.profile.combat_styles:
        results[style_key] = swing_metrics(attacker, style_key, defender)

    return results


# Public routines -- live pipeline simulation

def rules_for(rule_keys: list) -> tuple:
    """
    Purpose: Resolve a combat_rules key list into a priority-sorted contributor
    tuple, the way the live collector does.

    Entry:
        bootstrap() must have run. rule_keys may be empty.

    Exit/Returns:
        Returns a tuple of rules instances, lowest priority first. Unknown keys
        are skipped.

    Module Globals:
        None.

    Methodology:
        collect_contributors() walks an entity's equipment slots, which needs a
        live database object. A snapshot has ItemDefs, not spawned items, so
        the keys are resolved directly and sorted on priority alone -- the
        slot-index and key-index tiebreakers in the live sort exist only to
        make two EQUAL-priority contributors deterministic, and a single
        weapon's key list has no such ambiguity to resolve.

    Notes/References:
        Sorted lowest priority first because the pipeline lets a later entry
        overwrite an earlier one's seam claim.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    from systems.combat.rules.registry import find_rules

    resolved = []

    for rule_key in rule_keys:
        rules = find_rules(rule_key)

        if rules is not None:
            resolved.append(rules)

    resolved.sort(key=lambda entry: entry.priority)

    return tuple(resolved)


def build_context(attacker: Combatant, style_key: str, defender: Combatant,
                  rng):
    """
    Purpose: Assemble the ActionContext the live rules pipeline resolves.

    Entry:
        bootstrap() must have run. rng is a random.Random the caller owns, so
        a run can be seeded.

    Exit/Returns:
        Returns an ActionContext ready for resolve_action().

    Module Globals:
        None.

    Methodology:
        Mirrors ActionAttack._build_context field for field, with two
        substitutions a snapshot has no way around: the `attacker` and
        `defender` object slots are None, and the skill-level dicts are built
        from the Combatant rather than read off a live handler. No seam in
        rule_defs/ touches those two object slots -- every one of them reads
        levels and stats through the dicts -- so the substitution changes
        nothing about what resolves.

        Both sides' contributors are collected, because a defender's rules
        legitimately fill the defence channels even though seam WINNERS come
        from the attacker only.

    Notes/References:
        rng is threaded in rather than left to the module default so a
        distribution snapshot is reproducible across runs.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    from systems.combat.rules.context import ActionContext
    from systems.progression.skills.constants import (
        BRAWN_SKILL_KEY,
        DEFENSE_SKILL_KEY,
        FORTITUDE_SKILL_KEY,
        STRIKE_SKILL_KEY,
    )

    style = attacker.profile.combat_styles[style_key]
    attacker_levels = {
        STRIKE_SKILL_KEY: attacker.strike_level,
        BRAWN_SKILL_KEY: attacker.brawn_level,
        DEFENSE_SKILL_KEY: attacker.defense_level,
        FORTITUDE_SKILL_KEY: attacker.max_hp,
    }
    defender_levels = {
        STRIKE_SKILL_KEY: defender.strike_level,
        BRAWN_SKILL_KEY: defender.brawn_level,
        DEFENSE_SKILL_KEY: defender.defense_level,
        FORTITUDE_SKILL_KEY: defender.max_hp,
    }

    return ActionContext(
        attacker=None,
        defender=None,
        weapon=None,
        weapon_data={},
        style=style,
        attack_type=style["attack_type"],
        attacker_stats=dict(attacker.profile.combat_stat_bonuses),
        defender_stats=dict(defender.profile.combat_stat_bonuses),
        attacker_levels=attacker_levels,
        defender_levels=defender_levels,
        stance_boost=style.get("weapon_style_level_boost") or {},
        attacker_rules=rules_for(attacker.profile.combat_rules),
        defender_rules=rules_for(defender.profile.combat_rules),
        rng=rng,
    )


def simulate_swing(attacker: Combatant, style_key: str, defender: Combatant,
                   rng):
    """
    Purpose: Resolve one swing through the ACTUAL rules pipeline, dice and all.

    Entry:
        bootstrap() must have run.

    Exit/Returns:
        Returns the ActionResult -- hit, damage, self_damage, hit_prob,
        damage_type.

    Module Globals:
        None.

    Methodology:
        A fresh context per swing, because resolve_action fills the modifier
        bags and a reused context would accumulate them across trials.

    Notes/References:
        This is the only routine in this module that reflects a weapon
        carrying combat_rules. swing_metrics() is the OSRS formula and is
        blind to them by construction -- a d20 sword's damage is not a
        function of Brawn at all.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    from systems.combat.rules.pipeline import resolve_action

    context = build_context(attacker, style_key, defender, rng)

    return resolve_action(context)


def time_to_kill(damage_per_second: float, hit_points: int) -> float:
    """
    Purpose: Seconds to remove a pool of hit points at a sustained damage rate.

    Entry:
        damage_per_second may be 0.0. hit_points is the target's max_hp.

    Exit/Returns:
        Returns the time in seconds, or UNKILLABLE_SECONDS when the attacker
        deals no damage.

    Module Globals:
        UNKILLABLE_SECONDS read.

    Methodology:
        Expected-value division, not a simulation. It ignores the variance a
        Monte Carlo would show and the 1 HP/minute passive regen, both of
        which are second-order against these numbers -- regen is one point per
        hundred ticks against damage measured per four.

    Notes/References:
        Variance is what the proposed show_damage_distribution.py snapshot is
        for; this routine is deliberately the mean.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    if damage_per_second <= 0.0:
        return UNKILLABLE_SECONDS

    return hit_points / damage_per_second
