"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Master catalog importing and organizing all playable skill classes.
"""



from .skill_defs.gathering.gathering_skills import GATHERING_SKILLS
from .skill_defs.processing.processing_skills import PROCESSING_SKILLS
from .skill_defs.production.production_skills import PRODUCTION_SKILLS
# from .skill_defs.utility.utility_skills import UTILITY_SKILLS
# from .skill_defs.combat.combat_skills import COMBAT_SKILLS



# Unpack all category containers into the master registry using **
SKILL_REGISTRY = {
    **GATHERING_SKILLS,
    **PROCESSING_SKILLS,
    **PRODUCTION_SKILLS,
    # **UTILITY_SKILLS,
    # **COMBAT_SKILLS,
}