"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Decoupled helper functions for skill state evaluation and mutation.
"""

import math
from evennia.utils import logger
from .constants import (
    BASE_XP_MULTIPLIER, 
    XP_EXPONENT, 
    DEFAULT_START_LEVEL, 
    DEFAULT_START_XP, 
    MINIMUM_BASE_LEVEL
)
from .registry import SKILL_REGISTRY


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
        DEFAULT_START_LEVEL read
        DEFAULT_START_XP read
        
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
        skills_dict[skill_key] = {"level": DEFAULT_START_LEVEL, "xp": DEFAULT_START_XP}


def calculate_xp_needed(current_level: int) -> int:
    """
    Purpose: Calculates the XP required to clear the current level.
    
    Entry:
        current_level >= 0
        
    Exit/Returns:
        Returns the integer amount of XP needed to reach the next level.
        
    Module Globals:
        MINIMUM_BASE_LEVEL read
        BASE_XP_MULTIPLIER read
        XP_EXPONENT read
        
    Methodology:
        Applies an exponential curve using the base multiplier. Enforces
        a minimum base level to avoid multiplying by zero.
        
    Notes/References:
        None
        
    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    if current_level < MINIMUM_BASE_LEVEL:
        base_level = MINIMUM_BASE_LEVEL
    else:
        base_level = current_level
        
    # calculated_xp = BASE_XP_MULTIPLIER * (base_level ** XP_EXPONENT)
    # rounded_xp = int(calculated_xp)

    # Old School RuneScape XP Difference Formula
    # inner_calc = math.floor(base_level + 300 * (2 ** (base_level / 10.0)))
    # rounded_xp = math.floor(0.25 * inner_calc)

    # Constants for XP calculation
    BASE_CURVE_MULTIPLIER = 300
    EXPONENTIAL_BASE = 2
    LEVELS_PER_DOUBLING = 10.0  # Tweaked from OSRS's default of 7
    XP_SCALING_FACTOR = 0.25    # Equivalent to dividing by 4

    # XP Difference Formula
    inner_calc = math.floor(base_level + BASE_CURVE_MULTIPLIER * (EXPONENTIAL_BASE ** (base_level / LEVELS_PER_DOUBLING)))
    rounded_xp = math.floor(XP_SCALING_FACTOR * inner_calc)

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

    log_message = f"Total XP for {skill_key}: {total_xp} (Level: {current_lvl})"
    logger.log_info(log_message)
    print(log_message)
    
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

    log_message = f"Current XP level for {skill_key}: {current_progress_xp}/{total_xp_needed} (Remaining: {remaining_xp})"
    logger.log_info(log_message)
    print(log_message)
    
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
        msg_string = f"|g[PROG_UP] Your {skill_name} skill increased to level {skill_data['level']}!|n"
        obj.msg(msg_string)


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