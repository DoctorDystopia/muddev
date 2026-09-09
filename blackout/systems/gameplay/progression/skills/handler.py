"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Dynamic handler wrapper that attaches to Character typeclasses.
"""



from collections.abc import Mapping

from . import logic
from . import recovery

from .registry import SKILL_REGISTRY
from .constants import DEFAULT_START_LEVEL, DEFAULT_START_XP



class SkillHandler:
    """
    Handles progression state management on a specific character proxy.
    Saves automatically to the character's `db.skills` attribute dictionary.

    Satisfies BOTH halves of the skills contract in
    systems/gameplay/combat/protocols.py: SkillSource (levels, shared with the NPC-side
    StatBlockSkills) and XpEarner (experience, which only a character has).
    StatBlockSkills implements the first and not the second, which is how
    `isinstance(entity, XpEarner)` tells a player apart from a monster without
    anyone probing for an attribute name.
    """

    def __init__(self, obj: object) -> None:
        """
        Purpose: Initializes the handler linked to a specific Evennia Typeclass instance.
        
        Entry:
            obj is a valid Evennia object
        
        Exit/Returns:
            No conditions
        
        Module Globals:
            None
            
        Methodology:
            Sets the internal object reference, then makes db.skills a dict
            or explains why it could not be.

            The test is `Mapping`, NOT `dict`, and that distinction is the
            entire bug. Evennia does not hand back a plain dict: a saved
            Attribute comes back as `dbserialize._SaverDict`, which subclasses
            `_SaverMutable` and `MutableMapping` and is NOT a `dict` subclass.
            An `isinstance(attr, dict)` guard is therefore False for every
            HEALTHY character, and the reset it gates wipes the progress of
            whoever logs in next. That is what destroyed two characters on
            09/08/2026 -- the two who happened to log in after the check
            shipped -- and it would have taken every other character on their
            next login.

            A non-mapping db.skills is NOT assumed to be garbage either.
            Evennia's
            PickledObjectField.from_db_value swallows an unpickling failure
            and hands back the RAW BASE64 STRING, so the single most likely
            reason this attribute is not a dict is that it is a perfectly
            good pickle naming a module that has since moved -- the player's
            levels are still inside it. recovery.repair_skills_attribute is
            given first refusal, and only a value it cannot read at all is
            reset, after that value has been quarantined.

            The ordering is the fix for a 09/08/2026 data-loss incident: an
            earlier version of this guard reset the attribute the moment
            `isinstance(attr, dict)` came back False, which destroyed two
            characters' fully-recoverable progress. Resetting is the LAST
            resort here, never the first.

        Notes/References:
            systems/gameplay/progression/skills/recovery.py carries the
            incident write-up and the module-alias table it repairs with.

        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        self.obj = obj

        skills_attr = self.obj.db.skills
        has_valid_skills = isinstance(skills_attr, Mapping)

        if has_valid_skills:
            return

        was_repaired = recovery.repair_skills_attribute(self.obj)

        if not was_repaired:
            self.obj.db.skills = {}



    def init_all_skills(self) -> None:
        """
        Inject all registered skills at level 0/xp 0 if not already tracked.
        """

        if not isinstance(self.obj.db.skills, Mapping):
            was_repaired = recovery.repair_skills_attribute(self.obj)

            if not was_repaired:
                self.obj.db.skills = {}
        
        for skill_key in SKILL_REGISTRY:
            if skill_key not in self.obj.db.skills:
                self.obj.db.skills[skill_key] = {
                    "level": DEFAULT_START_LEVEL,
                    "xp": DEFAULT_START_XP,
                }



    def get_level(self, skill_key: str) -> int:
        """ Passes execution to logic.get_level """
        result = logic.get_level(self.obj, skill_key)
        return result



    def set_level(self, skill_key: str, level: int) -> int:
        """ Passes execution to logic.set_level """
        result = logic.set_level(self.obj, skill_key, level)
        return result



    def modify_level(self, skill_key: str, delta: int) -> int:
        """ Passes execution to logic.modify_level """
        result = logic.modify_level(self.obj, skill_key, delta)
        return result



    def get_total_xp(self, skill_key: str) -> int:
        """ Passes execution to logic.get_total_xp """
        result = logic.get_total_xp(self.obj, skill_key)
        return result



    def get_xp_level(self, skill_key: str) -> tuple[int, int, int]:
        """ Passes execution to logic.get_xp_level """
        result = logic.get_xp_level(self.obj, skill_key)
        return result



    def add_xp(self, skill_key: str, amount: int) -> None:
        """ Passes execution to logic.add_xp """
        logic.add_xp(self.obj, skill_key, amount)



    def meets_prerequisite(self, skill_key: str, required_level: int) -> bool:
        """ Passes execution to logic.meets_prerequisite """
        result = logic.meets_prerequisite(self.obj, skill_key, required_level)
        return result



    def check_synergy(self, skill_a: str, level_a: int, skill_b: str, level_b: int) -> bool:
        """ Passes execution to logic.check_synergy """
        result = logic.check_synergy(self.obj, skill_a, level_a, skill_b, level_b)
        return result



    def seed_fortitude_on_creation(self) -> None:
        """ Passes execution to logic.seed_fortitude_on_creation """
        logic.seed_fortitude_on_creation(self.obj)



    def sync_max_hp_from_fortitude(self) -> None:
        """ Passes execution to logic.sync_max_hp_from_fortitude """
        logic.sync_max_hp_from_fortitude(self.obj)



    def total_level(self) -> int:
        """ Passes execution to logic.get_total_level """
        result = logic.get_total_level(self.obj)
        return result



    def combined_xp(self) -> int:
        """ Passes execution to logic.get_combined_xp """
        result = logic.get_combined_xp(self.obj)
        return result



    def closest_to_level_up(self) -> dict:
        """ Passes execution to logic.get_closest_to_level_up """
        result = logic.get_closest_to_level_up(self.obj)
        return result