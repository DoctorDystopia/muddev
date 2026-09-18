"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/22/2026
Description: Shared bootstrap and math scaffolding for every script in
             analysis/. They all sweep the same pure combat_calc surface and
             differ only in what they tabulate and plot.

Django is deliberately NOT started at import time. Each script calls
bootstrap() from inside its own __main__ guard, which leaves this module inert
on import. A test can therefore import it inside the test runner, where Django
is already set up.

Every systems.gameplay.combat / world import therefore lives INSIDE a routine rather
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

# This file sits at blackout/analysis/, so the game directory is one
# parent up. Derived rather than hardcoded so a snapshot runs from any cwd.
_BLACKOUT_ROOT: Path = Path(__file__).resolve().parents[1]

# Per-damage-type equipment keys. The attack type is interpolated in, exactly
# as systems/gameplay/combat/combat.py does it: stab / slash / crush for a
# melee style, light / standard / heavy for a projectile one.
#
# There is no strength-bonus constant here. Which key carries the damage bonus
# depends on the style's axes -- melee_strength_bonus or
# projectile_strength_bonus -- so _equipment_bonuses reads it off the axes
# table rather than off a name written once.
_ATTACK_BONUS_TEMPLATE: str = "{attack_type}_attack_bonus"
_DEFENSE_BONUS_TEMPLATE: str = "{attack_type}_defense_bonus"

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

    # The style key the entity fights with when nothing picks one: an NpcDef's
    # default_combat_style. None for a weapon, because a player picks a style.
    default_style: str | None = None


@dataclass
class Combatant:
    """
    Purpose: One side of a swing -- the skill levels the OSRS maths reads plus
    the profile it swings with.

    Entry:
        Levels are on Blackout's 0..127 scale. fortitude_level is the Fortitude
        skill level. max_hp is the Fortitude-derived pool for a Character, or
        NpcDef.max_hp for a monster. They are two fields because an NpcDef may
        set a Fortitude that differs from its HP pool.

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
    fortitude_level: int
    max_hp: int
    profile: AttackProfile

    # The projectile axes. Guns decides whether a shot lands and Ballistics
    # decides how hard it lands, the same split Strike and Brawn make for
    # melee. They default to 0 so every Combatant written before projectile
    # weapons existed still builds.
    guns_level: int = 0
    ballistics_level: int = 0

    def level_for(self, skill_key: str) -> int:
        """This combatant's level in one combat skill, by key.

        THE ONE PLACE A SKILL KEY BECOMES A FIELD. Every reader below asks
        for the skill the active style names rather than for a field name,
        which is what lets one swing model cover a sword and a bow. Adding a
        seventh combat axis is one more row here.

        An unknown key reads 0 rather than raising: this is a snapshot tool,
        and a missing axis must print a zero row, not stop the report.
        """
        from systems.gameplay.progression.skills.constants import (
            SKILL_KEY_BALLISTICS,
            SKILL_KEY_BRAWN,
            SKILL_KEY_DEFENSE,
            SKILL_KEY_FORTITUDE,
            SKILL_KEY_GUNS,
            SKILL_KEY_STRIKE,
        )

        by_key = {
            SKILL_KEY_STRIKE: self.strike_level,
            SKILL_KEY_BRAWN: self.brawn_level,
            SKILL_KEY_DEFENSE: self.defense_level,
            SKILL_KEY_FORTITUDE: self.fortitude_level,
            SKILL_KEY_GUNS: self.guns_level,
            SKILL_KEY_BALLISTICS: self.ballistics_level,
        }

        return by_key.get(skill_key, 0)


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
        Returns the systems.gameplay.combat.constants module.

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
    from systems.gameplay.combat import constants as combat_const

    return combat_const


def tick_constants():
    """
    Purpose: Hand back the tick tunables module after bootstrap.

    Entry:
        bootstrap() must have run.

    Exit/Returns:
        Returns the systems.core.tick.constants module.

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
    from systems.core.tick import constants as tick_const

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
        Every field comes from NpcDef.to_combat_block, the dict that
        HostileNPC.apply_combat_stats applies at spawn. That block owns each
        fallback: attack_speed to the unarmed cadence, default_combat_style to
        the unarmed style, and fortitude_level to max_hp. The old version read
        max_hp as the Fortitude level and ignored fortitude_level.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    from world.npc_database import NPC_DB

    combatants = {}

    for npc_key, npc_def in NPC_DB.items():
        block = npc_def.to_combat_block()
        profile = AttackProfile(
            key=npc_def.key,
            name=npc_def.name,
            attack_speed=block["attack_speed"],
            combat_stat_bonuses=block["combat_stat_bonuses"],
            combat_styles=block["combat_styles"],
            combat_rules=block["combat_rules"],
            default_style=block["default_combat_style"],
        )
        # Guns and Ballistics take the Combatant default of 0. No NpcDef
        # declares them, because no NPC fires anything yet -- and a defender
        # never reads them at all, since the defence roll is Defense for
        # every weapon family. The day a projectile NPC ships, the two fields
        # come from to_combat_block like the rest.
        combatants[npc_key] = Combatant(
            name=npc_def.name,
            strike_level=block["strike_level"],
            brawn_level=block["brawn_level"],
            defense_level=block["defense_level"],
            fortitude_level=block["fortitude_level"],
            max_hp=block["max_hp"],
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
        Returns a Combatant whose every combat axis sits at `level`, with
        max_hp derived from Fortitude. That is Strike, Brawn, Defense,
        Fortitude, Guns and Ballistics.

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
        fortitude_level=level,
        guns_level=level,
        ballistics_level=level,
        max_hp=hit_points,
        profile=profile,
    )


def spawn_combatant(profile: AttackProfile,
                    name: str = "New character") -> Combatant:
    """
    Purpose: A Character exactly as character creation leaves it.

    Entry:
        bootstrap() must have run. profile is what the character swings.

    Exit/Returns:
        Returns a Combatant with Strike, Brawn and Defense at
        DEFAULT_START_LEVEL, Fortitude at FORTITUDE_START_LEVEL, and max_hp
        derived from Fortitude.

    Module Globals:
        None.

    Methodology:
        Mirrors init_all_skills followed by seed_fortitude_on_creation. Every
        skill starts at DEFAULT_START_LEVEL, and only Fortitude diverges.

    Notes/References:
        player_combatant(FORTITUDE_START_LEVEL) is NOT this character. It gives
        Strike, Brawn and Defense the Fortitude start level, which a new
        character does not have. Three snapshots used that build as "the spawn
        level" until 09/14/2026.

    Author: Nick Hobar
    Creation date: 09/14/2026
    """
    from systems.gameplay.progression.skills import constants as skill_const

    combat_const = combat_constants()
    start = skill_const.DEFAULT_START_LEVEL
    fortitude = combat_const.FORTITUDE_START_LEVEL

    return Combatant(
        name=name,
        strike_level=start,
        brawn_level=start,
        defense_level=start,
        fortitude_level=fortitude,
        max_hp=fortitude * combat_const.HP_PER_FORTITUDE_LEVEL,
        profile=profile,
    )


def spawn_label() -> str:
    """
    Purpose: Name the spawn_combatant build in a table title.

    Entry:
        bootstrap() must have run.

    Exit/Returns:
        Returns a label such as
        "new character (Strike, Brawn and Defense 0, Fortitude 1)".

    Module Globals:
        None.

    Methodology:
        Reads the same constants as spawn_combatant, so a change to a start
        level changes the label and the numbers together.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/14/2026
    """
    from systems.gameplay.progression.skills import constants as skill_const

    combat_const = combat_constants()

    return (f"new character (Strike, Brawn and Defense "
            f"{skill_const.DEFAULT_START_LEVEL}, Fortitude "
            f"{combat_const.FORTITUDE_START_LEVEL})")


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

def style_combat_axes(style: dict) -> dict:
    """The axes table a combat style resolves against.

    Reads the live constant rather than restating which skills a bow uses:
    a snapshot that named its own pair would be a second owner of the fact,
    and the whole point of this module is to model the game, not to repeat it.
    """
    combat_const = combat_constants()
    axes = style.get(combat_const.STYLE_COMBAT_AXES_KEY)

    if not axes:
        return combat_const.MELEE_COMBAT_AXES

    return axes


def style_attack_speed(profile: AttackProfile, style: dict) -> int:
    """The ticks between actions for one style on one weapon.

    The style's own delta applies, so rapid measures one tick faster than the
    bow's declared speed. A DPS row that ignored it would understate the one
    style whose entire cost-benefit is speed.
    """
    combat_const = combat_constants()
    delta = int(style.get(combat_const.STYLE_ATTACK_SPEED_DELTA_KEY, 0) or 0)

    return max(combat_const.MIN_ATTACK_SPEED_TICKS, profile.attack_speed + delta)


def _effective_levels(attacker: Combatant, defender: Combatant,
                      style: dict) -> tuple:
    """Return (eff_atk, eff_str, eff_def) for one swing.

    The attacker's stance boost applies to the attacker's two offensive axes
    only. The defender is not choosing a style this tick, which is why the
    live BaseActionRules.effective_defense_level passes a zero stance too --
    a defensive stance raises the DEFENDER's own defense on the swings they
    take, not the defense of whoever they are hitting.

    WHICH two offensive axes is read off the style, exactly as the live seams
    read it. Strike and Brawn for a sword, Guns and Ballistics for a bow. The
    field names are gone from this routine, which is what keeps one swing
    model honest about both.

    The defence axis is Defense for every weapon family. OSRS has no separate
    projectile-defence skill and neither does Blackout.
    """
    from systems.gameplay.combat import combat_calc

    axes = style_combat_axes(style)
    boost = style.get("weapon_style_level_boost") or {}

    accuracy_key = axes["accuracy_skill"]
    damage_key = axes["damage_skill"]

    effective_attack = combat_calc.effective_level(
        attacker.level_for(accuracy_key),
        stance_bonus=boost.get(accuracy_key, NO_STANCE_BONUS),
    )
    effective_strength = combat_calc.effective_level(
        attacker.level_for(damage_key),
        stance_bonus=boost.get(damage_key, NO_STANCE_BONUS),
    )
    effective_defense = combat_calc.effective_level(
        defender.defense_level, stance_bonus=NO_STANCE_BONUS
    )

    return effective_attack, effective_strength, effective_defense


def _equipment_bonuses(attacker: Combatant, defender: Combatant,
                       attack_type: str, style: dict) -> tuple:
    """Return (attack_bonus, strength_bonus, defense_bonus) for one swing.

    The defence number is read off the DEFENDER's stat block. Reading it from
    the attacker's is the specific bug get_defense_bonuses() exists to prevent.

    The damage bonus key comes off the style's axes, so a bow reads
    projectile_strength_bonus and a sword reads melee_strength_bonus. A model
    that read one key for both would report every bow as hitting for nothing,
    because a bow deliberately carries no melee strength bonus.

    NOT MODELLED: the AMMUNITION's own bonus. It lives in the AMMO equipment
    slot on a live character, and an AttackProfile here is a weapon plus
    armour. A bow snapshot therefore shows the floor, not the loaded number.
    """
    attack_key = _ATTACK_BONUS_TEMPLATE.format(attack_type=attack_type)
    defense_key = _DEFENSE_BONUS_TEMPLATE.format(attack_type=attack_type)
    strength_key = style_combat_axes(style)["strength_bonus_key"]

    attacker_stats = attacker.profile.combat_stat_bonuses
    defender_stats = defender.profile.combat_stat_bonuses

    attack_bonus = attacker_stats.get(attack_key, _ABSENT_BONUS)
    strength_bonus = attacker_stats.get(strength_key, _ABSENT_BONUS)
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
    from systems.gameplay.combat import combat_calc

    combat_const = combat_constants()
    tick_const = tick_constants()

    style = attacker.profile.combat_styles[style_key]
    attack_type = style["attack_type"]

    effective_attack, effective_strength, effective_defense = _effective_levels(
        attacker, defender, style
    )
    attack_bonus, strength_bonus, defense_bonus = _equipment_bonuses(
        attacker, defender, attack_type, style
    )

    attack_roll = combat_calc.attack_roll(effective_attack, attack_bonus)
    defense_roll = combat_calc.defense_roll(effective_defense, defense_bonus)
    raw_chance = combat_calc.hit_chance(attack_roll, defense_roll)
    capped_chance = min(raw_chance, combat_const.HIT_CHANCE_CEILING)
    clamped_chance = max(capped_chance, combat_const.HIT_CHANCE_FLOOR)

    max_hit = combat_calc.max_hit(effective_strength, strength_bonus)
    average_damage = clamped_chance * max_hit / UNIFORM_ROLL_MEAN_DIVISOR
    speed_ticks = style_attack_speed(attacker.profile, style)
    seconds_per_swing = speed_ticks * tick_const.TICK_SECONDS
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


def active_style_key(profile: AttackProfile) -> str:
    """
    Purpose: The style key an entity fights with when nothing picks one.

    Entry:
        profile.combat_styles must be non-empty.

    Exit/Returns:
        Returns profile.default_style when the profile declares that style,
        else the first declared style key. Raises ValueError when a default
        style is set but not declared.

    Module Globals:
        None.

    Methodology:
        Mirrors combat._resolve_style_and_speed. An NPC never changes style,
        so its swings use this key, never the best style against its target.

    Notes/References:
        For a default style the profile does not declare, the live game falls
        back to the unarmed default style. A snapshot cannot sweep a style
        that is not in the profile, so it raises and names the content bug.

    Author: Nick Hobar
    Creation date: 09/14/2026
    """
    styles = profile.combat_styles

    if profile.default_style is None:
        return next(iter(styles))

    if profile.default_style in styles:
        return profile.default_style

    raise ValueError(
        f"{profile.key} names default style {profile.default_style!r}, which "
        f"it does not declare. The live game falls back to unarmed."
    )


def best_plain_weapon(level: int, defender: Combatant) -> tuple:
    """
    Purpose: The weapon and style with the highest analytic damage per second
    against one defender, from the weapons that carry no combat_rules.

    Entry:
        bootstrap() must have run. level is a uniform player level.

    Exit/Returns:
        Returns (profile, style_key, metrics). Unarmed is a candidate.

    Module Globals:
        None.

    Methodology:
        A weapon with combat_rules is never a candidate, because swing_metrics
        does not model it (show_rules_map.py names each one). A tie keeps the
        first candidate: unarmed, then ITEM_DB order.

    Notes/References:
        show_xp_economy and show_damage_distribution both measure against this
        weapon, so their reference weapon cannot disagree.

    Author: Nick Hobar
    Creation date: 09/14/2026
    """
    candidates = [unarmed_profile()]
    candidates.extend(
        profile for profile in weapon_profiles().values()
        if not profile.combat_rules
    )
    best = None

    for profile in candidates:
        attacker = player_combatant(level, profile)

        for style_key, metrics in evaluate_styles(attacker, defender).items():
            if best is not None and metrics.damage_per_second <= best[2].damage_per_second:
                continue

            best = (profile, style_key, metrics)

    return best


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
    from systems.gameplay.combat.rules.registry import find_rules

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
    from systems.gameplay.combat.rules.context import ActionContext
    from systems.gameplay.progression.skills.constants import (
        SKILL_KEYS_CATEGORY_COMBAT,
    )

    style = attacker.profile.combat_styles[style_key]

    # Every combat axis, derived from the tuple that owns which axes exist.
    # Written out field by field until 09/17/2026, and a Guns-driven style
    # then raised KeyError('guns') out of the live seam the moment the first
    # bow reached ITEM_DB -- a model missing a key the game reads.
    attacker_levels = {
        skill_key: attacker.level_for(skill_key)
        for skill_key in SKILL_KEYS_CATEGORY_COMBAT
    }
    defender_levels = {
        skill_key: defender.level_for(skill_key)
        for skill_key in SKILL_KEYS_CATEGORY_COMBAT
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
    from systems.gameplay.combat.rules.pipeline import resolve_action

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
        show_damage_distribution.py measures the variance. This routine is
        deliberately the mean.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    if damage_per_second <= 0.0:
        return UNKILLABLE_SECONDS

    return hit_points / damage_per_second
