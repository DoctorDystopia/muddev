"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Implementation of the Cutting gathering skill.
"""



from systems.core.stat_tracker import constants as stat_constants
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.skill_defs.gathering.gathering_skill import (
    GatheringSkill,
)
from systems.gameplay.quests import constants as quest_constants



class Cutting(GatheringSkill):
    """
    Purpose: Manages the mechanics and unlock requirements for Cutting.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        Everything Cutting does is what every gathering skill does, so all of
        it lives in GatheringSkill and Cutting is the six values that differ.
        Which nodes it works is not among them: GATHERABLE_REGISTRY names
        this skill on the yields it owns, so a new cuttable node is a dict
        entry and nothing here changes.

    Notes/References:
        The rusty pole's bare_hands exemption is what keeps a brand-new
        character from being locked out of the game -- see GatherableDef in
        systems/gameplay/progression/skills/gatherables.py.

    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    key = skill_constants.CUTTING_SKILL_KEY
    name = "Cutting"
    category = "Gathering"
    description = "Proficiency with harvesting materials from anything cuttable."

    verb = "cut"
    # Just "axe". The battleaxe is deliberately NOT here: it was not a cutting
    # tool before this refactor and making it one would be a gameplay change
    # smuggled in under a code change. Adding it later is one string.
    tool_types = ("axe",)
    tool_description = "any kind of axe"
    quest_action = quest_constants.ACTION_CUT
    stat_key = stat_constants.CUTTING_TOTALS_STAT_KEY
