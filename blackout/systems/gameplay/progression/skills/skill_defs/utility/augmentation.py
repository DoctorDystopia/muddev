"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: Implementation of the Augmentation skill (the Grit pool). A
             Utility skill, by Nick's choice of 10/30/2026.
"""



from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill



class Augmentation(BaseSkill):
    """
    Purpose: Defines the Augmentation skill, the universal skill of
    DESIGN-0015. Every player has it, and it sits in the Utility category,
    not in Combat (Nick, 10/30/2026). The combat level still reads its
    level. The skill is the body: how much load a body carries, and
    for how long. The level sets the maximum Grit, the pool that each lit
    augment drains (`systems/gameplay/augmentation/pool.py`). OSRS calls
    the shape "Prayer", and nothing here copies the prayer book.

    A passive skill: no `execute` action and no unlock gate. The class
    keeps the defaults of BaseSkill.

    Notes/References:
        The vault note `03_Systems/Skills/Combat Skills/Augmentation_Skill.md`
        owns the rules. The combat level reads this key through
        `COMBAT_LEVEL_AUGMENTATION_SKILL`. The level-up side effect
        `sync_grit_from_augmentation` in skills/logic.py moves the pool
        maximum, as Fortitude moves max_hp.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """

    key = skill_constants.SKILL_KEY_AUGMENTATION
    name = "Augmentation"
    category = skill_constants.SKILL_CATEGORY_UTILITY
    description = "How much load your body can carry, and for how long. Sets your Grit."
