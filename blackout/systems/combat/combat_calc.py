"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Pure OSRS-exact combat math — no Evennia imports, no DB, no side effects.
"""

from __future__ import annotations

import math
import random as _random_module
from typing import Optional

from systems.combat import constants as combat_constants


# ─── Effective level ───────────────────────────────────────────

def effective_level(
    base: int,
    potion_boost: int = 0,
    augmentation_mult: float = combat_constants.AUGMENTATION_DEFAULT_MULT,
    set_mult: float = combat_constants.SET_DEFAULT_MULT,
    stance_bonus: int = 0,
) -> int:
    """
    Purpose: Compute an OSRS-style Effective Level for a single skill axis
    (strike, brawn, or defense).

    Entry:
        base             - the character's unbuffed skill level (0..127).
        potion_boost     - flat integer boost (OSRS potion). Defaults to 0.
        augmentation_mult - percentage multiplier (OSRS Prayer analog).
                            Defaults to 1.0; Blackout's Augmentation system
                            is not yet implemented, but the parameter is
                            present so combat resolution can be wired in
                            without re-touching this function.
        set_mult         - global equipment set multiplier (OSRS Void Knight
                            analog). Defaults to 1.0.
        stance_bonus     - hidden flat post-multiplier integer from the
                            attack style (OSRS +3 / +1). Defaults to 0.

    Exit/Returns:
        Integer Effective Level. All intermediate floors are taken to match
        OSRS's strict integer-arithmetic engine.

    Module Globals:
        EFFECTIVE_LEVEL_FLOOR_8 read.
        AUGMENTATION_DEFAULT_MULT read (default).
        SET_DEFAULT_MULT read (default).

    Methodology:
        L_eff = floor( floor( (base + potion) * augmentation ) * set ) + stance + 8
        Each nested floor matches the OSRS sequence: the engine floors
        before applying the next multiplier, never accumulating float error.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    after_potion = base + potion_boost
    after_augmentation = math.floor(after_potion * augmentation_mult)
    after_set = math.floor(after_augmentation * set_mult)

    return after_set + stance_bonus + combat_constants.EFFECTIVE_LEVEL_FLOOR_8


# ─── Max hit ───────────────────────────────────────────────────

def max_melee_hit(eff_str: int, equip_str_bonus: int) -> int:
    """
    Purpose: Compute the maximum melee damage for one swing.

    Entry:
        eff_str          - Effective Strength level (output of effective_level
                           with the aggressive/controlled weapon style bonus applied
                           to the melee strength stat).
        equip_str_bonus  - the cumulative B_equip_str integer from all
                           equipped gear (weapon + armor + jewellery).

    Exit/Returns:
        Integer max hit. The damage roll is uniform on [0, max_hit] inclusive.

    Module Globals:
        MAX_HIT_OFFSET read.
        MAX_HIT_K read.
        MAX_HIT_DIVISOR read.

    Methodology:
        H_max = floor( 0.5 + eff_str * (equip_str_bonus + 64) / 640 )
        Constants match OSRS verbatim; the +64 zero-floor and /640
        compression are structural anchors of the OSRS damage economy.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    inner = eff_str * (equip_str_bonus + combat_constants.MAX_HIT_K)
    return math.floor(combat_constants.MAX_HIT_OFFSET + inner / combat_constants.MAX_HIT_DIVISOR)


# ─── Attack and defense rolls ──────────────────────────────

def melee_attack_roll(eff_atk: int, equip_atk_bonus: int) -> int:
    """
    Purpose: Compute the attacker's maximum attack roll for hit resolution.

    Entry:
        eff_atk         - Effective Strike level (effective_level output
                          on the strike skill axis).
        equip_atk_bonus - cumulative attack bonus for the active attack style
                          from the equipped weapon.

    Exit/Returns:
        Integer R_atk. Higher is always better for the attacker.

    Module Globals:
        MAX_HIT_K read (re-used as the +64 structural offset).

    Methodology:
        R_atk = eff_atk * (equip_atk_bonus + 64)
        OSRS uses an identical structural shape for attack and defense rolls,
        hence the shared +64 constant.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    return eff_atk * (equip_atk_bonus + combat_constants.MAX_HIT_K)


def melee_defense_roll(eff_def: int, equip_def_bonus: int) -> int:
    """
    Purpose: Compute the defender's maximum defense roll for hit resolution.

    Entry:
        eff_def         - Effective defense level (effective_level output on
                          the defense axis; NPC combat_stats.defense_level for
                          non-Player combatants).
        equip_def_bonus - cumulative defense bonus for the active attack
                          style's damage type (slash/stab/crush) from armor.

    Exit/Returns:
        Integer R_def.

    Module Globals:
        MAX_HIT_K read.

    Methodology:
        R_def = eff_def * (equip_def_bonus + 64)
        Attack and defense rolls share the same structural formula; the
        only divergence is which equipment bonus feeds in.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    return eff_def * (equip_def_bonus + combat_constants.MAX_HIT_K)


# ─── Hit chance ───────────────────────────────────────────

def hit_chance(r_atk: int, r_def: int) -> float:
    """
    Purpose: Compute the probability that an attack lands (does >0 damage
    OR rolls a 0 damage on a successful accuracy check.

    Entry:
        r_atk - attacker's maximum attack roll.
        r_def - defender's maximum defense roll.

    Exit/Returns:
        Float probability on [0.0, 1.0). The curve is strictly sub-linear:
        an attacker can never reach 1.0, and a defender can never reach 0.0.

    Module Globals:
        HIT_CHANCE_ATK_NUMERATOR_OFFSET read.
        HIT_CHANCE_DEF_NUMERATOR_OFFSET read.
        HIT_CHANCE_DENOMINATOR_MULTIPLIER read.

    Methodology:
        If R_atk > R_def:   P = 1 - (R_def + 2) / (2 * (R_atk + 1))
        If R_atk <= R_def:  P = R_atk / (2 * (R_def + 1))
        The bifurcation guarantees the probability bounds. The diminishing-
        returns shape on the leading branch is what makes OSRS armor math
        cohere.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    denom_atk = combat_constants.HIT_CHANCE_DENOMINATOR_MULTIPLIER * (
        r_atk + combat_constants.HIT_CHANCE_ATK_NUMERATOR_OFFSET
    )

    if r_atk > r_def:
        return 1.0 - (r_def + combat_constants.HIT_CHANCE_DEF_NUMERATOR_OFFSET) / denom_atk
    
    return r_atk / (combat_constants.HIT_CHANCE_DENOMINATOR_MULTIPLIER * (r_def + 1))


# ─── Damage roll ────────────────────────────────────────────────────────────

def roll_damage(max_hit_value: int, rng: Optional[_random_module.Random] = None) -> int:
    """
    Purpose: Uniform integer damage on [0, max_hit] inclusive.

    Entry:
        max_hit_value - cap from max_hit(eff_str, equip_str_bonus).
        rng           - optional random.Random instance for deterministic tests.
                        If None, uses the module-level random.

    Exit/Returns:
        Integer damage in [0, max_hit_value]. A 0 is a successful accuracy
        check followed by a 0 damage roll (an OSRS "splash" with a connect).

    Module Globals:
        None.

    Methodology:
        Single randint call. Rolls damage uniformly across the full
        range, so 0 is as likely as max_hit, and the average DPS converges
        to max_hit * hit_chance / 2.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    source = rng if rng is not None else _random_module

    return source.randint(0, max_hit_value)


# def roll_damage(max_hit_value: int, rng: Optional[_random_module.Random] = None) -> int:
#     """
#     Purpose: Roughly bell curved distribution of integer damage on [0, max_hit] inclusive.

#     Methodology:
#         Average of two randint calls, rounded up or down randomly to avoid bias towards 0 or max_hit. 
#         0 is still as likely as max_hit, but both are less likely than the mid-range values.
#         The distribution is not a bell curve, it is a triangular distribution that peaks at max_hit/2. 

#     Author: Danny
#     Creation date: 08/08/2026
#     """
#     source = rng if rng is not None else _random_module

#     r = source.randint(0, 1)
#     a = source.randint(0, max_hit_value)
#     b = source.randint(0, max_hit_value)

#     if r == 0:
#         damage = math.floor((a + b) / 2.0)
#     else:
#         damage = math.ceil((a + b) / 2.0)

#     return damage


# ─── Combat action resolution (top-level pipeline) ────────────────────────────────

def resolve_melee_swing(
    attacker_eff_atk: int,
    attacker_equip_atk: int,
    attacker_eff_str: int,
    attacker_equip_str: int,
    defender_eff_def: int,
    defender_equip_def: int,
    rng: Optional[_random_module.Random] = None,
) -> dict:
    """
    Purpose: For melee combat. Resolve one melee swing end-to-end. This is the single entry
    point the CombatHandler calls per tick per queued attack action.

    Entry:
        attacker_eff_atk   - effective_level on the Strike skill axis (boosted
                              per the active style's weapon_style_level_boost).
        attacker_equip_atk - combat_stat_bonuses[attack_type + "_attack_bonus"]
                              from the weapon (e.g. "stab_attack_bonus").
        attacker_eff_str   - effective_level on the Brawn skill axis (boosted
                              per the active style's weapon_style_level_boost).
        attacker_equip_str - cumulative strength bonus (weapon + armor);
                              combat_stat_bonuses["melee_strength_bonus"].
        defender_eff_def   - effective_level on the Defense skill axis (or NPC's
                              combat_stats.defense_level).
        defender_equip_def - defender's combat_stat_bonuses for the relevant
                              damage-type defense (e.g. "stab_defense_bonus").
        rng                - optional random.Random for tests.

    Exit/Returns:
        dict with keys:
            hit       - bool, True iff the accuracy roll succeeded.
            damage    - int, 0 on miss OR on a successful accuracy roll
                        that then rolled 0 (the OSRS "0 splat"). Otherwise
                        uniform on [0, max_hit].
            hit_prob  - float, the probability the accuracy roll used.

    Module Globals:
        None (delegates to other module functions).

    Methodology:
        1. Compute R_atk and R_def via melee_attack_roll / melee_defense_roll.
        2. Compute hit_prob via hit_chance.
        3. Roll against hit_prob; if miss, return damage=0.
        4. Compute max_melee_hit and roll uniform damage.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    source = rng if rng is not None else _random_module

    r_atk = melee_attack_roll(attacker_eff_atk, attacker_equip_atk)
    r_def = melee_defense_roll(defender_eff_def, defender_equip_def)
    chance = hit_chance(r_atk, r_def)

    if source.random() >= chance:
        return {"hit": False, "damage": 0, "hit_prob": chance}

    dmg = roll_damage(max_melee_hit(attacker_eff_str, attacker_equip_str), source)

    return {"hit": True, "damage": dmg, "hit_prob": chance}
