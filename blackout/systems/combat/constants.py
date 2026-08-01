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
#
# There is deliberately NO companion start-XP constant. The level IS the seed:
# a character spawns exactly on the level-10 threshold with no progress into
# level 11, and logic.calculate_xp_needed already owns what that threshold
# costs. The constant that used to live here held 1154 -- OSRS's cumulative
# Hitpoints XP for level 10 -- and was wrong twice over. It was written into
# the skills dict's "xp" field, which every reader treats as progress WITHIN
# the current level, not a cumulative total; and Blackout's curve is not OSRS's
# (LEVELS_PER_DOUBLING is retuned to 10), so level 10 sits at 1052 cumulative
# here, not 1154. The visible symptom was a Fortitude bar reading "1154 / 152".
FORTITUDE_START_LEVEL: int = 10
MAX_FORTITUDE_LEVEL: int = MAX_BASE_SKILL_LEVEL

# ─── Fortitude → max HP scaling ──────────────────────────────────────────────
# Hitpoints are DIRECTLY linked to the Fortitude skill: max_hp scales one-to-one
# with Fortitude level, so a fresh character at FORTITUDE_START_LEVEL has
# exactly that many hitpoints and the cap rises by one per level to
# MAX_FORTITUDE_LEVEL.
#
# Design reference: 02_Player/Player_Overview.md §"Health" —
#   "Hitpoints ... is directly linked to the Fortitude skill", and Hitpoints is
#   the only skill players start with experience in, "placing them at exactly
#   level 10 when first spawning".
#
# This constant is the single knob if that relationship is ever retuned (e.g. a
# 10-HP-per-level scale); nothing should multiply a Fortitude level by a bare
# literal.
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

# ─── Weapon Style invisible bonuses ────────────────────────
# Four combat stances map to four discrete bonus profiles. Each dict maps
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
# Blackout grants XP per damage based on the *combat style's*.

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

# Fortitude does NOT earn at the style rate. Per 02_Player/Player_Overview.md
# §"Health": "for every point of damage dealt, 1.33 experience points are given
# to the player's Hitpoints" — regardless of which combat style landed the hit.
XP_PER_DAMAGE_FORTITUDE: float = 4.0 / 3.0

# Per-skill rate overrides consulted by _award_style_xp. A skill absent here
# earns the active style's rate; a skill present earns its own, whichever style
# named it. Keeps the "Fortitude is special" rule as data rather than a branch.
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


# ─── Unarmed fallback (no weapon wielded) ───────────────────────────────────
# When a CombatEntity has nothing in either hand, the combat handler substitutes
# UNARMED_DEFAULT_COMBAT_STATS and UNARMED_ATTACK_SPEED_TICKS so the resolution
# pipeline can run unchanged.
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

UNARMED_COMBAT_STYLES = {
    "punch":    {"attack_type": "crush", "weapon_style": "accurate", "weapon_style_xp_skill": ACCURATE_XP_SKILLS, "weapon_style_level_boost": MELEE_WEAPON_STYLE_LEVEL_BOOST_ACCURATE},
    "kick":     {"attack_type": "crush", "weapon_style": "aggressive", "weapon_style_xp_skill": AGGRESSIVE_XP_SKILLS, "weapon_style_level_boost": MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE},
    "headbutt": {"attack_type": "crush", "weapon_style": "aggressive", "weapon_style_xp_skill": AGGRESSIVE_XP_SKILLS, "weapon_style_level_boost": MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE},
    "guard":    {"attack_type": "crush", "weapon_style": "defensive", "weapon_style_xp_skill": DEFENSIVE_XP_SKILLS, "weapon_style_level_boost": MELEE_WEAPON_STYLE_LEVEL_BOOST_DEFENSIVE},
}