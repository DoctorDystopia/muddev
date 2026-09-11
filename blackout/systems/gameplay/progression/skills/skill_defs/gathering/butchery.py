"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/10/2026
Description: Implementation of the Butchery gathering skill.
"""



from systems.core.stat_tracker import constants as stat_constants
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.skill_defs.gathering.gathering_skill import (
    GatheringSkill,
)
from systems.gameplay.quests import constants as quest_constants



class Butchery(GatheringSkill):
    """
    Purpose: Manages the mechanics and unlock requirements for Butchery.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        The first skill on the skill-tree map's second chain: a corpse in,
        a cut of meat out, and everything downstream (Rendering, Curing,
        Gastronomy) is a crafting recipe rather than a skill with a body.

        Which cut a harvest gives is a level question answered by
        GATHERABLE_REGISTRY, not by anything here -- chuck at 0, filet at 10,
        both offered by name once both are open. Adding a third cut, or a
        second corpse, is a dict entry in gatherables.py.

    Notes/References:
        A corpse is bare_hands=True, so a player with no blade can still take
        a chuck off one for a hit point -- the same exemption the rusty pole
        carries, for the same reason: the first knife has to come from
        somewhere.

    Author: Nick Hobar
    Creation date: 09/10/2026
    """
    key = skill_constants.BUTCHERY_SKILL_KEY
    name = "Butchery"
    category = "Gathering"
    description = "Proficiency with breaking a carcass down into usable cuts."

    verb = "butcher"

    # Anything with a point and an edge. The dagger is the one the player can
    # actually reach today -- it is the cheapest Metalsmith recipe -- and a
    # dedicated butcher's knife is one more tool_type in this tuple when the
    # item exists.
    tool_types = ("dagger", "butcher_knife")
    tool_description = "a blade of some kind"

    quest_action = quest_constants.ACTION_BUTCHER
    stat_key = stat_constants.BUTCHERY_TOTALS_STAT_KEY
