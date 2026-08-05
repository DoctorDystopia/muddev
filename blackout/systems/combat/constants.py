"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Global tunables for the OSRS-derived Blackout combat engine (0-127 skill scaling).
"""

# ─── Tick rhythm ─────────────────────────────────────────────────────────────
# Blackout surfaces a universal tick so the engine rhythm can be retuned
# globally without touching weapon definitions.
#
# This is consumed by the twisted LoopingCall in tick_engine.py, NOT by an
# Evennia Script.interval — ScriptDB.db_interval is a Django IntegerField and
# would silently truncate 0.6 to 0, which disables the timer entirely.
COMBAT_TICK_SECONDS: float = 0.6

# How often the tick engine's Evennia-side watchdog fires to confirm the
# LoopingCall above is still alive. Must be a whole number of seconds.
TICK_ENGINE_WATCHDOG_SECONDS: int = 60

# ─── Skill scaling bounds ────────────────────────────────────────────────────
# Blackout scales all skills 0..127 (inclusive). OSRS uses 1..99; the formulas
# are scale-agnostic, so this constant exists purely as documentation and for
# any UI / cap-check code that wants a single source of truth.
MIN_BASE_SKILL_LEVEL: int = 0
MAX_BASE_SKILL_LEVEL: int = 127

# ─── Fortitude (HP) seed values ──────────────────────────────────────────────
# Player characters enter the world with Fortitude forced to this level, and
# max_hp therefore equal to it.

# a character spawns exactly on the level-10 threshold and
# logic.calculate_xp_needed owns what that threshold costs.
FORTITUDE_START_LEVEL: int = 10
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
# Which equipment bonus a swing reads. These strings are INTERPOLATED into
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

# ─── Weapon Style invisible bonuses ────────────────────────
# Four combat styles map to four discrete bonus profiles. Each dict maps
# Blackout skill keys to invisible level boosts consumed by
# combat_calc.effective_level.
#   accurate   -> +3 strike      (Strike skill)
#   aggressive -> +3 brawn       (Brawn skill)
#   defensive  -> +3 defense     (Defense skill)
#   controlled -> +1 to all three
MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE: dict = {"strike": 3}
MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE: dict = {"brawn": 3}
MELEE_WEAPON_STYLE_LEVEL_BOOST_CONTROLLED: dict = {
    "strike": 1,
    "brawn": 1,
    "defense": 1,
}
MELEE_WEAPON_STYLE_LEVEL_BOOST_DEFENSIVE: dict = {"defense": 3}


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
# XP_PER_DAMAGE_TAKEN_DEFENSE: float = 1.33  # Defense XP on being hit

# Fortitude does NOT earn at the style rate since all combat styles award it.
XP_PER_DAMAGE_FORTITUDE: float = 4.0 / 3.0

# Per-skill rate overrides consulted by _award_style_xp. A skill absent here
# earns the active style's rate, a skill present earns its own, whichever style
# named it.
XP_PER_DAMAGE_BY_SKILL: dict = {
    "fortitude": XP_PER_DAMAGE_FORTITUDE,
}

# A style's "weapon_style_xp_skill" may name one skill (a plain string) or several (any
# iterable of skill keys), in which case every named skill receives the full
# per-skill rate above.
ACCURATE_XP_SKILLS: tuple = ("strike", "fortitude")
AGGRESSIVE_XP_SKILLS: tuple = ("brawn", "fortitude")
CONTROLLED_XP_SKILLS: tuple = ("strike", "brawn", "defense", "fortitude")
DEFENSIVE_XP_SKILLS: tuple = ("defense", "fortitude")

# Weapons spawned before multi-skill styles existed stored the bare string
# "controlled" in their attack_type dicts. Those DB rows are still live, so the
# award path maps this sentinel onto CONTROLLED_XP_SKILLS above.
LEGACY_CONTROLLED_XP_SENTINEL: str = "controlled"

# ─── Augmentation ───────────────────────
# OSRS treats Prayer as a percentage multiplier on effective level.
# In Blackout that role belongs to the Augmentation system (not yet built).
# Crucially: Augmentation-flicking — toggling an augmentation for the tick a
# swing lands and un-toggling it the tick after — is a CORE MECHANIC, not an
# anti-pattern to guard against. No MIN_BUFF_DURATION_TICKS knob exists. The
# combat handler resolves each swing against the augmentation state at the
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
# and live on the aura class in systems/combat/auras/aura_defs/ — adding an aura
# must stay a one-file change, so nothing aura-specific belongs in this module.

# Floor applied to every aura tick's damage. Aura damage is a share of the
# CASTER's scaling skill level, and Blackout's levels start low: a character
# spawns at Fortitude 10, so a 10% share is 1.0 and anything below that
# truncates to 0. So one damage is the smallest meaningful hit.
AURA_MIN_DAMAGE: int = 1

# Default cadence, in ticks, between one aura's damage pulses. Four ticks is
# 2.4 seconds, exactly one speed-4 weapon swing.
AURA_DEFAULT_TICK_INTERVAL: int = 4

# Distance metric used to decide which grid tiles a radius covers.
#   "euclidean" -> dx*dx + dy*dy <= r*r   (a circle, corners of the box are cut)
#   "chebyshev" -> max(|dx|, |dy|) <= r   (the full square box)
# Euclidean matches the circular ground effect the mechanic is modelled on.
# The bounding-box DB query is the same either way, only the in-Python trim
# differs, so this is a pure retune knob.
AURA_DISTANCE_METRIC: str = "euclidean"


# ─── Damage types ────────────────────────────────────────────────────────────
# What KIND of damage landed, threaded through CombatEntity.at_damage so death
# attribution and messaging can tell a sword from fire, etc.

# Read the warning on ATTACK_TYPE_* above before adding one here: these two
# vocabularies look interchangeable and are not. An ATTACK_TYPE_* string is
# interpolated into "<type>_attack_bonus".
DAMAGE_TYPE_MELEE: str = "melee"    # a connecting weapon or unarmed swing
DAMAGE_TYPE_ENERGY: str = "energy"  # a gadget discharging at a target -- itself included
DAMAGE_TYPE_BURN: str = "burn"      # an aura pulse
DAMAGE_TYPE_TOXIN: str = "toxin"    # reserved for poison / venom / etc. mechanics

# No DAMAGE_TYPE_BACKFIRE: a backfire is a DELIVERY MECHANISM (an item hurting
# its own wielder instead of a target), not a kind of damage. The type is
# whatever the source actually deals -- a malfunctioning energy gizmo backfires
# as DAMAGE_TYPE_ENERGY. "Who got hit" is self_inflicted on the death path
# (CombatEntity.at_death / combat_msg.format_death), not a damage type.


# ─── Pluggable action rules ───────────────────────────────────────────────────
# Generic knobs only. Per-rule numbers (die sizes, proc odds, damage amounts)
# are DATA and live on the rules class in systems/combat/rules/rule_defs/

# Modifier channel keys. A channel is a named number in the action pipeline that
# any contributor may add into, the accumulator's four fields map one-to-one
# onto combat_calc.effective_level's four parameters, which is what finally
# wires up potion_boost / augmentation_mult / set_mult.
CHANNEL_STRIKE_LEVEL: str = "strike_level"
CHANNEL_BRAWN_LEVEL: str = "brawn_level"
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

# Every channel the action pipeline knows about, for validation and iteration.
ACTION_MODIFIER_CHANNELS: tuple = (
    CHANNEL_STRIKE_LEVEL,
    CHANNEL_BRAWN_LEVEL,
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


# ─── Unarmed fallback (no weapon wielded) ───────────────────────────────────
# When a CombatEntity has nothing in either hand, the combat handler substitutes
# these unarmed defaults.
UNARMED_DEFAULT_COMBAT_STATS: dict = {
    # attack bonuses
    "stab_attack_bonus": 0,
    "slash_attack_bonus": 0,
    "crush_attack_bonus": 0,
    # defense bonuses
    "stab_defense_bonus": 0,
    "slash_defense_bonus": 0,
    "crush_defense_bonus": 0,
    # other bonuses
    "melee_strength_bonus": 0,
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