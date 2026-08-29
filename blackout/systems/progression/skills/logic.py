"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Decoupled helper functions for skill state evaluation and mutation.
"""

import math

from evennia.utils import logger

from . import constants as skill_constants
from .constants import FORTITUDE_SKILL_KEY
from systems.combat import constants as combat_constants
from .registry import SKILL_REGISTRY
from systems.statefeed import constants as feed_const

# Every line this module sends a player is progression, so the routing tag is
# bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_PROGRESSION = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_PROGRESSION}


def ensure_skill(obj: object, skill_key: str) -> None:
    """
    Purpose: Internal safety check ensuring the skill key is valid and tracked.
    
    Entry:
        obj is a valid Evennia Character object
        skill_key is a string identifier
        
    Exit/Returns:
        No conditions
        
    Module Globals:
        SKILL_REGISTRY read
        skill_constants.DEFAULT_START_LEVEL read
        skill_constants.DEFAULT_START_XP read
        
    Methodology:
        Validates the key against the registry, raising an error if missing.
        If the valid key is untracked on the character, injects it with default values.
        
    Notes/References:
        None
        
    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    is_valid_skill = skill_key in SKILL_REGISTRY
    
    if not is_valid_skill:
        error_msg = f"Skill '{skill_key}' does not exist in the master catalog."
        raise ValueError(error_msg)
    
    skills_dict = obj.db.skills
    is_tracked = skill_key in skills_dict
    
    if not is_tracked:
        skills_dict[skill_key] = {"level": skill_constants.DEFAULT_START_LEVEL, "xp": skill_constants.DEFAULT_START_XP}


def calculate_xp_needed(current_level: int) -> int:
    """
    Purpose: Calculates the XP required to clear the current level.
    
    Entry:
        current_level >= 0
        
    Exit/Returns:
        Returns the integer amount of XP needed to reach the next level.
        
    Module Globals:
        MIN_BASE_SKILL_LEVEL read
        BASE_CURVE_MULTIPLIER read
        EXPONENTIAL_BASE read
        LEVELS_PER_DOUBLING read
        XP_SCALING_FACTOR read
        
    Methodology:
        Applies an exponential curve using the base multiplier. Enforces
        a minimum base level to avoid multiplying by zero.
        
    Notes/References:
        None
        
    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    if current_level < skill_constants.MIN_BASE_SKILL_LEVEL:
        base_level = skill_constants.MIN_BASE_SKILL_LEVEL
    else:
        base_level = current_level
        
    # calculated_xp = BASE_XP_MULTIPLIER * (base_level ** XP_EXPONENT)
    # rounded_xp = int(calculated_xp)

    # Old School RuneScape XP Difference Formula
    # inner_calc = math.floor(base_level + 300 * (2 ** (base_level / 10.0)))
    # rounded_xp = math.floor(0.25 * inner_calc)

    # Constants for XP calculation
    # BASE_CURVE_MULTIPLIER = 300
    # EXPONENTIAL_BASE = 2
    # LEVELS_PER_DOUBLING = 10.0  # Tweaked from OSRS's default of 7
    # XP_SCALING_FACTOR = 0.25    # Equivalent to dividing by 4

    # XP Difference Formula
    inner_calc = math.floor(base_level + skill_constants.BASE_CURVE_MULTIPLIER * (skill_constants.EXPONENTIAL_BASE ** (base_level / skill_constants.LEVELS_PER_DOUBLING)))
    rounded_xp = math.floor(skill_constants.XP_SCALING_FACTOR * inner_calc)

    return rounded_xp


def get_level(obj: object, skill_key: str) -> int:
    """
    Purpose: Returns the current level of a skill.
    
    Entry:
        obj is a valid Evennia Character object
        skill_key is a valid string matching a key in SKILL_REGISTRY
        
    Exit/Returns:
        Returns the integer level of the requested skill.
        
    Module Globals:
        None
        
    Methodology:
        Validates the skill exists via ensure_skill. Retrieves and 
        returns the level integer from the database attribute.
        
    Notes/References:
        None
        
    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    ensure_skill(obj, skill_key)
    
    skills_dict = obj.db.skills
    skill_data = skills_dict[skill_key]
    current_level = skill_data["level"]
    
    return current_level


def _publish_level_change(obj: object) -> None:
    """
    Purpose: Tell a graphical client that this character's levels moved.

    Entry:
        obj is the character whose level just changed. Anything without
        sessions -- an NPC, a test fixture -- is a supported no-op.

    Exit/Returns:
        No conditions. Never raises; the feed swallows its own failures and
        the two guards here cover the rest.

    Module Globals:
        None.

    Methodology:
        Called from the two places a level actually MOVES -- add_xp's level-up
        loop and set_level -- and from nowhere else. Both already guard on the
        level having changed, so this fires once per change rather than once
        per XP award; a skill tab does not need to be told about a level that
        stayed the same, and combat awards XP on every hit.

        THREE channels, because they answer different questions and a client
        may want any of them:

          char_status  -- the combat level table the 3D view reads. Cheap.
          char_summary -- the dossier, whose vitals band carries combat level,
                          total level and total XP. All three move when a
                          skill does.
          char_skills  -- the roster a skills PANE draws: every level, every XP
                          curve, every unlock. The most expensive payload in
                          the feed, which is why it fires here -- on a level
                          actually moving -- and not on an XP award.

        The last two check for a subscriber before building anything, so both
        cost nothing on a server with no graphical client attached.

        Runs AFTER apply_level_up_side_effects at both call sites, and the
        order is load-bearing: Fortitude's side effect is the one that moves
        max_hp, and a summary built before it would carry the old HP cap into
        the same payload that announces the new Fortitude level.

        The import is deferred. systems.statefeed.events reaches the payload
        builders and the summary registry, and this module is imported through
        the skills package by typeclasses/characters.py at startup -- the same
        ring QuestHandler._publishes keeps open by importing inside its
        wrapper.

    Notes/References:
        in_combat rides along on char_status and is correct at the moment of
        sending, but it is NOT published by its own transitions -- see
        emit_status.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    from systems.statefeed import events as feed

    feed.emit_status(obj)
    feed.emit_summary(obj)
    feed.emit_skills(obj)


def set_level(obj: object, skill_key: str, level: int) -> int:
    """
    Purpose: Set a skill's level directly, bypassing the XP curve.

    Entry:
        obj is a valid Evennia Character object
        skill_key is a valid string matching a key in SKILL_REGISTRY
        level is the wanted integer level

    Exit/Returns:
        Returns the level actually stored, after clamping into
        [MIN_BASE_SKILL_LEVEL, MAX_BASE_SKILL_LEVEL].

    Module Globals:
        skill_constants.MIN_BASE_SKILL_LEVEL read.
        skill_constants.MAX_BASE_SKILL_LEVEL read.

    Methodology:
        This is NOT how a character earns a level -- add_xp is. It is the write
        path a stat drain, a builder command, or a test fixture needs, and it
        is the character half of the SkillSource contract in
        systems/combat/protocols.py.

        Banked XP is deliberately left untouched. Zeroing it would mean a
        drained-then-restored character had silently lost progress toward
        their next level; carrying it means the level they were working toward
        is still the one they arrive back at.

        apply_level_up_side_effects runs when the level actually moves, for the
        same reason add_xp calls it: Fortitude drives max_hp, and a level set
        without that refresh leaves the HP cap pinned at its old value. It runs
        on a DECREASE too -- a drained Fortitude must lower the cap, or a
        drain would be free.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    ensure_skill(obj, skill_key)

    wanted = int(level)

    if wanted < skill_constants.MIN_BASE_SKILL_LEVEL:
        clamped = skill_constants.MIN_BASE_SKILL_LEVEL
    elif wanted > skill_constants.MAX_BASE_SKILL_LEVEL:
        clamped = skill_constants.MAX_BASE_SKILL_LEVEL
    else:
        clamped = wanted

    skills_dict = obj.db.skills
    skill_data = dict(skills_dict[skill_key])
    previous = skill_data["level"]
    skill_data["level"] = clamped

    obj.db.skills[skill_key] = skill_data

    if clamped != previous:
        apply_level_up_side_effects(obj, skill_key)
        _publish_level_change(obj)

    return clamped


def modify_level(obj: object, skill_key: str, delta: int) -> int:
    """
    Purpose: Shift a skill's level by a signed amount. The drain/buff path.

    Entry:
        obj is a valid Evennia Character object
        skill_key is a valid string matching a key in SKILL_REGISTRY
        delta is a signed integer; negative drains, positive buffs

    Exit/Returns:
        Returns the new level, after clamping.

    Module Globals:
        None

    Methodology:
        Expressed in terms of get_level and set_level so the clamp and the
        side-effect refresh are defined exactly once.

        Like set_level, this writes the PERMANENT level. A drain that wears off
        needs a layer that remembers the pre-drain value; combat_calc's
        transient `potion_boost` parameter is where that belongs, not here.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    current = get_level(obj, skill_key)
    wanted = current + int(delta)

    return set_level(obj, skill_key, wanted)


def get_total_xp(obj: object, skill_key: str) -> int:
    """
    Purpose: Returns the total cumulative XP earned for a skill across all levels.
    
    Entry:
        obj is a valid Evennia Character object
        skill_key is a valid string matching a key in SKILL_REGISTRY
        
    Exit/Returns:
        Returns the integer sum of all XP earned.
        
    Module Globals:
        None
        
    Methodology:
        Calculates the total XP by summing the XP required for all 
        previously cleared levels and adding the current level's progress.
        
    Notes/References:
        None
        
    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    ensure_skill(obj, skill_key)
    
    skills_dict = obj.db.skills
    skill_data = skills_dict[skill_key]
    current_lvl = skill_data["level"]
    level_progress_xp = skill_data["xp"]
    
    total_xp = level_progress_xp
    
    for level_index in range(current_lvl):
        xp_for_level = calculate_xp_needed(level_index)
        total_xp += xp_for_level

    return total_xp


def get_xp_level(obj: object, skill_key: str) -> tuple[int, int, int]:
    """
    Purpose: Returns the progress into the current level and requirements for the next.
    
    Entry:
        obj is a valid Evennia Character object
        skill_key is a valid string matching a key in SKILL_REGISTRY
        
    Exit/Returns:
        Returns a tuple of integers: (current_progress_xp, total_xp_needed, remaining_xp).
        
    Module Globals:
        None
        
    Methodology:
        Retrieves the current progress from the database. Calculates the total
        XP required for the next level. Subtracts the progress from the total
        to determine the remaining XP required to level up.
        
    Notes/References:
        None
        
    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    ensure_skill(obj, skill_key)
    
    skills_dict = obj.db.skills
    skill_data = skills_dict[skill_key]
    current_lvl = skill_data["level"]
    current_progress_xp = skill_data["xp"]
    
    total_xp_needed = calculate_xp_needed(current_lvl)
    remaining_xp = total_xp_needed - current_progress_xp

    return current_progress_xp, total_xp_needed, remaining_xp


def add_xp(obj: object, skill_key: str, amount: int) -> None:
    """
    Purpose: Adds XP to a skill and processes potential multi-level upgrades.
    
    Entry:
        obj is a valid Evennia Character object
        skill_key is a valid string matching a key in SKILL_REGISTRY
        amount is an integer value
        
    Exit/Returns:
        No conditions
        
    Module Globals:
        SKILL_REGISTRY read
        
    Methodology:
        Adds XP to the local copy of the skill state. Evaluates level ups
        in a loop until remaining XP is lower than the threshold. Re-saves
        data explicitly to ensure database serialization, sending a message
        if a level increased.
        
    Notes/References:
        None
        
    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    ensure_skill(obj, skill_key)
    
    skills_dict = obj.db.skills
    skill_data_ref = skills_dict[skill_key]
    skill_data = dict(skill_data_ref)
    
    if amount < 0:
        amount_to_add = 0
    else:
        amount_to_add = amount
        
    skill_data["xp"] += amount_to_add
    
    current_lvl = skill_data["level"]
    xp_needed = calculate_xp_needed(current_lvl)
    leveled_up = False
    
    while skill_data["xp"] >= xp_needed:
        skill_data["xp"] -= xp_needed
        skill_data["level"] += 1
        
        new_lvl = skill_data["level"]
        xp_needed = calculate_xp_needed(new_lvl)
        leveled_up = True
        
    obj.db.skills[skill_key] = skill_data

    if leveled_up:
        skill_class = SKILL_REGISTRY[skill_key]
        skill_name = skill_class.name
        msg_string = f"|g[LEVEL_UP] Your {skill_name} skill increased to level {skill_data['level']}!|n"
        obj.msg((msg_string, _MSG_PROGRESSION))

        # Refresh any state derived from this skill (Fortitude -> max_hp).
        apply_level_up_side_effects(obj, skill_key)
        _publish_level_change(obj)


def meets_prerequisite(obj: object, skill_key: str, required_level: int) -> bool:
    """
    Purpose: Verifies if a player meets a target level for a specific skill.
    
    Entry:
        obj is a valid Evennia Character object
        skill_key is a valid string matching a key in SKILL_REGISTRY
        required_level >= 0
        
    Exit/Returns:
        Returns True if the current level meets or exceeds the required level.
        
    Module Globals:
        None
        
    Methodology:
        Fetches the current level integer and compares it against the threshold.
        
    Notes/References:
        None
        
    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    current_lvl = get_level(obj, skill_key)
    meets_req = current_lvl >= required_level
    
    return meets_req


def check_synergy(obj: object, 
                  skill_a: str, 
                  level_a: int, 
                  skill_b: str, 
                  level_b: int) -> bool:
    """
    Purpose: Evaluates dual-skill synergy conditions.
    
    Entry:
        obj is a valid Evennia Character object
        skill_a and skill_b are valid string identifiers
        level_a and level_b are non-negative integers
        
    Exit/Returns:
        Returns True if both skill thresholds are satisfied, False otherwise.
        
    Module Globals:
        None
        
    Methodology:
        Checks the independent levels of both skills and returns the 
        logical AND result of their comparisons.
        
    Notes/References:
        None
        
    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    current_lvl_a = get_level(obj, skill_a)
    current_lvl_b = get_level(obj, skill_b)
    
    a_meets = current_lvl_a >= level_a
    b_meets = current_lvl_b >= level_b
    synergy_met = a_meets and b_meets
    
    return synergy_met


def seed_fortitude_on_creation(obj: object) -> None:
    """
    Purpose: Stamp Fortitude (Blackout's HP skill) at its seed level, exactly
    on that level's threshold. Run from Character.at_object_creation AFTER
    init_all_skills() has placed fortitude at the DEFAULT_START_LEVEL/XP.

    Entry:
        obj is a valid Evennia Character object whose db.skills dict
        already contains the 'fortitude' key (i.e. init_all_skills has
        already run).

    Exit/Returns:
        No conditions. After this call, obj.db.skills['fortitude'] ==
        {'level': 10, 'xp': 0} and obj.db.max_hp == 10. If the CombatEntity
        mixin is on the typeclass, obj.db.hp == 10 too. get_total_xp then
        reports 1052 — the cumulative cost of levels 0-9 on Blackout's curve,
        derived rather than stored.

    Module Globals:
        combat_constants.FORTITUDE_START_LEVEL read.
        skill_constants.DEFAULT_START_XP read.

    Methodology:
        1. ensure_skill(obj, 'fortitude') normalizes the slot.
        2. Overwrite level with the seed level and progress with zero.
        3. If the object exposes CombatEntity attrs (db.max_hp), set max_hp
           to FORTITUDE_START_LEVEL and HP to match (full heal on creation).
        4. If CombatEntity is NOT on this typeclass (e.g. a non-Character), the
           skill seed still lands but the combative side-effect is silently
           skipped — so this helper is safe to call on any Evennia object with
           db.skills, including NPCs that opt into the skills system.

        The "xp" field means progress INTO the current level, not a cumulative
        total — add_xp subtracts calculate_xp_needed from it, get_xp_level
        compares it against that threshold, and get_total_xp adds the cleared
        levels back on. Seeding it with a cumulative figure is what produced a
        "1154 / 152" progress bar, a negative remaining, and a first-XP-award
        cascade from Fortitude 10 straight to 16.

    Notes/References:
        Per design dialogue: only Fortitude diverges from DEFAULT_START_LEVEL.
        All other combat skills start at 0 just like gathering / processing.
        Vault 02_Player/Player_Overview.md §"Health": players spawn "at exactly
        level 10", i.e. on the threshold, with nothing banked toward level 11.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    ensure_skill(obj, FORTITUDE_SKILL_KEY)

    skills_dict = obj.db.skills
    skills_dict[FORTITUDE_SKILL_KEY] = {
        "level": combat_constants.FORTITUDE_START_LEVEL,
        "xp": skill_constants.DEFAULT_START_XP,
    }

    if hasattr(obj, "db"):
        # Derive the starting cap through the same scaling every later
        # level-up uses, rather than assuming level == hp at creation only.
        starting_hp = (
            combat_constants.FORTITUDE_START_LEVEL
            * combat_constants.HP_PER_FORTITUDE_LEVEL
        )
        obj.db.max_hp = starting_hp
        obj.db.hp = starting_hp


def sync_max_hp_from_fortitude(obj: object) -> None:
    """
    Purpose: Refresh max_hp from the fortitude skill level. Called by the
    combat handler after awarding XP that triggers a fortitude level-up,
    so the entity's HP cap tracks the skill.

    Entry:
        obj is a valid Evennia Character (or other CombatEntity host).

    Exit/Returns:
        No conditions. obj.db.max_hp is updated; obj.db.hp is NOT modified
        (this is an upper-bounds update only — current HP cap may rise
        without instantly topping the entity off).

    Module Globals:
        None.

    Methodology:
        Read the current fortitude level; assign through the CombatEntity
        `max_hp` SETTER rather than writing db.max_hp behind it. That setter
        is what publishes the new cap to a graphical client, and writing the
        attribute directly is how a Fortitude level-up used to raise the cap
        on the server while the client's health bar kept the old maximum --
        every other reader agreed the character had 48 hit points and the bar
        said 47 until an unrelated regen tick moved hp and carried the new
        number along with it.

        Unguarded, unlike seed_fortitude_on_creation's `hasattr(obj, "db")`,
        because the two run on different populations. Creation seeds the skill
        on anything with db.skills; this runs only as fortitude's registered
        level-up side effect, and the only things that earn fortitude XP are
        things that have been in a fight -- which is to say CombatEntity
        hosts. apply_level_up_side_effects logs whatever this raises anyway,
        so a host that somehow is not one fails loudly rather than by writing
        a cap nothing reads.

        Defensive against missing fortitude (raises KeyError → caller decides).

    Notes/References:
        Per design dialogue: max_hp == fortitude_level. OSRS Constitution
        analog. Stubbed in batch 2; per-hit XP integration is the live
        caller in batch 2's combat handler.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    fortitude_level = get_level(obj, FORTITUDE_SKILL_KEY)
    new_cap = fortitude_level * combat_constants.HP_PER_FORTITUDE_LEVEL
    obj.max_hp = new_cap


# ─── Level-up side effects ──────────────────────────────────────────────────
# Some skills change derived state when they level. Registering them as data
# keeps add_xp free of per-skill branches, and makes the coupling greppable:
# anything that must react to a level-up appears here.
#
# Fortitude drives max_hp. Without this entry sync_max_hp_from_fortitude had
# no callers at all, so every character's max HP stayed pinned at its creation
# value forever no matter how much Fortitude XP they earned.
_LEVEL_UP_SIDE_EFFECTS = {
    FORTITUDE_SKILL_KEY: sync_max_hp_from_fortitude,
}


def apply_level_up_side_effects(obj: object, skill_key: str) -> None:
    """
    Purpose: Run any derived-state refresh a skill declares on level-up.

    Entry:
        obj is a valid Evennia Character object.
        skill_key is a registered skill key.

    Exit/Returns:
        No conditions. Silent no-op for skills with no registered effect.

    Module Globals:
        _LEVEL_UP_SIDE_EFFECTS read.

    Methodology:
        Dict lookup, then call. Failures are logged rather than raised so a
        broken side effect cannot swallow the level-up itself.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/01/2026
    """
    side_effect = _LEVEL_UP_SIDE_EFFECTS.get(skill_key)

    if side_effect is None:
        return

    try:
        side_effect(obj)
    except Exception as exc:
        logger.log_err(
            f"apply_level_up_side_effects: {skill_key} handler failed on {obj}: {exc!r}"
        )


# ─── Whole-character rollups ────────────────────────────────────────────────
# The three routines below are the only ones here that answer a question about
# EVERY skill at once rather than about one named skill. They exist because the
# player summary screen is the first caller that needs a number no single skill
# can produce -- and because deriving "total level" inside a display module
# would put a rule about skills somewhere other than the skills package.


def get_total_level(obj: object) -> int:
    """
    Purpose: Sum the character's level across every registered skill.

    Entry:
        obj is a valid Evennia Character object.

    Exit/Returns:
        Returns the integer total. A character with no skills yet returns 0.

    Module Globals:
        SKILL_REGISTRY read.

    Methodology:
        Iterate the REGISTRY rather than obj.db.skills, so a skill that shipped
        after this character was created counts as level 0 instead of being
        omitted -- get_level's ensure_skill call backfills the slot on the way
        past.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    total = 0

    for skill_key in SKILL_REGISTRY:
        level = get_level(obj, skill_key)
        total += level

    return total


def get_combined_xp(obj: object) -> int:
    """
    Purpose: Sum the character's cumulative XP across every registered skill.

    Entry:
        obj is a valid Evennia Character object.

    Exit/Returns:
        Returns the integer total.

    Module Globals:
        SKILL_REGISTRY read.

    Methodology:
        Delegates per skill to get_total_xp, which reconstructs the cleared
        levels from the XP curve. Named `combined` rather than `total` because
        get_total_xp already means "the total for ONE skill" and two functions
        called total_xp differing only in scope is how a caller picks the wrong
        one.

    Notes/References:
        Cost is O(skills x level) since get_total_xp walks the curve per skill.
        At eight skills and a 127 cap that is trivial, but it is a per-read
        cost -- do not call this inside a combat tick.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    total = 0

    for skill_key in SKILL_REGISTRY:
        skill_xp = get_total_xp(obj, skill_key)
        total += skill_xp

    return total


def get_closest_to_level_up(obj: object) -> dict:
    """
    Purpose: Find the skill that needs the least XP to gain its next level.

    Entry:
        obj is a valid Evennia Character object.

    Exit/Returns:
        Returns a dict with keys skill_key, level, current_xp, needed_xp and
        remaining_xp; or None when every skill is capped.

    Module Globals:
        SKILL_REGISTRY read.
        skill_constants.MAX_BASE_SKILL_LEVEL read.

    Methodology:
        Linear scan for the smallest `remaining`. Capped skills are excluded
        outright -- calculate_xp_needed keeps returning a finite threshold past
        the cap, so a maxed skill would otherwise sit at the top of this list
        forever and the answer would be advice the player cannot act on.

        Ties break on the first key the registry yields. Arbitrary, but stable
        for a given skill roster, which is what stops the readout flickering
        between two equal skills on consecutive reads.

    Notes/References:
        This is the one fact on the summary screen that no per-skill panel can
        produce, since it needs the whole roster to compare.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    best = None

    for skill_key in SKILL_REGISTRY:
        current_level = get_level(obj, skill_key)

        if current_level >= skill_constants.MAX_BASE_SKILL_LEVEL:
            continue

        current_xp, needed_xp, remaining_xp = get_xp_level(obj, skill_key)

        if best is not None and remaining_xp >= best["remaining_xp"]:
            continue

        best = {
            "skill_key": skill_key,
            "level": current_level,
            "current_xp": current_xp,
            "needed_xp": needed_xp,
            "remaining_xp": remaining_xp,
        }

    return best
