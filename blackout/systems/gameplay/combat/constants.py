"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Global tunables for the OSRS-derived Blackout combat engine (0-127 skill scaling).
"""



from systems.core.tick.scheduler import seconds_to_ticks
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.constants import (
    SKILL_KEY_BALLISTICS,
    SKILL_KEY_BRAWN,
    SKILL_KEY_DEFENSE,
    SKILL_KEY_FORTITUDE,
    SKILL_KEY_GUNS,
    SKILL_KEY_STRIKE,
)



# ─── Skill scaling bounds ────────────────────────────────────────────────────
# Blackout scales all skills 0..127 (inclusive). OSRS uses 1..99; the formulas
# are scale-agnostic. The skills constants module owns the two bounds. These
# names give the combat maths and the analysis scripts the same values.
MIN_BASE_SKILL_LEVEL: int = skill_constants.MIN_BASE_SKILL_LEVEL
MAX_BASE_SKILL_LEVEL: int = skill_constants.MAX_BASE_SKILL_LEVEL

# ─── Fortitude (HP) seed values ──────────────────────────────────────────────
# Player characters enter the world with Fortitude forced to this level, and
# max_hp therefore equal to it.

# a character spawns exactly on the level-10 threshold and
# logic.calculate_xp_needed owns what that threshold costs.
FORTITUDE_START_LEVEL: int = 1
MAX_FORTITUDE_LEVEL: int = MAX_BASE_SKILL_LEVEL

# ─── Fortitude -> max HP scaling ──────────────────────────────────────────────
# Hitpoints are DIRECTLY linked to the Fortitude skill: max_hp scales one-to-one
# with Fortitude level, so a fresh character at FORTITUDE_START_LEVEL has
# exactly that many hitpoints and the cap rises by one per level to
# MAX_FORTITUDE_LEVEL.

# This constant is the single knob if that relationship is ever retuned (e.g., a
# 10-HP-per-level scale)
HP_PER_FORTITUDE_LEVEL: int = 1

# Absolute HP ceiling implied by the scaling above. Exists so UI/cap-check code
# has one place to read instead of recomputing the product.
MAX_HP_CAP: int = MAX_FORTITUDE_LEVEL * HP_PER_FORTITUDE_LEVEL

# ─── Passive HP regeneration ──────────────────────────────────────────────────
# Player_Overview.md: "Players regenerate 1 Hitpoint per minute." Per the
# 08/08 design dialogue this applies to every CombatEntity (players and NPCs
# alike), not just the player character, and runs ALL the time -- including
# mid-combat, not just while out of a fight.
#
# Rides on hp_regen.py's plain Evennia Script interval, NOT the twisted
# LoopingCall in systems/core/tick/engine.py -- 60 is a whole number of seconds, so
# ScriptDB.db_interval (a Django IntegerField) holds it natively.
HP_REGEN_INTERVAL_SECONDS: int = 60

# The same interval in ticks, which is what the regen sweep is actually
# scheduled on. Derived rather than written as 100 so retuning the tick moves
# regen with it; 60s at 0.6s is exactly 100 ticks, so nothing is quantised
# away here.
HP_REGEN_INTERVAL_TICKS: int = seconds_to_ticks(HP_REGEN_INTERVAL_SECONDS)
HP_REGEN_AMOUNT: int = 1

# ─── Effective-level formula constants ─────────────────────────
# L_eff = floor( floor( (base + potion) * augmentation ) * set ) + stance + 8
# In OSRS the +8 is an invisible universal baseline, we preserve it verbatim
# because the formula's behavior with B_equip=0 depends on it.
EFFECTIVE_LEVEL_FLOOR_8: int = 8

# ─── Max-hit formula constants ─────────────────────────────────
# H_max = floor( 0.5 + L_eff_str * (B_equip_str + 64) / 640 )
MAX_HIT_K: int = 64  # numerator offset
MAX_HIT_DIVISOR: int = 640  # denominator
MAX_HIT_OFFSET: float = 0.5  # rounding bias

# ─── Hit-chance formula constants ─────────────────────────
# Tuning knobs for the bifurcated probability curves, values match OSRS right now.
HIT_CHANCE_ATK_NUMERATOR_OFFSET: int = 1  # (R_atk + 1)
HIT_CHANCE_DEF_NUMERATOR_OFFSET: int = 2  # (R_def + 2)
HIT_CHANCE_DENOMINATOR_MULTIPLIER: int = 2  # 2 * (...)

# Clamp applied AFTER the CHANNEL_HIT_CHANCE modifiers run. An attacker never
# reaches 1.0 and a defender never reaches 0.0, but a modifier channel can
# drive the number anywhere, so the bounds have to be re-imposed once modifiers
# have had their say. The ceiling is deliberately below 1.0
HIT_CHANCE_FLOOR: float = 0.0
HIT_CHANCE_CEILING: float = 0.99

# ─── Melee attack types ──────────────────────────────────────────────────────
# Which equipment bonus a melee swing reads. These strings are INTERPOLATED into
# attribute keys — f"{attack_type}_attack_bonus" — so they must match the key
# spellings in UNARMED_DEFAULT_COMBAT_STATS below and in world/item_defs/.

# NOT interchangeable with the DAMAGE_TYPE_* constants further down: those name
# a KIND of damage for attribution and are never interpolated into anything.
ATTACK_TYPE_STAB: str = "stab"
ATTACK_TYPE_SLASH: str = "slash"
ATTACK_TYPE_CRUSH: str = "crush"

MELEE_ATTACK_TYPES: tuple = (
    ATTACK_TYPE_STAB,
    ATTACK_TYPE_SLASH,
    ATTACK_TYPE_CRUSH,
)

# ─── Projectile attack types ─────────────────────────────────────────────────────
# The projectile mirror of the three strings above, and interpolated the same way:
# f"{attack_type}_attack_bonus" gives "light_attack_bonus", and
# f"{attack_type}_defense_bonus" gives "light_defense_bonus". Three types
# therefore produce all six keys, and no key is written out anywhere.
#
# A sub-type, not a damage kind. A bow declares an attack bonus for each of
# the three and its styles pick one, exactly as a sword picks stab or slash.
# An arrow is not "light damage"; DAMAGE_TYPE_PROJECTILE further down is what
# names the kind.
PROJECTILE_ATTACK_TYPE_LIGHT: str = "light"
PROJECTILE_ATTACK_TYPE_STANDARD: str = "standard"
PROJECTILE_ATTACK_TYPE_HEAVY: str = "heavy"

PROJECTILE_ATTACK_TYPES: tuple = (
    PROJECTILE_ATTACK_TYPE_LIGHT,
    PROJECTILE_ATTACK_TYPE_STANDARD,
    PROJECTILE_ATTACK_TYPE_HEAVY,
)

# The equipment key carrying a projectile shot's damage bonus, the mirror of
# "melee_strength_bonus". Named here rather than typed at its two readers
# because the AMMUNITION carries it, not the bow -- so the key travels from
# an ItemDef in one slot to a formula that never names that slot.
PROJECTILE_STRENGTH_BONUS_KEY: str = "projectile_strength_bonus"
MELEE_STRENGTH_BONUS_KEY: str = "melee_strength_bonus"

# ─── Weapon Style invisible bonuses ────────────────────────
# Four combat styles map to four discrete bonus profiles. Each dict maps
# Blackout skill keys to invisible level boosts consumed by
# combat_calc.effective_level.
#   accurate   -> +3 strike      (Strike skill)
#   aggressive -> +3 brawn       (Brawn skill)
#   defensive  -> +3 defense     (Defense skill)
#   controlled -> +1 to all three
MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE: dict = {SKILL_KEY_STRIKE: 3}
MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE: dict = {SKILL_KEY_BRAWN: 3}
MELEE_WEAPON_STYLE_LEVEL_BOOST_CONTROLLED: dict = {
    SKILL_KEY_STRIKE: 1,
    SKILL_KEY_BRAWN: 1,
    SKILL_KEY_DEFENSE: 1,
}
MELEE_WEAPON_STYLE_LEVEL_BOOST_DEFENSIVE: dict = {SKILL_KEY_DEFENSE: 3}

# ─── Projectile weapon style invisible bonuses ───────────────────────────────────
# The projectile mirror of the four dicts above. The four bow styles are accurate,
# rapid, penetrate and snipe.
#   accurate  -> +3 guns        (accuracy)
#   rapid     -> nothing        (it buys one tick of speed instead)
#   penetrate -> +3 ballistics  (damage)
#   snipe     -> +3 defense     (and two extra tiles of range)
#
# RAPID DECLARES AN EMPTY DICT ON PURPOSE. Its whole cost-benefit is the
# attack_speed_delta on the style, and a style with no level boost must still
# carry the key so every reader can treat the four the same way.
PROJECTILE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE: dict = {SKILL_KEY_GUNS: 3}
PROJECTILE_WEAPON_STYLE_LEVEL_BOOST_RAPID: dict = {}
PROJECTILE_WEAPON_STYLE_LEVEL_BOOST_PENETRATE: dict = {SKILL_KEY_BALLISTICS: 3}
PROJECTILE_WEAPON_STYLE_LEVEL_BOOST_SNIPE: dict = {SKILL_KEY_DEFENSE: 3}



# ─── XP rewards ─────────────────────────────────────────────────────────────
# Blackout grants XP per damage based on the *combat style*.

# Each rate below is the XP awarded to EACH skill the style names, per point of
# damage dealt. XP_PER_DAMAGE_CONTROLLED_EACH is therefore already divided by
# three -- it is the per-skill share, not the pool. Dividing again in the award
# path (as _award_style_xp once did) cut controlled XP to a ninth of intent and
# floored it to zero for any hit of 2 damage or less.
XP_PER_DAMAGE_ACCURATE: float = 4.0
XP_PER_DAMAGE_AGGRESSIVE: float = 4.0
XP_PER_DAMAGE_CONTROLLED_EACH: float = 4.0 / 3.0  # three stats split 4 XP
XP_PER_DAMAGE_DEFENSIVE: float = 4.0

# The projectile snipe style names Guns AND Defense, so the 4.0 pool splits between
# them. ALREADY DIVIDED, the same as XP_PER_DAMAGE_CONTROLLED_EACH above --
# dividing again in the award path is the bug that constant's comment records.
#
# Snipe therefore pays 2.0 + 2.0 + the Fortitude rate of 1.33 = 5.33 per point
# of damage, which is what every other style pays. One action, one XP budget:
# a style that names more skills divides it, it does not earn more.
XP_PER_DAMAGE_PROJECTILE_DEFENSIVE_EACH: float = 4.0 / 2.0
# XP_PER_DAMAGE_TAKEN_DEFENSE: float = 1.33  # Defense XP on being hit

# Fortitude does NOT earn at the style rate since all combat styles award it.
XP_PER_DAMAGE_FORTITUDE: float = 4.0 / 3.0

# Per-skill rate overrides consulted by _award_style_xp. A skill absent here
# earns the active style's rate, a skill present earns its own, whichever style
# named it.
XP_PER_DAMAGE_BY_SKILL: dict = {
    SKILL_KEY_FORTITUDE: XP_PER_DAMAGE_FORTITUDE,
}

# A style's "weapon_style_xp_skill" may name one skill (a plain string) or several (any
# iterable of skill keys), in which case every named skill receives the full
# per-skill rate above.
ACCURATE_XP_SKILLS: tuple = (SKILL_KEY_STRIKE, SKILL_KEY_FORTITUDE)
AGGRESSIVE_XP_SKILLS: tuple = (SKILL_KEY_BRAWN, SKILL_KEY_FORTITUDE)
CONTROLLED_XP_SKILLS: tuple = (
    SKILL_KEY_STRIKE,
    SKILL_KEY_BRAWN,
    SKILL_KEY_DEFENSE,
    SKILL_KEY_FORTITUDE,
)
DEFENSIVE_XP_SKILLS: tuple = (SKILL_KEY_DEFENSE, SKILL_KEY_FORTITUDE)

# The projectile mirrors. Guns is the accuracy skill and Ballistics the damage one,
# so the accurate style trains Guns and the two aggressive styles train
# Ballistics -- the same accuracy/damage split the melee tuples make between
# Strike and Brawn.
PROJECTILE_ACCURATE_XP_SKILLS: tuple = (SKILL_KEY_GUNS, SKILL_KEY_FORTITUDE)
PROJECTILE_AGGRESSIVE_XP_SKILLS: tuple = (SKILL_KEY_BALLISTICS, SKILL_KEY_FORTITUDE)
PROJECTILE_DEFENSIVE_XP_SKILLS: tuple = (
    SKILL_KEY_GUNS,
    SKILL_KEY_DEFENSE,
    SKILL_KEY_FORTITUDE,
)

# ─── Per-style XP rate override ──────────────────────────────────────────────
# The key a combat style may carry to name its own per-skill XP rate, instead
# of the rate _WEAPON_STYLE_XP_MAP gives its weapon_style.
#
# It exists because snipe is a "defensive" weapon_style that must NOT pay the
# defensive rate: melee defensive names one skill and pays it 4.0, snipe names
# two and pays each 2.0. Without this key the fix would be a branch on
# "is this style projectile" in the award path, which is exactly the dispatch chain
# the repo's data-over-branches rule exists to prevent.
#
# A style that omits it takes its weapon_style's rate, which is every melee
# style and three of the four projectile ones.
STYLE_XP_RATE_KEY: str = "weapon_style_xp_rate"

# ─── Per-style speed and reach modifiers ─────────────────────────────────────
# Two more optional style keys, read by _resolve_style_and_speed and by
# reach.py. Both default to 0, so a style that declares neither behaves exactly
# as every melee style does today.
#
#   attack_speed_delta - ticks ADDED to the weapon's attack speed. Rapid
#                        declares -1. Floored at MIN_ATTACK_SPEED_TICKS.
#   range_bonus        - tiles ADDED to the weapon's max_range. Snipe
#                        declares +2.
STYLE_ATTACK_SPEED_DELTA_KEY: str = "attack_speed_delta"
STYLE_RANGE_BONUS_KEY: str = "range_bonus"

# The floor a style's attack_speed_delta may not push a weapon below. One tick
# is the engine's whole resolution: an action cannot resolve more than once per
# tick, so a faster number would be a number nothing could honour.
MIN_ATTACK_SPEED_TICKS: int = 1


# ─── Augmentation ───────────────────────
# OSRS treats Prayer as a percentage multiplier on effective level.
# In Blackout that role belongs to the Augmentation system (not yet built).
# Crucially: Augmentation-flicking — toggling an augmentation for the tick a
# melee swing lands and un-toggling it the tick after — is a CORE MECHANIC, not an
# anti-pattern to guard against. No MIN_BUFF_DURATION_TICKS knob exists. The
# combat handler resolves each melee swing against the augmentation state at the
# exact tick it lands, exactly as OSRS does, and lets the player own the APM.
AUGMENTATION_DEFAULT_MULT: float = 1.0  # M_augmentation baseline

# ─── Equipment set multiplier ────────────────────
# Reserved for future Blackout "set bonus" armor. The formula accepts it as a
# parameter today so adding sets later does not require touching combat_calc.
SET_DEFAULT_MULT: float = 1.0

# ─── Future-party hooks (declared, unused right now) ──────────────────
# Threat tables / aggro mechanics are deferred until party combat is implemented.
THREAT_AGGRO_MELEE_FLOOR: float = 1.10  # 110% to steal in melee
THREAT_AGGRO_RANGE_FLOOR: float = 1.30  # 130% to steal at range
THREAT_HEALING_COEFFICIENT: float = 0.5  # 0.5 threat per HP healed

# ─── Special-attack resource ──────────────────
# (declared, unused right now)
SPECIAL_ENERGY_MAX: int = 100
SPECIAL_ENERGY_REGEN_PER_30S: int = 10  # full bar in 5 min


# ─── Damage auras ────────────────────────────────────────────────────────────
# Generic knobs only. Per-aura numbers (radius, cadence, damage share) are DATA
# and live on the aura class in systems/gameplay/combat/auras/aura_defs/ — adding an aura
# must stay a one-file change, so nothing aura-specific belongs in this module.

# Floor applied to every aura tick's damage. Aura damage is a share of the
# CASTER's scaling skill level, and Blackout's levels start low: a character
# spawns at Fortitude 10, so a 10% share is 1.0 and anything below that
# truncates to 0. So one damage is the smallest meaningful hit.
AURA_MIN_DAMAGE: int = 1

# Default cadence, in ticks, between one aura's damage pulses. Four ticks is
# 2.4 seconds, exactly one speed-4 weapon combat action.
AURA_DEFAULT_TICK_INTERVAL: int = 4

# Distance metric used to decide which grid tiles a radius covers.
#   "euclidean" -> dx*dx + dy*dy <= r*r   (a circle, corners of the box are cut)
#   "chebyshev" -> max(|dx|, |dy|) <= r   (the full square box)
# Euclidean matches the circular ground effect the mechanic is modelled on.
# The bounding-box DB query is the same either way, only the in-Python trim
# differs, so this is a pure retune knob.
AURA_DISTANCE_METRIC: str = "euclidean"


# ─── Combat level ────────────────────────────────────────────────────────────
# Blackout's derived "how tough is this combatant" number, ported from OSRS:
#   Base    = COMBAT_LEVEL_BASE_WEIGHT * (Fortitude + Defense + floor(Augmentation / COMBAT_LEVEL_AUGMENTATION_DIVISOR))
#   Branch  = COMBAT_LEVEL_BRANCH_WEIGHT * (paired skills summed raw, or a
#             lone skill scaled by COMBAT_LEVEL_SOLO_SKILL_MULTIPLIER first)
#   Combat level = floor(Base + max(every registered branch's score))
#
# Coefficients are OSRS's literal values -- preserved verbatim per the same
# scale-agnostic precedent as EFFECTIVE_LEVEL_FLOOR_8 / MAX_HIT_* above.
# Blackout's 0-127 skill range therefore pushes the ceiling past OSRS's
# familiar 126 (a melee-maxed level-127 character lands around 162). That is
# accepted as a new number, not corrected for.
COMBAT_LEVEL_BASE_WEIGHT: float = 0.25
COMBAT_LEVEL_BRANCH_WEIGHT: float = 0.325
COMBAT_LEVEL_SOLO_SKILL_MULTIPLIER: float = 1.5
COMBAT_LEVEL_AUGMENTATION_DIVISOR: int = 2

# Skills summed into the flat base every combatant gets regardless of build --
# OSRS's Defence + Hitpoints. Augmentation (Blackout's Prayer analog: universal,
# buff-only, not tied to a style) is handled as its own constant below since
# it is halved before joining the sum and these two are not.
COMBAT_LEVEL_BASE_SKILLS: tuple = (SKILL_KEY_FORTITUDE, SKILL_KEY_DEFENSE)

# Augmentation does not exist as a built skill yet (03_Systems/Skills/Combat
# Skills/Augmentation_Skill.md is still a stub) -- combat_level's skill-level
# lookup treats any key absent from SKILL_REGISTRY as a 0 contribution rather
# than raising, so this is safe to reference today and starts contributing
# the moment the skill ships under this key.
COMBAT_LEVEL_AUGMENTATION_SKILL: str = "augmentation"

# ─── Damage types ────────────────────────────────────────────────────────────
# What KIND of damage landed, threaded through CombatEntity.at_damage so death
# attribution and messaging can tell a sword from fire, etc.

# Read the warning on ATTACK_TYPE_* above before adding one here: these two
# vocabularies look interchangeable and are not. An ATTACK_TYPE_* string is
# interpolated into "<type>_attack_bonus".
DAMAGE_TYPE_MELEE: str = "melee"    # a connecting weapon or unarmed swing
DAMAGE_TYPE_PROJECTILE: str = "projectile"  # a projectile that reached its target
DAMAGE_TYPE_ENERGY: str = "energy"  # a gadget discharging at a target -- itself included
DAMAGE_TYPE_BURN: str = "burn"      # an aura pulse
DAMAGE_TYPE_TOXIN: str = "toxin"    # reserved for poison / venom / etc. mechanics

# No DAMAGE_TYPE_BACKFIRE: a backfire is a DELIVERY MECHANISM (an item hurting
# its own wielder instead of a target), not a kind of damage. The type is
# whatever the source actually deals -- a malfunctioning energy gizmo backfires
# as DAMAGE_TYPE_ENERGY. "Who got hit" is self_inflicted on the death path
# (CombatEntity.at_death / combat_msg.format_death), not a damage type.



# ─── Miss vocabulary ─────────────────────────────────────────────────────────
# WHAT AN ACTION THAT CONNECTED WITH NOTHING IS CALLED, one row per damage
# type. A bow that "swings at" its target is the only thing a player can read
# on a missed shot, and the line had that word baked into it because melee was
# the only action there was.
#
# The damage type is the right owner rather than the weapon or the style: it
# is already what the action carries to at_damage and to the death line, and
# it is the axis that actually changes the word. Two bows and four styles miss
# in exactly the same way.
#
# BOTH PERSONS ARE WRITTEN OUT. Deriving "swings" from "swing" is a rule that
# holds for these three verbs and breaks on the first irregular one, and the
# breakage would be a typo shipped to players rather than an error.

# Keys into one row of MISS_VERBS.
MISS_VERB_SELF_KEY: str = "self"    # what the actor reads: "You swing at ..."
MISS_VERB_OTHER_KEY: str = "other"  # what everyone else reads: "X swings at ..."

MISS_VERBS: dict = {
    DAMAGE_TYPE_MELEE: {
        MISS_VERB_SELF_KEY: "swing at",
        MISS_VERB_OTHER_KEY: "swings at",
    },
    DAMAGE_TYPE_PROJECTILE: {
        MISS_VERB_SELF_KEY: "shoot at",
        MISS_VERB_OTHER_KEY: "shoots at",
    },
    DAMAGE_TYPE_ENERGY: {
        MISS_VERB_SELF_KEY: "fire at",
        MISS_VERB_OTHER_KEY: "fires at",
    },
}

# Read for a damage type with no row. DAMAGE_TYPE_BURN and DAMAGE_TYPE_TOXIN
# have none because neither can miss: an aura pulse and a poison tick do not
# roll accuracy, and both print their own lines. A row is what a new damage
# type adds when it CAN miss, so the fallback is the melee wording rather than
# a neutral verb that reads as placeholder text.
MISS_VERB_FALLBACK_TYPE: str = DAMAGE_TYPE_MELEE



# ─── Pluggable action rules ───────────────────────────────────────────────────
# Generic knobs only. Per-rule numbers (die sizes, proc odds, damage amounts)
# are DATA and live on the rules class in systems/gameplay/combat/rules/rule_defs/

# Modifier channel keys. A channel is a named number in the action pipeline that
# any contributor may add into, the accumulator's four fields map one-to-one
# onto combat_calc.effective_level's four parameters, which is what finally
# wires up potion_boost / augmentation_mult / set_mult.
CHANNEL_STRIKE_LEVEL: str = "strike_level"
CHANNEL_BRAWN_LEVEL: str = "brawn_level"
CHANNEL_GUNS_LEVEL: str = "guns_level"
CHANNEL_BALLISTICS_LEVEL: str = "ballistics_level"
CHANNEL_DEFENSE_LEVEL: str = "defense_level"
CHANNEL_ATTACK_BONUS: str = "attack_bonus"
CHANNEL_STRENGTH_BONUS: str = "strength_bonus"
CHANNEL_DEFENSE_BONUS: str = "defense_bonus"
CHANNEL_MAX_HIT: str = "max_hit"
CHANNEL_DAMAGE: str = "damage"
CHANNEL_HIT_CHANCE: str = "hit_chance"

# Declared but deliberately NOT wired into the action. Attack speed is read
# AFTER an action resolves, by BlackoutCombatHandler.tick, to recharge the weapon
# cooldown, a different lifetime and a different context from an ActionContext.
# Wiring it here would put a per-action modifier in charge of a between-action
# number. It is reserved so the key does not get invented twice.
CHANNEL_ATTACK_SPEED: str = "attack_speed"

# ─── Combat axes ─────────────────────────────────────────────────────────────
# WHICH SKILLS AN ACTION RESOLVES AGAINST, as one table for each family of
# weapon. A combat style names the table it uses, so the action pipeline never
# asks whether a weapon is a bow.
#
# THIS IS WHY THERE IS NO ProjectileActionRules CLASS. A projectile shot and a
# melee swing run the identical nine seams over the identical three formulas.
# Everything that differs between them is in these two dicts: two skills, two
# modifier channels, one equipment key and one damage type. A rules subclass
# would have restated all nine seams to change six values, and the tenth
# weapon family would have restated them again.
#
# Each key:
#   accuracy_skill      - the skill whose level feeds the attack roll.
#   accuracy_channel    - the modifier channel that boosts that level.
#   damage_skill        - the skill whose level feeds the max hit.
#   damage_channel      - the modifier channel that boosts that level.
#   strength_bonus_key  - the combat_stat_bonuses key the max hit reads.
#   damage_type         - what at_damage and the death line are told.
#
# A style that names no table reads the melee one, so every melee style in
# world/item_defs/ stays exactly as it was written.
MELEE_COMBAT_AXES: dict = {
    "accuracy_skill": SKILL_KEY_STRIKE,
    "accuracy_channel": CHANNEL_STRIKE_LEVEL,
    "damage_skill": SKILL_KEY_BRAWN,
    "damage_channel": CHANNEL_BRAWN_LEVEL,
    "strength_bonus_key": MELEE_STRENGTH_BONUS_KEY,
    "damage_type": DAMAGE_TYPE_MELEE,
}

# Guns is the accuracy half and Ballistics the damage half, the same split
# Strike and Brawn make for melee.
#
# THE CHANNELS ARE THEIR OWN, and that is the point of listing them. An amulet
# that adds to CHANNEL_BRAWN_LEVEL must not make an arrow hit harder, and it
# cannot, because a projectile action never reads that channel.
PROJECTILE_COMBAT_AXES: dict = {
    "accuracy_skill": SKILL_KEY_GUNS,
    "accuracy_channel": CHANNEL_GUNS_LEVEL,
    "damage_skill": SKILL_KEY_BALLISTICS,
    "damage_channel": CHANNEL_BALLISTICS_LEVEL,
    "strength_bonus_key": PROJECTILE_STRENGTH_BONUS_KEY,
    "damage_type": DAMAGE_TYPE_PROJECTILE,
}

# The optional style key naming one of the two tables above.
STYLE_COMBAT_AXES_KEY: str = "combat_axes"

# Every channel the action pipeline knows about, for validation and iteration.
ACTION_MODIFIER_CHANNELS: tuple = (
    CHANNEL_STRIKE_LEVEL,
    CHANNEL_BRAWN_LEVEL,
    CHANNEL_GUNS_LEVEL,
    CHANNEL_BALLISTICS_LEVEL,
    CHANNEL_DEFENSE_LEVEL,
    CHANNEL_ATTACK_BONUS,
    CHANNEL_STRENGTH_BONUS,
    CHANNEL_DEFENSE_BONUS,
    CHANNEL_MAX_HIT,
    CHANNEL_DAMAGE,
    CHANNEL_HIT_CHANCE,
)

# Contributor priority tiers. When two contributors override the SAME seam, the
# higher priority wins that seam outright, seams are not chained, because
# accuracy() would need previous-value plumbing and resolve() cannot chain at
# all, and mixed semantics across nine seams is not reasonable-about-able.

# Priority is a property of WHAT A RULE DOES, not of which item carries it: a
# whole-action replacement must outrank a damage tweak no matter what it is
# bolted to. Gaps of 100 leave room to slot a tier in between later.

# Modifier contributions are exempt: every contributor's modifiers are summed
# regardless of priority. That asymmetry is the point of having two mechanisms.
RULES_PRIORITY_DEFAULT: int = 0     # BaseActionRules, the OSRS baseline
RULES_PRIORITY_MODIFIER: int = 100  # contributes modifiers, overrides no seam
RULES_PRIORITY_WEAPON: int = 200    # the wielded weapon's own behaviour
RULES_PRIORITY_OVERRIDE: int = 300  # replaces the action outright

# Floor applied to the max-hit and damage channels after modifiers run. A
# modifier that drives damage negative must land on zero, never heal the target.
ACTION_DAMAGE_FLOOR: int = 0

# The db attribute an item or NPC carries to name its rules. Always a LIST of
# registry keys, never a single key: one key per class would force a bespoke
# class for every combination of behaviours.
COMBAT_RULES_ATTR: str = "combat_rules"


# ─── Reach ───────────────────────────────────────────────────────────────────
# How far an action can travel, in tiles. A weapon declares its own max_range
# on its ItemDef; ZERO means the same tile, which is every melee weapon and
# bare hands. So nothing in the melee data changes to gain this field.

# Distance metric for reach. Read from the aura metric deliberately: a player
# who has learnt that an aura covers a circle must not find that a bow covers a
# square. One geometry for the whole game, one knob to retune it.
REACH_DISTANCE_METRIC: str = AURA_DISTANCE_METRIC

# Reach of an attacker holding nothing, and of every melee weapon. Same tile.
MELEE_REACH_TILES: int = 0

# Ticks an attacker holds position after its target leaves reach, before the
# fight ends.
#
# WITHOUT THE GRACE, ONE STEP BY EITHER PARTY CANCELS THE FIGHT. A target that
# walks one tile out of range and back in on the next tick would end the combat
# and clear the attacker's queued action, which reads to the player as the
# fight dropping at random. Four ticks is 2.4 seconds -- long enough to cover
# ordinary movement, short enough that walking away still works.
OUT_OF_REACH_GRACE_TICKS: int = 4

# How far apart two combatants can stand and still be IN THE SAME FIGHT.
#
# THIS IS NOT A REACH, AND IT IS NOT THE ATTACKER'S. Reach answers "can I act
# on that". Engagement answers "is this fight still happening", and the two
# came apart the moment one weapon outranged another. A melee NPC shot from
# seven tiles reaches zero, so it found no enemy on its own tick, spent the
# grace, and ended ITS combat -- which deleted the handler its attacker was
# counting. The archer's fight then reported `You won!` over a raider standing
# at four hitpoints.
#
# One number for both sides, so neither can decide the fight is over while the
# other is still in it. It must exceed the longest reach in the game, or a
# weapon could shoot from outside the fight it started;
# test_engagement_covers_every_weapon in systems/gameplay/combat/tests asserts
# exactly that against ITEM_DB.
#
# It bounds the fight in SPACE, which is what still lets a player leave one by
# walking away. The scan is over the engaged, not over the area -- see
# BlackoutCombatHandler.get_sides -- so a generous number costs no query.
ENGAGEMENT_RADIUS_TILES: int = 12


# ─── Ammunition ──────────────────────────────────────────────────────────────
# The Evennia tag category an ammunition item files its FAMILY under. A bow
# declares the family it accepts in ItemDef.accepted_ammo, and the two are
# matched by exact string equality -- so both sides read this constant rather
# than typing the category.
#
# A category of its own rather than a reuse of the "weapon" family: an arrow is
# not a weapon that a player can wield, and the projectile action asks a question
# ("does this ammo fit this bow") that no other family answers.
AMMO_FAMILY_TAG_CATEGORY: str = "ammo_family"

# The families themselves. A bow's accepted_ammo and an arrow's family tag are
# matched by exact string equality, so both sides read the constant. A second
# family (a bolt, a cartridge) is one more line here plus the two ItemDefs
# that name it.
AMMO_FAMILY_ARROW: str = "arrow"

# Probability that a spent projectile survives and drops on the target's tile.
# The remainder breaks and is gone.
#
# One number for every projectile, not a per-item field. Recovery is a property
# of the MECHANIC -- it is what makes ammunition a cost the player manages
# rather than a tax -- and a per-arrow rate would make two arrows differ in a
# way no screen could explain.
AMMO_RECOVERY_CHANCE: float = 0.8


# ─── Unarmed fallback (no weapon wielded) ───────────────────────────────────
# When a CombatEntity has nothing in either hand, the combat handler substitutes
# these unarmed defaults.
#
# EVERY BONUS KEY THE GAME READS APPEARS HERE. The ATTACK_TYPE_* warning above
# points at this dict for the canonical spellings, so the six projectile keys are
# listed even though no unarmed action reads one. A key missing from an
# item's own block still reads 0 through .get, but a key missing from HERE has
# no spelling anyone can check against.
UNARMED_DEFAULT_COMBAT_STATS: dict = {
    # melee attack bonuses
    "stab_attack_bonus": 0,
    "slash_attack_bonus": 0,
    "crush_attack_bonus": 0,
    # melee defense bonuses
    "stab_defense_bonus": 0,
    "slash_defense_bonus": 0,
    "crush_defense_bonus": 0,
    # projectile attack bonuses
    "light_attack_bonus": 0,
    "standard_attack_bonus": 0,
    "heavy_attack_bonus": 0,
    # projectile defense bonuses
    "light_defense_bonus": 0,
    "standard_defense_bonus": 0,
    "heavy_defense_bonus": 0,
    # other bonuses
    "melee_strength_bonus": 0,
    "projectile_strength_bonus": 0,
}
UNARMED_ATTACK_SPEED_TICKS: int = 4  # 2.4s no weapons equipped cycle
UNARMED_DEFAULT_COMBAT_STYLE: str = "punch"
UNARMED_COMBAT_BONUS_FLAT: int = 0  # full equip_str_bonus = 0
UNARMED_WEAPON_NAME: str = "bare hands"

UNARMED_COMBAT_STYLES = {
    "punch":    {"attack_type": "crush", "weapon_style": "accurate", "weapon_style_xp_skill": ACCURATE_XP_SKILLS, "weapon_style_level_boost": MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE},
    "kick":     {"attack_type": "crush", "weapon_style": "aggressive", "weapon_style_xp_skill": AGGRESSIVE_XP_SKILLS, "weapon_style_level_boost": MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE},
    "headbutt": {"attack_type": "crush", "weapon_style": "aggressive", "weapon_style_xp_skill": AGGRESSIVE_XP_SKILLS, "weapon_style_level_boost": MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE},
    "guard":    {"attack_type": "crush", "weapon_style": "defensive", "weapon_style_xp_skill": DEFENSIVE_XP_SKILLS, "weapon_style_level_boost": MELEE_WEAPON_STYLE_LEVEL_BOOST_DEFENSIVE},
}

# ─── Player versus player ────────────────────────────────────────────────────
# systems/gameplay/combat/pvp.py owns the rule. These are its vocabulary.
#
# The flag lives on the CHARACTER as an Attribute, because it is a choice the
# player makes and it must survive a reload. It is OFF for every character
# until its owner turns it on, so a character already in the database is safe
# with no migration.
PVP_ENABLED_ATTR: str = "pvp_enabled"

# The two arguments `pvp` accepts. The Combat tab sends the same line.
PVP_ARG_ON: str = "on"
PVP_ARG_OFF: str = "off"

PVP_TURNED_ON_MSG: str = (
    "|rPvP is ON.|n Other players with PvP on can attack you, "
    "and you can attack them.")
PVP_TURNED_OFF_MSG: str = "|gPvP is OFF.|n Other players cannot attack you."
PVP_ALREADY_MSG: str = "PvP is already {state}."
PVP_LOCKED_IN_COMBAT_MSG: str = "You cannot turn PvP off during a fight."
PVP_ATTACKER_OFF_MSG: str = (
    "Turn PvP on in the Combat tab (|wpvp on|n) before you attack a player.")
PVP_TARGET_OFF_MSG: str = "{name} does not have PvP on."
PVP_USAGE_MSG: str = "Usage: pvp [on|off]. PvP is {state}."
PVP_STATE_ON: str = "on"
PVP_STATE_OFF: str = "off"
