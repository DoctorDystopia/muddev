"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/05/2026
Description: Test harness for generic gathering commands and progression.
"""



from evennia.utils.test_resources import EvenniaCommandTest
from evennia import create_object 
from typeclasses.objects import DefaultObject

from typeclasses.gathering_nodes import RustyPole
from systems.progression.skills.handler import SkillHandler
from systems.progression.skills.registry import SKILL_REGISTRY
from systems.progression.skills.skill_defs.base_skill import (
    BaseSkill,
    COOLDOWN_KEY_PREFIX,
    NO_COOLDOWN,
)
from commands.gathering_cmds import CmdCutGatheringNode, CUTTING_SKILL_KEY



# Public constant definitions
_STARTING_XP = 0
_EXPECTED_XP = 10



class TestCuttingProgression(EvenniaCommandTest):

    def setUp(self) -> None:
        parent_class = super()
        parent_class.setUp()
        
        char_obj = getattr(self, "char1", self.char1)
        room_obj = getattr(self, "room1", self.room1)
        
        self.handler = SkillHandler(char_obj)
        
        # Cutting._has_tool matches on db.tool_type, not on the object key.
        axe_obj = create_object(DefaultObject, key="axe", location=char_obj)
        axe_obj.db.tool_type = "axe"
        self.axe = axe_obj
        
        pole_obj = create_object(RustyPole, key="rusty pole", location=room_obj)
        self.pole = pole_obj


    def test_cut_rusty_pole_success(self) -> None:
        char_obj = self.char1
        handler = self.handler
        pole_obj = self.pole
        
        # Inject the full base dictionary for the skill, setting the level to 1
        char_obj.db.skills[CUTTING_SKILL_KEY] = {"level": 1, "xp": _STARTING_XP}
        
        # FIX: Dynamically store the historical XP (which evaluates to 80)
        initial_xp = handler.get_total_xp(CUTTING_SKILL_KEY)
        
        response = self.call(
            CmdCutGatheringNode(),        
            " rusty pole",       
            cmdstring="cut",     
            caller=char_obj,     
            obj=pole_obj         
        )
        
        print(f"\n[TEST OUTPUT - SUCCESS]: {response}")
        expected_response = "You successfully cut the rusty pole"
        self.assertIn(expected_response, response)
        
        # FIX: Verify the new total XP equals the initial XP plus the 10 XP reward
        new_xp = handler.get_total_xp(CUTTING_SKILL_KEY)
        expected_total = initial_xp + _EXPECTED_XP
        is_expected = (new_xp == expected_total)
        
        self.assertTrue(is_expected)


    def test_cut_level_requirement_fail(self) -> None:
        char_obj = self.char1
        pole_obj = self.pole
        
        pole_obj.db.required_level = 99
        
        # Apply the exact same formatting and instantiation here
        response = self.call(
            CmdCutGatheringNode(),
            " rusty pole",
            cmdstring="cut",
            caller=char_obj,
            obj=pole_obj
        )

        print(f"\n[TEST OUTPUT - FAIL]: {response}")
        # execute() accumulates every missing requirement into one line rather
        # than reporting only the first failure.
        expected_error = "Cutting level 99"
        self.assertIn(expected_error, response)


    def _cut(self):
        """Issue one cut command and return the response text."""
        response = self.call(
            CmdCutGatheringNode(),
            " rusty pole",
            cmdstring="cut",
            caller=self.char1,
            obj=self.pole,
        )

        return response


    def test_second_cut_is_refused_while_on_cooldown(self) -> None:
        char_obj = self.char1
        char_obj.db.skills[CUTTING_SKILL_KEY] = {"level": 1, "xp": _STARTING_XP}

        self._cut()
        second_response = self._cut()

        self.assertIn("already busy gathering", second_response)


    def test_cooldown_does_not_consume_a_second_node_use(self) -> None:
        """The refusal must happen before any loot is generated."""
        char_obj = self.char1
        char_obj.db.skills[CUTTING_SKILL_KEY] = {"level": 1, "xp": _STARTING_XP}

        self._cut()
        xp_after_first = self.handler.get_total_xp(CUTTING_SKILL_KEY)

        self._cut()
        xp_after_second = self.handler.get_total_xp(CUTTING_SKILL_KEY)

        self.assertEqual(xp_after_first, xp_after_second)


    def test_cooldown_is_stored_persistently_not_on_ndb(self) -> None:
        """This is the whole point of the swap. The previous implementation
        kept the timestamp on ndb.last_harvest_time, so every @reload handed
        the player a free harvest."""
        char_obj = self.char1
        char_obj.db.skills[CUTTING_SKILL_KEY] = {"level": 1, "xp": _STARTING_XP}

        self._cut()

        # Evennia hands back a _SaverDict wrapper, not a plain dict, so assert
        # on the mapping contract rather than the concrete type.
        stored = char_obj.attributes.get("cooldowns")
        self.assertIsNotNone(stored)
        self.assertIn(f"{COOLDOWN_KEY_PREFIX}{CUTTING_SKILL_KEY}", stored)
        self.assertIsNone(char_obj.ndb.last_harvest_time)


    def test_cooldown_clears_once_reset(self) -> None:
        char_obj = self.char1
        char_obj.db.skills[CUTTING_SKILL_KEY] = {"level": 1, "xp": _STARTING_XP}

        self._cut()
        char_obj.cooldowns.reset(f"{COOLDOWN_KEY_PREFIX}{CUTTING_SKILL_KEY}")
        response = self._cut()

        self.assertIn("You successfully cut", response)



class TestSkillCooldownKeying(EvenniaCommandTest):
    """The shared BaseSkill cooldown helpers, independent of any one skill."""

    def test_cooldown_keys_are_namespaced_per_skill(self) -> None:
        """The ndb timestamp this replaced was a single value shared by every
        gathering skill, so harvesting one node would have blocked every
        other gathering skill the moment a second one existed."""
        cutting = SKILL_REGISTRY[CUTTING_SKILL_KEY]()
        other_keys = [k for k in SKILL_REGISTRY if k != CUTTING_SKILL_KEY]
        other = SKILL_REGISTRY[other_keys[0]]()

        self.assertNotEqual(cutting.cooldown_key(), other.cooldown_key())
        self.assertTrue(cutting.cooldown_key().startswith(COOLDOWN_KEY_PREFIX))


    def test_arming_one_skill_leaves_another_ready(self) -> None:
        char_obj = self.char1
        cutting = SKILL_REGISTRY[CUTTING_SKILL_KEY]()
        other_keys = [k for k in SKILL_REGISTRY if k != CUTTING_SKILL_KEY]
        other = SKILL_REGISTRY[other_keys[0]]()

        cutting.arm_cooldown(char_obj)

        self.assertFalse(cutting.is_off_cooldown(char_obj))
        self.assertTrue(other.is_off_cooldown(char_obj))


    def test_skill_without_a_cooldown_is_always_ready(self) -> None:
        """Most skills declare no cooldown and must never touch the handler."""
        char_obj = self.char1
        plain = BaseSkill()

        self.assertEqual(plain.cooldown_seconds, NO_COOLDOWN)

        plain.arm_cooldown(char_obj)

        self.assertTrue(plain.is_off_cooldown(char_obj))
        self.assertEqual(char_obj.cooldowns.all, [])